import os
import sqlite3
import json
import io
from typing import Optional, List
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
from pydantic import BaseModel
from pypdf import PdfReader
from blogger_client import create_post, get_service

app = FastAPI(title='Blogger SEO Agent Dashboard')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('BLOGGER_DB_PATH', os.path.join(BASE_DIR, 'data.db'))
SEO_KB_PATH = os.environ.get('BLOGGER_SEO_KB_PATH', os.path.join(BASE_DIR, 'seo_knowledge.md'))
SEO_PROMPT_PATH = os.environ.get('BLOGGER_SEO_PROMPT_PATH', os.path.join(BASE_DIR, 'seo_master_prompt.md'))
UPLOADS_DIR = os.environ.get('BLOGGER_UPLOADS_DIR', os.path.join(BASE_DIR, 'uploads'))
CONFIG_FILE = os.environ.get('BLOGGER_CONFIG_FILE', os.path.join(BASE_DIR, 'config.json'))
DEFAULT_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', os.path.join(BASE_DIR, 'token.json'))
DEFAULT_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', os.path.join(BASE_DIR, 'client_secret.json'))
TOKENS_DIR = os.path.join(BASE_DIR, 'tokens')
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOADS_DIR), name='uploads')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

@app.get('/api/blogs')
def api_get_blogs():
    conn = get_db()
    blogs = conn.execute('SELECT * FROM blogs ORDER BY created_at ASC').fetchall()
    conn.close()
    return [dict(b) for b in blogs]

class BlogSelectReq(BaseModel):
    blog_id: str

@app.post('/api/blogs/select')
def api_select_blog(req: BlogSelectReq):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE blogs SET is_active = (id = ?)', (req.blog_id,))
    row = c.execute('SELECT * FROM blogs WHERE id = ?', (req.blog_id,)).fetchone()
    if row and os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'blog_id': row['id'],
                'client_secret_file': row['client_secret_file'] or DEFAULT_CLIENT_SECRET,
                'token_file': row['token_file']
            }, f, indent=2)
    conn.commit()
    conn.close()
    return {'success': True}

class BlogAddReq(BaseModel):
    id: str
    name: str
    url: Optional[str] = ''
    account_name: Optional[str] = 'Akun Utama'
    token_file: Optional[str] = None
    niche_description: Optional[str] = ''

@app.post('/api/blogs/add')
def api_add_blog(req: BlogAddReq):
    conn = get_db()
    c = conn.cursor()
    token = req.token_file or DEFAULT_TOKEN_FILE
    c.execute('''
        INSERT INTO blogs (id, name, url, account_name, token_file, client_secret_file, niche_description, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (
        req.id.strip(),
        req.name.strip(),
        req.url.strip(),
        req.account_name.strip() or 'Akun Google',
        token,
        DEFAULT_CLIENT_SECRET,
        req.niche_description.strip(),
        0
    ))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/blogs/{blog_id}/delete')
def api_delete_blog(blog_id: str):
    conn = get_db()
    c = conn.cursor()
    total = c.execute('SELECT COUNT(*) FROM blogs').fetchone()[0]
    if total <= 1:
        conn.close()
        return {'success': False, 'error': 'Tidak dapat menghapus blog satu-satunya.'}
    c.execute('DELETE FROM blogs WHERE id = ?', (blog_id,))
    active = c.execute('SELECT id FROM blogs WHERE is_active = 1').fetchone()
    if not active:
        c.execute('UPDATE blogs SET is_active = 1 WHERE id = (SELECT id FROM blogs LIMIT 1)')
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/blogs/upload-token')
async def api_upload_blog_token(file: UploadFile = File(...)):
    tokens_dir = TOKENS_DIR
    os.makedirs(tokens_dir, exist_ok=True)
    filename = f"token_{uuid.uuid4().hex[:8]}.json"
    save_path = os.path.join(tokens_dir, filename)
    content = await file.read()
    with open(save_path, 'wb') as f:
        f.write(content)
    return {'success': True, 'token_file': save_path, 'filename': filename}

@app.get('/api/articles')
def api_get_articles(blog_id: Optional[str] = None):
    conn = get_db()
    if not blog_id:
        active = conn.execute('SELECT id FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
        blog_id = active['id'] if active else '2940095957137948013'
    articles = conn.execute('SELECT * FROM articles WHERE blog_id = ? ORDER BY created_at DESC', (blog_id,)).fetchall()
    conn.close()
    return [dict(a) for a in articles]

@app.get('/api/keywords')
def api_get_keywords(blog_id: Optional[str] = None):
    conn = get_db()
    if not blog_id:
        active = conn.execute('SELECT id FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
        blog_id = active['id'] if active else '2940095957137948013'
    keywords = conn.execute('SELECT * FROM keywords WHERE blog_id = ? ORDER BY created_at DESC', (blog_id,)).fetchall()
    conn.close()
    return [dict(k) for k in keywords]

@app.get('/', response_class=HTMLResponse)
def index():
    kb_content = ''
    if os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r') as f:
            kb_content = f.read()
            
    prompt_content = ''
    if os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r') as f:
            prompt_content = f.read()
            
    html = f'''<!DOCTYPE html>
<html lang="id" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bagus Tech - SEO Agent Command Center</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace']
          }},
          colors: {{
            brand: {{
              50: '#f0f9ff',
              400: '#38bdf8',
              500: '#0ea5e9',
              600: '#0284c7'
            }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: rgba(15, 23, 42, 0.6); }}
    ::-webkit-scrollbar-thumb {{ background: rgba(51, 65, 85, 0.8); border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(100, 116, 139, 1); }}
    .prose-rendered h2 {{ font-size: 1.25rem; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 0.35rem; }}
    .prose-rendered h3 {{ font-size: 1.1rem; font-weight: 600; margin-top: 1.2rem; margin-bottom: 0.5rem; color: #f1f5f9; }}
    .prose-rendered p {{ margin-bottom: 0.85rem; line-height: 1.7; color: #cbd5e1; font-size: 0.95rem; }}
    .prose-rendered ul {{ list-style-type: disc; margin-left: 1.4rem; margin-bottom: 0.85rem; color: #cbd5e1; }}
    .prose-rendered table {{ width: 100%; border-collapse: collapse; margin: 1.25rem 0; font-size: 0.875rem; }}
    .prose-rendered th, .prose-rendered td {{ border: 1px solid #334155; padding: 0.6rem 0.8rem; text-align: left; }}
    .prose-rendered th {{ background: #1e293b; color: #f8fafc; font-weight: 600; }}
    .prose-rendered pre {{ background: #090d16; border: 1px solid #1e293b; border-radius: 0.5rem; padding: 0.85rem; overflow-x: auto; margin: 1rem 0; color: #a5f3fc; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }}
    .prose-rendered code {{ background: #1e293b; color: #38bdf8; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }}
    .prose-rendered figure {{ margin: 1.5rem 0; text-align: center; }}
    .prose-rendered figure img {{ max-width: 100%; height: auto; border-radius: 0.75rem; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }}
    .prose-rendered figcaption {{ font-size: 0.8rem; color: #94a3b8; margin-top: 0.5rem; font-style: italic; }}
  </style>
</head>
<body class="bg-[#070b14] text-slate-100 min-h-screen flex flex-col selection:bg-brand-500 selection:text-white">
  <!-- Header Navigation -->
  <header class="border-b border-slate-800/80 bg-[#0b1120]/80 backdrop-blur-xl sticky top-0 z-40 px-4 md:px-6 py-3 flex items-center justify-between shadow-sm flex-wrap gap-3">
    <div class="flex items-center space-x-3.5">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-brand-500/25 font-bold text-white text-xl tracking-wider shrink-0">B</div>
      <div>
        <div class="flex items-center gap-2.5 flex-wrap">
          <h1 class="font-bold text-base md:text-lg text-white leading-tight tracking-tight">Blogger SEO Agent</h1>
          
          <!-- Multi-Blog Selector Dropdown -->
          <div class="relative" id="blog-dropdown-container">
            <button onclick="toggleBlogDropdown()" class="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-slate-800/90 hover:bg-slate-700/90 border border-slate-700/70 transition text-xs font-semibold text-slate-200 active:scale-95 shadow-sm">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span id="active-blog-display-name">Bagus Tech</span>
              <svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            
            <!-- Dropdown Menu -->
            <div id="blog-dropdown-menu" class="hidden absolute left-0 mt-2 w-72 bg-[#0f172a] border border-slate-700/90 rounded-2xl shadow-2xl z-50 p-2 space-y-1 backdrop-blur-xl">
              <div class="text-[10px] font-bold text-slate-400 px-2 py-1 uppercase tracking-wider flex items-center justify-between">
                <span>Daftar Blog Terhubung</span>
                <span id="blog-total-badge" class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.2 rounded font-mono">1 Blog</span>
              </div>
              <div id="blog-items-list" class="space-y-1 max-h-56 overflow-y-auto pr-0.5">
                <!-- Populated dynamically via JS -->
              </div>
              <div class="border-t border-slate-800 pt-1.5 mt-1">
                <button onclick="openAddBlogModal()" class="w-full py-1.5 px-2.5 bg-brand-500/15 hover:bg-brand-500/25 border border-brand-500/30 text-brand-400 text-xs font-bold rounded-xl flex items-center justify-center gap-1.5 transition active:scale-95">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                  <span>+ Tambah Blog / Akun Baru</span>
                </button>
              </div>
            </div>
          </div>
        </div>
        <p class="text-xs text-slate-400 mt-0.5 font-mono" id="active-blog-meta-row">Blog ID: <span class="text-slate-300 font-semibold" id="active-blog-id">2940095957137948013</span> &bull; <a id="active-blog-url" href="https://bagustechnologia.blogspot.com/" target="_blank" class="text-brand-400 hover:text-brand-300 transition hover:underline">bagustechnologia.blogspot.com &nearr;</a></p>
      </div>
    </div>
    <div class="flex items-center gap-2.5 flex-wrap">
      <button id="btn-auto-generate" onclick="triggerAutoGenerate()" class="px-3.5 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white rounded-xl text-xs md:text-sm font-semibold transition duration-200 shadow-md shadow-amber-500/20 flex items-center gap-1.5 active:scale-95">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        <span id="btn-auto-generate-text">⚡ Riset & Draf Otomatis</span>
      </button>
      <button onclick="openNewArticleModal()" class="px-3.5 py-2 bg-gradient-to-r from-brand-500 to-indigo-600 hover:from-brand-400 hover:to-indigo-500 text-white rounded-xl text-xs md:text-sm font-semibold transition duration-200 shadow-md shadow-brand-500/20 flex items-center gap-1.5 active:scale-95">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        <span>Tulis Manual</span>
      </button>
    </div>
  </header>

  <!-- Main Content Grid -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
    <!-- Left 7 Cols: Articles Queue -->
    <div class="lg:col-span-7 space-y-6 flex flex-col">
      <div class="bg-[#0f172a]/90 border border-slate-800/90 rounded-2xl p-5 shadow-xl flex-1 flex flex-col">
        <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800/80">
          <div>
            <h2 class="font-bold text-base text-white flex items-center gap-2">
              <span>Antrean Artikel & Approval</span>
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">Tinjau draf hasil racikan SEO Specialist sebelum dipublikasikan ke Blogger</p>
          </div>
          <span id="article-count-badge" class="text-xs bg-slate-800/80 border border-slate-700/60 px-3 py-1 rounded-full text-slate-300 font-mono font-medium">Memuat...</span>
        </div>

        <div id="articles-list" class="space-y-3.5 flex-1 overflow-y-auto max-h-[750px] pr-1">
          <div class="text-center py-12 text-slate-400 text-xs">Memuat draf artikel...</div>
        </div>
      </div>
    </div>

    <!-- Right 5 Cols: Knowledge Base & Keywords -->
    <div class="lg:col-span-5 space-y-6 flex flex-col">
      <!-- SEO Knowledge & Master Prompt Tabs Card -->
      <div class="bg-[#0f172a]/90 border border-slate-800/90 rounded-2xl p-5 shadow-xl flex flex-col">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
          <div class="flex items-center bg-slate-950/80 p-1 rounded-xl border border-slate-800/60">
            <button id="tab-kb-btn" onclick="switchRightTab('kb')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-500 text-white shadow-sm transition">Knowledge Base</button>
            <button id="tab-prompt-btn" onclick="switchRightTab('prompt')" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-200 transition">Master Prompt</button>
          </div>
          
          <div id="kb-actions" class="flex items-center gap-2">
            <label for="pdf-upload-input" class="cursor-pointer text-xs bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 px-3 py-1.5 rounded-lg border border-amber-500/30 font-semibold transition flex items-center gap-1.5 shadow-sm active:scale-95">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
              <span>Upload PDF</span>
            </label>
            <input type="file" id="pdf-upload-input" accept=".pdf" multiple class="hidden" onchange="uploadPdf(this)">
            <button onclick="saveKb()" id="btn-save-kb" class="text-xs bg-brand-500/15 text-brand-400 hover:bg-brand-500/25 px-3 py-1.5 rounded-lg border border-brand-500/30 font-semibold transition active:scale-95">Simpan</button>
          </div>
          
          <div id="prompt-actions" class="hidden flex items-center gap-2">
            <button onclick="savePrompt()" id="btn-save-prompt" class="text-xs bg-brand-500/15 text-brand-400 hover:bg-brand-500/25 px-3 py-1.5 rounded-lg border border-brand-500/30 font-semibold transition active:scale-95">Simpan Prompt</button>
          </div>
        </div>

        <!-- KB Tab Content -->
        <div id="tab-kb-content" class="flex flex-col">
          <div class="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Pedoman materi SEO khusus & preferensi:</span>
            <span class="text-[11px] text-amber-400 font-medium">Auto-sync dari PDF</span>
          </div>
          <textarea id="kb-editor" rows="11" class="w-full bg-[#070b14] border border-slate-800 rounded-xl p-3.5 text-xs font-mono text-slate-300 focus:outline-none focus:border-brand-500/80 transition resize-none leading-relaxed">{kb_content}</textarea>
        </div>

        <!-- Master Prompt Tab Content -->
        <div id="tab-prompt-content" class="hidden flex flex-col">
          <div class="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Master System Prompt (Anti-AI Clichés, E-E-A-T, Schema):</span>
          </div>
          <textarea id="prompt-editor" rows="11" class="w-full bg-[#070b14] border border-slate-800 rounded-xl p-3.5 text-xs font-mono text-slate-300 focus:outline-none focus:border-brand-500/80 transition resize-none leading-relaxed">{prompt_content}</textarea>
        </div>
      </div>

      <!-- Target Keywords Bank Card -->
      <div class="bg-[#0f172a]/90 border border-slate-800/90 rounded-2xl p-5 shadow-xl">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
          <div>
            <h2 class="font-bold text-base text-white">🎯 Bank Target Keyword</h2>
            <p class="text-xs text-slate-400 mt-0.5">Daftar keyword yang direncanakan untuk diriset</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="autoGenerateKeywords()" id="btn-auto-kw" class="text-xs bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 px-2.5 py-1.5 rounded-lg border border-amber-500/30 font-semibold transition active:scale-95">⚡ Isi Ide SEO</button>
            <button onclick="openNewKeywordModal()" class="text-xs bg-slate-800/90 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 font-semibold transition active:scale-95">+ Tambah</button>
          </div>
        </div>
        <div id="keywords-list" class="space-y-2 max-h-56 overflow-y-auto pr-1">
          <div class="text-center py-6 text-slate-400 text-xs">Memuat keyword...</div>
        </div>
      </div>
    </div>
  </main>

  <!-- Preview & Edit Modal -->
  <div id="article-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md z-50 hidden flex items-center justify-center p-3 md:p-6 overflow-hidden">
    <div class="bg-[#0b1120] border border-slate-800 rounded-2xl w-full max-w-5xl h-[92vh] flex flex-col shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-slate-800/90 bg-[#0f172a] flex items-center justify-between shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
          </div>
          <div>
            <h3 id="modal-title-header" class="font-bold text-white text-base leading-tight">Preview & Edit Draf Artikel</h3>
            <p class="text-xs text-slate-400 mt-0.5">Pemeriksaan kualitas On-Page SEO sebelum publikasi resmi</p>
          </div>
        </div>
        <div class="flex items-center gap-2.5">
          <span id="modal-word-badge" class="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-brand-500/15 text-brand-400 border border-brand-500/30">0 kata</span>
          <button onclick="closeArticleModal()" class="w-8 h-8 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition">&times;</button>
        </div>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5 bg-[#0b1120]">
        <input type="hidden" id="modal-article-id">
        
        <!-- Row 1: Title -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">Judul Artikel (H1)</label>
            <span id="title-char-count" class="text-[11px] font-mono text-slate-400">0 karakter (Ideal: 50-60)</span>
          </div>
          <input type="text" id="modal-article-title" oninput="updateCharCount()" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-sm font-semibold text-white focus:outline-none focus:border-brand-500 transition">
        </div>

        <!-- Row 2: Target Keyword & Labels -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Target Primary Keyword</label>
            <input type="text" id="modal-article-keyword" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-brand-500 transition">
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Labels / Tags</label>
            <input type="text" id="modal-article-labels" placeholder="Tech, Tutorial, SEO" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-brand-500 transition">
          </div>
        </div>

        <!-- Row 3: Meta Description -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">Meta Description</label>
            <span id="meta-char-count" class="text-[11px] font-mono text-slate-400">0 karakter (Ideal: 140-155)</span>
          </div>
          <textarea id="modal-article-meta" rows="2" oninput="updateCharCount()" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500 transition resize-none leading-relaxed"></textarea>
        </div>

        <!-- Row 4: Image Helper Tools (Upload / Insert Image) -->
        <div class="bg-[#070b14] border border-slate-800/80 rounded-xl p-3.5 space-y-2.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
              <svg class="w-4 h-4 text-brand-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
              <span>Kelola & Sisipkan Gambar (Image SEO)</span>
            </span>
            <span class="text-[11px] text-slate-400 font-mono">Format: &lt;figure&gt; + &lt;img alt&gt; + &lt;figcaption&gt;</span>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-12 gap-2 text-xs">
            <div class="md:col-span-4">
              <input type="text" id="img-url-input" placeholder="URL Gambar (Unsplash/CDN/Hosting)" class="w-full bg-[#0b1120] border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500 transition">
            </div>
            <div class="md:col-span-3">
              <input type="text" id="img-alt-input" placeholder="Alt Text (Sertakan Keyword)" class="w-full bg-[#0b1120] border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500 transition">
            </div>
            <div class="md:col-span-3">
              <input type="text" id="img-caption-input" placeholder="Caption / Keterangan Gambar" class="w-full bg-[#0b1120] border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500 transition">
            </div>
            <div class="md:col-span-2 flex items-center gap-1.5">
              <label for="modal-img-upload" class="cursor-pointer flex-1 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-center font-medium transition active:scale-95">
                <span>Upload</span>
              </label>
              <input type="file" id="modal-img-upload" accept="image/*" class="hidden" onchange="handleImageUpload(this)">
              <button type="button" onclick="insertImageSnippet()" class="px-3 py-1.5 bg-brand-500 hover:bg-brand-400 text-white rounded-lg font-semibold transition active:scale-95 shadow-sm">+ Sisipkan</button>
            </div>
          </div>
        </div>

        <!-- Row 5: Content Tabs (Visual Render vs Raw HTML) -->
        <div class="flex flex-col space-y-2">
          <div class="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <div class="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800/60">
              <button id="btn-tab-preview" onclick="switchModalView('preview')" class="px-3 py-1 text-xs font-semibold rounded bg-brand-500 text-white shadow-sm transition">Visual Preview</button>
              <button id="btn-tab-code" onclick="switchModalView('code')" class="px-3 py-1 text-xs font-semibold rounded text-slate-400 hover:text-slate-200 transition">Raw HTML</button>
            </div>
            <div class="flex items-center gap-3">
              <span id="content-word-count" class="text-[11px] font-mono text-brand-400 font-semibold">0 kata (~0 mnt baca)</span>
              <span class="text-[11px] text-slate-500 hidden sm:inline">&bull;</span>
              <span class="text-[11px] text-slate-400 hidden sm:inline">Format HTML siap terbit ke Blogger</span>
            </div>
          </div>

          <!-- Visual Rendered Container -->
          <div id="modal-render-container" class="bg-[#070b14] border border-slate-800 rounded-xl p-5 min-h-[300px] max-h-[420px] overflow-y-auto prose-rendered">
            <!-- Content rendered via innerHTML -->
          </div>

          <!-- Raw Code Container -->
          <div id="modal-code-container" class="hidden">
            <textarea id="modal-article-content" rows="14" oninput="syncModalContent()" class="w-full bg-[#070b14] border border-slate-800 rounded-xl p-4 text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500 transition resize-none leading-relaxed"></textarea>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-6 py-4 border-t border-slate-800/90 bg-[#0f172a] flex items-center justify-between shrink-0">
        <button onclick="saveArticleDraft()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition active:scale-95 flex items-center gap-2">
          <span>Simpan Perubahan</span>
        </button>
        <div class="flex items-center gap-3">
          <button onclick="closeArticleModal()" class="px-4 py-2 text-slate-400 hover:text-slate-200 text-xs font-medium">Tutup</button>
          <button id="btn-publish-action" onclick="publishArticle()" class="px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-600/20 flex items-center gap-2 transition active:scale-95">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <span>Setujui & Publish ke Blogger</span>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Tambah Blog / Akun Google Baru -->
  <div id="add-blog-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md z-50 hidden flex items-center justify-center p-3 md:p-6 overflow-hidden">
    <div class="bg-[#0b1120] border border-slate-800 rounded-2xl w-full max-w-lg flex flex-col shadow-2xl overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-800 bg-[#0f172a] flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          </div>
          <div>
            <h3 class="font-bold text-white text-base leading-tight">Hubungkan Blog Baru</h3>
            <p class="text-xs text-slate-400 mt-0.5">Daftarkan blog lain (satu akun atau akun Google berbeda)</p>
          </div>
        </div>
        <button onclick="closeAddBlogModal()" class="w-8 h-8 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition">&times;</button>
      </div>

      <div class="p-6 space-y-4 overflow-y-auto max-h-[75vh]">
        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">ID Blog Blogger *</label>
          <input type="text" id="new-blog-id" placeholder="Contoh: 8492019482019482019" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 transition">
          <p class="text-[10px] text-slate-500 mt-1">Dapat dilihat di URL dashboard Blogger (blogger.com/blog/posts/<b>[BLOG_ID]</b>)</p>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Nama Blog *</label>
          <input type="text" id="new-blog-name" placeholder="Contoh: Info Finansial ID" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 transition">
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">URL Blog</label>
          <input type="text" id="new-blog-url" placeholder="https://namablog.blogspot.com/" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 transition">
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Nama Label Akun Google</label>
          <input type="text" id="new-blog-account" placeholder="Contoh: Akun Kantor, Akun Pribadi" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 transition">
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Niche / Topik Pembahasan</label>
          <input type="text" id="new-blog-niche" placeholder="Contoh: Bisnis, Investasi, Tutorial, Kuliner" class="w-full bg-[#070b14] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 transition">
        </div>

        <div class="pt-2 border-t border-slate-800">
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Kredensial Akun Google</label>
          <div class="space-y-2">
            <label class="flex items-center gap-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-slate-700">
              <input type="radio" name="token-choice" value="existing" checked onchange="toggleTokenUpload(false)" class="text-brand-500 focus:ring-0">
              <div class="text-xs">
                <span class="font-semibold text-white block">Satu Akun Google dengan Blog Aktif</span>
                <span class="text-slate-400 text-[11px]">Memakai token OAuth yang sama tanpa perlu login ulang</span>
              </div>
            </label>

            <label class="flex items-center gap-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-800 cursor-pointer hover:border-slate-700">
              <input type="radio" name="token-choice" value="new" onchange="toggleTokenUpload(true)" class="text-brand-500 focus:ring-0">
              <div class="text-xs">
                <span class="font-semibold text-white block">Akun Google Berbeda (Upload Token Baru)</span>
                <span class="text-slate-400 text-[11px]">Unggah file token.json dari akun Google kedua</span>
              </div>
            </label>
          </div>

          <div id="token-upload-area" class="hidden mt-3 p-3 bg-brand-500/10 border border-brand-500/30 rounded-xl">
            <label class="block text-[11px] font-bold text-brand-300 mb-1">Pilih File token.json:</label>
            <input type="file" id="new-blog-token-file" accept=".json" class="text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-500 file:text-white hover:file:bg-brand-400 cursor-pointer">
            <p id="token-upload-status" class="text-[10px] text-slate-400 mt-1"></p>
          </div>
        </div>
      </div>

      <div class="px-6 py-3.5 bg-[#0f172a] border-t border-slate-800 flex items-center justify-end gap-2.5">
        <button onclick="closeAddBlogModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition">Batal</button>
        <button id="btn-save-new-blog" onclick="saveNewBlog()" class="px-4 py-2 bg-brand-500 hover:bg-brand-400 text-white rounded-xl text-xs font-bold transition shadow-md shadow-brand-500/20 flex items-center gap-1.5">
          <span>Simpan & Daftarkan</span>
        </button>
      </div>
    </div>
  </div>

  <script>
    let blogs = [];
    let activeBlog = null;
    let articles = [];
    let keywords = [];

    async function loadBlogs() {{
      try {{
        const res = await fetch('/api/blogs');
        blogs = await res.json();
        activeBlog = blogs.find(b => b.is_active === 1) || blogs[0] || null;
        renderBlogSelector();
      }} catch (e) {{
        console.error('Error loading blogs:', e);
      }}
    }}

    function renderBlogSelector() {{
      if (!activeBlog) return;
      document.getElementById('active-blog-display-name').innerText = activeBlog.name;
      document.getElementById('active-blog-id').innerText = activeBlog.id;
      const urlEl = document.getElementById('active-blog-url');
      if (urlEl) {{
        urlEl.href = activeBlog.url || '#';
        urlEl.innerText = (activeBlog.url ? activeBlog.url.replace(/^https?:\/\//, '').replace(/\/$/, '') : activeBlog.name) + ' ↗';
      }}
      const totalBadge = document.getElementById('blog-total-badge');
      if (totalBadge) totalBadge.innerText = blogs.length + ' Blog';

      const itemsList = document.getElementById('blog-items-list');
      if (itemsList) {{
        itemsList.innerHTML = blogs.map(b => {{
          const isActive = b.id === activeBlog.id;
          return `
            <div class="flex items-center justify-between p-2 rounded-xl transition ${{isActive ? 'bg-brand-500/15 border border-brand-500/30' : 'hover:bg-slate-800/80'}}">
              <button onclick="selectBlog('${{b.id}}')" class="flex-1 text-left min-w-0 pr-2">
                <div class="flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full ${{isActive ? 'bg-emerald-400' : 'bg-slate-600'}}"></span>
                  <span class="font-bold text-xs text-white truncate">${{b.name}}</span>
                  ${{isActive ? '<span class="text-[9px] bg-emerald-500/20 text-emerald-400 px-1 rounded">Aktif</span>' : ''}}
                </div>
                <div class="text-[10px] text-slate-400 truncate mt-0.5 font-mono">
                  ${{b.account_name || 'Akun'}} &bull; ID: ${{b.id}}
                </div>
              </button>
              ${{blogs.length > 1 && !isActive ? `
                <button onclick="deleteBlog('${{b.id}}', '${{b.name}}')" title="Hapus blog ini" class="w-6 h-6 rounded flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition text-xs font-bold shrink-0">&times;</button>
              ` : ''}}
            </div>
          `;
        }}).join('');
      }}
    }}

    function toggleBlogDropdown() {{
      const menu = document.getElementById('blog-dropdown-menu');
      if (menu) menu.classList.toggle('hidden');
    }}

    document.addEventListener('click', (e) => {{
      const container = document.getElementById('blog-dropdown-container');
      const menu = document.getElementById('blog-dropdown-menu');
      if (container && menu && !container.contains(e.target)) {{
        menu.classList.add('hidden');
      }}
    }});

    async function selectBlog(id) {{
      try {{
        const res = await fetch('/api/blogs/select', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ blog_id: id }})
        }});
        if (res.ok) {{
          activeBlog = blogs.find(b => b.id === id);
          blogs.forEach(b => b.is_active = (b.id === id ? 1 : 0));
          renderBlogSelector();
          const menu = document.getElementById('blog-dropdown-menu');
          if (menu) menu.classList.add('hidden');
          await loadData();
        }}
      }} catch (e) {{
        alert('Gagal berganti blog: ' + e.message);
      }}
    }}

    function openAddBlogModal() {{
      const menu = document.getElementById('blog-dropdown-menu');
      if (menu) menu.classList.add('hidden');
      document.getElementById('new-blog-id').value = '';
      document.getElementById('new-blog-name').value = '';
      document.getElementById('new-blog-url').value = '';
      document.getElementById('new-blog-account').value = '';
      document.getElementById('new-blog-niche').value = '';
      document.getElementById('token-upload-status').innerText = '';
      toggleTokenUpload(false);
      document.getElementById('add-blog-modal').classList.remove('hidden');
    }}

    function closeAddBlogModal() {{
      document.getElementById('add-blog-modal').classList.add('hidden');
    }}

    function toggleTokenUpload(show) {{
      const area = document.getElementById('token-upload-area');
      if (area) {{
        if (show) area.classList.remove('hidden');
        else area.classList.add('hidden');
      }}
    }}

    async function saveNewBlog() {{
      const id = document.getElementById('new-blog-id').value.trim();
      const name = document.getElementById('new-blog-name').value.trim();
      const url = document.getElementById('new-blog-url').value.trim();
      const account = document.getElementById('new-blog-account').value.trim();
      const niche = document.getElementById('new-blog-niche').value.trim();
      const tokenChoice = document.querySelector('input[name="token-choice"]:checked').value;

      if (!id || !name) {{
        alert('ID Blog dan Nama Blog wajib diisi!');
        return;
      }}

      const btn = document.getElementById('btn-save-new-blog');
      btn.disabled = true;
      btn.innerText = 'Menyimpan...';

      let tokenFile = null;
      if (tokenChoice === 'new') {{
        const fileInput = document.getElementById('new-blog-token-file');
        if (!fileInput.files || fileInput.files.length === 0) {{
          alert('Silakan pilih file token.json terlebih dahulu untuk akun Google baru!');
          btn.disabled = false;
          btn.innerText = 'Simpan & Daftarkan';
          return;
        }}
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        try {{
          const upRes = await fetch('/api/blogs/upload-token', {{
            method: 'POST',
            body: formData
          }});
          const upData = await upRes.json();
          if (!upData.success) {{
            throw new Error(upData.error || 'Gagal upload token');
          }}
          tokenFile = upData.token_file;
        }} catch (e) {{
          alert('Gagal mengunggah token: ' + e.message);
          btn.disabled = false;
          btn.innerText = 'Simpan & Daftarkan';
          return;
        }}
      }} else {{
        tokenFile = activeBlog ? activeBlog.token_file : 'token.json';
      }}

      try {{
        const res = await fetch('/api/blogs/add', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            id: id,
            name: name,
            url: url,
            account_name: account || 'Akun Google',
            token_file: tokenFile,
            niche_description: niche
          }})
        }});
        const data = await res.json();
        if (data.success) {{
          closeAddBlogModal();
          await loadBlogs();
          await selectBlog(id);
          alert('🎉 Blog baru berhasil didaftarkan dan diaktifkan!');
        }} else {{
          alert('Gagal: ' + (data.error || 'Terjadi kesalahan'));
        }}
      }} catch (e) {{
        alert('Terjadi kesalahan: ' + e.message);
      }} finally {{
        btn.disabled = false;
        btn.innerText = 'Simpan & Daftarkan';
      }}
    }}

    async function deleteBlog(id, name) {{
      if (!confirm(`Hapus blog "${{name}}" (ID: ${{id}}) dari daftar?`)) return;
      try {{
        const res = await fetch(`/api/blogs/${{id}}/delete`, {{ method: 'POST' }});
        const data = await res.json();
        if (data.success) {{
          await loadBlogs();
          if (activeBlog) await loadData();
        }} else {{
          alert(data.error || 'Gagal menghapus blog.');
        }}
      }} catch (e) {{
        alert('Terjadi kesalahan: ' + e.message);
      }}
    }}

    async function loadData() {{
      try {{
        const blogParam = activeBlog ? `?blog_id=${{activeBlog.id}}` : '';
        const [resArt, resKw] = await Promise.all([
          fetch('/api/articles' + blogParam),
          fetch('/api/keywords' + blogParam)
        ]);
        articles = await resArt.json();
        keywords = await resKw.json();
        
        const countBadge = document.getElementById('article-count-badge');
        if (countBadge) countBadge.innerText = articles.length + ' Draf';
        
        renderArticles();
        renderKeywords();
      }} catch (err) {{
        console.error('Error loading data:', err);
      }}
    }}

    function renderArticles() {{
      const list = document.getElementById('articles-list');
      if (!articles || !articles.length) {{
        list.innerHTML = `
          <div class="text-center py-16 border border-dashed border-slate-800 rounded-2xl p-6">
            <div class="w-12 h-12 rounded-full bg-slate-800/50 text-slate-400 flex items-center justify-center mx-auto mb-3 font-bold text-lg">✍️</div>
            <p class="text-slate-300 font-semibold text-sm">Belum ada antrean draf artikel</p>
            <p class="text-xs text-slate-500 mt-1 max-w-sm mx-auto">Klik <b>Tulis / Draf Baru</b> di pojok kanan atas atau perintahkan agent untuk menulis artikel baru.</p>
          </div>
        `;
        return;
      }}
      
      list.innerHTML = articles.map(a => {{
        const isPublished = a.status === 'published';
        const badge = isPublished
          ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Published</span>`
          : `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>Need Approval</span>`;
        
        return `
          <div class="p-4 rounded-xl border border-slate-800/90 bg-[#070b14]/70 hover:border-slate-700/80 transition duration-150 flex flex-col justify-between gap-3 shadow-sm">
            <div class="space-y-2">
              <div class="flex items-center justify-between flex-wrap gap-2">
                ${{badge}}
                <span class="text-[11px] text-slate-400 font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">KW: ${{a.target_keyword || '-'}}</span>
              </div>
              <h3 class="font-bold text-slate-100 text-sm md:text-base leading-snug hover:text-brand-400 cursor-pointer transition" onclick="viewArticle(${{a.id}})">${{a.title}}</h3>
              <p class="text-xs text-slate-400 line-clamp-2 leading-relaxed">${{a.meta_description || 'Belum ada meta deskripsi'}}</p>
              ${{a.blogger_url ? `<a href="${{a.blogger_url}}" target="_blank" class="text-xs text-brand-400 hover:text-brand-300 font-medium inline-flex items-center gap-1 hover:underline pt-1">Buka Post Live di Blogger &rarr;</a>` : ''}}
            </div>
            <div class="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/50">
              <button onclick="viewArticle(${{a.id}})" class="px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition active:scale-95">Preview / Edit</button>
              ${{!isPublished ? `<button onclick="quickPublish(${{a.id}}, this)" class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow-sm shadow-emerald-600/20 active:scale-95 flex items-center gap-1.5"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>Publish</button>` : ''}}
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderKeywords() {{
      const list = document.getElementById('keywords-list');
      if (!keywords || !keywords.length) {{
        list.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">Belum ada target keyword. Klik <b>⚡ Isi Ide SEO</b> atau <b>+ Tambah</b>.</div>`;
        return;
      }}
      list.innerHTML = keywords.map(k => `
        <div class="p-3 rounded-xl border border-slate-800/80 bg-[#070b14]/50 flex items-center justify-between text-xs gap-2 hover:border-slate-700 transition">
          <div class="flex-1 min-w-0">
            <span class="font-semibold text-slate-200 block truncate" title="${{k.keyword}}">${{k.keyword}}</span>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-[10px] text-slate-400 font-mono">Intent: ${{k.search_intent || 'Informational'}}</span>
              <span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium border border-slate-700/60">${{k.priority || 'Medium'}}</span>
            </div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/90 text-slate-300 font-mono font-medium border border-slate-700/50">${{k.status}}</span>
            <button onclick="deleteKeyword(${{k.id}})" title="Hapus Keyword" class="w-6 h-6 rounded flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition text-sm font-bold">&times;</button>
          </div>
        </div>
      `).join('');
    }}

    function viewArticle(id) {{
      const a = articles.find(x => x.id === id);
      if (!a) return;
      document.getElementById('modal-article-id').value = a.id;
      document.getElementById('modal-article-title').value = a.title;
      document.getElementById('modal-article-keyword').value = a.target_keyword || '';
      document.getElementById('modal-article-labels').value = a.labels || '';
      document.getElementById('modal-article-meta').value = a.meta_description || '';
      document.getElementById('modal-article-content').value = a.content_html;
      
      syncModalContent();
      updateCharCount();
      
      const publishBtn = document.getElementById('btn-publish-action');
      if (a.status === 'published') {{
        publishBtn.classList.add('hidden');
      }} else {{
        publishBtn.classList.remove('hidden');
      }}
      
      switchModalView('preview');
      document.getElementById('article-modal').classList.remove('hidden');
    }}

    function syncModalContent() {{
      const raw = document.getElementById('modal-article-content').value;
      document.getElementById('modal-render-container').innerHTML = raw;
      updateWordCount();
    }}

    function updateWordCount() {{
      const raw = (document.getElementById('modal-article-content') ? document.getElementById('modal-article-content').value : '') || '';
      // Hilangkan tag script, style, dan seluruh tag HTML menggunakan regex agar aman di semua browser
      const clean = raw
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ' ')
        .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&[a-z]+;/gi, ' ')
        .trim();
      
      const words = clean ? clean.split(/\s+/).filter(w => w.length > 0) : [];
      const wordCount = words.length;
      const readMins = Math.max(1, Math.ceil(wordCount / 200));
      const timeStr = wordCount > 0 ? ` (~${{readMins}} mnt baca)` : ' (~0 mnt baca)';
      
      const el = document.getElementById('content-word-count');
      if (el) {{
        let badgeClass = 'text-amber-400';
        if (wordCount >= 1000) {{
          badgeClass = 'text-emerald-400';
        }} else if (wordCount >= 500) {{
          badgeClass = 'text-brand-400';
        }}
        el.className = `text-[11px] font-mono font-semibold ${{badgeClass}}`;
        el.innerText = `${{wordCount.toLocaleString('id-ID')}} kata${{timeStr}}` + (wordCount < 600 && wordCount > 0 ? ' (Ideal: 800-1500+)' : '');
      }}

      const headerBadge = document.getElementById('modal-word-badge');
      if (headerBadge) {{
        let hBadgeClass = 'bg-amber-500/15 text-amber-400 border-amber-500/30';
        if (wordCount >= 1000) {{
          hBadgeClass = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
        }} else if (wordCount >= 500) {{
          hBadgeClass = 'bg-brand-500/15 text-brand-400 border-brand-500/30';
        }}
        headerBadge.className = `text-xs font-mono font-semibold px-3 py-1 rounded-full border ${{hBadgeClass}}`;
        headerBadge.innerText = `${{wordCount.toLocaleString('id-ID')}} kata`;
      }}
    }}

    function updateCharCount() {{
      const title = document.getElementById('modal-article-title').value;
      const meta = document.getElementById('modal-article-meta').value;
      document.getElementById('title-char-count').innerText = title.length + ' karakter (Ideal: 50-60)';
      document.getElementById('meta-char-count').innerText = meta.length + ' karakter (Ideal: 140-155)';
    }}

    async function handleImageUpload(input) {{
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append('file', file);
      try {{
        const res = await fetch('/api/images/upload', {{
          method: 'POST',
          body: formData
        }});
        const data = await res.json();
        if (data.success) {{
          document.getElementById('img-url-input').value = window.location.origin + data.url;
          if (!document.getElementById('img-alt-input').value) {{
            const kw = document.getElementById('modal-article-keyword').value;
            document.getElementById('img-alt-input').value = kw ? ('Ilustrasi panduan ' + kw) : file.name;
          }}
          alert('Gambar berhasil diunggah! Klik "+ Sisipkan" untuk memasukkannya ke draf artikel.');
        }} else {{
          alert('Gagal upload gambar: ' + (data.error || 'Terjadi kesalahan'));
        }}
      }} catch (err) {{
        alert('Error upload: ' + err.message);
      }} finally {{
        input.value = '';
      }}
    }}

    function insertImageSnippet() {{
      const url = document.getElementById('img-url-input').value.trim();
      const alt = document.getElementById('img-alt-input').value.trim() || document.getElementById('modal-article-keyword').value.trim() || 'Ilustrasi Artikel';
      const caption = document.getElementById('img-caption-input').value.trim();
      
      if (!url) {{
        alert('Silakan masukkan URL gambar atau unggah file gambar terlebih dahulu.');
        return;
      }}
      
      const captionHtml = caption ? `<figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">${{caption}}</figcaption>` : '';
      const figureHtml = `\n<figure style="text-align: center; margin: 1.75rem 0;">\n  <img src="${{url}}" alt="${{alt}}" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">\n  ${{captionHtml}}\n</figure>\n`;
      
      const contentArea = document.getElementById('modal-article-content');
      contentArea.value = figureHtml + contentArea.value;
      syncModalContent();
      alert('Gambar berhasil disisipkan ke dalam draf!');
    }}

    function switchModalView(view) {{
      const renderContainer = document.getElementById('modal-render-container');
      const codeContainer = document.getElementById('modal-code-container');
      const btnPreview = document.getElementById('btn-tab-preview');
      const btnCode = document.getElementById('btn-tab-code');
      
      if (view === 'preview') {{
        renderContainer.classList.remove('hidden');
        codeContainer.classList.add('hidden');
        btnPreview.className = 'px-3 py-1 text-xs font-semibold rounded bg-brand-500 text-white shadow-sm transition';
        btnCode.className = 'px-3 py-1 text-xs font-semibold rounded text-slate-400 hover:text-slate-200 transition';
        syncModalContent();
      }} else {{
        renderContainer.classList.add('hidden');
        codeContainer.classList.remove('hidden');
        btnCode.className = 'px-3 py-1 text-xs font-semibold rounded bg-brand-500 text-white shadow-sm transition';
        btnPreview.className = 'px-3 py-1 text-xs font-semibold rounded text-slate-400 hover:text-slate-200 transition';
      }}
    }}

    function openNewArticleModal() {{
      document.getElementById('modal-article-id').value = '';
      document.getElementById('modal-article-title').value = '';
      document.getElementById('modal-article-keyword').value = '';
      document.getElementById('modal-article-labels').value = 'Tech, Tutorial';
      document.getElementById('modal-article-meta').value = '';
      document.getElementById('modal-article-content').value = '<p>Tulis konten atau masukkan kode HTML draf di sini...</p>';
      document.getElementById('btn-publish-action').classList.remove('hidden');
      syncModalContent();
      updateCharCount();
      switchModalView('preview');
      document.getElementById('article-modal').classList.remove('hidden');
    }}

    function closeArticleModal() {{
      document.getElementById('article-modal').classList.add('hidden');
    }}

    async function saveArticleDraft() {{
      const id = document.getElementById('modal-article-id').value;
      const data = {{
        id: id ? parseInt(id) : null,
        title: document.getElementById('modal-article-title').value,
        target_keyword: document.getElementById('modal-article-keyword').value,
        labels: document.getElementById('modal-article-labels').value,
        meta_description: document.getElementById('modal-article-meta').value,
        content_html: document.getElementById('modal-article-content').value,
        blog_id: activeBlog ? activeBlog.id : null
      }};
      const res = await fetch('/api/articles/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data)
      }});
      if (res.ok) {{
        closeArticleModal();
        await loadData();
      }}
    }}

    async function publishArticle() {{
      const id = document.getElementById('modal-article-id').value;
      if (!confirm('Publikasikan artikel ini langsung ke Blogger Bagus Tech sekarang?')) return;
      
      const btn = document.getElementById('btn-publish-action');
      const originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.classList.add('opacity-75', 'cursor-not-allowed');
      btn.innerHTML = `
        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
        <span>Mempublikasikan ke Blogger...</span>
      `;
      
      try {{
        const res = await fetch(`/api/articles/${{id}}/publish`, {{ method: 'POST' }});
        const result = await res.json();
        if (result.success) {{
          btn.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <span>Berhasil Terbit!</span>
          `;
          setTimeout(() => {{
            alert('Sukses! Artikel berhasil live di Blogger.');
            window.location.reload();
          }}, 300);
        }} else {{
          alert('Gagal publish: ' + (result.error || 'Unknown error'));
          btn.disabled = false;
          btn.classList.remove('opacity-75', 'cursor-not-allowed');
          btn.innerHTML = originalHtml;
        }}
      }} catch (err) {{
        alert('Terjadi kesalahan koneksi: ' + err.message);
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'cursor-not-allowed');
        btn.innerHTML = originalHtml;
      }}
    }}

    async function quickPublish(id, btnEl) {{
      if (!confirm('Publikasikan artikel ini ke Blogger sekarang?')) return;
      let originalHtml = '';
      if (btnEl) {{
        originalHtml = btnEl.innerHTML;
        btnEl.disabled = true;
        btnEl.classList.add('opacity-75', 'cursor-not-allowed');
        btnEl.innerHTML = `
          <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
          <span>Publishing...</span>
        `;
      }}
      
      try {{
        const res = await fetch(`/api/articles/${{id}}/publish`, {{ method: 'POST' }});
        const result = await res.json();
        if (result.success) {{
          if (btnEl) btnEl.innerText = 'Selesai!';
          setTimeout(() => {{
            alert('Artikel berhasil dipublish ke Blogger!');
            window.location.reload();
          }}, 300);
        }} else {{
          alert('Gagal: ' + (result.error || 'Terjadi kesalahan'));
          if (btnEl) {{
            btnEl.disabled = false;
            btnEl.classList.remove('opacity-75', 'cursor-not-allowed');
            btnEl.innerHTML = originalHtml;
          }}
        }}
      }} catch (err) {{
        alert('Error: ' + err.message);
        if (btnEl) {{
          btnEl.disabled = false;
          btnEl.classList.remove('opacity-75', 'cursor-not-allowed');
          btnEl.innerHTML = originalHtml;
        }}
      }}
    }}

    function switchRightTab(tab) {{
      const kbContent = document.getElementById('tab-kb-content');
      const promptContent = document.getElementById('tab-prompt-content');
      const kbActions = document.getElementById('kb-actions');
      const promptActions = document.getElementById('prompt-actions');
      const tabKbBtn = document.getElementById('tab-kb-btn');
      const tabPromptBtn = document.getElementById('tab-prompt-btn');
      
      if (tab === 'kb') {{
        kbContent.classList.remove('hidden');
        promptContent.classList.add('hidden');
        kbActions.classList.remove('hidden');
        promptActions.classList.add('hidden');
        tabKbBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-500 text-white shadow-sm transition';
        tabPromptBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-200 transition';
      }} else {{
        kbContent.classList.add('hidden');
        promptContent.classList.remove('hidden');
        kbActions.classList.add('hidden');
        promptActions.classList.remove('hidden');
        tabPromptBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-500 text-white shadow-sm transition';
        tabKbBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-200 transition';
      }}
    }}

    async function savePrompt() {{
      const content = document.getElementById('prompt-editor').value;
      const btn = document.getElementById('btn-save-prompt');
      btn.innerText = 'Menyimpan...';
      const res = await fetch('/api/prompt/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ content }})
      }});
      if (res.ok) {{
        btn.innerText = 'Tersimpan ✓';
        setTimeout(() => {{ btn.innerText = 'Simpan Prompt'; }}, 2000);
      }}
    }}

    async function saveKb() {{
      const content = document.getElementById('kb-editor').value;
      const btn = document.getElementById('btn-save-kb');
      btn.innerText = 'Menyimpan...';
      const res = await fetch('/api/kb/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ content }})
      }});
      if (res.ok) {{
        btn.innerText = 'Tersimpan ✓';
        setTimeout(() => {{ btn.innerText = 'Simpan'; }}, 2000);
      }}
    }}

    async function uploadPdf(input) {{
      if (!input.files || input.files.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < input.files.length; i++) {{
        formData.append('files', input.files[i]);
      }}
      
      const count = input.files.length;
      const btn = document.getElementById('btn-save-kb');
      btn.innerText = 'Memproses ' + count + ' PDF...';
      try {{
        const res = await fetch('/api/kb/upload-pdf', {{
          method: 'POST',
          body: formData
        }});
        const data = await res.json();
        if (data.success) {{
          document.getElementById('kb-editor').value = data.content;
          alert('Berhasil mengekstrak ' + data.total_files + ' file PDF (' + data.total_pages + ' total halaman)! Materi sudah ditambahkan ke Knowledge Base.');
        }} else {{
          alert('Gagal memproses PDF: ' + (data.error || 'Error'));
        }}
      }} catch (err) {{
        alert('Terjadi kesalahan saat upload PDF: ' + err.message);
      }} finally {{
        btn.innerText = 'Simpan';
        input.value = '';
      }}
    }}

    async function openNewKeywordModal() {{
      const kw = prompt('Masukkan target keyword baru:');
      if (!kw) return;
      const intent = prompt('Search intent (Informational / Commercial / Navigational):', 'Informational');
      await fetch('/api/keywords/add', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          keyword: kw,
          search_intent: intent || 'Informational',
          blog_id: activeBlog ? activeBlog.id : null
        }})
      }});
      await loadData();
    }}

    async function deleteKeyword(id) {{
      if (!confirm('Hapus keyword ini dari daftar?')) return;
      const res = await fetch(`/api/keywords/${{id}}/delete`, {{ method: 'POST' }});
      if (res.ok) await loadData();
    }}

    async function autoGenerateKeywords() {{
      const btn = document.getElementById('btn-auto-kw');
      btn.innerText = 'Menyusun...';
      try {{
        const blogParam = activeBlog ? `?blog_id=${{activeBlog.id}}` : '';
        const res = await fetch('/api/keywords/auto-generate' + blogParam, {{ method: 'POST' }});
        if (res.ok) {{
          await loadData();
          const bName = activeBlog ? activeBlog.name : 'Blog';
          alert(`Berhasil mengisi bank keyword dengan topik-topik SEO berkualitas untuk ${{bName}}!`);
        }}
      }} finally {{
        btn.innerText = '⚡ Isi Ide SEO';
      }}
    }}

    async function triggerAutoGenerate() {{
      const btn = document.getElementById('btn-auto-generate');
      const txt = document.getElementById('btn-auto-generate-text');
      const bName = activeBlog ? activeBlog.name : 'Blogger';
      if (!confirm(`Minta Agent SEO Specialist meriset topik baru dari blog ${{bName}} dan menyusun draf sekarang?`)) return;
      
      btn.disabled = true;
      btn.classList.add('opacity-70');
      txt.innerText = '⏳ Agent sedang meriset...';
      
      try {{
        const res = await fetch('/api/agent/generate-now', {{ method: 'POST' }});
        const data = await res.json();
        alert('🚀 Permintaan diterima! Agent SEO Specialist sedang menganalisis blog dan menyusun artikel baru di background. Draf akan otomatis muncul di antrean.');
        
        const checkInterval = setInterval(async () => {{
          await loadData();
        }}, 12000);
        
        setTimeout(() => {{
          btn.disabled = false;
          btn.classList.remove('opacity-70');
          txt.innerText = '⚡ Riset & Draf Otomatis';
          clearInterval(checkInterval);
        }}, 180000);
      }} catch (e) {{
        alert('Terjadi kesalahan: ' + e.message);
        btn.disabled = false;
        btn.classList.remove('opacity-70');
        txt.innerText = '⚡ Riset & Draf Otomatis';
      }}
    }}

    async function init() {{
      await loadBlogs();
      await loadData();
    }}
    init();
  </script>
</body>
</html>'''
    return html

class ArticleSaveReq(BaseModel):
    id: Optional[int] = None
    title: str
    target_keyword: Optional[str] = None
    meta_description: Optional[str] = None
    content_html: str
    labels: Optional[str] = None
    blog_id: Optional[str] = None

@app.post('/api/articles/save')
def api_save_article(req: ArticleSaveReq):
    conn = get_db()
    c = conn.cursor()
    target_blog_id = req.blog_id
    if not target_blog_id:
        active = c.execute('SELECT id FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
        target_blog_id = active['id'] if active else '2940095957137948013'

    if req.id:
        c.execute('''
            UPDATE articles SET title = ?, target_keyword = ?, meta_description = ?, content_html = ?, labels = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (req.title, req.target_keyword, req.meta_description, req.content_html, req.labels, req.id))
    else:
        c.execute('''
            INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, blog_id, status) VALUES (?, ?, ?, ?, ?, ?, 'draft')
        ''', (req.title, req.target_keyword, req.meta_description, req.content_html, req.labels, target_blog_id))
    
    if req.target_keyword:
        c.execute('''
            UPDATE keywords SET status = 'in_progress' WHERE LOWER(keyword) = LOWER(?) AND status = 'planned' AND (blog_id = ? OR blog_id IS NULL)
        ''', (req.target_keyword.strip(), target_blog_id))
    
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/articles/{article_id}/publish')
def api_publish_article(article_id: int):
    conn = get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail='Article not found')
        
    art_blog_id = row['blog_id'] if 'blog_id' in row.keys() and row['blog_id'] else None
    token_file = None
    target_b_id = art_blog_id
    if art_blog_id:
        b_row = c.execute('SELECT * FROM blogs WHERE id = ?', (art_blog_id,)).fetchone()
        if b_row:
            token_file = b_row['token_file']
            target_b_id = b_row['id']
            
    try:
        post = create_post(
            title=row['title'],
            content_html=row['content_html'],
            labels=row['labels'],
            is_draft=False,
            token_file=token_file,
            blog_id=target_b_id
        )
        blogger_post_id = post.get('id')
        blogger_url = post.get('url')
        
        c.execute('''
            UPDATE articles SET status = 'published', blogger_post_id = ?, blogger_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (blogger_post_id, blogger_url, article_id))
        
        if row['target_keyword']:
            c.execute('''
                UPDATE keywords SET status = 'used' WHERE LOWER(keyword) = LOWER(?) AND (blog_id = ? OR blog_id IS NULL)
            ''', (row['target_keyword'].strip(), target_b_id or ''))
            
        conn.commit()
        conn.close()
        return {'success': True, 'url': blogger_url, 'post_id': blogger_post_id}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

class PromptSaveReq(BaseModel):
    content: str

@app.post('/api/prompt/save')
def api_save_prompt(req: PromptSaveReq):
    with open(SEO_PROMPT_PATH, 'w') as f:
        f.write(req.content)
    return {'success': True}

class KbSaveReq(BaseModel):
    content: str

@app.post('/api/kb/save')
def api_save_kb(req: KbSaveReq):
    with open(SEO_KB_PATH, 'w') as f:
        f.write(req.content)
    return {'success': True}

@app.post('/api/kb/upload-pdf')
async def api_upload_pdf(files: List[UploadFile] = File(...)):
    try:
        total_pages = 0
        added_texts = []
        for file in files:
            contents = await file.read()
            reader = PdfReader(io.BytesIO(contents))
            total_pages += len(reader.pages)
            extracted_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_text.append(f"\n--- [{file.filename} - Halaman {i+1}] ---\n" + text.strip())
            if extracted_text:
                added_texts.append(f"\n\n## Materi Tambahan dari Dokumen PDF: {file.filename}\n" + "\n".join(extracted_text))
                
        existing_content = ''
        if os.path.exists(SEO_KB_PATH):
            with open(SEO_KB_PATH, 'r') as f:
                existing_content = f.read()
                
        new_content = existing_content + "".join(added_texts)
        with open(SEO_KB_PATH, 'w') as f:
            f.write(new_content)
            
        return {'success': True, 'total_files': len(files), 'total_pages': total_pages, 'content': new_content}
    except Exception as e:
        return {'success': False, 'error': str(e)}

class KeywordAddReq(BaseModel):
    keyword: str
    search_intent: Optional[str] = 'Informational'
    blog_id: Optional[str] = None

@app.post('/api/keywords/add')
def api_add_keyword(req: KeywordAddReq):
    conn = get_db()
    c = conn.cursor()
    b_id = req.blog_id
    if not b_id:
        active = c.execute('SELECT id FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
        b_id = active['id'] if active else '2940095957137948013'
    try:
        c.execute('INSERT OR IGNORE INTO keywords (keyword, search_intent, blog_id) VALUES (?, ?, ?)', (req.keyword, req.search_intent, b_id))
        conn.commit()
    finally:
        conn.close()
    return {'success': True}

@app.post('/api/keywords/{kw_id}/delete')
def api_delete_keyword(kw_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM keywords WHERE id = ?', (kw_id,))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/keywords/auto-generate')
def api_auto_generate_keywords(blog_id: Optional[str] = None):
    conn = get_db()
    c = conn.cursor()
    b_id = blog_id
    if not b_id:
        active = c.execute('SELECT id FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
        b_id = active['id'] if active else '2940095957137948013'
    c.execute("DELETE FROM keywords WHERE keyword = 'tes'")
    high_quality_keywords = [
        ('rekomendasi ai coding assistant gratis untuk vs code', 'Informational'),
        ('cara integrasi api gemini di web modern', 'Informational'),
        ('tips prompt engineering untuk software engineer', 'Informational'),
        ('perbandingan claude dan chatgpt untuk programming', 'Commercial'),
        ('panduan optimasi loading website skor 100', 'Informational'),
        ('tools ai produktivitas terbaik untuk freelancer tech', 'Informational')
    ]
    for kw, intent in high_quality_keywords:
        c.execute('''
            INSERT OR IGNORE INTO keywords (keyword, search_intent, status, blog_id) 
            VALUES (?, ?, 'planned', ?)
        ''', (kw, intent, b_id))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/agent/generate-now')
def api_agent_generate_now():
    import subprocess
    log_path = os.environ.get('BLOGGER_LOG_FILE', os.path.join(BASE_DIR, 'agent_run.log'))
    log_file = open(log_path, 'a')
    log_file.write('\n=== Triggered via Dashboard ===\n')
    log_file.flush()
    hermes_bin = '/opt/hermes/.venv/bin/hermes'
    if os.path.exists(hermes_bin):
        cmd = [hermes_bin, 'cron', 'run', 'ef1ee19a17b2']
    else:
        worker_script = os.path.join(BASE_DIR, 'agent_worker.py')
        cmd = [sys.executable, worker_script]
    subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )
    return {'success': True, 'message': 'Agent dimulai di background'}

@app.post('/api/images/upload')
async def api_upload_image(file: UploadFile = File(...)):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            return JSONResponse({'success': False, 'error': 'Format file harus JPG, PNG, WEBP, atau GIF'}, status_code=400)
        filename = f"{uuid.uuid4().hex[:12]}_{file.filename.replace(' ', '_')}"
        file_path = os.path.join(UPLOADS_DIR, filename)
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        file_url = f"/uploads/{filename}"
        return {'success': True, 'url': file_url, 'filename': filename}
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8090)

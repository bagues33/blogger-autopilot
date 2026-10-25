#!/usr/bin/env python3
"""
Autonomous SEO Agent Worker for Blogger Auto-Pilot
Generates high-quality SEO-optimized draft articles following Google E-E-A-T & HCU guidelines.
"""

import os
import sys
import json
import re
import sqlite3
from datetime import datetime
import urllib.request
import urllib.error

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db import DB_PATH, BASE_DIR

SEO_KB_PATH = os.environ.get('BLOGGER_SEO_KB_PATH', os.path.join(BASE_DIR, 'seo_knowledge.md'))
SEO_PROMPT_PATH = os.environ.get('BLOGGER_SEO_PROMPT_PATH', os.path.join(BASE_DIR, 'seo_master_prompt.md'))

def get_active_blog():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    row = c.execute('SELECT * FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
    if not row:
        row = c.execute('SELECT * FROM blogs LIMIT 1').fetchone()
    conn.close()
    return dict(row) if row else None

def get_next_keyword(blog_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if blog_id:
        row = c.execute(
            "SELECT * FROM keywords WHERE status = 'planned' AND (blog_id = ? OR blog_id IS NULL) ORDER BY id ASC LIMIT 1",
            (blog_id,)
        ).fetchone()
    else:
        row = c.execute("SELECT * FROM keywords WHERE status = 'planned' ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def read_guidelines():
    master_prompt = ""
    if os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, "r", encoding="utf-8") as f:
            master_prompt = f.read()

    kb_notes = ""
    if os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, "r", encoding="utf-8") as f:
            kb_notes = f.read()

    return master_prompt, kb_notes

def clean_and_parse_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise

def resolve_topic_image(keyword: str) -> str:
    kw = keyword.lower()
    if any(k in kw for k in ['ai', 'prompt', 'gemini', 'gpt', 'claude', 'intelligence', 'robot']):
        photo_id = 'photo-1677442136019-21780efad99a'
    elif any(k in kw for k in ['code', 'coding', 'program', 'developer', 'python', 'javascript', 'vs code']):
        photo_id = 'photo-1555066931-4365d14bab8c'
    elif any(k in kw for k in ['web', 'website', 'html', 'css', 'frontend', 'blogger', 'blogspot']):
        photo_id = 'photo-1461749280684-dccba630e2f6'
    elif any(k in kw for k in ['cloud', 'server', 'hosting', 'api', 'backend', 'database']):
        photo_id = 'photo-1451187580459-43490279c0fa'
    elif any(k in kw for k in ['speed', 'vitals', 'perform', 'loading', 'optimas']):
        photo_id = 'photo-1551288049-bebda4e38f71'
    elif any(k in kw for k in ['tool', 'alat', 'aplikasi', 'freelance', 'kerja']):
        photo_id = 'photo-1517694712202-14dd9538aa97'
    else:
        photo_id = 'photo-1518770660439-4636190af475'
    return f"https://images.unsplash.com/{photo_id}?w=1200&auto=format&fit=crop&q=80"

def sanitize_article_metadata(title: str, meta_desc: str):
    title = title.strip()
    if len(title) > 60:
        cut = title[:60].rfind(" ")
        title = title[:cut] if cut > 40 else title[:60]
    meta_desc = meta_desc.strip()
    if len(meta_desc) > 155:
        cut = meta_desc[:155].rfind(" ")
        meta_desc = (meta_desc[:cut] if cut > 120 else meta_desc[:155])
        if not meta_desc.endswith(('.', '!', '?')):
            meta_desc += '.'
    return title, meta_desc

def call_gemini(api_key, system_prompt, user_prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\n---\nPERMINTAAN USER:\n{user_prompt}\n\nFormat output WAJIB JSON murni tanpa markdown triple-backticks:\n{{\"title\": \"...\", \"meta_description\": \"...\", \"labels\": \"...\", \"content_html\": \"...\"}}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json"
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        content = res['candidates'][0]['content']['parts'][0]['text']
        return clean_and_parse_json(content)

def call_openai_compatible(api_url, api_key, model_name, system_prompt, user_prompt):
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt + "\n\nFormat output WAJIB JSON murni:\n{\"title\": \"...\", \"meta_description\": \"...\", \"labels\": \"...\", \"content_html\": \"...\"}"},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        content = res['choices'][0]['message']['content']
        return clean_and_parse_json(content)

def generate_fallback_article(keyword, search_intent, blog_name, blog_url):
    kw_title = keyword.title()
    title = f"{kw_title}: Panduan Praktis dan Lengkap"
    if len(title) > 60:
        title = f"{kw_title}: Panduan Lengkap"
    if len(title) < 50:
        title = f"{kw_title}: Panduan Praktis Lengkap"

    meta_desc = f"Simak ulasan lengkap mengenai {keyword}. Temukan langkah praktis, tips teruji, dan solusi efektif untuk optimasi kebutuhan Anda sekarang!"
    if len(meta_desc) < 140:
        meta_desc += f" Baca panduan komprehensif di sini!"

    topic_image_url = resolve_topic_image(keyword)

    content_html = f"""<p><strong>{keyword.capitalize()}</strong> merupakan solusi strategis yang dapat diimplementasikan untuk meningkatkan efisiensi alur kerja digital, meminimalisir kesalahan teknis, serta memberikan hasil optimal melalui pendekatan berbasis metode terbaik dan prinsip kerja terstruktur.</p>

<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="{topic_image_url}" alt="{keyword.capitalize()} dalam implementasi praktis" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  <figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">Ilustrasi penerapan {keyword} untuk efektivitas alur kerja.</figcaption>
</figure>

<p>Menerapkan konsep ini secara tepat membutuhkan pemahaman menyeluruh terhadap dasar-dasar operasional dan pemilihan alat yang sesuai. Tanpa fondasi yang kuat, banyak praktisi menghadapi kendala implementasi yang sebenarnya dapat dihindari sejak tahap perencanaan awal.</p>

<h2>Mengapa {keyword.capitalize()} Sangat Krusial?</h2>
<p>Kebutuhan terhadap efisiensi dan keakuratan data menjadikan pemahaman mendalam atas topik ini sangat penting. Berikut ringkasan parameter pertimbangan utama:</p>

<table border="1" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
  <thead>
    <tr style="background-color: #f1f5f9; color: #0f172a;">
      <th>Parameter</th>
      <th>Metode Konvensional</th>
      <th>Pendekatan Teroptimasi</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Efisiensi Waktu</strong></td>
      <td>Memerlukan konfigurasi manual berulang</td>
      <td>Otomatisasi proses & alur terintegrasi</td>
    </tr>
    <tr>
      <td><strong>Akurasi & Stabilitas</strong></td>
      <td>Rentan terhadap kesalahan manusiawi</td>
      <td>Standarisasi prosedur & pengujian konsisten</td>
    </tr>
    <tr>
      <td><strong>Skalabilitas</strong></td>
      <td>Terbatas pada kapasitas individual</td>
      <td>Mudah disesuaikan dengan volume kerja tinggi</td>
    </tr>
  </tbody>
</table>

<h2>Langkah Praktis Implementasi</h2>
<p>Untuk menerapkan strategi ini secara efektif, ikuti tahapan teruji berikut:</p>
<ol>
  <li><strong>Identifikasi Kebutuhan & Target:</strong> Tentukan metrik keberhasilan sebelum memulai proses eksekusi.</li>
  <li><strong>Konfigurasi Lingkungan Kerja:</strong> Siapkan dependensi, izin akses, dan perkakas pendukung yang diperlukan.</li>
  <li><strong>Eksekusi Bertahap:</strong> Terapkan solusi pada ruang lingkup kecil terlebih dahulu guna memvalidasi efektivitas sebelum rilis menyeluruh.</li>
  <li><strong>Evaluasi dan Optimasi Berkelanjutan:</strong> Lakukan peninjauan performa secara berkala untuk menjaga stabilitas hasil.</li>
</ol>

<div class="faq-section">
  <h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>
  <h3>Apa langkah awal yang harus disiapkan untuk {keyword}?</h3>
  <p>Langkah awal adalah memahami sasaran kebutuhan spesifik, menyiapkan alat atau dependensi pendukung, dan memastikan prosedur keamanan telah dipenuhi.</p>
  <h3>Berapa lama waktu yang dibutuhkan untuk melihat hasil optimal?</h3>
  <p>Implementasi standar biasanya dapat diselesaikan dalam beberapa jam hingga hari tergantung kompleksitas lingkungan kerja yang digunakan.</p>
  <h3>Apakah pendekatan ini cocok untuk pemula?</h3>
  <p>Ya, dengan mengikuti panduan terstruktur dan dokumentasi yang jelas, pemula dapat menerapkan metode ini secara bertahap tanpa kendala berarti.</p>
</div>

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "Apa langkah awal yang harus disiapkan untuk {keyword}?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Langkah awal adalah memahami sasaran kebutuhan spesifik dan menyiapkan dependensi pendukung."
      }}
    }},
    {{
      "@type": "Question",
      "name": "Berapa lama waktu yang dibutuhkan untuk melihat hasil optimal?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Implementasi standar biasanya diselesaikan dalam hitungan jam hingga hari tergantung lingkungan kerja."
      }}
    }},
    {{
      "@type": "Question",
      "name": "Apakah pendekatan ini cocok untuk pemula?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Ya, panduan terstruktur memudahkan pemula menerapkan metode ini secara aman."
      }}
    }}
  ]
}}
</script>"""

    return {
        "title": title[:60],
        "meta_description": meta_desc[:155],
        "labels": f"SEO, {kw_title}, Tutorial, Web",
        "content_html": content_html
    }

def run_agent(user_id=None):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Autonomous SEO Agent...")

    # Multi-tenant credit check
    saas_db = None
    user_sub = None
    if user_id:
        try:
            from db_saas import SessionLocal
            from models_saas import Subscription
            saas_db = SessionLocal()
            user_sub = saas_db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if user_sub:
                if user_sub.article_credits_used >= user_sub.article_credits_limit:
                    print(f"[QUOTA EXCEEDED] Kuota artikel habis: {user_sub.article_credits_used}/{user_sub.article_credits_limit} kredit telah terpakai.")
                    print("Silakan upgrade langganan Anda ke paket Starter atau Pro di dashboard.")
                    saas_db.close()
                    sys.exit(2)
        except Exception as e:
            print(f"Notice: SaaS credit check skipped ({e})")

    blog = get_active_blog()
    blog_id = blog['id'] if blog else '2940095957137948013'
    blog_name = blog['name'] if blog else 'Bagus Tech'
    blog_url = blog['url'] if blog else 'https://bagustechnologia.blogspot.com/'
    print(f"Target Blog: {blog_name} (ID: {blog_id})")

    kw_data = get_next_keyword(blog_id)
    if not kw_data:
        print("Tidak ada keyword berstatus 'planned' yang ditemukan di database. Agent selesai.")
        if saas_db:
            saas_db.close()
        return

    kw_id = kw_data['id']
    keyword = kw_data['keyword']
    intent = kw_data.get('search_intent', 'Informational')
    print(f"Selected Keyword [{kw_id}]: '{keyword}' (Intent: {intent})")

    master_prompt, kb_notes = read_guidelines()
    combined_system_prompt = f"{master_prompt}\n\n---\nKNOWLEDGE BASE & GUIDELINES:\n{kb_notes}"

    user_prompt = f"""Tulis draf artikel blog mendalam untuk target keyword: "{keyword}"
Search Intent: {intent}
Blog Name: {blog_name}
Blog URL: {blog_url}

Patuhi seluruh Negative Constraints (dilarang basa-basi pembuka, dilarang heading H2 'Kesimpulan', dilarang filler words).
Wajib sertakan Hook Direct Answer 40-50 kata pertama, minimal 1 tabel komparasi, minimal 1 gambar Image SEO dengan <figure> dan deskriptif alt text, serta FAQPage JSON-LD Schema.
"""

    gemini_key = os.environ.get('GEMINI_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')

    article_data = None

    if gemini_key:
        print("Menghasilkan konten via Google Gemini API...")
        try:
            article_data = call_gemini(gemini_key, combined_system_prompt, user_prompt)
        except Exception as e:
            print(f"Gemini API error: {e}")

    if not article_data and groq_key:
        print("Menghasilkan konten via Groq API...")
        try:
            article_data = call_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                groq_key,
                "llama-3.3-70b-versatile",
                combined_system_prompt,
                user_prompt
            )
        except Exception as e:
            print(f"Groq API error: {e}")

    if not article_data and openai_key:
        print("Menghasilkan konten via OpenAI API...")
        try:
            article_data = call_openai_compatible(
                "https://api.openai.com/v1/chat/completions",
                openai_key,
                "gpt-4o-mini",
                combined_system_prompt,
                user_prompt
            )
        except Exception as e:
            print(f"OpenAI API error: {e}")

    if not article_data:
        print("[INFO] Tidak ada LLM API key yang dikonfigurasi (atau terjadi error). Menggunakan Generator Template SEO berstruktur penuh...")
        article_data = generate_fallback_article(keyword, intent, blog_name, blog_url)

    raw_title = article_data.get('title', f"{keyword.title()}: Panduan Lengkap")
    raw_meta = article_data.get('meta_description', f"Panduan lengkap mengenai {keyword}.")
    title, meta_desc = sanitize_article_metadata(raw_title, raw_meta)
    content_html = article_data.get('content_html', '')
    labels = article_data.get('labels', 'Teknologi, SEO, Tutorial')

    # Auto-inject Google E-E-A-T Schema JSON-LD if not yet present
    try:
        from schema_builder import inject_schema_if_missing
        content_html = inject_schema_if_missing(
            html_content=content_html,
            title=title,
            meta_description=meta_desc
        )
    except Exception:
        pass

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Update keyword status to in_progress
    c.execute("UPDATE keywords SET status = 'in_progress' WHERE id = ?", (kw_id,))

    # 2. Insert draft article
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, status, created_at, updated_at, blog_id)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
    ''', (title, keyword, meta_desc, content_html, labels, now_str, now_str, blog_id))

    new_article_id = c.lastrowid
    conn.commit()
    conn.close()

    # Save to SaaS models & increment SaaS credits used
    if saas_db and user_sub:
        try:
            from models_saas import Article as SaasArticle, Keyword as SaasKeyword
            saas_art = SaasArticle(
                user_id=user_id,
                blog_id=blog_id,
                title=title,
                target_keyword=keyword,
                meta_description=meta_desc,
                content_html=content_html,
                labels=labels,
                status='draft'
            )
            saas_db.add(saas_art)

            kw_saas = saas_db.query(SaasKeyword).filter(SaasKeyword.user_id == user_id, SaasKeyword.keyword == keyword).first()
            if kw_saas:
                kw_saas.status = 'in_progress'

            user_sub.article_credits_used += 1
            saas_db.commit()
            print(f"[SAAS QUOTA] Kredit diperbarui: {user_sub.article_credits_used}/{user_sub.article_credits_limit} telah digunakan.")

            # Send Telegram / Webhook notification
            try:
                from notification_service import dispatch_notification
                dispatch_notification(
                    user_id=user_id,
                    event_type="draft_created",
                    data={
                        "title": title,
                        "keyword": keyword,
                        "blog_name": blog_info.get('name') if blog_info else 'Blog',
                        "article_id": saas_art.id
                    },
                    db_session=saas_db
                )

                remaining = user_sub.article_credits_limit - user_sub.article_credits_used
                if remaining <= 1:
                    dispatch_notification(
                        user_id=user_id,
                        event_type="credit_low",
                        data={"remaining_credits": remaining},
                        db_session=saas_db
                    )
            except Exception as notify_err:
                print(f"[NOTIFICATION] Warning: {notify_err}")
        except Exception as e:
            print(f"Error saving to SaasArticle: {e}")
        finally:
            saas_db.close()

    print(f"SUCCESS: Artikel baru berhasil dibuat dengan ID {new_article_id} untuk keyword '{keyword}'.")
    print(f"Title: {title}")
    print(f"Status: draft (tersimpan di database untuk direview)")

if __name__ == '__main__':
    target_user = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--user-id='):
        target_user = sys.argv[1].split('=', 1)[1].strip()
    elif len(sys.argv) > 2 and sys.argv[1] == '--user-id':
        target_user = sys.argv[2].strip()
    run_agent(user_id=target_user)

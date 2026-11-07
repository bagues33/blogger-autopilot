"""
Content Generator Deep Module for Blogger Auto-Pilot SaaS
Encapsulates prompt synthesis, LLM generation behind an interchangeable seam,
schema audit injection, atomic tenant quota deduction, and article drafting.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from db_saas import SessionLocal, BASE_DIR
from models_saas import User, Blog, Keyword, Article, Subscription
from schema_builder import inject_schema_if_missing
from notification_service import dispatch_notification
from audit_service import record_audit_log

logger = logging.getLogger("ContentGenerator")

SEO_KB_PATH = os.environ.get('BLOGGER_SEO_KB_PATH', os.path.join(BASE_DIR, 'seo_knowledge.md'))
SEO_PROMPT_PATH = os.environ.get('BLOGGER_SEO_PROMPT_PATH', os.path.join(BASE_DIR, 'seo_master_prompt.md'))

@dataclass
class ArticleGenerationResult:
    success: bool
    article_id: Optional[int] = None
    title: Optional[str] = None
    keyword: Optional[str] = None
    blog_name: Optional[str] = None
    status: str = "draft"
    credits_remaining: Optional[int] = None
    error: Optional[str] = None

# --- Helpers ---

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

def generate_structured_fallback_article(keyword: str, search_intent: str, blog_name: str, blog_url: str) -> dict:
    kw_title = keyword.title()
    title = f"{kw_title}: Panduan Praktis dan Lengkap"
    if len(title) > 60:
        title = f"{kw_title}: Panduan Lengkap"
    if len(title) < 50:
        title = f"{kw_title}: Panduan Praktis Lengkap"

    meta_desc = f"Simak ulasan lengkap mengenai {keyword}. Temukan langkah praktis, tips teruji, dan solusi efektif untuk optimasi kebutuhan Anda sekarang!"
    if len(meta_desc) < 140:
        meta_desc += " Baca panduan komprehensif di sini!"

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
"""
    return {
        "title": title[:60],
        "meta_description": meta_desc[:155],
        "labels": f"SEO, {kw_title}, Tutorial, Web",
        "content_html": content_html
    }

# --- LLM Seam & Adapters ---

class BaseLLMAdapter(ABC):
    """Abstract interface defining the seam for LLM content generation."""
    @abstractmethod
    def generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        keyword: str,
        search_intent: str,
        blog_name: str,
        blog_url: str,
        custom_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        pass

class LiveLLMAdapter(BaseLLMAdapter):
    """
    Production adapter querying Google Gemini, Groq, or OpenAI endpoints,
    with an algorithmic structured fallback if no provider keys are present.
    """
    def _call_gemini(self, api_key: str, system_prompt: str, user_prompt: str) -> dict:
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

    def _call_openai_compatible(self, api_url: str, api_key: str, model_name: str, system_prompt: str, user_prompt: str) -> dict:
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

    def generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        keyword: str,
        search_intent: str,
        blog_name: str,
        blog_url: str,
        custom_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        keys = custom_keys or {}
        gemini_key = keys.get('gemini_key') or os.environ.get('GEMINI_API_KEY')
        groq_key = keys.get('groq_key') or os.environ.get('GROQ_API_KEY')
        openai_key = keys.get('openai_key') or os.environ.get('OPENAI_API_KEY')

        if gemini_key:
            try:
                return self._call_gemini(gemini_key, system_prompt, user_prompt)
            except Exception as e:
                logger.warning(f"Gemini API request failed: {e}")

        if groq_key:
            try:
                return self._call_openai_compatible(
                    "https://api.groq.com/openai/v1/chat/completions",
                    groq_key,
                    "llama-3.3-70b-versatile",
                    system_prompt,
                    user_prompt
                )
            except Exception as e:
                logger.warning(f"Groq API request failed: {e}")

        if openai_key:
            try:
                return self._call_openai_compatible(
                    "https://api.openai.com/v1/chat/completions",
                    openai_key,
                    "gpt-4o-mini",
                    system_prompt,
                    user_prompt
                )
            except Exception as e:
                logger.warning(f"OpenAI API request failed: {e}")

        logger.info("Using structured fallback article generation engine.")
        return generate_structured_fallback_article(keyword, search_intent, blog_name, blog_url)

class InMemoryLLMAdapter(BaseLLMAdapter):
    """
    In-memory test adapter returning predictable, deterministic article payloads
    without making any network requests.
    """
    def __init__(self, canned_response: Optional[Dict[str, Any]] = None):
        self.canned_response = canned_response
        self.call_history = []

    def generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        keyword: str,
        search_intent: str,
        blog_name: str,
        blog_url: str,
        custom_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        self.call_history.append({
            'keyword': keyword,
            'search_intent': search_intent,
            'blog_name': blog_name,
            'blog_url': blog_url,
            'custom_keys': custom_keys
        })
        if self.canned_response:
            return self.canned_response

        return {
            "title": f"Panduan Lengkap {keyword.title()}",
            "meta_description": f"Pelajari seluk beluk {keyword} secara mendalam dan terstruktur di blog ini.",
            "labels": "Teknologi, SEO, Otomatisasi",
            "content_html": f"<p>Artikel komprehensif mengenai {keyword} untuk optimasi alur kerja Anda.</p><h2>FAQ</h2><p>Pertanyaan umum mengenai {keyword}.</p>"
        }

_current_llm_adapter: Optional[BaseLLMAdapter] = None

def get_llm_adapter() -> BaseLLMAdapter:
    global _current_llm_adapter
    if _current_llm_adapter is None:
        _current_llm_adapter = LiveLLMAdapter()
    return _current_llm_adapter

def set_llm_adapter(adapter: Optional[BaseLLMAdapter]) -> None:
    global _current_llm_adapter
    _current_llm_adapter = adapter

# --- Deep Module Core Interface ---

def generate_article(
    tenant_id: str,
    blog_id: Optional[str] = None,
    keyword_id: Optional[int] = None,
    llm_adapter: Optional[BaseLLMAdapter] = None,
    db: Optional[Session] = None
) -> ArticleGenerationResult:
    """
    Orchestrates end-to-end article drafting:
    Validates tenant quota, resolves active blog and target keyword,
    synthesizes prompt, calls LLM via seam adapter, injects Schema,
    commits database state atomically, and dispatches notifications.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True

    try:
        # 1. Resolve Tenant & Quota Validation
        user = db.query(User).filter(User.id == tenant_id).first()
        if not user:
            # Fallback to default admin if tenant_id not found
            user = db.query(User).filter(User.email == 'admin@bagustech.id').first()
            if not user:
                return ArticleGenerationResult(
                    success=False,
                    error=f"Tenant user '{tenant_id}' not found."
                )

        sub = user.subscription
        is_byok = bool(
            getattr(user, 'custom_gemini_key', None) or
            getattr(user, 'custom_openai_key', None) or
            getattr(user, 'custom_groq_key', None)
        )
        if sub and not is_byok and sub.article_credits_used >= sub.article_credits_limit:
            return ArticleGenerationResult(
                success=False,
                error=f"Kuota kredit artikel tenant telah habis ({sub.article_credits_used}/{sub.article_credits_limit})."
            )

        # 2. Resolve Target Blog
        blog = None
        if blog_id:
            blog = db.query(Blog).filter(Blog.id == blog_id, Blog.user_id == user.id).first()
        if not blog:
            blog = db.query(Blog).filter(Blog.user_id == user.id, Blog.is_active == 1).first()
        if not blog:
            blog = db.query(Blog).filter(Blog.user_id == user.id).first()
        if not blog:
            # Local fallback for admin onboarding
            blog = db.query(Blog).filter(Blog.is_active == 1).first() or db.query(Blog).first()

        if not blog:
            return ArticleGenerationResult(
                success=False,
                error=f"Tidak ada blog terdaftar untuk tenant '{user.email}'."
            )

        # 3. Resolve Target Keyword
        kw = None
        if keyword_id:
            kw = db.query(Keyword).filter(Keyword.id == keyword_id, Keyword.user_id == user.id).first()
        if not kw:
            kw = db.query(Keyword).filter(
                Keyword.user_id == user.id,
                Keyword.blog_id == blog.id,
                Keyword.status == 'planned'
            ).order_by(Keyword.id.asc()).first()
        if not kw:
            kw = db.query(Keyword).filter(
                Keyword.user_id == user.id,
                Keyword.status == 'planned'
            ).order_by(Keyword.id.asc()).first()

        if not kw:
            return ArticleGenerationResult(
                success=False,
                blog_name=blog.name,
                error="Tidak ada keyword berstatus 'planned' yang tersedia."
            )

        # 4. Construct Prompt (Tenant isolated with fallback to system defaults)
        master_prompt = ""
        if user and getattr(user, 'custom_prompt', None):
            master_prompt = user.custom_prompt
        elif os.path.exists(SEO_PROMPT_PATH):
            with open(SEO_PROMPT_PATH, "r", encoding="utf-8") as f:
                master_prompt = f.read()

        kb_notes = ""
        if user and getattr(user, 'custom_kb', None):
            kb_notes = user.custom_kb
        elif os.path.exists(SEO_KB_PATH):
            with open(SEO_KB_PATH, "r", encoding="utf-8") as f:
                kb_notes = f.read()

        combined_system_prompt = f"{master_prompt}\n\n---\nKNOWLEDGE BASE & GUIDELINES:\n{kb_notes}"
        user_prompt = f"""Tulis draf artikel blog mendalam untuk target keyword: "{kw.keyword}"
Search Intent: {kw.search_intent or 'Informational'}
Blog Name: {blog.name}
Blog URL: {blog.url or ''}

Patuhi seluruh Negative Constraints (dilarang basa-basi pembuka, dilarang heading H2 'Kesimpulan', dilarang filler words).
Wajib sertakan Hook Direct Answer 40-50 kata pertama, minimal 1 tabel komparasi, minimal 1 gambar Image SEO dengan <figure> dan deskriptif alt text, serta FAQPage JSON-LD Schema.
"""

        # 5. Invoke LLM via Seam Adapter
        custom_keys = {
            'gemini_key': getattr(user, 'custom_gemini_key', None),
            'openai_key': getattr(user, 'custom_openai_key', None),
            'groq_key': getattr(user, 'custom_groq_key', None)
        } if is_byok else None

        adapter = llm_adapter or get_llm_adapter()
        raw_article = adapter.generate_content(
            system_prompt=combined_system_prompt,
            user_prompt=user_prompt,
            keyword=kw.keyword,
            search_intent=kw.search_intent or 'Informational',
            blog_name=blog.name,
            blog_url=blog.url or '',
            custom_keys=custom_keys
        )

        # 6. Sanitize Metadata & Inject Schema
        raw_title = raw_article.get('title', f"{kw.keyword.title()}: Panduan Lengkap")
        raw_meta = raw_article.get('meta_description', f"Panduan lengkap mengenai {kw.keyword}.")
        title, meta_desc = sanitize_article_metadata(raw_title, raw_meta)
        content_html = raw_article.get('content_html', '')
        labels = raw_article.get('labels', 'Teknologi, SEO, Tutorial')

        try:
            content_html = inject_schema_if_missing(
                html_content=content_html,
                title=title,
                meta_description=meta_desc,
                url=blog.url,
                author_name=user.full_name or "Tim Editorial SEO"
            )
        except Exception as schema_err:
            logger.warning(f"Schema injection warning: {schema_err}")

        # 7. Atomic Storage Mutation & Publish Mode Handling
        kw.status = 'in_progress'

        pub_mode = getattr(blog, 'publish_mode', 'draft') or 'draft'
        initial_status = 'draft'
        blogger_post_id = None
        blogger_url = None

        if pub_mode in ['blogger_draft', 'published'] and (getattr(blog, 'encrypted_token', None) or getattr(blog, 'token_file', None)):
            try:
                from blogger_client import create_post
                is_draft = (pub_mode == 'blogger_draft')
                b_post = create_post(
                    title=title,
                    content_html=content_html,
                    labels=labels,
                    is_draft=is_draft,
                    token_file=blog.token_file,
                    blog_id=blog.id,
                    encrypted_token=blog.encrypted_token
                )
                if b_post and b_post.get('id'):
                    blogger_post_id = str(b_post.get('id'))
                    blogger_url = b_post.get('url')
                    initial_status = 'published' if pub_mode == 'published' else 'blogger_draft'
            except Exception as blog_err:
                logger.warning(f"Could not sync with Blogger on generation: {blog_err}")

        article = Article(
            user_id=user.id,
            blog_id=blog.id,
            title=title,
            target_keyword=kw.keyword,
            meta_description=meta_desc,
            content_html=content_html,
            labels=labels,
            status=initial_status,
            blogger_post_id=blogger_post_id,
            blogger_url=blogger_url
        )
        db.add(article)

        if sub and not is_byok:
            sub.article_credits_used += 1

        db.commit()
        db.refresh(article)

        # Audit Logging
        record_audit_log(
            db=db,
            event_type="article.generated",
            user_id=user.id,
            entity_id=str(article.id),
            metadata={
                "title": title,
                "keyword": kw.keyword,
                "status": initial_status,
                "byok": is_byok
            }
        )

        remaining_credits = (sub.article_credits_limit - sub.article_credits_used) if sub else None

        # 8. Dispatch Real-Time Notifications
        try:
            dispatch_notification(
                user_id=user.id,
                event_type="draft_created",
                data={
                    "title": title,
                    "keyword": kw.keyword,
                    "blog_name": blog.name,
                    "article_id": article.id
                },
                db_session=db
            )

            if sub and remaining_credits is not None and remaining_credits <= 1:
                dispatch_notification(
                    user_id=user.id,
                    event_type="credit_low",
                    data={"remaining_credits": remaining_credits},
                    db_session=db
                )
        except Exception as notify_err:
            logger.warning(f"Notification dispatch error: {notify_err}")

        return ArticleGenerationResult(
            success=True,
            article_id=article.id,
            title=title,
            keyword=kw.keyword,
            blog_name=blog.name,
            status="draft",
            credits_remaining=remaining_credits
        )

    except Exception as e:
        if db:
            db.rollback()
        logger.error(f"Article generation failed: {e}")
        return ArticleGenerationResult(
            success=False,
            error=str(e)
        )
    finally:
        if owns_db:
            db.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Article Content Generator")
    parser.add_argument('--user-id', type=str, help="Tenant User ID")
    parser.add_argument('--blog-id', type=str, help="Blog ID")
    parser.add_argument('--keyword-id', type=int, help="Keyword ID")
    args = parser.parse_args()

    result = generate_article(
        tenant_id=args.user_id,
        blog_id=args.blog_id,
        keyword_id=args.keyword_id
    )
    if result.success:
        print(f"SUCCESS: Article ID {result.article_id} created for '{result.keyword}'.")
        print(f"Title: {result.title}")
    else:
        print(f"ERROR: {result.error}")
        sys.exit(1)

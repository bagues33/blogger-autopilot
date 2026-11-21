"""
Keyword Management Router for Blogger Auto-Pilot SaaS
Handles keyword retrieval, manual addition, bulk imports, auto-generation, and deletion
with full multi-tenant RBAC and granular blog assignment scoping.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_saas_db
from src.models.models import User, Blog as SaasBlog, Keyword as SaasKeyword
from src.core.dependencies import get_session_user, get_current_user, get_optional_user
from src.core.rbac import (
    get_accessible_blogs,
    has_blog_permission,
    get_blog_effective_owner,
    Permission
)
from src.services.audit import record_audit_log

router = APIRouter(tags=['Keywords'])

# --- Request Schemas ---

class KeywordAddReq(BaseModel):
    keyword: str
    search_intent: Optional[str] = 'Informational'
    blog_id: Optional[str] = None

class KeywordBulkAddReq(BaseModel):
    keywords_text: str
    search_intent: Optional[str] = 'Informational'
    blog_id: Optional[str] = None

class KeywordSuggestReq(BaseModel):
    niche_seed: str
    blog_id: Optional[str] = None

# --- Helper ---

def _resolve_target_blog(user: User, blog_id: Optional[str], db: Session, required_perm: Permission = Permission.ARTICLE_CREATE) -> SaasBlog:
    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        raise HTTPException(status_code=400, detail="Silakan tambahkan atau hubungkan blog terlebih dahulu.")

    if blog_id:
        target = next((b for b in accessible_blogs if b.id == blog_id), None)
        if not target:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki izin akses ke blog ini.")
    else:
        target = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])

    if not has_blog_permission(user, target, required_perm, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk mengelola keyword pada blog ini.")

    return target

# --- Endpoints ---

@router.get('/api/keywords')
def api_get_keywords(request: Request, blog_id: Optional[str] = None, user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_saas_db)):
    if not user:
        return []

    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        return []

    accessible_ids = [b.id for b in accessible_blogs]

    if blog_id:
        if blog_id not in accessible_ids:
            return []
        target_blog_id = blog_id
    else:
        active_b = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])
        target_blog_id = active_b.id

    kws = db.query(SaasKeyword).filter(
        SaasKeyword.blog_id == target_blog_id
    ).order_by(SaasKeyword.created_at.desc()).all()

    return [
        {
            'id': k.id,
            'keyword': k.keyword,
            'search_intent': k.search_intent,
            'status': k.status,
            'blog_id': k.blog_id
        }
        for k in kws
    ]

@router.post('/api/keywords/add')
def api_add_keyword(req: KeywordAddReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = _resolve_target_blog(user, req.blog_id, db, Permission.ARTICLE_CREATE)
    blog_owner = get_blog_effective_owner(blog, db) or user

    clean_kw = req.keyword.strip()
    if not clean_kw:
        raise HTTPException(status_code=400, detail="Keyword tidak boleh kosong.")

    existing = db.query(SaasKeyword).filter(
        SaasKeyword.blog_id == blog.id,
        SaasKeyword.keyword == clean_kw
    ).first()

    if not existing:
        sk = SaasKeyword(
            user_id=blog_owner.id,
            blog_id=blog.id,
            keyword=clean_kw,
            search_intent=req.search_intent or 'Informational',
            status='planned'
        )
        db.add(sk)
        db.commit()

    return {'success': True}

@router.post('/api/keywords/{kw_id}/delete')
def api_delete_keyword(kw_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    kw = db.query(SaasKeyword).filter(SaasKeyword.id == kw_id).first()
    if not kw:
        return {'success': True}

    blog = kw.blog
    if blog and not has_blog_permission(user, blog, Permission.ARTICLE_EDIT, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk menghapus keyword ini.")

    db.delete(kw)
    db.commit()
    return {'success': True}

@router.post('/api/keywords/auto-generate')
def api_auto_generate_keywords(blog_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = _resolve_target_blog(user, blog_id, db, Permission.ARTICLE_CREATE)
    blog_owner = get_blog_effective_owner(blog, db) or user

    high_quality_keywords = [
        ('rekomendasi ai coding assistant gratis untuk vs code', 'Informational'),
        ('cara integrasi api gemini di web modern', 'Informational'),
        ('tips prompt engineering untuk software engineer', 'Informational'),
        ('perbandingan claude dan chatgpt untuk programming', 'Commercial'),
        ('panduan optimasi loading website skor 100', 'Informational'),
        ('tools ai produktivitas terbaik untuk freelancer tech', 'Informational')
    ]
    added = 0
    for kw, intent in high_quality_keywords:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.blog_id == blog.id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=blog_owner.id,
                blog_id=blog.id,
                keyword=kw,
                search_intent=intent,
                status='planned'
            )
            db.add(sk)
            added += 1
    db.commit()

    return {'success': True, 'added_count': added}

@router.post('/api/keywords/bulk-add')
def api_bulk_add_keywords(req: KeywordBulkAddReq, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = _resolve_target_blog(user, req.blog_id, db, Permission.ARTICLE_CREATE)
    blog_owner = get_blog_effective_owner(blog, db) or user

    lines = [line.strip() for line in req.keywords_text.splitlines() if line.strip()]
    added = 0
    for kw in lines:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.blog_id == blog.id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=blog_owner.id,
                blog_id=blog.id,
                keyword=kw,
                search_intent=req.search_intent or 'Informational',
                status='planned'
            )
            db.add(sk)
            added += 1
    db.commit()

    return {'success': True, 'added_count': added, 'total_submitted': len(lines)}

def fetch_ai_keywords_from_llm(niche: str, user) -> list:
    """
    Dynamically queries LLM (Gemini, OpenAI, Groq, or tenant BYOK) for search-intent clustered keywords.
    """
    gemini_key = getattr(user, 'custom_gemini_key', None) or os.environ.get('GEMINI_API_KEY')
    openai_key = getattr(user, 'custom_openai_key', None) or os.environ.get('OPENAI_API_KEY')
    groq_key = getattr(user, 'custom_groq_key', None) or os.environ.get('GROQ_API_KEY')

    prompt = (
        f"Anda adalah konsultan SEO Google. Berikan 10 target keyword spesifik dan potensial dalam bahasa Indonesia untuk niche: '{niche}'. "
        f"Klasifikasikan masing-masing ke search_intent: 'Informational', 'Commercial', atau 'Transactional'. "
        f"Format WAJIB JSON murni array of objects tanpa markdown: "
        f"[{{\"keyword\": \"...\", \"search_intent\": \"Informational\"}}]"
    )

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json"}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                text = res['candidates'][0]['content']['parts'][0]['text']
                items = json.loads(text.strip())
                if isinstance(items, list) and len(items) > 0:
                    return [(it.get('keyword', '').strip(), it.get('search_intent', 'Informational')) for it in items if it.get('keyword')]
        except Exception:
            pass

    target_key = openai_key or groq_key
    target_url = "https://api.openai.com/v1/chat/completions" if openai_key else "https://api.groq.com/openai/v1/chat/completions"
    target_model = "gpt-4o-mini" if openai_key else "llama-3.3-70b-versatile"
    if target_key:
        try:
            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": "You are a professional SEO keyword research tool. Respond only in pure JSON."},
                    {"role": "user", "content": prompt}
                ]
            }
            if openai_key:
                payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(
                target_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {target_key}'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                raw = res['choices'][0]['message']['content']
                parsed = json.loads(raw.strip())
                items = parsed if isinstance(parsed, list) else parsed.get('keywords', [])
                if isinstance(items, list) and len(items) > 0:
                    return [(it.get('keyword', '').strip(), it.get('search_intent', 'Informational')) for it in items if it.get('keyword')]
        except Exception:
            pass

    return []

@router.post('/api/keywords/ai-suggest')
def api_suggest_keywords(req: KeywordSuggestReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = _resolve_target_blog(user, req.blog_id, db, Permission.ARTICLE_CREATE)
    blog_owner = get_blog_effective_owner(blog, db) or user

    niche = req.niche_seed.strip()

    # 1. Attempt dynamic LLM generation (using blog owner's BYOK if available)
    llm_keywords = fetch_ai_keywords_from_llm(niche, blog_owner)
    used_llm = bool(llm_keywords)

    if used_llm:
        generated_keywords = llm_keywords
    else:
        generated_keywords = [
            (f"cara mudah {niche} untuk pemula", "Informational"),
            (f"panduan lengkap {niche} terbaru 2026", "Informational"),
            (f"rekomendasi tools terbaik untuk {niche}", "Commercial"),
            (f"tips dan trik optimasi {niche} agar maksimal", "Informational"),
            (f"perbandingan metode {niche} gratis vs berbayar", "Commercial"),
            (f"kesalahan umum dalam {niche} yang wajib dihindari", "Informational"),
            (f"studi kasus keberhasilan penerapan {niche}", "Informational"),
            (f"biaya dan estimasi modal untuk {niche}", "Commercial")
        ]

    added = 0
    for kw, intent in generated_keywords:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.blog_id == blog.id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=blog_owner.id,
                blog_id=blog.id,
                keyword=kw,
                search_intent=intent,
                status='planned'
            )
            db.add(sk)
            added += 1
    db.commit()

    record_audit_log(
        db=db,
        event_type="keywords.suggested",
        user_id=user.id,
        entity_id=blog.id,
        metadata={"niche": niche, "added_count": added, "dynamic_ai": used_llm},
        ip_address=request.client.host if request.client else None
    )

    return {
        'success': True,
        'added_count': added,
        'keywords': [k[0] for k in generated_keywords],
        'dynamic_ai': used_llm
    }

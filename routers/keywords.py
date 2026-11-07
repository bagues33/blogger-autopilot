"""
Keyword Management Router for Blogger Auto-Pilot SaaS
Handles keyword retrieval, manual addition, bulk imports, auto-generation, and deletion.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import Blog as SaasBlog, Keyword as SaasKeyword
from dependencies import get_session_user, get_or_create_default_admin
from audit_service import record_audit_log

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

# --- Endpoints ---

@router.get('/api/keywords')
def api_get_keywords(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if not blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        blog_id = active_b.id if active_b else '2940095957137948013'

    kws = db.query(SaasKeyword).filter(SaasKeyword.user_id == user.id, SaasKeyword.blog_id == blog_id).order_by(SaasKeyword.created_at.desc()).all()

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
def api_add_keyword(req: KeywordAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    existing = db.query(SaasKeyword).filter(
        SaasKeyword.user_id == user.id,
        SaasKeyword.blog_id == b_id,
        SaasKeyword.keyword == req.keyword.strip()
    ).first()

    if not existing:
        sk = SaasKeyword(
            user_id=user.id,
            blog_id=b_id,
            keyword=req.keyword.strip(),
            search_intent=req.search_intent or 'Informational',
            status='planned'
        )
        db.add(sk)
        db.commit()

    return {'success': True}

@router.post('/api/keywords/{kw_id}/delete')
def api_delete_keyword(kw_id: int, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    kw = db.query(SaasKeyword).filter(SaasKeyword.id == kw_id, SaasKeyword.user_id == user.id).first()
    if kw:
        db.delete(kw)
        db.commit()

    return {'success': True}

@router.post('/api/keywords/auto-generate')
def api_auto_generate_keywords(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    high_quality_keywords = [
        ('rekomendasi ai coding assistant gratis untuk vs code', 'Informational'),
        ('cara integrasi api gemini di web modern', 'Informational'),
        ('tips prompt engineering untuk software engineer', 'Informational'),
        ('perbandingan claude dan chatgpt untuk programming', 'Commercial'),
        ('panduan optimasi loading website skor 100', 'Informational'),
        ('tools ai produktivitas terbaik untuk freelancer tech', 'Informational')
    ]
    for kw, intent in high_quality_keywords:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.user_id == user.id,
            SaasKeyword.blog_id == b_id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=user.id,
                blog_id=b_id,
                keyword=kw,
                search_intent=intent,
                status='planned'
            )
            db.add(sk)
    db.commit()

    return {'success': True}

@router.post('/api/keywords/bulk-add')
def api_bulk_add_keywords(req: KeywordBulkAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    lines = [line.strip() for line in req.keywords_text.splitlines() if line.strip()]
    added = 0
    for kw in lines:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.user_id == user.id,
            SaasKeyword.blog_id == b_id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=user.id,
                blog_id=b_id,
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
def api_suggest_keywords(req: KeywordSuggestReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    niche = req.niche_seed.strip()
    
    # 1. Attempt dynamic LLM generation
    llm_keywords = fetch_ai_keywords_from_llm(niche, user)
    used_llm = bool(llm_keywords)

    if used_llm:
        generated_keywords = llm_keywords
    else:
        # Fallback to enhanced high-intent niche templates
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
            SaasKeyword.user_id == user.id,
            SaasKeyword.blog_id == b_id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=user.id,
                blog_id=b_id,
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
        metadata={"niche": niche, "added_count": added, "dynamic_ai": used_llm},
        ip_address=request.client.host if request.client else None
    )

    return {
        'success': True,
        'added_count': added,
        'keywords': [k[0] for k in generated_keywords],
        'dynamic_ai': used_llm
    }

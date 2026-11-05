"""
Keyword Management Router for Blogger Auto-Pilot SaaS
Handles keyword retrieval, manual addition, bulk imports, auto-generation, and deletion.
"""

from typing import Optional
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import Blog as SaasBlog, Keyword as SaasKeyword
from dependencies import get_session_user, get_or_create_default_admin

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

@router.post('/api/keywords/ai-suggest')
def api_suggest_keywords(req: KeywordSuggestReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    niche = req.niche_seed.strip()
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

    return {'success': True, 'added_count': added, 'keywords': [k[0] for k in generated_keywords]}

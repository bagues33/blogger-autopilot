"""
Article Management Router for Blogger Auto-Pilot SaaS
Handles article listing, saving with Schema JSON-LD injection, publishing to Blogger, deletion,
on-demand article generation, and image uploads.
"""

import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import Blog as SaasBlog, Article as SaasArticle, Keyword as SaasKeyword
from blogger_client import create_post, update_post
from image_service import process_and_upload_image
from schema_builder import inject_schema_if_missing
from notification_service import dispatch_notification
from content_generator import generate_article
from dependencies import get_session_user, get_or_create_default_admin, BASE_DIR

router = APIRouter(tags=['Articles'])

# --- Request Schemas ---

class ArticleSaveReq(BaseModel):
    id: Optional[int] = None
    title: str
    target_keyword: Optional[str] = None
    meta_description: Optional[str] = None
    content_html: str
    labels: Optional[str] = None
    blog_id: Optional[str] = None

class ArticlePublishReq(BaseModel):
    is_draft: Optional[bool] = False

class ArticleStatusReq(BaseModel):
    status: str

# --- Endpoints ---

@router.get('/api/articles')
def api_get_articles(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    if not blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        if not active_b:
            active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).first()
        blog_id = active_b.id if active_b else '2940095957137948013'

    arts = db.query(SaasArticle).filter(SaasArticle.user_id == user.id, SaasArticle.blog_id == blog_id).order_by(SaasArticle.created_at.desc()).all()

    return [
        {
            'id': a.id,
            'title': a.title,
            'target_keyword': a.target_keyword,
            'meta_description': a.meta_description,
            'content_html': a.content_html,
            'labels': a.labels,
            'status': a.status,
            'blogger_post_id': a.blogger_post_id,
            'blogger_url': a.blogger_url,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'updated_at': a.updated_at.isoformat() if a.updated_at else None,
            'blog_id': a.blog_id
        }
        for a in arts
    ]

@router.post('/api/articles/save')
def api_save_article(req: ArticleSaveReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    target_blog_id = req.blog_id
    if not target_blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        target_blog_id = active_b.id if active_b else '2940095957137948013'

    # Auto-inject Google E-E-A-T Schema JSON-LD if missing
    try:
        final_content = inject_schema_if_missing(
            html_content=req.content_html,
            title=req.title,
            meta_description=req.meta_description,
            author_name=user.full_name or "Tim Editorial SEO"
        )
    except Exception:
        final_content = req.content_html

    if req.id:
        art = db.query(SaasArticle).filter(SaasArticle.id == req.id, SaasArticle.user_id == user.id).first()
        if art:
            art.title = req.title
            art.target_keyword = req.target_keyword
            art.meta_description = req.meta_description
            art.content_html = final_content
            art.labels = req.labels
            from datetime import datetime, timezone
            art.updated_at = datetime.now(timezone.utc)
    else:
        art = SaasArticle(
            user_id=user.id,
            blog_id=target_blog_id,
            title=req.title,
            target_keyword=req.target_keyword,
            meta_description=req.meta_description,
            content_html=final_content,
            labels=req.labels,
            status='draft'
        )
        db.add(art)

    if req.target_keyword:
        kw = db.query(SaasKeyword).filter(
            SaasKeyword.user_id == user.id,
            SaasKeyword.keyword == req.target_keyword.strip(),
            SaasKeyword.status == 'planned'
        ).first()
        if kw:
            kw.status = 'in_progress'

    db.commit()

    return {'success': True}

@router.post('/api/articles/{article_id}/publish')
def api_publish_article(article_id: int, request: Request, is_draft: Optional[bool] = None, req: Optional[ArticlePublishReq] = None, db: Session = Depends(get_saas_db)):
    target_draft = False
    if req is not None and req.is_draft is not None:
        target_draft = req.is_draft
    elif is_draft is not None:
        target_draft = is_draft

    user = get_session_user(request, db) or get_or_create_default_admin(db)
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id, SaasArticle.user_id == user.id).first()
    
    if not art:
        raise HTTPException(status_code=404, detail='Article not found')

    art_title = art.title
    art_content = art.content_html
    art_labels = art.labels
    art_keyword = art.target_keyword
    art_blog_id = art.blog_id
    existing_post_id = art.blogger_post_id
    art_url = art.blogger_url

    blog = db.query(SaasBlog).filter(SaasBlog.id == art_blog_id, SaasBlog.user_id == user.id).first()
    encrypted_token = blog.encrypted_token if blog else None
    token_file = blog.token_file if blog else None

    # Auto-inject Google E-E-A-T Schema JSON-LD before sending to Blogger
    try:
        art_content = inject_schema_if_missing(
            html_content=art_content,
            title=art_title,
            meta_description=art.meta_description if art else None,
            url=art_url,
            author_name=user.full_name or "Tim Editorial SEO"
        )
    except Exception:
        pass

    try:
        if existing_post_id:
            post = update_post(
                post_id=existing_post_id,
                title=art_title,
                content_html=art_content,
                labels=art_labels,
                is_draft=target_draft,
                token_file=token_file,
                blog_id=art_blog_id,
                encrypted_token=encrypted_token
            )
            blogger_post_id = existing_post_id
            blogger_url = post.get('url') or art_url
            action = 'updated'
        else:
            post = create_post(
                title=art_title,
                content_html=art_content,
                labels=art_labels,
                is_draft=target_draft,
                token_file=token_file,
                blog_id=art_blog_id,
                encrypted_token=encrypted_token
            )
            blogger_post_id = post.get('id')
            blogger_url = post.get('url')
            action = 'created'

        new_status = 'blogger_draft' if target_draft else 'published'
        
        art.status = new_status
        art.blogger_post_id = blogger_post_id
        art.blogger_url = blogger_url
        if art_keyword:
            kw = db.query(SaasKeyword).filter(
                SaasKeyword.user_id == user.id,
                SaasKeyword.keyword == art_keyword.strip()
            ).first()
            if kw:
                kw.status = 'in_progress' if target_draft else 'used'
        db.commit()

        # Dispatch notification
        try:
            dispatch_notification(
                user_id=user.id,
                event_type="article_published" if not target_draft else "draft_created",
                data={
                    "title": art_title,
                    "keyword": art_keyword or "-",
                    "blog_name": blog.name if blog else "Blog",
                    "url": blogger_url or ""
                },
                db_session=db
            )
        except Exception as notify_err:
            print(f"[NOTIFICATION] Warning: {notify_err}")

        return {
            'success': True,
            'action': action,
            'is_draft': target_draft,
            'status': new_status,
            'url': blogger_url,
            'post_id': blogger_post_id
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.post('/api/articles/{article_id}/delete')
def api_delete_article(article_id: int, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id, SaasArticle.user_id == user.id).first()
    if art:
        db.delete(art)
        db.commit()

    return {'success': True}

@router.post('/api/articles/{article_id}/status')
def api_update_article_status(article_id: int, req: ArticleStatusReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id, SaasArticle.user_id == user.id).first()
    if not art:
        raise HTTPException(status_code=404, detail='Artikel tidak ditemukan.')

    allowed = ['draft', 'pending_review', 'approved', 'blogger_draft', 'published']
    target_status = req.status.lower().strip()
    if target_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status tidak valid. Pilihan: {', '.join(allowed)}")

    art.status = target_status
    art.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        'success': True,
        'status': art.status,
        'message': f"Status artikel berhasil diubah ke '{art.status}'"
    }

@router.post('/api/agent/generate-now')
def api_agent_generate_now(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    # Check tenant quota
    if user and user.subscription:
        sub = user.subscription
        if sub.article_credits_used >= sub.article_credits_limit:
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': f"Kuota kredit artikel Anda telah habis ({sub.article_credits_used}/{sub.article_credits_limit}). Silakan upgrade ke paket Starter atau Pro di dashboard."
                }
            )

    # Check planned keywords availability
    kw_count = db.query(SaasKeyword).filter(
        SaasKeyword.user_id == user.id,
        SaasKeyword.status == 'planned'
    ).count()
    if kw_count == 0:
        return JSONResponse(
            status_code=400,
            content={
                'success': False,
                'error': "Bank keyword Anda masih kosong. Tambahkan minimal 1 keyword dengan status 'planned' atau gunakan fitur 'Ide Niche' terlebih dahulu."
            }
        )

    background_tasks.add_task(generate_article, tenant_id=user.id)
    return {'success': True, 'message': 'Agent dimulai di background'}

@router.post('/api/images/upload')
async def api_upload_image(request: Request, file: UploadFile = File(...), db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
            return JSONResponse({'success': False, 'error': 'Format file harus JPG, PNG, WEBP, atau GIF'}, status_code=400)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            return JSONResponse({'success': False, 'error': 'Ukuran file gambar maksimal 10MB.'}, status_code=400)
        res = process_and_upload_image(content, file.filename)
        return res
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

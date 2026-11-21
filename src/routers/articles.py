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

from src.core.database import get_saas_db
from src.models.models import Blog as SaasBlog, Article as SaasArticle, Keyword as SaasKeyword
from src.services.blogger import create_post, update_post
from src.services.images import process_and_upload_image
from src.services.schema import inject_schema_if_missing
from src.services.notifications import dispatch_notification
from src.services.content_generator import generate_article
from src.services.audit import record_audit_log
from src.services.indexing import ping_websub_for_blog
from src.core.rate_limiter import check_rate_limit
from src.core.rbac import (
    get_accessible_blogs,
    get_user_role_for_blog,
    has_blog_permission,
    get_blog_effective_owner,
    Permission
)
from src.core.dependencies import get_session_user, get_current_user, get_optional_user, check_feature_access, BASE_DIR

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
def api_get_articles(request: Request, blog_id: Optional[str] = None, user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_saas_db)):
    if not user:
        return []

    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        return []

    accessible_blog_ids = [b.id for b in accessible_blogs]

    query = db.query(SaasArticle).filter(SaasArticle.blog_id.in_(accessible_blog_ids))
    if blog_id:
        if blog_id not in accessible_blog_ids:
            return []
        query = query.filter(SaasArticle.blog_id == blog_id)
    else:
        active_b = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])
        query = query.filter(SaasArticle.blog_id == active_b.id)

    arts = query.order_by(SaasArticle.created_at.desc()).all()
    blogs_map = {b.id: b for b in accessible_blogs}

    result = []
    for a in arts:
        blog_obj = blogs_map.get(a.blog_id) or a.blog
        role = get_user_role_for_blog(user, blog_obj, db)
        author_name = (a.author.full_name or a.author.email) if a.author else None

        result.append({
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
            'blog_id': a.blog_id,
            'author_id': a.author_id,
            'author_name': author_name,
            'role': role,
            'can_edit': has_blog_permission(user, blog_obj, Permission.ARTICLE_EDIT, db),
            'can_review': has_blog_permission(user, blog_obj, Permission.ARTICLE_REVIEW, db),
            'can_approve': has_blog_permission(user, blog_obj, Permission.ARTICLE_APPROVE, db),
            'can_publish': has_blog_permission(user, blog_obj, Permission.ARTICLE_PUBLISH, db),
        })

    return result

@router.post('/api/articles')
@router.post('/api/articles/save')
def api_save_article(req: ArticleSaveReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        raise HTTPException(status_code=400, detail="Silakan tambahkan atau hubungkan blog terlebih dahulu.")

    target_blog_id = req.blog_id
    if not target_blog_id:
        active_b = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])
        target_blog_id = active_b.id

    blog = next((b for b in accessible_blogs if b.id == target_blog_id), None)
    if not blog:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin akses ke blog ini.")

    needed_perm = Permission.ARTICLE_EDIT if req.id else Permission.ARTICLE_CREATE
    if not has_blog_permission(user, blog, needed_perm, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk menyimpan artikel di blog ini.")

    blog_owner = get_blog_effective_owner(blog, db) or user

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
        art = db.query(SaasArticle).filter(SaasArticle.id == req.id).first()
        if art:
            if not has_blog_permission(user, art.blog, Permission.ARTICLE_EDIT, db):
                raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk mengedit artikel ini.")
            art.title = req.title
            art.target_keyword = req.target_keyword
            art.meta_description = req.meta_description
            art.content_html = final_content
            art.labels = req.labels
            art.updated_at = datetime.now(timezone.utc)
    else:
        art = SaasArticle(
            user_id=blog_owner.id,
            author_id=user.id,
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
            SaasKeyword.blog_id == target_blog_id,
            SaasKeyword.keyword == req.target_keyword.strip(),
            SaasKeyword.status == 'planned'
        ).first()
        if kw:
            kw.status = 'in_progress'

    db.commit()
    db.refresh(art)

    return {'success': True, 'id': art.id}

@router.post('/api/articles/{article_id}/publish')
def api_publish_article(article_id: int, request: Request, is_draft: Optional[bool] = None, req: Optional[ArticlePublishReq] = None, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    target_draft = False
    if req is not None and req.is_draft is not None:
        target_draft = req.is_draft
    elif is_draft is not None:
        target_draft = is_draft

    art = db.query(SaasArticle).filter(SaasArticle.id == article_id).first()
    if not art:
        raise HTTPException(status_code=404, detail='Article not found')

    blog = art.blog
    if not blog:
        raise HTTPException(status_code=404, detail='Blog not found')

    # RBAC Check: Writer cannot publish live directly
    if not target_draft:
        if not has_blog_permission(user, blog, Permission.ARTICLE_PUBLISH, db):
            raise HTTPException(
                status_code=403,
                detail="Penulis (Writer) tidak memiliki izin untuk mempublikasikan artikel secara langsung ke Blogger. Silakan ajukan draf untuk direview oleh Editor atau Owner."
            )
    else:
        # Kirim draft ke Blogger: butuh ARTICLE_PUBLISH atau ARTICLE_APPROVE
        if not has_blog_permission(user, blog, Permission.ARTICLE_PUBLISH, db) and not has_blog_permission(user, blog, Permission.ARTICLE_APPROVE, db):
            raise HTTPException(
                status_code=403,
                detail="Hanya Editor atau Owner yang dapat mengirim draf ke Blogger."
            )

    art_title = art.title
    art_content = art.content_html
    art_labels = art.labels
    art_keyword = art.target_keyword
    art_blog_id = art.blog_id
    existing_post_id = art.blogger_post_id
    art_url = art.blogger_url

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
                SaasKeyword.blog_id == art_blog_id,
                SaasKeyword.keyword == art_keyword.strip()
            ).first()
            if kw:
                kw.status = 'in_progress' if target_draft else 'used'
        db.commit()

        # Google WebSub Instant Indexing Ping on Live Publish
        websub_pinged = False
        if not target_draft and blog and blog.url:
            try:
                ping_res = ping_websub_for_blog(blog_url=blog.url, post_url=blogger_url)
                websub_pinged = bool(ping_res.get("success"))
                if websub_pinged:
                    record_audit_log(
                        db=db,
                        event_type="article.websub_pinged",
                        user_id=user.id,
                        entity_id=str(art.id),
                        metadata={"feed_url": ping_res.get("feed_url"), "post_url": blogger_url},
                        ip_address=request.client.host if request.client else None
                    )
            except Exception as idx_err:
                print(f"[INDEXING] Warning: {idx_err}")

        # Dispatch notification
        try:
            dispatch_notification(
                user_id=art.user_id,
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

        # Record Audit Log
        record_audit_log(
            db=db,
            event_type="article.published" if not target_draft else "article.draft_synced",
            user_id=user.id,
            entity_id=str(art.id),
            metadata={
                "title": art_title,
                "url": blogger_url,
                "post_id": blogger_post_id,
                "is_draft": target_draft,
                "websub_pinged": websub_pinged
            },
            ip_address=request.client.host if request.client else None
        )

        return {
            'success': True,
            'action': action,
            'is_draft': target_draft,
            'status': new_status,
            'url': blogger_url,
            'post_id': blogger_post_id,
            'websub_pinged': websub_pinged
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.post('/api/articles/{article_id}/delete')
def api_delete_article(article_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id).first()
    if art:
        if not has_blog_permission(user, art.blog, Permission.ARTICLE_DELETE, db):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk menghapus artikel ini.")
        art_title = art.title
        db.delete(art)
        db.commit()
        record_audit_log(
            db=db,
            event_type="article.deleted",
            user_id=user.id,
            entity_id=str(article_id),
            metadata={"title": art_title},
            ip_address=request.client.host if request.client else None
        )

    return {'success': True}

@router.post('/api/articles/{article_id}/status')
def api_update_article_status(article_id: int, req: ArticleStatusReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id).first()
    if not art:
        raise HTTPException(status_code=404, detail='Artikel tidak ditemukan.')

    allowed = ['draft', 'pending_review', 'approved', 'blogger_draft', 'published']
    target_status = req.status.lower().strip()
    if target_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status tidak valid. Pilihan: {', '.join(allowed)}")

    if target_status == 'approved':
        if not has_blog_permission(user, art.blog, Permission.ARTICLE_APPROVE, db):
            raise HTTPException(status_code=403, detail="Hanya Editor atau Owner yang dapat menyetujui draf artikel.")
    elif target_status == 'pending_review':
        if not has_blog_permission(user, art.blog, Permission.ARTICLE_REVIEW, db):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk mengajukan review artikel.")

    old_status = art.status
    art.status = target_status
    art.updated_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_log(
        db=db,
        event_type=f"article.{target_status}",
        user_id=user.id,
        entity_id=str(art.id),
        metadata={
            "title": art.title,
            "old_status": old_status,
            "new_status": target_status
        },
        ip_address=request.client.host if request.client else None
    )

    return {
        'success': True,
        'status': art.status,
        'message': f"Status artikel berhasil diubah ke '{art.status}'"
    }

@router.post('/api/agent/generate-now')
def api_agent_generate_now(request: Request, background_tasks: BackgroundTasks, blog_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=10, window_seconds=60, endpoint_tag="generate")

    accessible_blogs = get_accessible_blogs(user, db)
    if not accessible_blogs:
        return JSONResponse(status_code=400, content={'success': False, 'error': 'Silakan hubungkan blog terlebih dahulu.'})

    if blog_id:
        active_b = next((b for b in accessible_blogs if b.id == blog_id), None)
        if not active_b:
            return JSONResponse(status_code=403, content={'success': False, 'error': 'Anda tidak memiliki izin akses ke blog ini.'})
    else:
        active_b = next((b for b in accessible_blogs if b.is_active == 1), accessible_blogs[0])

    if not has_blog_permission(user, active_b, Permission.ARTICLE_CREATE, db):
        return JSONResponse(status_code=403, content={'success': False, 'error': 'Anda tidak memiliki izin untuk memicu draf artikel di blog ini.'})

    # Shared Credit Pool: Resolve quota billing owner
    blog_owner = get_blog_effective_owner(active_b, db) or user

    # Check tenant quota (BYOK only exempts Pro, Agency, or Admin)
    can_byok = check_feature_access(blog_owner, 'byok')
    is_byok = can_byok and bool(
        getattr(blog_owner, 'custom_gemini_key', None) or
        getattr(blog_owner, 'custom_openai_key', None) or
        getattr(blog_owner, 'custom_groq_key', None)
    )
    if blog_owner and blog_owner.subscription and not is_byok:
        sub = blog_owner.subscription
        if sub.article_credits_used >= sub.article_credits_limit:
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': f"Kuota kredit artikel agensi bulan ini telah habis ({sub.article_credits_used}/{sub.article_credits_limit}). Silakan hubungi pemilik agensi untuk penambahan kuota."
                }
            )

    # Check planned keywords availability for this blog
    kw_count = db.query(SaasKeyword).filter(
        SaasKeyword.blog_id == active_b.id,
        SaasKeyword.status == 'planned'
    ).count()
    if kw_count == 0:
        # Fallback to any user keyword
        kw_count = db.query(SaasKeyword).filter(
            SaasKeyword.user_id == blog_owner.id,
            SaasKeyword.status == 'planned'
        ).count()
        if kw_count == 0:
            return JSONResponse(
                status_code=400,
                content={
                    'success': False,
                    'error': "Bank keyword blog ini masih kosong. Tambahkan minimal 1 keyword dengan status 'planned' atau gunakan fitur 'Ide Niche' terlebih dahulu."
                }
            )

    background_tasks.add_task(generate_article, tenant_id=blog_owner.id, blog_id=active_b.id, author_id=user.id)
    return {'success': True, 'message': 'Agent dimulai di background'}

@router.post('/api/images/upload')
async def api_upload_image(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
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

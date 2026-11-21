"""
Blog Management Router for Blogger Auto-Pilot SaaS
Handles blog CRUD operations, blog selection, autopilot configuration, token upload, and Blogger post syncing.
"""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_saas_db
from src.models.models import Blog as SaasBlog, Article as SaasArticle
from src.services.payment import PLAN_TIERS
from src.core.rate_limiter import check_rate_limit
from src.core.crypto import encrypt_token_data
from src.services.audit import record_audit_log
from src.core.rbac import (
    get_accessible_blogs,
    get_user_role_for_blog,
    has_blog_permission,
    Permission
)
from src.core.dependencies import (
    get_session_user,
    get_current_user,
    get_optional_user,
    check_feature_access,
    get_effective_plan_tier,
    BASE_DIR,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_TOKEN_FILE,
    CONFIG_FILE,
    TOKENS_DIR
)

router = APIRouter(tags=['Blogs'])

# --- Request Schemas ---

class BlogSelectReq(BaseModel):
    blog_id: str

class BlogAddReq(BaseModel):
    id: str
    name: str
    url: Optional[str] = ''
    account_name: Optional[str] = 'Akun Utama'
    token_file: Optional[str] = None
    encrypted_token: Optional[str] = None
    niche_description: Optional[str] = ''

class AutopilotSettingsReq(BaseModel):
    blog_id: str
    autopilot_enabled: bool
    publish_mode: str
    schedule: str

# --- Endpoints ---

@router.get('/api/blogs')
def api_get_blogs(user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_saas_db)):
    if not user:
        return []
    blogs = get_accessible_blogs(user, db)

    return [
        {
            'id': b.id,
            'name': b.name,
            'url': b.url,
            'account_name': b.account_name,
            'token_file': b.token_file,
            'niche_description': b.niche_description,
            'is_active': b.is_active,
            'role': get_user_role_for_blog(user, b, db),
            'is_owner': (b.user_id == user.id)
        }
        for b in blogs
    ]

@router.post('/api/blogs/select')
def api_select_blog(req: BlogSelectReq, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    accessible_blogs = get_accessible_blogs(user, db)
    selected_blog = next((b for b in accessible_blogs if b.id == req.blog_id), None)
    if not selected_blog:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke blog ini.")

    # Only mutate persisted is_active on blogs owned directly by the user
    # (prevents team members from overwriting the Agency Owner's active blog selection)
    if selected_blog.user_id == user.id:
        for b in accessible_blogs:
            if b.user_id == user.id:
                b.is_active = 1 if b.id == req.blog_id else 0
        db.commit()

    if user.email == 'admin@bagustech.id' and selected_blog and os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({
                    'blog_id': selected_blog.id,
                    'client_secret_file': selected_blog.client_secret_file or DEFAULT_CLIENT_SECRET,
                    'token_file': selected_blog.token_file
                }, f, indent=2)
        except Exception:
            pass

    return {'success': True}

@router.post('/api/blogs')
@router.post('/api/blogs/add')
def api_add_blog(req: BlogAddReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    plan = get_effective_plan_tier(user)
    max_blogs = PLAN_TIERS.get(plan, {}).get('blogs', 1)
    target_id = req.id.strip()

    existing = db.query(SaasBlog).filter(SaasBlog.id == target_id, SaasBlog.user_id == user.id).first()
    current_count = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).count()
    if not existing and current_count >= max_blogs:
        raise HTTPException(
            status_code=400,
            detail=f"Batas maksimal ({max_blogs} blog) untuk paket {plan.upper()} telah tercapai. Silakan upgrade paket langganan Anda."
        )

    # Prevent Cross-Tenant Token Path Hijack:
    # Non-admin users cannot point a blog to arbitrary server file paths or global token.json
    safe_token_file = None
    if user.role == 'admin' and req.token_file:
        safe_token_file = req.token_file

    safe_encrypted_token = req.encrypted_token if req.encrypted_token else None
    target_name = req.name.strip()
    target_url = req.url.strip() if req.url else ''
    target_account = req.account_name.strip() if req.account_name else 'Akun Google'
    target_niche = req.niche_description.strip() if req.niche_description else ''

    if existing:
        existing.name = target_name
        existing.url = target_url
        existing.account_name = target_account or 'Akun Google'
        if safe_token_file:
            existing.token_file = safe_token_file
        if safe_encrypted_token:
            existing.encrypted_token = safe_encrypted_token
        existing.niche_description = target_niche
    else:
        new_b = SaasBlog(
            id=target_id,
            user_id=user.id,
            name=target_name,
            url=target_url,
            account_name=target_account or 'Akun Google',
            token_file=safe_token_file,
            encrypted_token=safe_encrypted_token,
            client_secret_file=DEFAULT_CLIENT_SECRET,
            niche_description=target_niche,
            is_active=1 if current_count == 0 else 0
        )
        db.add(new_b)
    db.commit()

    record_audit_log(
        db=db,
        event_type="blog.connected",
        user_id=user.id,
        entity_id=target_id,
        metadata={"name": target_name, "url": target_url},
        ip_address=request.client.host if request and request.client else None
    )

    return {'success': True}

@router.post('/api/blogs/{blog_id}/delete')
def api_delete_blog(blog_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")

    if not has_blog_permission(user, blog, Permission.BLOG_DELETE, db):
        raise HTTPException(status_code=403, detail="Hanya pemilik blog yang dapat menghapus blog ini.")

    user_blog_count = db.query(SaasBlog).filter(SaasBlog.user_id == blog.user_id).count()
    if user_blog_count <= 1:
        return {'success': False, 'error': 'Tidak dapat menghapus blog satu-satunya.'}

    db.delete(blog)
    active = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
    if not active:
        first = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).first()
        if first:
            first.is_active = 1
    db.commit()

    return {'success': True}

@router.post('/api/blogs/upload-token')
async def api_upload_blog_token(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    content = await file.read()
    if len(content) > 100 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file token maksimal 100KB.")
    try:
        parsed = json.loads(content.decode('utf-8'))
        if not isinstance(parsed, dict) or not (parsed.get('refresh_token') or parsed.get('token')):
            raise ValueError("Missing OAuth token fields")
    except Exception:
        raise HTTPException(status_code=400, detail="File harus berupa JSON kredensial Google OAuth yang valid.")

    encrypted_blob = encrypt_token_data(parsed)
    return {
        'success': True,
        'encrypted_token': encrypted_blob,
        'filename': os.path.basename(file.filename or 'token.json')
    }

@router.post('/api/blogs/autopilot-settings')
def api_save_autopilot_settings(req: AutopilotSettingsReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if req.autopilot_enabled and not check_feature_access(user, 'autopilot'):
        raise HTTPException(
            status_code=403,
            detail="Fitur Autopilot Scheduler mandiri memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )
    blog = db.query(SaasBlog).filter(SaasBlog.id == req.blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")
    if not has_blog_permission(user, blog, Permission.BLOG_CONFIGURE, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin untuk mengonfigurasi autopilot blog ini.")

    # Persist in database
    blog.autopilot_enabled = bool(req.autopilot_enabled)
    blog.publish_mode = req.publish_mode
    blog.schedule_frequency = req.schedule
    db.commit()

    record_audit_log(
        db=db,
        event_type="blog.autopilot_updated",
        user_id=user.id,
        entity_id=blog.id,
        metadata={
            "blog_name": blog.name,
            "autopilot_enabled": blog.autopilot_enabled,
            "publish_mode": blog.publish_mode,
            "schedule": blog.schedule_frequency
        },
        ip_address=request.client.host if request.client else None
    )

    # Legacy file backup mirror
    settings_dir = os.path.join(BASE_DIR, 'settings')
    os.makedirs(settings_dir, exist_ok=True)
    settings_file = os.path.join(settings_dir, f"autopilot_{blog.id}.json")
    try:
        with open(settings_file, 'w') as f:
            json.dump({
                'blog_id': blog.id,
                'autopilot_enabled': req.autopilot_enabled,
                'publish_mode': req.publish_mode,
                'schedule': req.schedule,
                'user_id': user.id
            }, f, indent=2)
    except Exception:
        pass

    return {'success': True, 'message': 'Pengaturan autopilot berhasil disimpan.'}

@router.get('/api/blogs/{blog_id}/autopilot-settings')
def api_get_autopilot_settings(blog_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")
    if not has_blog_permission(user, blog, Permission.ARTICLE_VIEW, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin akses ke pengaturan blog ini.")

    return {
        'blog_id': blog.id,
        'autopilot_enabled': bool(blog.autopilot_enabled),
        'publish_mode': blog.publish_mode or 'blogger_draft',
        'schedule': blog.schedule_frequency or 'daily',
        'last_run_at': blog.last_run_at.isoformat() if blog.last_run_at else None
    }

@router.post('/api/blogs/{blog_id}/sync-blogger-posts')
def api_sync_blogger_posts(blog_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=10, window_seconds=60, endpoint_tag="sync")
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")
    if not has_blog_permission(user, blog, Permission.ARTICLE_VIEW, db):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin akses ke blog ini.")

    encrypted_token = blog.encrypted_token
    token_file = blog.token_file

    try:
        from src.services.blogger import fetch_blogger_posts_sync
        blogger_items = fetch_blogger_posts_sync(
            token_file=token_file,
            blog_id=blog.id,
            encrypted_token=encrypted_token,
            max_results=50,
            status_list=['LIVE', 'DRAFT']
        )
    except Exception as e:
        return {'success': False, 'error': f"Gagal mengambil postingan dari Blogger: {str(e)}"}

    updated_count = 0
    imported_count = 0

    existing_arts = db.query(SaasArticle).filter(
        SaasArticle.blog_id == blog.id
    ).all()

    by_post_id = {str(a.blogger_post_id): a for a in existing_arts if a.blogger_post_id}
    by_title = {a.title.strip().lower(): a for a in existing_arts if a.title}

    for item in blogger_items:
        p_id = str(item.get('id', ''))
        p_title = item.get('title', '').strip()
        p_status = item.get('status', 'LIVE').upper()
        p_url = item.get('url', '')
        p_labels = ', '.join(item.get('labels', [])) if item.get('labels') else ''
        p_content = item.get('content', '')

        local_status = 'published' if p_status == 'LIVE' else 'blogger_draft'

        art = by_post_id.get(p_id) or by_title.get(p_title.lower())
        if art:
            changed = False
            if art.status != local_status:
                art.status = local_status
                changed = True
            if not art.blogger_post_id or art.blogger_post_id != p_id:
                art.blogger_post_id = p_id
                changed = True
            if p_url and art.blogger_url != p_url:
                art.blogger_url = p_url
                changed = True
            if changed:
                art.updated_at = datetime.now(timezone.utc)
                updated_count += 1
        else:
            new_art = SaasArticle(
                user_id=user.id,
                blog_id=blog.id,
                title=p_title or 'Postingan Blogger',
                content_html=p_content or '<p></p>',
                labels=p_labels,
                status=local_status,
                blogger_post_id=p_id,
                blogger_url=p_url
            )
            db.add(new_art)
            imported_count += 1

    db.commit()

    return {
        'success': True,
        'message': f"Sinkronisasi berhasil! {updated_count} artikel diperbarui, {imported_count} postingan baru diimpor dari Blogger.",
        'updated_count': updated_count,
        'imported_count': imported_count,
        'total_blogger_posts': len(blogger_items)
    }

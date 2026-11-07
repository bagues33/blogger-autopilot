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

from db_saas import get_saas_db
from models_saas import Blog as SaasBlog, Article as SaasArticle
from dependencies import (
    get_session_user,
    get_or_create_default_admin,
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
    niche_description: Optional[str] = ''

class AutopilotSettingsReq(BaseModel):
    blog_id: str
    autopilot_enabled: bool
    publish_mode: str
    schedule: str

# --- Endpoints ---

@router.get('/api/blogs')
def api_get_blogs(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blogs = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).order_by(SaasBlog.created_at.asc()).all()

    return [
        {
            'id': b.id,
            'name': b.name,
            'url': b.url,
            'account_name': b.account_name,
            'token_file': b.token_file,
            'niche_description': b.niche_description,
            'is_active': b.is_active
        }
        for b in blogs
    ]

@router.post('/api/blogs/select')
def api_select_blog(req: BlogSelectReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    user_blogs = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).all()
    selected_blog = None
    for b in user_blogs:
        b.is_active = 1 if b.id == req.blog_id else 0
        if b.id == req.blog_id:
            selected_blog = b
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

@router.post('/api/blogs/add')
def api_add_blog(req: BlogAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    plan = user.subscription.plan_tier if user.subscription else 'free'
    max_blogs = {'free': 1, 'starter': 3, 'pro': 10, 'agency': 50}.get(plan, 1)
    current_count = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).count()
    if current_count >= max_blogs:
        raise HTTPException(
            status_code=400,
            detail=f"Batas maksimal ({max_blogs} blog) untuk paket {plan.upper()} telah tercapai. Silakan upgrade paket langganan Anda."
        )

    token = req.token_file or DEFAULT_TOKEN_FILE
    
    existing = db.query(SaasBlog).filter(SaasBlog.id == req.id.strip(), SaasBlog.user_id == user.id).first()
    if existing:
        existing.name = req.name.strip()
        existing.url = req.url.strip()
        existing.account_name = req.account_name.strip() or 'Akun Google'
        existing.token_file = token
        existing.niche_description = req.niche_description.strip()
    else:
        new_b = SaasBlog(
            id=req.id.strip(),
            user_id=user.id,
            name=req.name.strip(),
            url=req.url.strip(),
            account_name=req.account_name.strip() or 'Akun Google',
            token_file=token,
            client_secret_file=DEFAULT_CLIENT_SECRET,
            niche_description=req.niche_description.strip(),
            is_active=1 if current_count == 0 else 0
        )
        db.add(new_b)
    db.commit()

    return {'success': True}

@router.post('/api/blogs/{blog_id}/delete')
def api_delete_blog(blog_id: str, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id, SaasBlog.user_id == user.id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")

    user_blog_count = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).count()
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
async def api_upload_blog_token(file: UploadFile = File(...)):
    tokens_dir = TOKENS_DIR
    os.makedirs(tokens_dir, exist_ok=True)
    filename = f"token_{uuid.uuid4().hex[:8]}.json"
    save_path = os.path.join(tokens_dir, filename)
    content = await file.read()
    with open(save_path, 'wb') as f:
        f.write(content)
    return {'success': True, 'token_file': save_path, 'filename': filename}

@router.post('/api/blogs/autopilot-settings')
def api_save_autopilot_settings(req: AutopilotSettingsReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blog = db.query(SaasBlog).filter(SaasBlog.id == req.blog_id, SaasBlog.user_id == user.id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")

    # Persist in database
    blog.autopilot_enabled = bool(req.autopilot_enabled)
    blog.publish_mode = req.publish_mode
    blog.schedule_frequency = req.schedule
    db.commit()

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
def api_get_autopilot_settings(blog_id: str, request: Request, db: Session = Depends(get_saas_db)):
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id).first()
    if blog:
        return {
            'blog_id': blog.id,
            'autopilot_enabled': bool(blog.autopilot_enabled),
            'publish_mode': blog.publish_mode or 'blogger_draft',
            'schedule': blog.schedule_frequency or 'daily',
            'last_run_at': blog.last_run_at.isoformat() if blog.last_run_at else None
        }

    settings_file = os.path.join(BASE_DIR, 'settings', f"autopilot_{blog_id}.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'blog_id': blog_id,
        'autopilot_enabled': True,
        'publish_mode': 'blogger_draft',
        'schedule': 'daily'
    }

@router.post('/api/blogs/{blog_id}/sync-blogger-posts')
def api_sync_blogger_posts(blog_id: str, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blog = db.query(SaasBlog).filter(SaasBlog.id == blog_id, SaasBlog.user_id == user.id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")

    encrypted_token = blog.encrypted_token
    token_file = blog.token_file

    try:
        from blogger_client import fetch_blogger_posts_sync
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
        SaasArticle.user_id == user.id,
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

"""
Admin Management Router for Blogger Auto-Pilot SaaS
Handles platform metrics, tenant management, plan/credits adjustments, tenant data exports,
and autopilot background scheduler administration.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import User, Subscription, Blog as SaasBlog, Article as SaasArticle, Keyword as SaasKeyword
import midtrans_service
from dependencies import get_session_user, get_or_create_default_admin

router = APIRouter(tags=['Admin'])

def require_admin(request: Request, db: Session):
    user = get_session_user(request, db)
    if not user:
        default_admin = get_or_create_default_admin(db)
        return default_admin
    if user.role != 'admin' and user.email != 'admin@bagustech.id':
        raise HTTPException(status_code=403, detail="Akses ditolak: Hanya untuk Administrator SaaS.")
    return user

# --- Request Schemas ---

class AdminSetPlanReq(BaseModel):
    plan_tier: str
    credits_limit: Optional[int] = None

class AdminAddCreditsReq(BaseModel):
    amount: int

# --- Tenant Data Backup & 1-Click Export ---

@router.get('/api/tenant/export')
def api_export_tenant_data(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    blogs = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).all()
    blogs_data = [
        {
            'id': b.id,
            'name': b.name,
            'url': b.url,
            'account_name': b.account_name,
            'niche_description': b.niche_description,
            'is_active': b.is_active,
            'created_at': b.created_at.isoformat() if b.created_at else None
        }
        for b in blogs
    ]

    articles = db.query(SaasArticle).filter(SaasArticle.user_id == user.id).order_by(SaasArticle.created_at.desc()).all()
    articles_data = [
        {
            'id': a.id,
            'blog_id': a.blog_id,
            'title': a.title,
            'target_keyword': a.target_keyword,
            'meta_description': a.meta_description,
            'content_html': a.content_html,
            'labels': a.labels,
            'status': a.status,
            'blogger_post_id': a.blogger_post_id,
            'blogger_url': a.blogger_url,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'updated_at': a.updated_at.isoformat() if a.updated_at else None
        }
        for a in articles
    ]

    keywords = db.query(SaasKeyword).filter(SaasKeyword.user_id == user.id).all()
    keywords_data = [
        {
            'id': k.id,
            'blog_id': k.blog_id,
            'keyword': k.keyword,
            'search_intent': k.search_intent,
            'status': k.status,
            'created_at': k.created_at.isoformat() if k.created_at else None
        }
        for k in keywords
    ]

    sub = user.subscription
    sub_data = {
        'plan_tier': sub.plan_tier if sub else 'free',
        'status': sub.status if sub else 'active',
        'article_credits_limit': sub.article_credits_limit if sub else 3,
        'article_credits_used': sub.article_credits_used if sub else 0
    } if sub else None

    export_payload = {
        'service': 'Blogger Auto-Pilot SaaS',
        'version': '1.0',
        'export_timestamp': datetime.now(timezone.utc).isoformat(),
        'tenant': {
            'user_id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'subscription': sub_data
        },
        'blogs': blogs_data,
        'articles': articles_data,
        'keywords': keywords_data
    }

    json_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False)
    user_prefix = user.email.split('@')[0] if user.email else 'user'
    filename = f"blogger_autopilot_backup_{user_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        content=json_bytes,
        media_type='application/json',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

# --- SaaS Autopilot Background Scheduler Endpoints ---

@router.get('/api/saas/scheduler/status')
def api_scheduler_status(request: Request, db: Session = Depends(get_saas_db)):
    active_count = db.query(Subscription).filter(
        Subscription.status == 'active',
        Subscription.article_credits_used < Subscription.article_credits_limit
    ).count()
    return {
        'status': 'ready',
        'eligible_subscribers': active_count,
        'message': f'{active_count} pelanggan aktif siap untuk siklus autopilot harian.'
    }

@router.post('/api/saas/scheduler/run-cycle')
def api_scheduler_run_cycle(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user.role != 'admin' and user.email != 'admin@bagustech.id':
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat memicu siklus scheduler global.")
    from autopilot_scheduler import run_scheduler_cycle
    result = run_scheduler_cycle()
    return result

# --- Superadmin Management Console Endpoints ---

@router.get('/api/admin/metrics')
def api_admin_metrics(request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    total_users = db.query(User).count()
    subs = db.query(Subscription).all()
    tier_counts = {'free': 0, 'starter': 0, 'pro': 0, 'agency': 0}
    for s in subs:
        t = s.plan_tier if s.plan_tier in tier_counts else 'free'
        tier_counts[t] += 1

    mrr = (
        tier_counts['starter'] * 99000 +
        tier_counts['pro'] * 249000 +
        tier_counts['agency'] * 699000
    )

    total_blogs = db.query(SaasBlog).count()
    total_articles = db.query(SaasArticle).count()
    total_keywords = db.query(SaasKeyword).count()
    published_articles = db.query(SaasArticle).filter(SaasArticle.status == 'published').count()
    draft_articles = db.query(SaasArticle).filter(SaasArticle.status.in_(['draft', 'blogger_draft'])).count()

    recent_users = db.query(User).order_by(User.created_at.desc()).limit(8).all()
    recent_list = [
        {
            'id': u.id,
            'email': u.email,
            'full_name': u.full_name or u.email.split('@')[0],
            'role': u.role,
            'plan_tier': u.subscription.plan_tier if u.subscription else 'free',
            'created_at': u.created_at.isoformat() if u.created_at else None
        }
        for u in recent_users
    ]

    return {
        'total_tenants': total_users,
        'active_paying': tier_counts['starter'] + tier_counts['pro'] + tier_counts['agency'],
        'tier_breakdown': tier_counts,
        'mrr_idr': mrr,
        'total_blogs': total_blogs,
        'total_articles': total_articles,
        'published_articles': published_articles,
        'draft_articles': draft_articles,
        'total_keywords': total_keywords,
        'recent_tenants': recent_list
    }

@router.get('/api/admin/tenants')
def api_admin_tenants(request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    users = db.query(User).order_by(User.created_at.desc()).all()
    tenant_list = []
    for u in users:
        sub = u.subscription
        tenant_list.append({
            'id': u.id,
            'email': u.email,
            'full_name': u.full_name or u.email.split('@')[0],
            'role': u.role,
            'is_active': u.is_active,
            'plan_tier': sub.plan_tier if sub else 'free',
            'credits_used': sub.article_credits_used if sub else 0,
            'credits_limit': sub.article_credits_limit if sub else 3,
            'blogs_count': len(u.blogs),
            'articles_count': len(u.articles),
            'created_at': u.created_at.isoformat() if u.created_at else None
        })

    return {'tenants': tenant_list, 'count': len(tenant_list)}

@router.post('/api/admin/tenants/{user_id}/plan')
def api_admin_set_tenant_plan(user_id: str, req: AdminSetPlanReq, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    clean_tier = req.plan_tier.lower().strip()
    tier_info = midtrans_service.PLAN_TIERS.get(clean_tier, midtrans_service.PLAN_TIERS['free'])

    sub = target_user.subscription
    if not sub:
        sub = Subscription(user_id=target_user.id)
        db.add(sub)

    sub.plan_tier = clean_tier
    sub.status = 'active'
    sub.article_credits_limit = req.credits_limit if req.credits_limit is not None else tier_info['credits']
    sub.article_credits_used = 0
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()

    return {
        'success': True,
        'message': f"Paket untuk {target_user.email} berhasil diubah ke {clean_tier.upper()} ({sub.article_credits_limit} kredit).",
        'plan_tier': clean_tier,
        'credits_limit': sub.article_credits_limit
    }

@router.post('/api/admin/tenants/{user_id}/credits')
def api_admin_add_tenant_credits(user_id: str, req: AdminAddCreditsReq, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    sub = target_user.subscription
    if not sub:
        sub = Subscription(user_id=target_user.id)
        db.add(sub)

    sub.article_credits_limit += req.amount
    db.commit()

    return {
        'success': True,
        'message': f"Berhasil menambahkan {req.amount} kredit untuk {target_user.email}. Limit baru: {sub.article_credits_limit} kredit.",
        'new_limit': sub.article_credits_limit
    }

@router.post('/api/admin/tenants/{user_id}/toggle-status')
def api_admin_toggle_tenant_status(user_id: str, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    if target_user.id == admin.id:
        raise HTTPException(status_code=400, detail="Tidak dapat menonaktifkan akun admin sendiri.")

    target_user.is_active = not target_user.is_active
    db.commit()

    status_str = "diaktifkan" if target_user.is_active else "dinonaktifkan (suspend)"
    return {
        'success': True,
        'message': f"Akun {target_user.email} berhasil {status_str}.",
        'is_active': target_user.is_active
    }

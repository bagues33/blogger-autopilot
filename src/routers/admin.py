"""
Admin Management Router for Blogger Auto-Pilot SaaS
Handles platform metrics, tenant management, plan/credits adjustments, tenant data exports,
agency workspace monitoring, global audit trails, and autopilot scheduler administration.
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.core.database import get_saas_db
from src.models.models import (
    User,
    Subscription,
    Blog as SaasBlog,
    Article as SaasArticle,
    Keyword as SaasKeyword,
    Workspace,
    WorkspaceMembership,
    WorkspaceBlogAssignment,
    AuditLog
)
from src.core.security import hash_password
import src.services.payment as midtrans_service
from src.services.audit import record_audit_log
from src.core.dependencies import get_session_user, get_current_user, get_current_admin, check_feature_access

router = APIRouter(tags=['Admin'])

def require_admin(request: Request, db: Session):
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir atau belum login. Silakan login sebagai administrator.")
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Akses ditolak: Hanya untuk Administrator SaaS.")
    return user

# --- Request Schemas ---

class AdminSetPlanReq(BaseModel):
    plan_tier: str
    credits_limit: Optional[int] = None

class AdminAddCreditsReq(BaseModel):
    amount: int

class AdminResetPasswordReq(BaseModel):
    new_password: str

class AdminSetRoleReq(BaseModel):
    role: str # 'admin' or 'subscriber'

# --- Tenant Data Backup & 1-Click Export ---

@router.get('/api/tenant/export')
def api_export_tenant_data(user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if not check_feature_access(user, 'export_backup'):
        raise HTTPException(
            status_code=403,
            detail="Fitur Ekspor Backup Data 1-Klik memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )

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

# --- SaaS Autopilot Background Scheduler Endpoints (Admin Only) ---

@router.get('/api/saas/scheduler/status')
def api_scheduler_status(admin: User = Depends(get_current_admin), db: Session = Depends(get_saas_db)):
    active_count = db.query(Subscription).join(User, Subscription.user_id == User.id).filter(
        User.is_active == True,
        Subscription.status == 'active',
        Subscription.plan_tier.in_(['pro', 'agency']),
        Subscription.article_credits_used < Subscription.article_credits_limit
    ).count()
    return {
        'status': 'ready',
        'eligible_subscribers': active_count,
        'message': f'{active_count} pelanggan Pro/Agency aktif siap untuk siklus autopilot.'
    }

@router.post('/api/saas/scheduler/run-cycle')
def api_scheduler_run_cycle(request: Request, admin: User = Depends(get_current_admin), db: Session = Depends(get_saas_db)):
    from autopilot_scheduler import run_scheduler_cycle
    result = run_scheduler_cycle()
    record_audit_log(
        db=db,
        event_type="admin.scheduler_triggered",
        user_id=admin.id,
        metadata={"processed_count": result.get("processed_count", 0)},
        ip_address=request.client.host if request and request.client else None
    )
    return result

# --- Superadmin Management Console Endpoints ---

@router.get('/api/admin/metrics')
def api_admin_metrics(request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    total_users = db.query(User).count()
    suspended_users = db.query(User).filter(User.is_active == False).count()

    # Count only active subscriptions on active non-admin accounts for accurate MRR
    active_subs = db.query(Subscription, User).join(User, Subscription.user_id == User.id).filter(
        Subscription.status == 'active',
        User.is_active == True
    ).all()

    tier_counts = {'free': 0, 'starter': 0, 'pro': 0, 'agency': 0}
    paying_tier_counts = {'starter': 0, 'pro': 0, 'agency': 0}

    for sub, u in active_subs:
        t = sub.plan_tier if sub.plan_tier in tier_counts else 'free'
        tier_counts[t] += 1
        if t in paying_tier_counts and u.role != 'admin':
            paying_tier_counts[t] += 1

    mrr = sum(
        paying_tier_counts[t] * midtrans_service.PLAN_TIERS.get(t, {}).get('price', 0)
        for t in ['starter', 'pro', 'agency']
    )

    total_blogs = db.query(SaasBlog).count()
    total_articles = db.query(SaasArticle).count()
    total_keywords = db.query(SaasKeyword).count()
    published_articles = db.query(SaasArticle).filter(SaasArticle.status == 'published').count()
    draft_articles = db.query(SaasArticle).filter(SaasArticle.status.in_(['draft', 'blogger_draft'])).count()
    total_workspaces = db.query(Workspace).count()
    total_team_members = db.query(WorkspaceMembership).count()

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
        'suspended_tenants': suspended_users,
        'active_paying': sum(paying_tier_counts.values()),
        'tier_breakdown': tier_counts,
        'mrr_idr': mrr,
        'total_blogs': total_blogs,
        'total_articles': total_articles,
        'published_articles': published_articles,
        'draft_articles': draft_articles,
        'total_keywords': total_keywords,
        'total_workspaces': total_workspaces,
        'total_team_members': total_team_members,
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

@router.get('/api/admin/workspaces')
def api_admin_workspaces(request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    workspaces = db.query(Workspace).order_by(desc(Workspace.created_at)).all()
    items = []
    for w in workspaces:
        owner = w.owner
        m_ids = [m.id for m in w.memberships]
        assigned_count = db.query(WorkspaceBlogAssignment).filter(
            WorkspaceBlogAssignment.membership_id.in_(m_ids)
        ).count() if m_ids else 0

        items.append({
            'id': w.id,
            'name': w.name,
            'owner_email': owner.email if owner else '-',
            'owner_name': (owner.full_name or owner.email.split('@')[0]) if owner else '-',
            'owner_plan': owner.subscription.plan_tier if (owner and owner.subscription) else 'free',
            'member_count': len(w.memberships) + 1,
            'assigned_blogs_count': assigned_count,
            'created_at': w.created_at.isoformat() if w.created_at else None
        })

    return {'success': True, 'workspaces': items, 'count': len(items)}

@router.get('/api/admin/audit-logs')
def api_admin_global_audit_logs(request: Request, limit: int = 50, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)
    safe_limit = max(1, min(limit, 200))

    logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(safe_limit).all()
    items = []
    for l in logs:
        actor_email = l.user.email if l.user else 'system'
        meta = {}
        if l.metadata_json:
            try:
                meta = json.loads(l.metadata_json)
            except Exception:
                meta = {'raw': l.metadata_json}
        items.append({
            'id': l.id,
            'event_type': l.event_type,
            'actor_email': actor_email,
            'entity_id': l.entity_id,
            'metadata': meta,
            'ip_address': l.ip_address,
            'created_at': l.created_at.isoformat() if l.created_at else None
        })

    return {'success': True, 'logs': items, 'count': len(items)}

@router.post('/api/admin/tenants/{user_id}/plan')
def api_admin_set_tenant_plan(user_id: str, req: AdminSetPlanReq, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    clean_tier = req.plan_tier.lower().strip()
    tier_info = midtrans_service.PLAN_TIERS.get(clean_tier, midtrans_service.PLAN_TIERS['free'])

    sub = target_user.subscription
    old_tier = sub.plan_tier if sub else 'free'
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

    record_audit_log(
        db=db,
        event_type="admin.plan_changed",
        user_id=admin.id,
        entity_id=target_user.id,
        metadata={
            "target_email": target_user.email,
            "old_tier": old_tier,
            "new_tier": clean_tier,
            "credits_limit": sub.article_credits_limit
        },
        ip_address=request.client.host if request and request.client else None
    )

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

    record_audit_log(
        db=db,
        event_type="admin.credits_added",
        user_id=admin.id,
        entity_id=target_user.id,
        metadata={
            "target_email": target_user.email,
            "amount_added": req.amount,
            "new_limit": sub.article_credits_limit
        },
        ip_address=request.client.host if request and request.client else None
    )

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

    record_audit_log(
        db=db,
        event_type="admin.status_toggled",
        user_id=admin.id,
        entity_id=target_user.id,
        metadata={"target_email": target_user.email, "is_active": target_user.is_active},
        ip_address=request.client.host if request and request.client else None
    )

    return {
        'success': True,
        'message': f"Akun {target_user.email} berhasil {status_str}.",
        'is_active': target_user.is_active
    }

@router.post('/api/admin/tenants/{user_id}/reset-password')
def api_admin_reset_user_password(user_id: str, req: AdminResetPasswordReq, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    clean_pw = req.new_password.strip()
    if len(clean_pw) < 6:
        raise HTTPException(status_code=400, detail="Password baru minimal 6 karakter.")

    target_user.hashed_password = hash_password(clean_pw)
    db.commit()

    record_audit_log(
        db=db,
        event_type="admin.password_reset",
        user_id=admin.id,
        entity_id=target_user.id,
        metadata={"target_email": target_user.email},
        ip_address=request.client.host if request and request.client else None
    )

    return {
        'success': True,
        'message': f"Kata sandi untuk pengguna {target_user.email} berhasil direset."
    }

@router.post('/api/admin/tenants/{user_id}/role')
def api_admin_set_user_role(user_id: str, req: AdminSetRoleReq, request: Request, db: Session = Depends(get_saas_db)):
    admin = require_admin(request, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan.")

    clean_role = req.role.lower().strip()
    if clean_role not in ['admin', 'subscriber']:
        raise HTTPException(status_code=400, detail="Peran tidak valid. Pilihan yang diizinkan: 'admin' atau 'subscriber'.")

    if target_user.id == admin.id and clean_role != 'admin':
        raise HTTPException(status_code=400, detail="Tidak dapat mencabut hak admin dari akun Anda sendiri.")

    old_role = target_user.role
    target_user.role = clean_role
    db.commit()

    record_audit_log(
        db=db,
        event_type="admin.role_changed",
        user_id=admin.id,
        entity_id=target_user.id,
        metadata={
            "target_email": target_user.email,
            "old_role": old_role,
            "new_role": clean_role
        },
        ip_address=request.client.host if request and request.client else None
    )

    label = "Superadmin" if clean_role == "admin" else "Subscriber"
    return {
        'success': True,
        'role': clean_role,
        'message': f"Peran pengguna {target_user.email} berhasil diubah menjadi {label}."
    }

"""
Shared Dependencies and Session Helpers for Blogger Auto-Pilot SaaS
Provides reusable session authentication, tenant resolution, and configuration constants.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from src.models.models import User
from src.core.security import decode_access_token, register_new_tenant_user
from src.core.database import get_saas_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = PROJECT_ROOT
SEO_KB_PATH = os.environ.get('BLOGGER_SEO_KB_PATH', os.path.join(BASE_DIR, 'seo_knowledge.md'))
SEO_PROMPT_PATH = os.environ.get('BLOGGER_SEO_PROMPT_PATH', os.path.join(BASE_DIR, 'seo_master_prompt.md'))
UPLOADS_DIR = os.environ.get('BLOGGER_UPLOADS_DIR', os.path.join(BASE_DIR, 'uploads'))
CONFIG_FILE = os.environ.get('BLOGGER_CONFIG_FILE', os.path.join(BASE_DIR, 'config.json'))
DEFAULT_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', os.path.join(BASE_DIR, 'token.json'))
DEFAULT_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', os.path.join(BASE_DIR, 'client_secret.json'))
TOKENS_DIR = os.path.join(BASE_DIR, 'tokens')

def get_session_user(request: Request, db: Session) -> Optional[User]:
    """
    Extracts the current tenant User from HttpOnly JWT cookie or Authorization Bearer header.
    """
    token = request.cookies.get('saas_token')
    if not token:
        auth_hdr = request.headers.get('Authorization')
        if auth_hdr and auth_hdr.startswith('Bearer '):
            token = auth_hdr.split(' ', 1)[1].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or 'sub' not in payload:
        return None
    user = db.query(User).filter(User.id == payload['sub'], User.is_active == True).first()
    return user

def get_current_user(request: Request, db: Session = Depends(get_saas_db)) -> User:
    """
    Strict FastAPI dependency for protected tenant endpoints.
    Requires an authenticated user session (cookie or bearer token).
    Raises HTTP 401 Unauthorized if not authenticated.
    """
    user = get_session_user(request, db)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sesi telah berakhir atau belum login. Silakan login terlebih dahulu."
        )
    return user

def get_optional_user(request: Request, db: Session = Depends(get_saas_db)) -> Optional[User]:
    """
    FastAPI dependency for endpoints accessible by both guests and authenticated users.
    Returns the User if logged in, or None otherwise.
    """
    return get_session_user(request, db)

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Strict FastAPI dependency for admin-only endpoints.
    Requires user to have role == 'admin'.
    Raises HTTP 403 Forbidden if not authorized.
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Hanya untuk Administrator SaaS."
        )
    return current_user

PLAN_FEATURES = {
    'free': {
        'max_blogs': 1,
        'monthly_credits': 3,
        'byok': False,
        'autopilot': False,
        'custom_kb': False,
        'workspaces': False,
        'export_backup': False,
    },
    'starter': {
        'max_blogs': 3,
        'monthly_credits': 50,
        'byok': False,
        'autopilot': False,
        'custom_kb': False,
        'workspaces': False,
        'export_backup': False,
    },
    'pro': {
        'max_blogs': 10,
        'monthly_credits': 200,
        'byok': True,
        'autopilot': True,
        'custom_kb': True,
        'workspaces': False,
        'export_backup': True,
    },
    'agency': {
        'max_blogs': 50,
        'monthly_credits': 600,
        'byok': True,
        'autopilot': True,
        'custom_kb': True,
        'workspaces': True,
        'export_backup': True,
    }
}

def is_subscription_expired(sub) -> bool:
    """
    Checks whether a paid subscription has expired based on status or current_period_end.
    Free tier does not expire; naive timestamps from SQLite are normalized to UTC.
    """
    if not sub:
        return False
    tier = (sub.plan_tier or 'free').lower()
    if tier == 'free':
        return False
    if sub.status not in ('active', 'trialing'):
        return True
    if sub.current_period_end is not None:
        end_dt = sub.current_period_end
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if end_dt < datetime.now(timezone.utc):
            return True
    return False

def get_effective_plan_tier(user: Optional[User]) -> str:
    """
    Returns the tenant's active effective plan tier.
    Paid plans whose period has ended or whose status is no longer active automatically
    downgrade to 'free' until renewed.
    """
    if not user:
        return 'free'
    if getattr(user, 'role', None) == 'admin':
        return 'agency'
    sub = getattr(user, 'subscription', None)
    if not sub or not sub.plan_tier:
        return 'free'
    if is_subscription_expired(sub):
        return 'free'
    return sub.plan_tier.lower()

def check_feature_access(user: Optional[User], feature_name: str) -> bool:
    """
    Validates whether a tenant has access to an advanced/premium feature.
    Enforces subscription expiration; Superadmins always bypass all tier gating.
    """
    if not user:
        return False
    if getattr(user, 'role', None) == 'admin':
        return True

    tier = get_effective_plan_tier(user)
    tier_config = PLAN_FEATURES.get(tier, PLAN_FEATURES['free'])
    return bool(tier_config.get(feature_name, False))

def get_or_create_default_admin(db: Session) -> User:
    """
    Retrieves or lazily provisions the default admin tenant for initial bootstrapping/seeding.
    Do NOT use as a fallback for unauthenticated requests.
    """
    admin = db.query(User).filter(User.email == 'admin@bagustech.id').first()
    if not admin:
        admin = register_new_tenant_user(
            db,
            email='admin@bagustech.id',
            password='admin-saas-password-2026',
            full_name='Admin Bagus Tech',
            plan_tier='pro'
        )
    if admin and admin.role != 'admin':
        admin.role = 'admin'
        db.commit()
        db.refresh(admin)
    return admin

"""
Shared Dependencies and Session Helpers for Blogger Auto-Pilot SaaS
Provides reusable session authentication, tenant resolution, and configuration constants.
"""

import os
import json
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session
from models_saas import User
from auth_saas import decode_access_token, register_new_tenant_user

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

def get_or_create_default_admin(db: Session) -> User:
    """
    Retrieves or lazily provisions the default admin tenant for seamless initial onboarding.
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
    return admin

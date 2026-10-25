"""
SaaS Authentication & Tenant Authorization Suite
Handles password hashing (bcrypt), JWT cookie/bearer tokens, and multi-tenant user isolation.
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import bcrypt
import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models_saas import User, Subscription
from db_saas import get_saas_db

def get_jwt_secret() -> str:
    raw_secret = os.environ.get('JWT_SECRET_KEY', '').strip()
    if not raw_secret:
        raw_secret = 'blogger-autopilot-saas-jwt-secret-key-32bytes-min!'
    # Ensure minimum 32 bytes for secure HMAC-SHA256
    return hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()

JWT_SECRET = get_jwt_secret()
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_saas_db)
) -> User:
    """
    Extracts authenticated user from Authorization Header (Bearer) or HttpOnly cookie (saas_token).
    Enforces strict multi-tenant context.
    """
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif 'saas_token' in request.cookies:
        token = request.cookies.get('saas_token')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi diperlukan. Silakan login ke akun SaaS Anda.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or 'sub' not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi login kedaluwarsa atau tidak valid. Silakan login kembali.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get('sub')
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan atau dinonaktifkan.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def register_new_tenant_user(
    db: Session,
    email: str,
    password: Optional[str] = None,
    full_name: Optional[str] = None,
    google_sub_id: Optional[str] = None,
    plan_tier: str = 'free'
) -> User:
    """
    Registers a new tenant user and automatically provisions their initial subscription plan.
    """
    clean_email = email.strip().lower()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise ValueError(f"Email '{clean_email}' sudah terdaftar. Silakan login.")

    hashed_pw = hash_password(password) if password else None
    new_user = User(
        email=clean_email,
        hashed_password=hashed_pw,
        full_name=full_name.strip() if full_name else None,
        google_sub_id=google_sub_id,
        role='subscriber'
    )
    db.add(new_user)
    db.flush()

    # Credit limits based on tier
    credits_map = {
        'free': 3,
        'starter': 30,
        'pro': 120,
        'agency': 500
    }
    credits = credits_map.get(plan_tier, 3)

    new_sub = Subscription(
        user_id=new_user.id,
        plan_tier=plan_tier,
        status='active',
        article_credits_limit=credits,
        article_credits_used=0,
        billing_cycle='monthly'
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_user)
    return new_user

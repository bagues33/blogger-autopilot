"""
Authentication Router for Blogger Auto-Pilot SaaS
Handles tenant registration, login/logout, JWT sessions, and Google OAuth credentials.
"""

import os
import json
import uuid
from typing import Optional
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build

from datetime import timedelta
from src.core.database import get_saas_db, SessionLocal
from src.models.models import User, Blog as SaasBlog, NotificationSetting
from src.core.security import (
    register_new_tenant_user,
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token
)
from src.core.crypto import encrypt_token_data, decrypt_token_data
from src.core.rate_limiter import check_rate_limit
from src.services.audit import record_audit_log
from src.services.payment import PLAN_TIERS
from src.core.dependencies import (
    get_session_user,
    get_current_user,
    get_effective_plan_tier,
    is_subscription_expired,
    BASE_DIR,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_TOKEN_FILE,
    TOKENS_DIR
)

router = APIRouter(tags=['Auth'])
SCOPES = ['https://www.googleapis.com/auth/blogger']

# --- Request Schemas ---
class RegisterReq(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class LoginReq(BaseModel):
    email: str
    password: str

class AuthCodeReq(BaseModel):
    code: str
    token_filename: Optional[str] = None

class ForgotPasswordReq(BaseModel):
    email: str

class ResetPasswordConfirmReq(BaseModel):
    token: str
    new_password: str

# --- SaaS Auth Endpoints ---

@router.post('/api/saas/auth/register')
def api_saas_register(req: RegisterReq, request: Request, response: Response, db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=15, window_seconds=60, endpoint_tag="register")

    if len(req.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter.")
    try:
        user = register_new_tenant_user(
            db=db,
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            plan_tier='free'
        )
        token = create_access_token({'sub': user.id, 'email': user.email})
        is_prod = os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('SECURE_COOKIES', '').lower() in ('true', '1')
        response.set_cookie(
            key='saas_token',
            value=token,
            httponly=True,
            max_age=86400 * 30,
            samesite='lax',
            secure=is_prod
        )
        return {
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name or user.email.split('@')[0],
                'role': user.role
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registrasi gagal: {str(e)}")

@router.post('/api/saas/auth/login')
def api_saas_login(req: LoginReq, request: Request, response: Response, db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=25, window_seconds=60, endpoint_tag="login")

    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email atau kata sandi tidak valid.")

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Akun Anda sedang dinonaktifkan (suspend). Silakan hubungi administrator."
        )

    token = create_access_token({'sub': user.id, 'email': user.email})
    is_prod = os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('SECURE_COOKIES', '').lower() in ('true', '1')
    response.set_cookie(
        key='saas_token',
        value=token,
        httponly=True,
        max_age=86400 * 30,
        samesite='lax',
        secure=is_prod
    )
    return {
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name or user.email.split('@')[0],
            'role': user.role
        }
    }

@router.post('/api/saas/auth/logout')
def api_saas_logout(response: Response):
    response.delete_cookie(key='saas_token')
    return {'success': True}

@router.get('/api/saas/auth/me')
def api_saas_me(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db)
    if not user:
        return {
            'authenticated': False,
            'user': None,
            'subscription': {
                'plan_tier': 'free',
                'status': 'guest',
                'article_credits_limit': 0,
                'article_credits_used': 0,
                'credits_remaining': 0,
                'current_period_end': None
            }
        }

    sub = user.subscription
    plan_tier = sub.plan_tier if sub else 'free'
    credits_limit = sub.article_credits_limit if sub else 3
    credits_used = sub.article_credits_used if sub else 0
    remaining = max(0, credits_limit - credits_used)
    expired = is_subscription_expired(sub)
    effective_tier = get_effective_plan_tier(user)

    return {
        'authenticated': True,
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name or user.email.split('@')[0],
            'role': user.role,
        },
        'subscription': {
            'plan_tier': plan_tier,
            'effective_plan_tier': effective_tier,
            'is_expired': expired,
            'status': 'expired' if expired else (sub.status if sub else 'active'),
            'article_credits_limit': credits_limit,
            'article_credits_used': credits_used,
            'credits_remaining': remaining,
            'current_period_end': sub.current_period_end.isoformat() if sub and sub.current_period_end else None
        }
    }

# --- Self-Service Password Reset ---

@router.post('/api/saas/auth/forgot-password')
def api_saas_forgot_password(req: ForgotPasswordReq, request: Request, db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=5, window_seconds=300, endpoint_tag="forgot_password")
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email, User.is_active == True).first()

    is_prod = os.environ.get('ENVIRONMENT', '').strip().lower() == 'production'
    dev_token = None

    if user:
        reset_token = create_access_token(
            {'sub': user.id, 'email': user.email, 'purpose': 'password_reset'},
            expires_delta=timedelta(minutes=15)
        )
        # Notify via Telegram if user configured Telegram alerts
        try:
            ns = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id, NotificationSetting.is_active == True).first()
            if ns and ns.telegram_bot_token and ns.telegram_chat_id:
                from src.services.notifications import send_telegram_message
                send_telegram_message(
                    ns.telegram_bot_token,
                    ns.telegram_chat_id,
                    f"🔐 <b>Permintaan Reset Kata Sandi</b>\n\nGunakan token berikut (berlaku 15 menit) untuk mengatur ulang kata sandi akun <code>{user.email}</code>:\n\n<code>{reset_token}</code>"
                )
        except Exception:
            pass

        record_audit_log(
            db=db,
            event_type="auth.password_reset_requested",
            user_id=user.id,
            entity_id=user.id,
            metadata={"email": user.email},
            ip_address=request.client.host if request and request.client else None
        )
        if not is_prod:
            dev_token = reset_token

    # Always return neutral response to prevent email enumeration
    resp = {
        'success': True,
        'message': "Jika email terdaftar di sistem, instruksi & token reset kata sandi (berlaku 15 menit) telah dikirimkan. Hubungi CS jika Anda belum menghubungkan kanal notifikasi."
    }
    if dev_token and not is_prod:
        resp['dev_reset_token'] = dev_token
    return resp

@router.post('/api/saas/auth/reset-password-confirm')
def api_saas_reset_password_confirm(req: ResetPasswordConfirmReq, request: Request, db: Session = Depends(get_saas_db)):
    check_rate_limit(request, max_requests=10, window_seconds=300, endpoint_tag="reset_password_confirm")

    if len(req.new_password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Kata sandi baru minimal 8 karakter.")

    payload = decode_access_token(req.token.strip())
    if not payload or payload.get('purpose') != 'password_reset' or not payload.get('sub'):
        raise HTTPException(status_code=400, detail="Token reset kata sandi tidak valid atau sudah kedaluwarsa.")

    user = db.query(User).filter(User.id == payload['sub'], User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Akun pengguna tidak ditemukan atau tidak aktif.")

    user.hashed_password = hash_password(req.new_password.strip())
    db.commit()

    record_audit_log(
        db=db,
        event_type="auth.password_reset_completed",
        user_id=user.id,
        entity_id=user.id,
        metadata={"email": user.email},
        ip_address=request.client.host if request and request.client else None
    )

    return {'success': True, 'message': "Kata sandi Anda berhasil diperbarui. Silakan masuk dengan kata sandi baru."}

# --- Google OAuth Flow (Hardened Multi-Tenant) ---

@router.get('/api/auth/google/login')
def api_google_login(request: Request, account_name: Optional[str] = 'Akun Google', user: User = Depends(get_current_user)):
    if not os.path.exists(DEFAULT_CLIENT_SECRET):
        raise HTTPException(
            status_code=400,
            detail="File client_secret.json belum dikonfigurasi di server. Hubungi administrator."
        )

    base_url = str(request.base_url).rstrip('/')
    app_base = os.environ.get('APP_BASE_URL', '').strip().rstrip('/')
    if app_base:
        base_url = app_base

    redirect_uri = f"{base_url}/api/auth/google/callback"

    flow = Flow.from_client_secrets_file(
        DEFAULT_CLIENT_SECRET,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    state_payload = {
        'state': state,
        'user_id': user.id,
        'code_verifier': getattr(flow, 'code_verifier', None),
        'account_name': (account_name or 'Akun Google').strip()[:100],
        'redirect_uri': redirect_uri
    }
    encrypted_state = encrypt_token_data(state_payload)
    resp = RedirectResponse(auth_url)
    resp.set_cookie(
        key="bap_oauth_state",
        value=encrypted_state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=os.environ.get('ENVIRONMENT') == 'production'
    )
    return resp

@router.get('/api/auth/google/callback')
async def api_google_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None, state: Optional[str] = None):
    if error:
        return RedirectResponse(f"/dashboard?auth_error={error}")
    if not code:
        return RedirectResponse("/dashboard?auth_error=no_code_provided")

    cookie_state = request.cookies.get("bap_oauth_state")
    if not cookie_state or not state:
        return RedirectResponse("/dashboard?auth_error=invalid_state")

    try:
        state_data = decrypt_token_data(cookie_state)
    except Exception:
        return RedirectResponse("/dashboard?auth_error=invalid_state")

    expected_state = state_data.get('state')
    expected_user_id = state_data.get('user_id')
    code_verifier = state_data.get('code_verifier')
    account_name = state_data.get('account_name', 'Akun Google')
    redirect_uri = state_data.get('redirect_uri')

    # Strict CSRF state validation
    if not expected_state or state != expected_state:
        return RedirectResponse("/dashboard?auth_error=state_mismatch")

    # Strict authenticated tenant check (prevents Account Takeover)
    saas_db = SessionLocal()
    try:
        session_u = get_session_user(request, saas_db)
        if not session_u or (expected_user_id and session_u.id != expected_user_id):
            return RedirectResponse("/?auth_error=login_required")

        if not redirect_uri:
            base_url = str(request.base_url).rstrip('/')
            app_base = os.environ.get('APP_BASE_URL', '').strip().rstrip('/')
            if app_base:
                base_url = app_base
            redirect_uri = f"{base_url}/api/auth/google/callback"

        flow = Flow.from_client_secrets_file(
            DEFAULT_CLIENT_SECRET,
            scopes=SCOPES,
            redirect_uri=redirect_uri,
            state=expected_state
        )
        if code_verifier:
            flow.code_verifier = code_verifier

        flow.fetch_token(code=code)
        creds = flow.credentials

        creds_json = creds.to_json()
        # Store OAuth credentials strictly encrypted in DB (no plaintext disk token leak)
        encrypted_token = encrypt_token_data(creds_json)

        imported_count = 0
        skipped_limit = 0
        try:
            service = build('blogger', 'v3', credentials=creds)
            res = service.blogs().listByUser(userId='self').execute()
            items = res.get('items', [])

            effective_plan = get_effective_plan_tier(session_u)
            max_blogs = PLAN_TIERS.get(effective_plan, PLAN_TIERS['free']).get('blogs', 1)
            existing_count = saas_db.query(SaasBlog).filter(SaasBlog.user_id == session_u.id).count()

            for b in items:
                b_id = b.get('id')
                sb = saas_db.query(SaasBlog).filter(SaasBlog.id == b_id).first()
                if sb:
                    if sb.user_id == session_u.id:
                        sb.encrypted_token = encrypted_token
                        sb.name = b.get('name', 'Blogger Blog')
                        sb.url = b.get('url', '')
                        imported_count += 1
                else:
                    if existing_count >= max_blogs:
                        skipped_limit += 1
                        continue
                    sb = SaasBlog(
                        id=b_id,
                        user_id=session_u.id,
                        name=b.get('name', 'Blogger Blog'),
                        url=b.get('url', ''),
                        account_name=account_name,
                        encrypted_token=encrypted_token,
                        niche_description=b.get('description', ''),
                        is_active=1 if existing_count == 0 else 0
                    )
                    saas_db.add(sb)
                    existing_count += 1
                    imported_count += 1
            saas_db.commit()
        except Exception as e:
            print(f"Error auto-importing blogs: {e}")

        redirect_target = f"/dashboard?auth_success=1&imported={imported_count}"
        if skipped_limit > 0:
            redirect_target += f"&skipped_limit={skipped_limit}"

        resp = RedirectResponse(redirect_target)
        resp.delete_cookie("bap_oauth_state")
        return resp
    finally:
        saas_db.close()

@router.get('/api/auth/url')
def api_get_auth_url():
    if not os.path.exists(DEFAULT_CLIENT_SECRET):
        return {'success': False, 'error': f"File '{DEFAULT_CLIENT_SECRET}' belum dikonfigurasi di server."}
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            DEFAULT_CLIENT_SECRET,
            SCOPES,
            redirect_uri='http://localhost'
        )
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        return {'success': True, 'auth_url': auth_url}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.post('/api/auth/exchange')
def api_exchange_auth_code(req: AuthCodeReq, user: User = Depends(get_current_user)):
    if not os.path.exists(DEFAULT_CLIENT_SECRET):
        return {'success': False, 'error': f"File '{DEFAULT_CLIENT_SECRET}' belum dikonfigurasi di server."}
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            DEFAULT_CLIENT_SECRET,
            SCOPES,
            redirect_uri='http://localhost'
        )

        code_input = req.code.strip()
        if 'code=' in code_input:
            query = urlparse(code_input).query
            parsed = parse_qs(query)
            if 'code' in parsed:
                code_input = parsed['code'][0]

        flow.fetch_token(code=code_input)
        creds = flow.credentials
        encrypted_blob = encrypt_token_data(creds.to_json())

        return {'success': True, 'encrypted_token': encrypted_blob}
    except Exception as e:
        return {'success': False, 'error': str(e)}

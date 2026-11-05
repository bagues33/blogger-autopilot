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

from db_saas import get_saas_db, SessionLocal
from models_saas import User, Blog as SaasBlog
from auth_saas import (
    register_new_tenant_user,
    verify_password,
    create_access_token
)
from crypto_service import encrypt_token_data, decrypt_token_data
from rate_limiter import check_rate_limit
from dependencies import (
    get_session_user,
    get_or_create_default_admin,
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
        user = get_or_create_default_admin(db)
        is_default = True
    else:
        is_default = False

    sub = user.subscription
    plan_tier = sub.plan_tier if sub else 'free'
    credits_limit = sub.article_credits_limit if sub else 3
    credits_used = sub.article_credits_used if sub else 0
    remaining = max(0, credits_limit - credits_used)

    return {
        'authenticated': not is_default,
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name or user.email.split('@')[0],
            'role': user.role,
        },
        'subscription': {
            'plan_tier': plan_tier,
            'status': sub.status if sub else 'active',
            'article_credits_limit': credits_limit,
            'article_credits_used': credits_used,
            'credits_remaining': remaining,
            'current_period_end': sub.current_period_end.isoformat() if sub and sub.current_period_end else None
        }
    }

# --- Google OAuth Flow ---

@router.get('/api/auth/google/login')
def api_google_login(request: Request, account_name: Optional[str] = 'Akun Google'):
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
        'code_verifier': getattr(flow, 'code_verifier', None),
        'account_name': account_name,
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
        return RedirectResponse(f"/?auth_error={error}")
    if not code:
        return RedirectResponse("/?auth_error=no_code_provided")

    cookie_state = request.cookies.get("bap_oauth_state")
    state_data = {}
    if cookie_state:
        try:
            state_data = decrypt_token_data(cookie_state)
        except Exception:
            pass

    expected_state = state_data.get('state')
    code_verifier = state_data.get('code_verifier')
    account_name = state_data.get('account_name', 'Akun Google')
    redirect_uri = state_data.get('redirect_uri')

    if not expected_state:
        auth_state_path = os.path.join(BASE_DIR, 'auth_state.json')
        if os.path.exists(auth_state_path):
            try:
                with open(auth_state_path, 'r') as f:
                    file_data = json.load(f)
                    expected_state = file_data.get('state')
                    code_verifier = file_data.get('code_verifier')
                    account_name = file_data.get('account_name', 'Akun Google')
                    redirect_uri = file_data.get('redirect_uri')
            except Exception:
                pass

    if state and expected_state and state != expected_state:
        return RedirectResponse("/?auth_error=state_mismatch")

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

    tokens_dir = TOKENS_DIR
    os.makedirs(tokens_dir, exist_ok=True)
    token_filename = f"token_{uuid.uuid4().hex[:8]}.json"
    save_path = os.path.join(tokens_dir, token_filename)
    with open(save_path, 'w') as f:
        f.write(creds.to_json())

    if not os.path.exists(DEFAULT_TOKEN_FILE):
        with open(DEFAULT_TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    imported_count = 0
    creds_json = creds.to_json()
    encrypted_token = encrypt_token_data(creds_json)

    try:
        service = build('blogger', 'v3', credentials=creds)
        res = service.blogs().listByUser(userId='self').execute()
        items = res.get('items', [])

        try:
            saas_db = SessionLocal()
            session_u = get_session_user(request, saas_db) or get_or_create_default_admin(saas_db)
            for b in items:
                b_id = b.get('id')
                sb = saas_db.query(SaasBlog).filter(SaasBlog.id == b_id).first()
                if sb:
                    sb.encrypted_token = encrypted_token
                    sb.token_file = save_path
                    sb.name = b.get('name', 'Blogger Blog')
                    sb.url = b.get('url', '')
                else:
                    sb = SaasBlog(
                        id=b_id,
                        user_id=session_u.id,
                        name=b.get('name', 'Blogger Blog'),
                        url=b.get('url', ''),
                        account_name=account_name,
                        encrypted_token=encrypted_token,
                        token_file=save_path,
                        niche_description=b.get('description', ''),
                        is_active=1 if imported_count == 0 else 0
                    )
                    saas_db.add(sb)
                imported_count += 1
            saas_db.commit()
            saas_db.close()
        except Exception as saas_err:
            print(f"Notice: SaaS blog sync error ({saas_err})")

    except Exception as e:
        print(f"Error auto-importing blogs: {e}")

    resp = RedirectResponse(f"/?auth_success=1&imported={imported_count}")
    resp.delete_cookie("bap_oauth_state")
    return resp

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
def api_exchange_auth_code(req: AuthCodeReq):
    if not os.path.exists(DEFAULT_CLIENT_SECRET):
        return {'success': False, 'error': f"File '{DEFAULT_CLIENT_SECRET}' belum dikonfigurasi di server."}
    try:
        out_path = os.path.join(TOKENS_DIR, req.token_filename) if req.token_filename else DEFAULT_TOKEN_FILE
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

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
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

        return {'success': True, 'token_file': out_path}
    except Exception as e:
        return {'success': False, 'error': str(e)}

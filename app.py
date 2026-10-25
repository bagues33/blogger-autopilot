import os
import sys
import sqlite3
import json
import io
import uuid
from typing import Optional, List
from fastapi import FastAPI, Request, Response, Form, HTTPException, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session

from blogger_client import create_post, update_post, get_post, get_service
from image_service import process_and_upload_image
from db_saas import get_saas_db, SessionLocal, init_saas_db
from models_saas import User, Subscription, Blog as SaasBlog, Article as SaasArticle, Keyword as SaasKeyword
from auth_saas import register_new_tenant_user, verify_password, hash_password, create_access_token, decode_access_token
from crypto_service import encrypt_token_data, decrypt_token_data
import midtrans_service

# Auto-initialize SaaS schema on startup
try:
    init_saas_db()
except Exception as _e:
    print(f"Warning initializing SaaS DB: {_e}")

import time
APP_START_TIME = time.time()

tags_metadata = [
    {"name": "Health", "description": "Liveness & readiness probes for cloud monitoring."},
    {"name": "Auth", "description": "Tenant user registration, bcrypt login, and JWT HttpOnly session."},
    {"name": "Billing", "description": "Midtrans Indonesian payment gateway (QRIS, VA Bank) & subscriptions."},
    {"name": "Blogs", "description": "Multi-tenant Google Blogger accounts and blog management."},
    {"name": "Articles", "description": "SEO-optimized articles, E-E-A-T audits, and Blogger publishing."},
    {"name": "Keywords", "description": "Keyword research bank, bulk import, and AI niche suggestions."},
    {"name": "Autopilot", "description": "Autonomous 24/7 background worker and daemon scheduling."},
    {"name": "Admin", "description": "Superadmin command center, MRR metrics, and tenant overrides."},
    {"name": "Notifications", "description": "Real-time Telegram bot alerts and webhook event dispatcher."},
]

app = FastAPI(
    title="Blogger Auto-Pilot SaaS API",
    description="Multi-tenant Commercial SEO & Content Automation SaaS for Indonesian Creators and Publishers.",
    version="2.0.0",
    openapi_tags=tags_metadata
)

@app.get('/health', tags=['Health'])
@app.get('/api/health', tags=['Health'])
def api_health(db: Session = Depends(get_saas_db)):
    from db_saas import is_sqlite
    from sqlalchemy import text
    try:
        db.execute(text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        raise HTTPException(status_code=503, detail={'status': 'unhealthy', 'database': str(e)})

    uptime_secs = int(time.time() - APP_START_TIME)
    return {
        'status': 'healthy',
        'service': 'Blogger Auto-Pilot SaaS',
        'version': '2.0.0',
        'uptime_seconds': uptime_secs,
        'database': {
            'status': db_status,
            'engine': 'sqlite' if is_sqlite else 'postgresql'
        },
        'environment': os.environ.get('ENVIRONMENT', 'production')
    }
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('BLOGGER_DB_PATH', os.path.join(BASE_DIR, 'data.db'))
SEO_KB_PATH = os.environ.get('BLOGGER_SEO_KB_PATH', os.path.join(BASE_DIR, 'seo_knowledge.md'))
SEO_PROMPT_PATH = os.environ.get('BLOGGER_SEO_PROMPT_PATH', os.path.join(BASE_DIR, 'seo_master_prompt.md'))
UPLOADS_DIR = os.environ.get('BLOGGER_UPLOADS_DIR', os.path.join(BASE_DIR, 'uploads'))
CONFIG_FILE = os.environ.get('BLOGGER_CONFIG_FILE', os.path.join(BASE_DIR, 'config.json'))
DEFAULT_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', os.path.join(BASE_DIR, 'token.json'))
DEFAULT_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', os.path.join(BASE_DIR, 'client_secret.json'))
TOKENS_DIR = os.path.join(BASE_DIR, 'tokens')
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOADS_DIR), name='uploads')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

def get_session_user(request: Request, db: Session) -> Optional[User]:
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

# --- SaaS Auth Models & Endpoints ---
class RegisterReq(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class LoginReq(BaseModel):
    email: str
    password: str

class SnapTokenReq(BaseModel):
    plan_tier: str

class UpgradeDemoReq(BaseModel):
    plan_tier: str

@app.post('/api/saas/auth/register', tags=['Auth'])
def api_saas_register(req: RegisterReq, request: Request, response: Response, db: Session = Depends(get_saas_db)):
    from rate_limiter import check_rate_limit
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
        response.set_cookie(
            key='saas_token',
            value=token,
            httponly=True,
            max_age=86400 * 30,
            samesite='lax'
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

@app.post('/api/saas/auth/login', tags=['Auth'])
def api_saas_login(req: LoginReq, request: Request, response: Response, db: Session = Depends(get_saas_db)):
    from rate_limiter import check_rate_limit
    check_rate_limit(request, max_requests=25, window_seconds=60, endpoint_tag="login")

    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email atau kata sandi tidak valid.")
    
    token = create_access_token({'sub': user.id, 'email': user.email})
    response.set_cookie(
        key='saas_token',
        value=token,
        httponly=True,
        max_age=86400 * 30,
        samesite='lax'
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

@app.post('/api/saas/auth/logout')
def api_saas_logout(response: Response):
    response.delete_cookie(key='saas_token')
    return {'success': True}

@app.get('/api/saas/auth/me')
def api_saas_me(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db)
    if not user:
        # Default local dev user fallback
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

# --- Indonesian Billing & Midtrans Endpoints ---
@app.get('/api/billing/plans')
def api_get_billing_plans():
    return {
        'success': True,
        'plans': midtrans_service.PLAN_TIERS,
        'midtrans_client_key': midtrans_service.MIDTRANS_CLIENT_KEY,
        'is_production': midtrans_service.MIDTRANS_IS_PRODUCTION,
        'snap_js_url': midtrans_service.get_snap_js_url()
    }

@app.post('/api/billing/create-snap-token')
def api_create_snap_token(req: SnapTokenReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    res = midtrans_service.create_snap_transaction(user, req.plan_tier)
    if not res.get('success'):
        raise HTTPException(status_code=400, detail=res.get('error', 'Gagal membuat transaksi pembayaran.'))
    return res

@app.post('/api/billing/midtrans/webhook')
async def api_midtrans_webhook(request: Request, db: Session = Depends(get_saas_db)):
    try:
        body = await request.json()
        res = midtrans_service.handle_midtrans_webhook(body, db)
        return res
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post('/api/billing/upgrade-demo')
def api_upgrade_demo(req: UpgradeDemoReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    tier_info = midtrans_service.PLAN_TIERS.get(req.plan_tier, midtrans_service.PLAN_TIERS['starter'])
    sub = user.subscription
    if not sub:
        sub = Subscription(user_id=user.id)
        db.add(sub)
        
    from datetime import datetime, timezone, timedelta
    sub.plan_tier = req.plan_tier
    sub.status = 'active'
    sub.article_credits_limit = tier_info['credits']
    sub.article_credits_used = 0
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    return {
        'success': True,
        'message': f"Paket berhasil diaktifkan ke {tier_info['name']} (Simulasi Demo Sukses).",
        'plan_tier': req.plan_tier,
        'credits': tier_info['credits']
    }

@app.get('/api/blogs')
def api_get_blogs(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blogs = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).order_by(SaasBlog.created_at.asc()).all()
    
    # Auto-seed from legacy SQLite if empty (for smooth initial transition)
    if not blogs and user.email == 'admin@bagustech.id':
        conn = get_db()
        legacy_blogs = conn.execute('SELECT * FROM blogs ORDER BY created_at ASC').fetchall()
        for b in legacy_blogs:
            sb = SaasBlog(
                id=b['id'],
                user_id=user.id,
                name=b['name'],
                url=b['url'],
                account_name=b['account_name'],
                token_file=b['token_file'],
                client_secret_file=b['client_secret_file'],
                niche_description=b['niche_description'],
                is_active=b['is_active']
            )
            db.add(sb)
        db.commit()
        conn.close()
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

class BlogSelectReq(BaseModel):
    blog_id: str

@app.post('/api/blogs/select')
def api_select_blog(req: BlogSelectReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    user_blogs = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).all()
    for b in user_blogs:
        b.is_active = 1 if b.id == req.blog_id else 0
    db.commit()

    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE blogs SET is_active = (id = ?)', (req.blog_id,))
    row = c.execute('SELECT * FROM blogs WHERE id = ?', (req.blog_id,)).fetchone()
    if row and os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'blog_id': row['id'],
                'client_secret_file': row['client_secret_file'] or DEFAULT_CLIENT_SECRET,
                'token_file': row['token_file']
            }, f, indent=2)
    conn.commit()
    conn.close()
    return {'success': True}

class BlogAddReq(BaseModel):
    id: str
    name: str
    url: Optional[str] = ''
    account_name: Optional[str] = 'Akun Utama'
    token_file: Optional[str] = None
    niche_description: Optional[str] = ''

@app.post('/api/blogs/add')
def api_add_blog(req: BlogAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    # Check plan limit for blogs
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

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO blogs (id, name, url, account_name, token_file, client_secret_file, niche_description, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(id) DO UPDATE SET token_file = excluded.token_file, account_name = excluded.account_name, name = excluded.name, url = excluded.url
    ''', (
        req.id.strip(),
        req.name.strip(),
        req.url.strip(),
        req.account_name.strip() or 'Akun Google',
        token,
        DEFAULT_CLIENT_SECRET,
        req.niche_description.strip()
    ))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/blogs/{blog_id}/delete')
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

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM blogs WHERE id = ?', (blog_id,))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/blogs/upload-token')
async def api_upload_blog_token(file: UploadFile = File(...)):
    tokens_dir = TOKENS_DIR
    os.makedirs(tokens_dir, exist_ok=True)
    filename = f"token_{uuid.uuid4().hex[:8]}.json"
    save_path = os.path.join(tokens_dir, filename)
    content = await file.read()
    with open(save_path, 'wb') as f:
        f.write(content)
    return {'success': True, 'token_file': save_path, 'filename': filename}

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/blogger']

@app.get('/api/auth/google/login')
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
    
    auth_state_path = os.path.join(BASE_DIR, 'auth_state.json')
    try:
        with open(auth_state_path, 'w') as f:
            json.dump({
                'state': state,
                'code_verifier': getattr(flow, 'code_verifier', None),
                'account_name': account_name,
                'redirect_uri': redirect_uri
            }, f)
    except Exception:
        pass
        
    return RedirectResponse(auth_url)

@app.get('/api/auth/google/callback')
async def api_google_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    if error:
        return RedirectResponse(f"/?auth_error={error}")
    if not code:
        return RedirectResponse("/?auth_error=no_code_provided")

    auth_state_path = os.path.join(BASE_DIR, 'auth_state.json')
    state = None
    code_verifier = None
    account_name = 'Akun Google'
    redirect_uri = None

    if os.path.exists(auth_state_path):
        try:
            with open(auth_state_path, 'r') as f:
                state_data = json.load(f)
                state = state_data.get('state')
                code_verifier = state_data.get('code_verifier')
                account_name = state_data.get('account_name', 'Akun Google')
                redirect_uri = state_data.get('redirect_uri')
        except Exception:
            pass

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
        state=state
    )
    if code_verifier:
        flow.code_verifier = code_verifier

    flow.fetch_token(code=code)
    creds = flow.credentials

    # Generate a unique token file in tokens/
    tokens_dir = TOKENS_DIR
    os.makedirs(tokens_dir, exist_ok=True)
    token_filename = f"token_{uuid.uuid4().hex[:8]}.json"
    save_path = os.path.join(tokens_dir, token_filename)
    with open(save_path, 'w') as f:
        f.write(creds.to_json())

    # Also save as default token.json if none exists
    if not os.path.exists(DEFAULT_TOKEN_FILE):
        with open(DEFAULT_TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    # Auto-discover blogs!
    imported_count = 0
    creds_json = creds.to_json()
    encrypted_token = encrypt_token_data(creds_json)
    
    try:
        service = build('blogger', 'v3', credentials=creds)
        res = service.blogs().listByUser(userId='self').execute()
        items = res.get('items', [])
        
        # 1. Update SQLite
        conn = get_db()
        c = conn.cursor()
        for b in items:
            b_id = b.get('id')
            b_name = b.get('name', 'Blogger Blog')
            b_url = b.get('url', '')
            b_desc = b.get('description', '')
            c.execute('''
                INSERT INTO blogs (id, name, url, account_name, token_file, client_secret_file, niche_description, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET token_file = excluded.token_file, account_name = excluded.account_name, name = excluded.name, url = excluded.url
            ''', (b_id, b_name, b_url, account_name, save_path, DEFAULT_CLIENT_SECRET, b_desc))
            imported_count += 1
            
        active = c.execute('SELECT id FROM blogs WHERE is_active = 1').fetchone()
        if not active and items:
            c.execute('UPDATE blogs SET is_active = 1 WHERE id = ?', (items[0]['id'],))
            
        conn.commit()
        conn.close()

        # 2. Update SaaS Supabase / PostgreSQL models
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
                        is_active=1 if imported_count == 1 else 0
                    )
                    saas_db.add(sb)
            saas_db.commit()
            saas_db.close()
        except Exception as saas_err:
            print(f"Notice: SaaS blog sync error ({saas_err})")

    except Exception as e:
        print(f"Error auto-importing blogs: {e}")

    return RedirectResponse(f"/?auth_success=1&imported={imported_count}")

@app.get('/api/auth/url')
def api_get_auth_url():
    try:
        from auth import get_auth_url
        url = get_auth_url()
        return {'success': True, 'auth_url': url}
    except Exception as e:
        return {'success': False, 'error': str(e)}

class AuthCodeReq(BaseModel):
    code: str
    token_filename: Optional[str] = None

@app.post('/api/auth/exchange')
def api_exchange_auth_code(req: AuthCodeReq):
    try:
        from auth import exchange_code
        out_path = None
        if req.token_filename:
            tokens_dir = TOKENS_DIR
            os.makedirs(tokens_dir, exist_ok=True)
            out_path = os.path.join(tokens_dir, req.token_filename)
        saved_file = exchange_code(req.code, output_file=out_path)
        return {'success': True, 'token_file': saved_file}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get('/api/articles')
def api_get_articles(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    if not blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        if not active_b:
            active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id).first()
        blog_id = active_b.id if active_b else '2940095957137948013'

    arts = db.query(SaasArticle).filter(SaasArticle.user_id == user.id, SaasArticle.blog_id == blog_id).order_by(SaasArticle.created_at.desc()).all()

    # Sync from SQLite if empty for default admin
    if not arts and user.email == 'admin@bagustech.id':
        conn = get_db()
        legacy_arts = conn.execute('SELECT * FROM articles WHERE blog_id = ? ORDER BY created_at DESC', (blog_id,)).fetchall()
        for a in legacy_arts:
            sa = SaasArticle(
                user_id=user.id,
                blog_id=blog_id,
                title=a['title'],
                target_keyword=a['target_keyword'],
                meta_description=a['meta_description'],
                content_html=a['content_html'],
                labels=a['labels'],
                status=a['status'],
                blogger_post_id=a['blogger_post_id'] if 'blogger_post_id' in a.keys() else None,
                blogger_url=a['blogger_url'] if 'blogger_url' in a.keys() else None
            )
            db.add(sa)
        db.commit()
        conn.close()
        arts = db.query(SaasArticle).filter(SaasArticle.user_id == user.id, SaasArticle.blog_id == blog_id).order_by(SaasArticle.created_at.desc()).all()

    return [
        {
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
            'blog_id': a.blog_id
        }
        for a in arts
    ]

@app.get('/api/keywords')
def api_get_keywords(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if not blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        blog_id = active_b.id if active_b else '2940095957137948013'

    kws = db.query(SaasKeyword).filter(SaasKeyword.user_id == user.id, SaasKeyword.blog_id == blog_id).order_by(SaasKeyword.created_at.desc()).all()

    # Sync from SQLite if empty for default admin
    if not kws and user.email == 'admin@bagustech.id':
        conn = get_db()
        legacy_kws = conn.execute('SELECT * FROM keywords WHERE blog_id = ? ORDER BY created_at DESC', (blog_id,)).fetchall()
        for k in legacy_kws:
            sk = SaasKeyword(
                user_id=user.id,
                blog_id=blog_id,
                keyword=k['keyword'],
                search_intent=k['search_intent'] if 'search_intent' in k.keys() else 'Informational',
                status=k['status'] if 'status' in k.keys() else 'planned'
            )
            db.add(sk)
        db.commit()
        conn.close()
        kws = db.query(SaasKeyword).filter(SaasKeyword.user_id == user.id, SaasKeyword.blog_id == blog_id).order_by(SaasKeyword.created_at.desc()).all()

    return [
        {
            'id': k.id,
            'keyword': k.keyword,
            'search_intent': k.search_intent,
            'status': k.status,
            'blog_id': k.blog_id
        }
        for k in kws
    ]

@app.get('/', response_class=HTMLResponse)
def index():
    kb_content = ''
    if os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
            kb_content = f.read()
            
    prompt_content = ''
    if os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
            
    template_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            tpl = f.read()
            return tpl.replace('{{ kb_content }}', kb_content).replace('{{ prompt_content }}', prompt_content)

    return HTMLResponse('<h1>Template templates/index.html tidak ditemukan</h1>', status_code=500)

class ArticleSaveReq(BaseModel):
    id: Optional[int] = None
    title: str
    target_keyword: Optional[str] = None
    meta_description: Optional[str] = None
    content_html: str
    labels: Optional[str] = None
    blog_id: Optional[str] = None

@app.post('/api/articles/save')
def api_save_article(req: ArticleSaveReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    target_blog_id = req.blog_id
    if not target_blog_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        target_blog_id = active_b.id if active_b else '2940095957137948013'

    # Auto-inject Google E-E-A-T Schema JSON-LD if missing
    try:
        from schema_builder import inject_schema_if_missing
        final_content = inject_schema_if_missing(
            html_content=req.content_html,
            title=req.title,
            meta_description=req.meta_description,
            author_name=user.full_name or "Tim Editorial SEO"
        )
    except Exception:
        final_content = req.content_html

    if req.id:
        art = db.query(SaasArticle).filter(SaasArticle.id == req.id, SaasArticle.user_id == user.id).first()
        if art:
            art.title = req.title
            art.target_keyword = req.target_keyword
            art.meta_description = req.meta_description
            art.content_html = final_content
            art.labels = req.labels
            from datetime import datetime, timezone
            art.updated_at = datetime.now(timezone.utc)
    else:
        art = SaasArticle(
            user_id=user.id,
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
            SaasKeyword.user_id == user.id,
            SaasKeyword.keyword == req.target_keyword.strip(),
            SaasKeyword.status == 'planned'
        ).first()
        if kw:
            kw.status = 'in_progress'

    db.commit()

    conn = get_db()
    c = conn.cursor()
    if req.id:
        c.execute('''
            UPDATE articles SET title = ?, target_keyword = ?, meta_description = ?, content_html = ?, labels = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (req.title, req.target_keyword, req.meta_description, final_content, req.labels, req.id))
    else:
        c.execute('''
            INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, blog_id, status) VALUES (?, ?, ?, ?, ?, ?, 'draft')
        ''', (req.title, req.target_keyword, req.meta_description, final_content, req.labels, target_blog_id))
    conn.commit()
    conn.close()

    return {'success': True}

class ArticlePublishReq(BaseModel):
    is_draft: Optional[bool] = False

@app.post('/api/articles/{article_id}/publish')
def api_publish_article(article_id: int, request: Request, is_draft: Optional[bool] = None, req: Optional[ArticlePublishReq] = None, db: Session = Depends(get_saas_db)):
    target_draft = False
    if req is not None and req.is_draft is not None:
        target_draft = req.is_draft
    elif is_draft is not None:
        target_draft = is_draft

    user = get_session_user(request, db) or get_or_create_default_admin(db)
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id, SaasArticle.user_id == user.id).first()
    
    if not art:
        conn = get_db()
        row = conn.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail='Article not found')
        art_title = row['title']
        art_content = row['content_html']
        art_labels = row['labels']
        art_keyword = row['target_keyword']
        art_blog_id = row['blog_id']
        existing_post_id = row['blogger_post_id'] if 'blogger_post_id' in row.keys() else None
        art_url = row['blogger_url'] if 'blogger_url' in row.keys() else None
    else:
        art_title = art.title
        art_content = art.content_html
        art_labels = art.labels
        art_keyword = art.target_keyword
        art_blog_id = art.blog_id
        existing_post_id = art.blogger_post_id
        art_url = art.blogger_url

    blog = db.query(SaasBlog).filter(SaasBlog.id == art_blog_id, SaasBlog.user_id == user.id).first()
    encrypted_token = blog.encrypted_token if blog else None
    token_file = blog.token_file if blog else None

    # Auto-inject Google E-E-A-T Schema JSON-LD before sending to Blogger
    try:
        from schema_builder import inject_schema_if_missing
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
        
        if art:
            art.status = new_status
            art.blogger_post_id = blogger_post_id
            art.blogger_url = blogger_url
            if art_keyword:
                kw = db.query(SaasKeyword).filter(
                    SaasKeyword.user_id == user.id,
                    SaasKeyword.keyword == art_keyword.strip()
                ).first()
                if kw:
                    kw.status = 'in_progress' if target_draft else 'used'
            db.commit()

        conn = get_db()
        c = conn.cursor()
        c.execute('''
            UPDATE articles SET status = ?, blogger_post_id = ?, blogger_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (new_status, blogger_post_id, blogger_url, article_id))
        conn.commit()
        conn.close()

        # Dispatch notification
        try:
            from notification_service import dispatch_notification
            dispatch_notification(
                user_id=user.id,
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

        return {
            'success': True,
            'action': action,
            'is_draft': target_draft,
            'status': new_status,
            'url': blogger_url,
            'post_id': blogger_post_id
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.post('/api/articles/{article_id}/delete')
def api_delete_article(article_id: int, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    art = db.query(SaasArticle).filter(SaasArticle.id == article_id, SaasArticle.user_id == user.id).first()
    if art:
        db.delete(art)
        db.commit()

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM articles WHERE id = ?', (article_id,))
    conn.commit()
    conn.close()
    return {'success': True}

class PromptSaveReq(BaseModel):
    content: str

@app.post('/api/prompt/save')
def api_save_prompt(req: PromptSaveReq):
    with open(SEO_PROMPT_PATH, 'w') as f:
        f.write(req.content)
    return {'success': True}

class KbSaveReq(BaseModel):
    content: str

@app.post('/api/kb/save')
def api_save_kb(req: KbSaveReq):
    with open(SEO_KB_PATH, 'w') as f:
        f.write(req.content)
    return {'success': True}

@app.post('/api/kb/upload-pdf')
async def api_upload_pdf(files: List[UploadFile] = File(...)):
    try:
        total_pages = 0
        added_texts = []
        for file in files:
            contents = await file.read()
            reader = PdfReader(io.BytesIO(contents))
            total_pages += len(reader.pages)
            extracted_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_text.append(f"\n--- [{file.filename} - Halaman {i+1}] ---\n" + text.strip())
            if extracted_text:
                added_texts.append(f"\n\n## Materi Tambahan dari Dokumen PDF: {file.filename}\n" + "\n".join(extracted_text))
                
        existing_content = ''
        if os.path.exists(SEO_KB_PATH):
            with open(SEO_KB_PATH, 'r') as f:
                existing_content = f.read()
                
        new_content = existing_content + "".join(added_texts)
        with open(SEO_KB_PATH, 'w') as f:
            f.write(new_content)
            
        return {'success': True, 'total_files': len(files), 'total_pages': total_pages, 'content': new_content}
    except Exception as e:
        return {'success': False, 'error': str(e)}

class KeywordAddReq(BaseModel):
    keyword: str
    search_intent: Optional[str] = 'Informational'
    blog_id: Optional[str] = None

@app.post('/api/keywords/add')
def api_add_keyword(req: KeywordAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    existing = db.query(SaasKeyword).filter(
        SaasKeyword.user_id == user.id,
        SaasKeyword.blog_id == b_id,
        SaasKeyword.keyword == req.keyword.strip()
    ).first()

    if not existing:
        sk = SaasKeyword(
            user_id=user.id,
            blog_id=b_id,
            keyword=req.keyword.strip(),
            search_intent=req.search_intent or 'Informational',
            status='planned'
        )
        db.add(sk)
        db.commit()

    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO keywords (keyword, search_intent, blog_id) VALUES (?, ?, ?)', (req.keyword, req.search_intent, b_id))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/keywords/{kw_id}/delete')
def api_delete_keyword(kw_id: int, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    kw = db.query(SaasKeyword).filter(SaasKeyword.id == kw_id, SaasKeyword.user_id == user.id).first()
    if kw:
        db.delete(kw)
        db.commit()

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM keywords WHERE id = ?', (kw_id,))
    conn.commit()
    conn.close()
    return {'success': True}

@app.post('/api/keywords/auto-generate')
def api_auto_generate_keywords(request: Request, blog_id: Optional[str] = None, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    high_quality_keywords = [
        ('rekomendasi ai coding assistant gratis untuk vs code', 'Informational'),
        ('cara integrasi api gemini di web modern', 'Informational'),
        ('tips prompt engineering untuk software engineer', 'Informational'),
        ('perbandingan claude dan chatgpt untuk programming', 'Commercial'),
        ('panduan optimasi loading website skor 100', 'Informational'),
        ('tools ai produktivitas terbaik untuk freelancer tech', 'Informational')
    ]
    for kw, intent in high_quality_keywords:
        existing = db.query(SaasKeyword).filter(
            SaasKeyword.user_id == user.id,
            SaasKeyword.blog_id == b_id,
            SaasKeyword.keyword == kw
        ).first()
        if not existing:
            sk = SaasKeyword(
                user_id=user.id,
                blog_id=b_id,
                keyword=kw,
                search_intent=intent,
                status='planned'
            )
            db.add(sk)
    db.commit()

    conn = get_db()
    c = conn.cursor()
    for kw, intent in high_quality_keywords:
        c.execute('''
            INSERT OR IGNORE INTO keywords (keyword, search_intent, status, blog_id) 
            VALUES (?, ?, 'planned', ?)
        ''', (kw, intent, b_id))
    conn.commit()
    conn.close()
    return {'success': True}

class KeywordBulkAddReq(BaseModel):
    keywords_text: str
    search_intent: Optional[str] = 'Informational'
    blog_id: Optional[str] = None

@app.post('/api/keywords/bulk-add')
def api_bulk_add_keywords(req: KeywordBulkAddReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    lines = [line.strip() for line in req.keywords_text.splitlines() if line.strip()]
    added = 0
    conn = get_db()
    c = conn.cursor()
    try:
        for kw in lines:
            existing = db.query(SaasKeyword).filter(
                SaasKeyword.user_id == user.id,
                SaasKeyword.blog_id == b_id,
                SaasKeyword.keyword == kw
            ).first()
            if not existing:
                sk = SaasKeyword(
                    user_id=user.id,
                    blog_id=b_id,
                    keyword=kw,
                    search_intent=req.search_intent or 'Informational',
                    status='planned'
                )
                db.add(sk)
                added += 1
            c.execute('INSERT OR IGNORE INTO keywords (keyword, search_intent, blog_id) VALUES (?, ?, ?)', (kw, req.search_intent, b_id))
        db.commit()
        conn.commit()
    finally:
        conn.close()

    return {'success': True, 'added_count': added, 'total_submitted': len(lines)}

class KeywordSuggestReq(BaseModel):
    niche_seed: str
    blog_id: Optional[str] = None

@app.post('/api/keywords/ai-suggest')
def api_suggest_keywords(req: KeywordSuggestReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    b_id = req.blog_id
    if not b_id:
        active_b = db.query(SaasBlog).filter(SaasBlog.user_id == user.id, SaasBlog.is_active == 1).first()
        b_id = active_b.id if active_b else '2940095957137948013'

    niche = req.niche_seed.strip()
    generated_keywords = [
        (f"cara mudah {niche} untuk pemula", "Informational"),
        (f"panduan lengkap {niche} terbaru 2026", "Informational"),
        (f"rekomendasi tools terbaik untuk {niche}", "Commercial"),
        (f"tips dan trik optimasi {niche} agar maksimal", "Informational"),
        (f"perbandingan metode {niche} gratis vs berbayar", "Commercial"),
        (f"kesalahan umum dalam {niche} yang wajib dihindari", "Informational"),
        (f"studi kasus keberhasilan penerapan {niche}", "Informational"),
        (f"biaya dan estimasi modal untuk {niche}", "Commercial")
    ]

    added = 0
    conn = get_db()
    c = conn.cursor()
    try:
        for kw, intent in generated_keywords:
            existing = db.query(SaasKeyword).filter(
                SaasKeyword.user_id == user.id,
                SaasKeyword.blog_id == b_id,
                SaasKeyword.keyword == kw
            ).first()
            if not existing:
                sk = SaasKeyword(
                    user_id=user.id,
                    blog_id=b_id,
                    keyword=kw,
                    search_intent=intent,
                    status='planned'
                )
                db.add(sk)
                added += 1
            c.execute('INSERT OR IGNORE INTO keywords (keyword, search_intent, blog_id) VALUES (?, ?, ?)', (kw, intent, b_id))
        db.commit()
        conn.commit()
    finally:
        conn.close()

    return {'success': True, 'added_count': added, 'keywords': [k[0] for k in generated_keywords]}

class AutopilotSettingsReq(BaseModel):
    blog_id: str
    autopilot_enabled: bool
    publish_mode: str
    schedule: str

@app.post('/api/blogs/autopilot-settings')
def api_save_autopilot_settings(req: AutopilotSettingsReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    blog = db.query(SaasBlog).filter(SaasBlog.id == req.blog_id, SaasBlog.user_id == user.id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog tidak ditemukan.")

    settings_dir = os.path.join(BASE_DIR, 'settings')
    os.makedirs(settings_dir, exist_ok=True)
    settings_file = os.path.join(settings_dir, f"autopilot_{blog.id}.json")
    with open(settings_file, 'w') as f:
        json.dump({
            'blog_id': blog.id,
            'autopilot_enabled': req.autopilot_enabled,
            'publish_mode': req.publish_mode,
            'schedule': req.schedule,
            'user_id': user.id
        }, f, indent=2)

    return {'success': True, 'message': 'Pengaturan autopilot berhasil disimpan.'}

@app.get('/api/blogs/{blog_id}/autopilot-settings')
def api_get_autopilot_settings(blog_id: str, request: Request, db: Session = Depends(get_saas_db)):
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

# --- SaaS Autopilot Background Scheduler Endpoints ---
@app.get('/api/saas/scheduler/status')
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

@app.post('/api/saas/scheduler/run-cycle')
def api_scheduler_run_cycle(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user.role != 'admin' and user.email != 'admin@bagustech.id':
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat memicu siklus scheduler global.")
    from autopilot_scheduler import run_scheduler_cycle
    result = run_scheduler_cycle()
    return result

@app.post('/api/agent/generate-now')
def api_agent_generate_now(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    # Check tenant quota
    if user and user.subscription:
        sub = user.subscription
        if sub.article_credits_used >= sub.article_credits_limit:
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': f"Kuota kredit artikel Anda telah habis ({sub.article_credits_used}/{sub.article_credits_limit}). Silakan upgrade ke paket Starter atau Pro di dashboard."
                }
            )

    import subprocess
    log_path = os.environ.get('BLOGGER_LOG_FILE', os.path.join(BASE_DIR, 'agent_run.log'))
    log_file = open(log_path, 'a')
    log_file.write(f"\n=== Triggered via Dashboard [{user.email if user else 'local'}] ===\n")
    log_file.flush()
    hermes_bin = '/opt/hermes/.venv/bin/hermes'
    if os.path.exists(hermes_bin):
        cmd = [hermes_bin, 'cron', 'run', 'ef1ee19a17b2']
    else:
        worker_script = os.path.join(BASE_DIR, 'agent_worker.py')
        cmd = [sys.executable, worker_script]
        if user:
            cmd.append(f"--user-id={user.id}")
            
    subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )
    return {'success': True, 'message': 'Agent dimulai di background'}

@app.post('/api/images/upload')
async def api_upload_image(file: UploadFile = File(...)):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
            return JSONResponse({'success': False, 'error': 'Format file harus JPG, PNG, WEBP, atau GIF'}, status_code=400)
        content = await file.read()
        res = process_and_upload_image(content, file.filename)
        return res
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

# --- Two-Way Blogger Synchronization ---
@app.post('/api/blogs/{blog_id}/sync-blogger-posts')
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
                from datetime import datetime, timezone
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

# --- Tenant Data Backup & 1-Click Export ---
@app.get('/api/tenant/export')
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

    from datetime import datetime, timezone
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

# --- Notification Settings Endpoints ---
class NotificationSettingsReq(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    notify_on_draft: Optional[bool] = True
    notify_on_publish: Optional[bool] = True
    notify_on_credit_low: Optional[bool] = True
    is_active: Optional[bool] = True

@app.get('/api/notifications/settings')
def api_get_notification_settings(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    from models_saas import NotificationSetting
    setting = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    
    if not setting:
        return {
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'webhook_url': '',
            'notify_on_draft': True,
            'notify_on_publish': True,
            'notify_on_credit_low': True,
            'is_active': True
        }
    
    return {
        'telegram_bot_token': setting.telegram_bot_token or '',
        'telegram_chat_id': setting.telegram_chat_id or '',
        'webhook_url': setting.webhook_url or '',
        'notify_on_draft': setting.notify_on_draft,
        'notify_on_publish': setting.notify_on_publish,
        'notify_on_credit_low': setting.notify_on_credit_low,
        'is_active': setting.is_active
    }

@app.post('/api/notifications/settings')
def api_save_notification_settings(req: NotificationSettingsReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    from models_saas import NotificationSetting
    setting = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    
    if not setting:
        setting = NotificationSetting(
            user_id=user.id,
            telegram_bot_token=req.telegram_bot_token,
            telegram_chat_id=req.telegram_chat_id,
            webhook_url=req.webhook_url,
            notify_on_draft=req.notify_on_draft if req.notify_on_draft is not None else True,
            notify_on_publish=req.notify_on_publish if req.notify_on_publish is not None else True,
            notify_on_credit_low=req.notify_on_credit_low if req.notify_on_credit_low is not None else True,
            is_active=req.is_active if req.is_active is not None else True
        )
        db.add(setting)
    else:
        if req.telegram_bot_token is not None:
            setting.telegram_bot_token = req.telegram_bot_token
        if req.telegram_chat_id is not None:
            setting.telegram_chat_id = req.telegram_chat_id
        if req.webhook_url is not None:
            setting.webhook_url = req.webhook_url
        if req.notify_on_draft is not None:
            setting.notify_on_draft = req.notify_on_draft
        if req.notify_on_publish is not None:
            setting.notify_on_publish = req.notify_on_publish
        if req.notify_on_credit_low is not None:
            setting.notify_on_credit_low = req.notify_on_credit_low
        if req.is_active is not None:
            setting.is_active = req.is_active
            
    db.commit()
    return {'success': True, 'message': 'Pengaturan notifikasi berhasil disimpan.'}

class NotificationTestReq(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None

@app.post('/api/notifications/test')
def api_test_notification(req: NotificationTestReq):
    from notification_service import send_telegram_message, send_webhook_event
    results = {}
    
    if req.telegram_bot_token and req.telegram_chat_id:
        test_msg = (
            "✅ <b>Blogger Auto-Pilot: Tes Notifikasi Berhasil!</b>\n\n"
            "Bot Telegram Anda telah terhubung secara sukses dengan Blogger Auto-Pilot SaaS.\n"
            "Notifikasi artikel otomatis akan dikirim ke sini."
        )
        results['telegram'] = send_telegram_message(req.telegram_bot_token, req.telegram_chat_id, test_msg)
        
    if req.webhook_url:
        results['webhook'] = send_webhook_event(
            req.webhook_url,
            "test_notification",
            {"message": "Tes webhook berhasil dari Blogger Auto-Pilot SaaS!"}
        )
        
    if not results:
        return {'success': False, 'error': 'Harap masukkan Telegram Bot Token & Chat ID atau Webhook URL untuk diuji.'}
        
    return {'success': True, 'results': results}

# --- Superadmin Management Console Endpoints ---
def require_admin(request: Request, db: Session):
    user = get_session_user(request, db)
    if not user:
        default_admin = get_or_create_default_admin(db)
        return default_admin
    if user.role != 'admin' and user.email != 'admin@bagustech.id':
        raise HTTPException(status_code=403, detail="Akses ditolak: Hanya untuk Administrator SaaS.")
    return user

@app.get('/api/admin/metrics')
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

@app.get('/api/admin/tenants')
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

class AdminSetPlanReq(BaseModel):
    plan_tier: str
    credits_limit: Optional[int] = None

@app.post('/api/admin/tenants/{user_id}/plan')
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
    from datetime import datetime, timezone, timedelta
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()

    return {
        'success': True,
        'message': f"Paket untuk {target_user.email} berhasil diubah ke {clean_tier.upper()} ({sub.article_credits_limit} kredit).",
        'plan_tier': clean_tier,
        'credits_limit': sub.article_credits_limit
    }

class AdminAddCreditsReq(BaseModel):
    amount: int

@app.post('/api/admin/tenants/{user_id}/credits')
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

@app.post('/api/admin/tenants/{user_id}/toggle-status')
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



if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8090)

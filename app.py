"""
Blogger Auto-Pilot SaaS - Main Application Module
Provides application lifecycle orchestration, static file mounts, health monitoring,
and router composition across domain contexts.
"""

import os
import time
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.core.database import get_saas_db, is_sqlite, init_saas_db
from src.core.dependencies import (
    BASE_DIR,
    SEO_KB_PATH,
    SEO_PROMPT_PATH,
    UPLOADS_DIR,
    CONFIG_FILE,
    DEFAULT_TOKEN_FILE,
    DEFAULT_CLIENT_SECRET,
    TOKENS_DIR,
    get_session_user
)
from src.routers import auth, billing, blogs, articles, keywords, settings, admin, workspaces, audit_logs, analytics, cron

# Auto-initialize SaaS schema on startup
try:
    init_saas_db()
except Exception as _e:
    print(f"Warning initializing SaaS DB: {_e}")

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
    {"name": "Settings", "description": "Knowledge base management, prompts, and notification configurations."},
]

app = FastAPI(
    title="Blogger Auto-Pilot SaaS API",
    description="Multi-tenant Commercial SEO & Content Automation SaaS for Indonesian Creators and Publishers.",
    version="2.0.0",
    openapi_tags=tags_metadata
)

# Production fail-fast validation for cryptographic secrets & cron key
if os.environ.get('ENVIRONMENT', '').strip().lower() == 'production':
    from src.core.security import get_jwt_secret
    from src.core.crypto import get_encryption_key
    from src.routers.cron import get_cron_secret
    get_jwt_secret()
    get_encryption_key()
    get_cron_secret()

# CORS policy: strict allowlist from env in production, localhost allowed in dev
_raw_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '').strip()
_app_base = os.environ.get('APP_BASE_URL', '').strip().rstrip('/')
_allowed_origins = [o.strip().rstrip('/') for o in _raw_origins.split(',') if o.strip()]
if _app_base and _app_base not in _allowed_origins:
    _allowed_origins.append(_app_base)
if os.environ.get('ENVIRONMENT', '').strip().lower() != 'production':
    for _dev_orig in ['http://localhost:8090', 'http://127.0.0.1:8090']:
        if _dev_orig not in _allowed_origins:
            _allowed_origins.append(_dev_orig)

if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'X-Cron-Key'],
    )

# Standard HTTP Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://app.midtrans.com https://app.sandbox.midtrans.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' https: data: blob:; "
        "connect-src 'self' https://app.midtrans.com https://app.sandbox.midtrans.com https://api.midtrans.com https://api.sandbox.midtrans.com; "
        "frame-src 'self' https://app.midtrans.com https://app.sandbox.midtrans.com; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    if os.environ.get('ENVIRONMENT', '').strip().lower() == 'production':
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# Static file mounts & Jinja2 Templates
STATIC_DIR = os.path.join(BASE_DIR, 'static')
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOADS_DIR), name='uploads')

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))

# --- Root HTML & Health Monitoring Endpoints ---

@app.get('/health', tags=['Health'])
@app.get('/api/health', tags=['Health'])
def api_health(db: Session = Depends(get_saas_db)):
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

@app.get('/', response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db)
    show_landing = request.query_params.get('landing') == '1'
    if not user or show_landing:
        return templates.TemplateResponse(
            request=request,
            name='landing.html',
            context={
                'is_authenticated': user is not None,
                'user': user
            }
        )
    return dashboard_view(request, db)

@app.get('/dashboard', response_class=HTMLResponse)
@app.get('/app', response_class=HTMLResponse)
def dashboard_view(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db)
    
    kb_content = (user.custom_kb if user and user.custom_kb else '')
    if not kb_content and os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
            kb_content = f.read()
            
    prompt_content = (user.custom_prompt if user and user.custom_prompt else '')
    if not prompt_content and os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
            
    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context={
            'kb_content': kb_content,
            'prompt_content': prompt_content,
            'user': user
        }
    )

# --- Public Legal & Compliance Routes (Required for Google OAuth & Midtrans Approval) ---

@app.get('/privacy', response_class=HTMLResponse, tags=['Health'])
def legal_privacy(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='legal.html',
        context={'page_title': 'Kebijakan Privasi (Privacy Policy)', 'active_doc': 'privacy'}
    )

@app.get('/terms', response_class=HTMLResponse, tags=['Health'])
def legal_terms(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='legal.html',
        context={'page_title': 'Syarat & Ketentuan Layanan', 'active_doc': 'terms'}
    )

@app.get('/refund', response_class=HTMLResponse, tags=['Health'])
def legal_refund(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='legal.html',
        context={'page_title': 'Kebijakan Pengembalian Dana (Refund)', 'active_doc': 'refund'}
    )

# --- Mount Domain Routers ---
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(blogs.router)
app.include_router(articles.router)
app.include_router(keywords.router)
app.include_router(settings.router)
app.include_router(admin.router)
app.include_router(workspaces.router)
app.include_router(audit_logs.router)
app.include_router(analytics.router)
app.include_router(cron.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8090)

"""
Blogger Auto-Pilot SaaS - Main Application Module
Provides application lifecycle orchestration, static file mounts, health monitoring,
and router composition across domain contexts.
"""

import os
import time
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text

from db_saas import get_saas_db, is_sqlite, init_saas_db
from dependencies import (
    BASE_DIR,
    SEO_KB_PATH,
    SEO_PROMPT_PATH,
    UPLOADS_DIR,
    CONFIG_FILE,
    DEFAULT_TOKEN_FILE,
    DEFAULT_CLIENT_SECRET,
    TOKENS_DIR,
    get_session_user,
    get_or_create_default_admin
)
from routers import auth, billing, blogs, articles, keywords, settings, admin, workspaces, audit_logs, analytics

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

# Static file mounts
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOADS_DIR), name='uploads')

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
    
    kb_content = (user.custom_kb if user and user.custom_kb else '')
    if not kb_content and os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
            kb_content = f.read()
            
    prompt_content = (user.custom_prompt if user and user.custom_prompt else '')
    if not prompt_content and os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
            
    template_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            tpl = f.read()
            return tpl.replace('{{ kb_content }}', kb_content).replace('{{ prompt_content }}', prompt_content)

    return HTMLResponse('<h1>Template templates/index.html tidak ditemukan</h1>', status_code=500)

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

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8090)

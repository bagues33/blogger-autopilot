"""
Cron & Autopilot Automation Router for Blogger Auto-Pilot SaaS
Provides secured HTTP webhook endpoints for external scheduler services
(e.g., Cloudflare Workers, cron-job.org, AWS EventBridge, GitHub Actions, Linux crontab).
"""

import os
import hmac
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header
from sqlalchemy.orm import Session

from src.core.database import get_saas_db
from src.core.dependencies import get_session_user
from src.models.models import User
from autopilot_scheduler import run_scheduler_cycle, get_scheduler_status

logger = logging.getLogger("CronRouter")
router = APIRouter(tags=["Autopilot & Cron"])

_DEV_CRON_FALLBACK = "blogger-autopilot-cron-secret-2026"
_PLACEHOLDER_MARKERS = ("ganti_dengan", "dev-secret", "change_me", "placeholder", "your_secret")

def _is_weak_cron_secret(secret: str) -> bool:
    if not secret or len(secret) < 24:
        return True
    low = secret.lower()
    return any(m in low for m in _PLACEHOLDER_MARKERS) or secret == _DEV_CRON_FALLBACK

def get_cron_secret() -> str:
    raw = os.environ.get("CRON_SECRET_KEY", "").strip()
    is_prod = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if is_prod and _is_weak_cron_secret(raw):
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: CRON_SECRET_KEY wajib diisi dengan token acak minimal 24 karakter saat ENVIRONMENT=production!"
        )
    return raw or _DEV_CRON_FALLBACK

def verify_cron_access(
    request: Request,
    x_cron_key: Optional[str] = Header(None, alias="X-Cron-Key"),
    authorization: Optional[str] = Header(None),
    key: Optional[str] = Query(None),
    db: Session = Depends(get_saas_db)
):
    """
    Verifies that the request carries a valid Cron Secret Token
    or originates from an authenticated superadmin session.
    """
    try:
        secret = get_cron_secret()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # 1. Check Query parameter ?key=
    if key and hmac.compare_digest(key.strip(), secret):
        return True

    # 2. Check X-Cron-Key header
    if x_cron_key and hmac.compare_digest(x_cron_key.strip(), secret):
        return True

    # 3. Check Authorization: Bearer <key>
    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()
        if hmac.compare_digest(bearer_token, secret):
            return True

    # 4. Check if originating from an authenticated Admin user session
    session_user = get_session_user(request, db)
    if session_user and getattr(session_user, 'role', '') == 'admin':
        return True

    raise HTTPException(
        status_code=401,
        detail="Akses ditolak: Kunci rahasia cron (X-Cron-Key / Authorization / ?key=) tidak valid."
    )

@router.get('/api/cron/status')
def api_cron_status(
    authorized: bool = Depends(verify_cron_access),
    db: Session = Depends(get_saas_db)
):
    """
    Returns current health and queue metrics of the Autopilot daemon.
    """
    status = get_scheduler_status(db=db)
    return {
        'success': True,
        'service': 'Autopilot Scheduler Daemon',
        'metrics': status
    }

@router.post('/api/cron/trigger-cycle')
@router.get('/api/cron/trigger-cycle')
def api_cron_trigger_cycle(
    authorized: bool = Depends(verify_cron_access),
    max_per_cycle: int = Query(5, ge=1, le=50),
    force: bool = Query(False, description="Paksa eksekusi tanpa memeriksa jeda frekuensi jadwal"),
    db: Session = Depends(get_saas_db)
):
    """
    Triggers one autonomous generation cycle across eligible subscriptions and blogs.
    Supports both POST and GET to accommodate simple HTTP cron services.
    """
    logger.info(f"Cron cycle triggered via HTTP API (max_per_cycle={max_per_cycle}, force={force})")
    result = run_scheduler_cycle(max_per_cycle=max_per_cycle, force=force)
    return result


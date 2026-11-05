"""
Billing Router for Blogger Auto-Pilot SaaS
Handles pricing plans, Midtrans payment token generation, webhooks, and demo upgrades.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_saas import get_saas_db
from models_saas import Subscription
import midtrans_service
from dependencies import get_session_user, get_or_create_default_admin

router = APIRouter(tags=['Billing'])

# --- Request Schemas ---

class SnapTokenReq(BaseModel):
    plan_tier: str

class UpgradeDemoReq(BaseModel):
    plan_tier: str

# --- Endpoints ---

@router.get('/api/billing/plans')
def api_get_billing_plans():
    return {
        'success': True,
        'plans': midtrans_service.PLAN_TIERS,
        'midtrans_client_key': midtrans_service.MIDTRANS_CLIENT_KEY,
        'is_production': midtrans_service.MIDTRANS_IS_PRODUCTION,
        'snap_js_url': midtrans_service.get_snap_js_url()
    }

@router.post('/api/billing/create-snap-token')
def api_create_snap_token(req: SnapTokenReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    res = midtrans_service.create_snap_transaction(user, req.plan_tier)
    if not res.get('success'):
        raise HTTPException(status_code=400, detail=res.get('error', 'Gagal membuat transaksi pembayaran.'))
    return res

@router.post('/api/billing/midtrans/webhook')
async def api_midtrans_webhook(request: Request, db: Session = Depends(get_saas_db)):
    try:
        body = await request.json()
        res = midtrans_service.handle_midtrans_webhook(body, db)
        return res
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.post('/api/billing/upgrade-demo')
def api_upgrade_demo(req: UpgradeDemoReq, request: Request, db: Session = Depends(get_saas_db)):
    import os
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    
    # In production, strictly restrict demo upgrades to administrators
    is_prod = os.environ.get('ENVIRONMENT') == 'production' or midtrans_service.MIDTRANS_IS_PRODUCTION
    if is_prod and user.role != 'admin' and user.email != 'admin@bagustech.id':
        raise HTTPException(
            status_code=403,
            detail="Simulasi demo dinonaktifkan di lingkungan produksi. Silakan lakukan pembayaran resmi melalui Midtrans."
        )

    tier_info = midtrans_service.PLAN_TIERS.get(req.plan_tier, midtrans_service.PLAN_TIERS['starter'])
    sub = user.subscription
    if not sub:
        sub = Subscription(user_id=user.id)
        db.add(sub)
        
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

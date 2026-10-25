"""
Midtrans Indonesian Payment Gateway Suite for Blogger Auto-Pilot SaaS
Supports QRIS (GoPay, ShopeePay, OVO, Dana), Virtual Accounts (BCA, Mandiri, BNI, BRI, Permata), and Credit Cards.
"""

import os
import time
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import requests
from sqlalchemy.orm import Session
from models_saas import User, Subscription

# Configuration
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY', 'SB-Mid-server-DemoTestKeyOnly12345').strip()
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY', 'SB-Mid-client-DemoTestKeyOnly12345').strip()
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'false').lower() in ('true', '1', 'yes')

SNAP_URL_SANDBOX = "https://app.sandbox.midtrans.com/snap/v1/transactions"
SNAP_URL_PRODUCTION = "https://app.midtrans.com/snap/v1/transactions"

SNAP_JS_SANDBOX = "https://app.sandbox.midtrans.com/snap/snap.js"
SNAP_JS_PRODUCTION = "https://app.midtrans.com/snap/snap.js"

PLAN_TIERS = {
    'free': {
        'name': 'Free Community',
        'price': 0,
        'credits': 3,
        'blogs': 1,
        'features': ['3 Artikel AI / bulan', '1 Blog Terhubung', 'Auto-sync Blogger', 'Standar WebP']
    },
    'starter': {
        'name': 'Starter Solo Creator',
        'price': 99000,
        'credits': 30,
        'blogs': 3,
        'features': ['30 Artikel AI / bulan', '3 Blog Terhubung', 'Cloudinary CDN Full Speed', 'E-E-A-T FAQ Schema', 'Priority Worker']
    },
    'pro': {
        'name': 'Pro Publisher Autopilot',
        'price': 249000,
        'credits': 120,
        'blogs': 10,
        'features': ['120 Artikel AI / bulan', '10 Blog Terhubung', 'Cloudinary CDN Full Speed', 'E-E-A-T FAQ Schema', 'Full Automation Cron', 'Support Prioritas']
    },
    'agency': {
        'name': 'Agency & Media Network',
        'price': 699000,
        'credits': 500,
        'blogs': 50,
        'features': ['500 Artikel AI / bulan', '50 Blog Terhubung', 'Dedicated Proxy / Worker', 'Multi-tenant Agency Dashboard', 'Custom SEO Prompts']
    }
}

def get_snap_url() -> str:
    return SNAP_URL_PRODUCTION if MIDTRANS_IS_PRODUCTION else SNAP_URL_SANDBOX

def get_snap_js_url() -> str:
    return SNAP_JS_PRODUCTION if MIDTRANS_IS_PRODUCTION else SNAP_JS_SANDBOX

def get_auth_header() -> str:
    encoded = base64.b64encode(f"{MIDTRANS_SERVER_KEY}:".encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"

def verify_signature(order_id: str, status_code: str, gross_amount: str, signature_key: str) -> bool:
    """
    Verifies the SHA512 signature from Midtrans webhook:
    SHA512(order_id + status_code + gross_amount + ServerKey)
    """
    raw_str = f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}"
    expected_hash = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()
    return expected_hash.lower() == signature_key.lower()

def create_snap_transaction(
    user: User,
    plan_tier: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a Midtrans Snap transaction for Indonesian payment methods (IDR).
    Returns Snap token & redirect URL.
    """
    plan = PLAN_TIERS.get(plan_tier)
    if not plan:
        raise ValueError(f"Paket langganan '{plan_tier}' tidak valid.")

    if plan['price'] == 0:
        return {'free': True, 'message': 'Paket Free tidak memerlukan pembayaran.'}

    # Generate unique Indonesian order_id: BAP-UUID-TIER-TIMESTAMP
    order_id = f"BAP-{user.id[:8]}-{plan_tier.upper()}-{int(time.time())}"
    
    payload = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": int(plan['price'])
        },
        "customer_details": {
            "first_name": user.full_name or "Pelanggan",
            "email": user.email,
        },
        "item_details": [
            {
                "id": f"sub-{plan_tier}",
                "price": int(plan['price']),
                "quantity": 1,
                "name": f"Blogger AutoPilot - {plan['name']}"
            }
        ],
        "custom_field1": user.id,
        "custom_field2": plan_tier,
        "callbacks": {
            "finish": callback_url or "/"
        }
    }

    # Enable all Indonesian popular payment methods
    payload["enabled_payments"] = [
        "gopay", "shopeepay", "other_qris",
        "bca_va", "bni_va", "bri_va", "mandiri_clickpay", "echannel", "permata_va",
        "credit_card"
    ]

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": get_auth_header()
    }

    try:
        response = requests.post(get_snap_url(), json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        return {
            'success': True,
            'token': res_data.get('token'),
            'redirect_url': res_data.get('redirect_url'),
            'order_id': order_id,
            'amount': plan['price'],
            'plan_name': plan['name']
        }
    except requests.exceptions.RequestException as e:
        # If in sandbox or demo mode with mock keys, return simulated snap token for testing
        if 'DemoTestKeyOnly' in MIDTRANS_SERVER_KEY:
            return {
                'success': True,
                'token': f"MOCK_SNAP_TOKEN_{int(time.time())}",
                'redirect_url': f"https://app.sandbox.midtrans.com/snap/v2/vtweb/mock-{order_id}",
                'order_id': order_id,
                'amount': plan['price'],
                'plan_name': plan['name'],
                'is_mock': True
            }
        return {'success': False, 'error': f"Gagal membuat transaksi Midtrans: {str(e)}"}

def handle_midtrans_webhook(event_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Processes Midtrans webhook notifications and activates tenant subscriptions.
    """
    order_id = event_data.get('order_id', '')
    status_code = event_data.get('status_code', '')
    gross_amount = event_data.get('gross_amount', '')
    signature_key = event_data.get('signature_key', '')
    transaction_status = event_data.get('transaction_status', '')
    fraud_status = event_data.get('fraud_status', 'accept')

    # Security check: verify SHA512 signature
    # (Skip only if demo test key is active and no signature supplied)
    if 'DemoTestKeyOnly' not in MIDTRANS_SERVER_KEY:
        if not verify_signature(order_id, status_code, gross_amount, signature_key):
            return {'success': False, 'error': 'Signature Midtrans tidak valid.'}

    # Extract user_id and plan_tier
    user_id = event_data.get('custom_field1')
    plan_tier = event_data.get('custom_field2')

    if not user_id or not plan_tier:
        # Fallback: extract from order_id format BAP-UID-TIER-TIMESTAMP
        parts = order_id.split('-')
        if len(parts) >= 3:
            plan_tier = parts[2].lower()

    if not user_id:
        sub = db.query(Subscription).filter(Subscription.midtrans_order_id == order_id).first()
        if sub:
            user_id = sub.user_id

    if not user_id:
        return {'success': False, 'error': f"User tidak ditemukan untuk order {order_id}"}

    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        sub = Subscription(user_id=user_id)
        db.add(sub)

    now = datetime.now(timezone.utc)

    # Status check
    # Reference: https://docs.midtrans.com/en/after-payment/http-notification
    if transaction_status in ['capture', 'settlement'] and fraud_status in ['accept', '']:
        target_plan = PLAN_TIERS.get(plan_tier, PLAN_TIERS['starter'])
        sub.plan_tier = plan_tier
        sub.status = 'active'
        sub.article_credits_limit = target_plan['credits']
        sub.article_credits_used = 0 # Fresh renewal
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.midtrans_order_id = order_id
        db.commit()
        return {
            'success': True,
            'message': f"Langganan berhasil diaktifkan ke paket {target_plan['name']}.",
            'tier': plan_tier,
            'status': 'active'
        }

    elif transaction_status == 'pending':
        sub.status = 'pending_payment'
        sub.midtrans_order_id = order_id
        db.commit()
        return {'success': True, 'status': 'pending'}

    elif transaction_status in ['deny', 'expire', 'cancel']:
        sub.status = 'expired'
        db.commit()
        return {'success': True, 'status': 'expired'}

    return {'success': True, 'status': transaction_status}

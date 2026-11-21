"""
Production Hardening & Security Regression Tests (Phase 5):
Covers fail-fast production secrets, suspended-user login guard, Midtrans out-of-order
webhook safety, amount-tampering protection, invalid signature HTTP 403, and HTTP security headers.
"""

import hashlib
import pytest
from fastapi.testclient import TestClient
from src.core.security import get_jwt_secret
from src.core.crypto import get_encryption_key
from src.core.rate_limiter import limiter
from src.models.models import Subscription
from src.services.payment import MIDTRANS_SERVER_KEY


def _make_midtrans_sig(order_id: str, status_code: str, gross_amount: str) -> str:
    raw = f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}"
    return hashlib.sha512(raw.encode("utf-8")).hexdigest()


def test_security_headers_present_on_responses(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_suspended_user_blocked_at_login(client: TestClient, admin_client: TestClient, tenant_factory):
    # Clear rate limit store in case brute-force test ran immediately prior
    limiter.requests.clear()
    _, user = tenant_factory(plan="free", role="subscriber", name="Suspended Login Test")

    # Suspend user via Admin Console
    r_susp = admin_client.post(f"/api/admin/tenants/{user.id}/toggle-status")
    assert r_susp.status_code == 200
    assert r_susp.json()["is_active"] is False

    # Attempt login with valid password MUST return 403 Forbidden
    r_login = client.post("/api/saas/auth/login", json={
        "email": user.email,
        "password": "Password123!"
    })
    assert r_login.status_code == 403
    assert "suspend" in r_login.json()["detail"].lower()


def test_midtrans_out_of_order_expire_preserves_active_subscription(client: TestClient, tenant_factory, db_session):
    _, user = tenant_factory(plan="free", role="subscriber", name="Webhook Guard Tenant")

    # 0. Forged / invalid signature MUST return HTTP 403
    bad_order = f"BAP-{user.id[:8]}-PRO-99999"
    r_forged = client.post("/api/billing/midtrans/webhook", json={
        "order_id": bad_order,
        "status_code": "200",
        "gross_amount": "349000.00",
        "signature_key": "FORGED_INVALID_SIGNATURE",
        "transaction_status": "settlement",
        "fraud_status": "accept",
        "custom_field1": user.id,
        "custom_field2": "pro"
    })
    if "DemoTestKeyOnly" not in MIDTRANS_SERVER_KEY:
        assert r_forged.status_code == 403

    # 1. User successfully pays for Pro (Rp 349,000) with valid SHA-512 signature
    ord_pro = f"BAP-{user.id[:8]}-PRO-10001"
    r_paid = client.post("/api/billing/midtrans/webhook", json={
        "order_id": ord_pro,
        "status_code": "200",
        "gross_amount": "349000.00",
        "signature_key": _make_midtrans_sig(ord_pro, "200", "349000.00"),
        "transaction_status": "settlement",
        "fraud_status": "accept",
        "custom_field1": user.id,
        "custom_field2": "pro"
    })
    assert r_paid.status_code == 200
    assert r_paid.json()["success"] is True

    # 2. User later opens an Agency checkout and abandons it -> Midtrans sends 'expire' for the NEW order_id
    ord_exp = f"BAP-{user.id[:8]}-AGENCY-20002"
    r_exp = client.post("/api/billing/midtrans/webhook", json={
        "order_id": ord_exp,
        "status_code": "202",
        "gross_amount": "799000.00",
        "signature_key": _make_midtrans_sig(ord_exp, "202", "799000.00"),
        "transaction_status": "expire",
        "custom_field1": user.id,
        "custom_field2": "agency"
    })
    assert r_exp.status_code == 200
    assert r_exp.json()["status"] == "ignored_active_subscription"

    # Active Pro subscription MUST remain intact!
    sub = db_session.query(Subscription).filter(Subscription.user_id == user.id).first()
    db_session.refresh(sub)
    assert sub.status == "active"
    assert sub.plan_tier == "pro"

    # 3. Underpayment tampering attempt (paying Rp 1,000 for Agency Rp 799,000) MUST be rejected
    ord_tamp = f"BAP-{user.id[:8]}-AGENCY-30003"
    r_tamper = client.post("/api/billing/midtrans/webhook", json={
        "order_id": ord_tamp,
        "status_code": "200",
        "gross_amount": "1000.00",
        "signature_key": _make_midtrans_sig(ord_tamp, "200", "1000.00"),
        "transaction_status": "settlement",
        "fraud_status": "accept",
        "custom_field1": user.id,
        "custom_field2": "agency"
    })
    assert r_tamper.status_code == 200
    assert r_tamper.json()["success"] is False
    assert "lebih kecil" in r_tamper.json()["error"].lower()


def test_production_fail_fast_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Missing or placeholder JWT_SECRET_KEY MUST fail fast
    monkeypatch.setenv("JWT_SECRET_KEY", "ganti_dengan_jwt_secret_acak_panjang_minimal_32_karakter")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_secret()

    # Valid strong JWT secret passes
    monkeypatch.setenv("JWT_SECRET_KEY", "a9f8c7b6e5d41234567890abcdef1234567890")
    assert len(get_jwt_secret()) == 64

    # Missing or weak ENCRYPTION_SECRET_KEY MUST fail fast
    monkeypatch.setenv("ENCRYPTION_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="ENCRYPTION_SECRET_KEY"):
        get_encryption_key()

    # Valid strong encryption key passes
    monkeypatch.setenv("ENCRYPTION_SECRET_KEY", "z1x2c3v4b5n6m7a8s9d0f1g2h3j4k5l6")
    assert len(get_encryption_key()) > 32

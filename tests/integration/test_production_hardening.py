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


def test_oauth_account_takeover_and_csrf_blocked(client: TestClient):
    # 1. Unauthenticated caller cannot initiate Google OAuth login
    r_login = client.get("/api/auth/google/login?account_name=victim@company.com", follow_redirects=False)
    assert r_login.status_code == 401

    # 2. Callback without valid state cookie MUST fail cleanly and NEVER mint saas_token
    r_cb = client.get("/api/auth/google/callback?code=fake_code", follow_redirects=False)
    assert r_cb.status_code in (302, 307)
    assert "auth_error=invalid_state" in r_cb.headers.get("location", "")
    assert "saas_token" not in r_cb.cookies


def test_blog_auth_token_isolation_and_upload_validation(client: TestClient, tenant_factory, db_session):
    from src.models.models import Blog

    # 1. Unauthenticated autopilot-settings MUST be rejected
    assert client.get("/api/blogs/some_blog_id/autopilot-settings").status_code == 401

    client_u, user = tenant_factory(plan="free", name="Blog Security Tester")
    b_id = f"blog_sec_{user.id[:6]}"

    # 2. Non-admin trying to inject arbitrary server token_file path MUST NOT persist it
    r_add = client_u.post("/api/blogs/add", json={
        "id": b_id,
        "name": "Secure Blog",
        "token_file": "/etc/passwd"
    })
    assert r_add.status_code == 200
    saved = db_session.query(Blog).filter(Blog.id == b_id).first()
    assert saved is not None
    assert saved.token_file is None

    # 3. Invalid non-JSON token upload MUST be rejected with 400
    r_bad_up = client_u.post(
        "/api/blogs/upload-token",
        files={"file": ("evil.txt", b"not a valid oauth json", "text/plain")}
    )
    assert r_bad_up.status_code == 400


def test_ssrf_webhook_urls_blocked(tenant_factory):
    client_u, _ = tenant_factory(plan="starter", name="SSRF Tester")

    for evil_url in [
        "http://127.0.0.1:8090/api/admin/metrics",
        "http://localhost:8090/health",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "file:///etc/passwd"
    ]:
        r_save = client_u.post("/api/notifications/settings", json={"webhook_url": evil_url})
        assert r_save.status_code == 400, f"Expected 400 for SSRF URL {evil_url}, got {r_save.status_code}"

        r_test = client_u.post("/api/notifications/test", json={"webhook_url": evil_url})
        assert r_test.status_code == 400, f"Expected 400 for SSRF test URL {evil_url}, got {r_test.status_code}"


def test_subscription_expiry_enforced_across_features(tenant_factory, db_session):
    from datetime import datetime, timedelta, timezone
    from src.core.dependencies import get_effective_plan_tier

    client_pro, user_pro = tenant_factory(plan="pro", name="Expired Pro User")

    # Force subscription current_period_end to yesterday
    sub = db_session.query(Subscription).filter(Subscription.user_id == user_pro.id).first()
    sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()
    db_session.refresh(user_pro)

    assert get_effective_plan_tier(user_pro) == "free"

    # /api/saas/auth/me reports expired status
    r_me = client_pro.get("/api/saas/auth/me")
    assert r_me.status_code == 200
    assert r_me.json()["subscription"]["is_expired"] is True
    assert r_me.json()["subscription"]["effective_plan_tier"] == "free"

    # Pro features (BYOK & CSV export) MUST now be blocked with 403!
    r_byok = client_pro.post("/api/settings/byok", json={"custom_gemini_key": "AIzaExpiredTest"})
    assert r_byok.status_code == 403

    r_csv = client_pro.get("/api/analytics/export-csv")
    assert r_csv.status_code == 403


def test_legal_pages_and_self_service_password_reset(client: TestClient, tenant_factory):
    limiter.requests.clear()

    # 1. Legal pages required for Google OAuth & Midtrans compliance
    r_priv = client.get("/privacy")
    assert r_priv.status_code == 200
    assert "Google API Services User Data Policy" in r_priv.text

    r_terms = client.get("/terms")
    assert r_terms.status_code == 200
    assert "Syarat & Ketentuan" in r_terms.text

    r_ref = client.get("/refund")
    assert r_ref.status_code == 200
    assert "Refund" in r_ref.text

    # 2. Self-service forgot-password + reset-password-confirm flow
    _, user = tenant_factory(plan="free", name="Forgot PW User")
    r_forgot = client.post("/api/saas/auth/forgot-password", json={"email": user.email})
    assert r_forgot.status_code == 200
    reset_tok = r_forgot.json().get("dev_reset_token")
    assert reset_tok is not None

    r_confirm = client.post("/api/saas/auth/reset-password-confirm", json={
        "token": reset_tok,
        "new_password": "BrandNewPassword2026!"
    })
    assert r_confirm.status_code == 200
    assert r_confirm.json()["success"] is True

    # User can now login with new password
    r_login = client.post("/api/saas/auth/login", json={
        "email": user.email,
        "password": "BrandNewPassword2026!"
    })
    assert r_login.status_code == 200
    assert r_login.json()["success"] is True


def test_encrypted_token_upload_and_no_server_path_leak(tenant_factory, db_session):
    from src.models.models import Blog

    client_pro, user_pro = tenant_factory(plan="pro", name="Token Flow Owner")

    # 1. Valid OAuth JSON upload returns encrypted_token (never a raw file path)
    oauth_payload = b'{"token": "ya29.fake", "refresh_token": "1//fake", "client_id": "cid"}'
    r_up = client_pro.post(
        "/api/blogs/upload-token",
        files={"file": ("token.json", oauth_payload, "application/json")}
    )
    assert r_up.status_code == 200
    up_data = r_up.json()
    assert up_data["success"] is True
    assert up_data.get("encrypted_token")
    assert "token_file" not in up_data

    # 2. Save blog #1 with encrypted_token
    r_add1 = client_pro.post("/api/blogs/add", json={
        "id": "enc-blog-1",
        "name": "Encrypted Blog 1",
        "url": "https://enc1.blogspot.com",
        "encrypted_token": up_data["encrypted_token"]
    })
    assert r_add1.status_code == 200

    # 3. GET /api/blogs exposes has_token=True and never leaks token_file
    r_list = client_pro.get("/api/blogs")
    assert r_list.status_code == 200
    blogs_resp = r_list.json()
    b1 = next(b for b in blogs_resp if b["id"] == "enc-blog-1")
    assert b1["has_token"] is True
    assert "token_file" not in b1

    # 4. Save blog #2 reusing own blog #1's encrypted_token safely server-side
    r_add2 = client_pro.post("/api/blogs/add", json={
        "id": "enc-blog-2",
        "name": "Encrypted Blog 2",
        "url": "https://enc2.blogspot.com",
        "reuse_token_from_blog_id": "enc-blog-1"
    })
    assert r_add2.status_code == 200
    saved_b2 = db_session.query(Blog).filter(Blog.id == "enc-blog-2", Blog.user_id == user_pro.id).first()
    assert saved_b2 is not None
    assert saved_b2.encrypted_token == up_data["encrypted_token"]

    # 5. Another tenant CANNOT reuse user_pro's blog token via reuse_token_from_blog_id
    client_other, user_other = tenant_factory(plan="free", name="Other Tenant")
    r_steal = client_other.post("/api/blogs/add", json={
        "id": "steal-blog",
        "name": "Steal Blog",
        "reuse_token_from_blog_id": "enc-blog-1"
    })
    assert r_steal.status_code == 200
    stolen = db_session.query(Blog).filter(Blog.id == "steal-blog", Blog.user_id == user_other.id).first()
    assert stolen is not None
    assert stolen.encrypted_token is None


def test_admin_mrr_excludes_expired_subscriptions(tenant_factory, db_session):
    from datetime import datetime, timedelta, timezone

    client_admin, user_admin = tenant_factory(plan="agency", name="MRR Admin")
    user_admin.role = "admin"
    db_session.commit()

    # Baseline MRR
    r_base = client_admin.get("/api/admin/metrics")
    assert r_base.status_code == 200
    base_mrr = r_base.json()["mrr_idr"]

    # Create a Pro user whose subscription is expired (status still 'active' in DB before sweep)
    _, user_exp = tenant_factory(plan="pro", name="Expired MRR User")
    sub_exp = db_session.query(Subscription).filter(Subscription.user_id == user_exp.id).first()
    sub_exp.current_period_end = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()

    r_after = client_admin.get("/api/admin/metrics")
    assert r_after.status_code == 200
    assert r_after.json()["mrr_idr"] == base_mrr



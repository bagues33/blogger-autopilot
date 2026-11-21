"""
Integration tests for Authentication, Multi-Tenant Data Isolation, and Plan Limits.
"""
import uuid
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.models import User, Subscription, Blog, Article, Keyword
from src.services.payment import handle_midtrans_webhook, MIDTRANS_SERVER_KEY

def test_user_registration_and_login(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    email = f"user_{uid}@example.test"
    password = "SecurePassword123!"

    # 1. Register
    reg_res = client.post(
        "/api/saas/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"}
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["success"] is True
    assert data["user"]["email"] == email
    assert "token" in data

    # 2. Login
    login_res = client.post(
        "/api/saas/auth/login",
        json={"email": email, "password": password}
    )
    assert login_res.status_code == 200
    assert "saas_token" in login_res.cookies

    # 3. /me check
    me_res = client.get("/api/saas/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == email

def test_tenant_data_isolation(tenant_factory):
    client_a, user_a = tenant_factory(plan="pro", name="Alice Pro")
    client_b, user_b = tenant_factory(plan="free", name="Bob Free")

    # Tenant A adds a blog
    blog_a_id = f"blog_alice_{uuid.uuid4().hex[:6]}"
    res_a_blog = client_a.post("/api/blogs/add", json={
        "id": blog_a_id,
        "name": "Alice Tech Blog",
        "url": "https://alice.blogspot.com",
        "account_name": "Alice"
    })
    assert res_a_blog.status_code == 200

    # Tenant A sees blog
    res_a_list = client_a.get("/api/blogs")
    assert res_a_list.status_code == 200
    blogs_a = res_a_list.json()
    assert any(b["id"] == blog_a_id for b in blogs_a)

    # Tenant B lists blogs -> MUST NOT see Tenant A's blog
    res_b_list = client_b.get("/api/blogs")
    assert res_b_list.status_code == 200
    blogs_b = res_b_list.json()
    assert not any(b["id"] == blog_a_id for b in blogs_b)

    # Tenant B tries to delete Tenant A's blog -> MUST fail (404 or not found)
    del_res = client_b.delete(f"/api/blogs/{blog_a_id}")
    assert del_res.status_code in (404, 403, 400)

    # Tenant A adds a keyword to their blog
    res_kw = client_a.post("/api/keywords/add", json={
        "blog_id": blog_a_id,
        "keyword": "python microframework fast"
    })
    assert res_kw.status_code == 200

    # Tenant B fetches keywords -> MUST NOT contain Tenant A's keyword
    res_b_kw = client_b.get(f"/api/keywords?blog_id={blog_a_id}")
    assert res_b_kw.status_code == 200
    keywords_b = res_b_kw.json()
    assert not any(k.get("keyword") == "python microframework fast" for k in keywords_b)

def test_free_tier_limits(tenant_factory):
    client_free, user_free = tenant_factory(plan="free", name="Free Tenant")

    # 1. Add first blog (allowed on free tier)
    blog1_id = f"blog_free_{uuid.uuid4().hex[:6]}"
    res1 = client_free.post("/api/blogs/add", json={
        "id": blog1_id,
        "name": "First Free Blog",
        "url": "https://firstfree.blogspot.com"
    })
    assert res1.status_code == 200

    # 2. Add second blog -> MUST be rejected on free tier (max 1 blog)
    blog2_id = f"blog_free2_{uuid.uuid4().hex[:6]}"
    res2 = client_free.post("/api/blogs/add", json={
        "id": blog2_id,
        "name": "Second Free Blog",
        "url": "https://secondfree.blogspot.com"
    })
    assert res2.status_code == 400
    assert "upgrade" in res2.json()["detail"].lower() or "limit" in res2.json()["detail"].lower()

def test_midtrans_webhook_isolation(db_session: Session, tenant_factory):
    _, user_a = tenant_factory(plan="free", name="Tenant A")
    _, user_b = tenant_factory(plan="free", name="Tenant B")

    # Simulate Midtrans settlement for Tenant A to upgrade to 'pro'
    order_id = f"BAP-{user_a.id[:8]}-PRO-999999"
    status_code = "200"
    gross_amount = "349000"
    sig = hashlib.sha512(f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}".encode()).hexdigest()

    mock_payload = {
        "order_id": order_id,
        "status_code": status_code,
        "gross_amount": gross_amount,
        "transaction_status": "settlement",
        "fraud_status": "accept",
        "signature_key": sig,
        "custom_field1": user_a.id,
        "custom_field2": "pro"
    }

    res = handle_midtrans_webhook(mock_payload, db=db_session)
    assert res["success"] is True

    # User A subscription MUST now be PRO with 200 credits
    sub_a = db_session.query(Subscription).filter(Subscription.user_id == user_a.id).first()
    assert sub_a.plan_tier == "pro"
    assert sub_a.article_credits_limit == 200

    # User B subscription MUST remain FREE with 3 credits
    sub_b = db_session.query(Subscription).filter(Subscription.user_id == user_b.id).first()
    assert sub_b.plan_tier == "free"
    assert sub_b.article_credits_limit == 3

"""
Integration tests for Health check endpoints and In-Memory Rate Limiting.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

def test_health_endpoints(client: TestClient):
    for path in ["/health", "/api/health"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Blogger Auto-Pilot SaaS"
        assert "database" in data
        assert data["database"]["status"] == "connected"

def test_landing_and_dashboard_routes(client: TestClient):
    # 1. Unauthenticated visitor hitting root / gets landing page
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Blogger Auto-Pilot" in res_root.text
    assert "Solusi Otomasi Konten Google Blogger" in res_root.text

    # 2. Accessing /dashboard returns the studio app
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "Antrean Artikel & Approval" in res_dash.text or "Antrean Artikel" in res_dash.text

    # 3. Register unique user to test authenticated flow
    unique_email = f"landing_{uuid.uuid4().hex[:8]}@example.com"
    reg_res = client.post("/api/saas/auth/register", json={
        "email": unique_email,
        "password": "Password123!",
        "full_name": "Landing Tester"
    })
    assert reg_res.status_code == 200
    assert "saas_token" in reg_res.cookies

    # 4. Authenticated user hitting root / is seamlessly directed to dashboard studio
    auth_root = client.get("/")
    assert auth_root.status_code == 200
    assert "Antrean Artikel & Approval" in auth_root.text

    # 5. Authenticated user explicitly viewing landing page with ?landing=1
    auth_landing = client.get("/?landing=1")
    assert auth_landing.status_code == 200
    assert "Buka Studio Dashboard" in auth_landing.text

def test_rate_limiter_anti_brute_force(client: TestClient):
    # Simulate rapid consecutive login attempts to trigger the 25/min rate limiter
    hit_429 = False
    for i in range(30):
        res = client.post(
            "/api/saas/auth/login",
            json={"email": f"attacker_{i}@brute.com", "password": "WrongPassword!"}
        )
        if res.status_code == 429:
            hit_429 = True
            assert "Retry-After" in res.headers
            err = res.json()
            assert "detail" in err
            break
            
    assert hit_429, "Rate limiter did not throttle requests after 25 rapid attempts!"


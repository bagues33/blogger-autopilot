"""
Test Suite for:
1. Health Probes (/health and /api/health)
2. In-Memory Anti-Brute Force Rate Limiter (HTTP 429 Too Many Requests)
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar
import uuid

BASE_URL = "http://127.0.0.1:8090"

def test_health_endpoints():
    print("--- Testing Health Endpoints ---")
    for path in ["/health", "/api/health"]:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            data = json.loads(res.read().decode())
            assert data["status"] == "healthy"
            assert data["service"] == "Blogger Auto-Pilot SaaS"
            assert data["database"]["status"] == "connected"
            print(f"✓ {path} probe passed: status=healthy, db={data['database']['engine']}")

def test_rate_limiter():
    print("--- Testing Rate Limiter (Anti-Brute Force) ---")
    rate_limited_hit = False

    # Simulate 30 rapid login attempts to trigger 25/min limit
    for i in range(30):
        req = urllib.request.Request(
            f"{BASE_URL}/api/saas/auth/login",
            data=json.dumps({"email": "attacker@brute.com", "password": "WrongPassword!"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as res:
                pass
        except urllib.error.HTTPError as e:
            if e.code == 429:
                rate_limited_hit = True
                assert "Retry-After" in e.headers
                err_data = json.loads(e.read().decode())
                print(f"✓ Rate Limiter triggered at attempt #{i+1}: HTTP 429 - {err_data.get('detail')}")
                break

    assert rate_limited_hit, "Rate limiter did not throttle requests after 25 rapid attempts!"
    print("✓ Anti-Brute Force Protection verified.")

if __name__ == "__main__":
    test_health_endpoints()
    test_rate_limiter()
    print("\n🎉 ALL HEALTH & RATE LIMITER TESTS PASSED 100%!")

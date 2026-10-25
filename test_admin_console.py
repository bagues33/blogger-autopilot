"""
Test Suite for:
1. Superadmin Master Console API (/api/admin/*)
2. Admin Access Control & Permission Guard (HTTP 403 for non-admins)
3. SEO Schema & JSON-LD Auto-Injector (schema_builder.py)
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar
import uuid
from db_saas import SessionLocal
from models_saas import User, Subscription, Blog, Article, Keyword
from schema_builder import inject_schema_if_missing, extract_faq_qa_pairs

BASE_URL = "http://127.0.0.1:8090"

def test_schema_builder():
    print("--- Testing SEO Schema Builder ---")
    sample_html = """
    <h2>Pengantar Panduan</h2>
    <p>Ini adalah artikel komprehensif tentang topik teknologi.</p>
    <h2>Pertanyaan yang Sering Diajukan</h2>
    <h3>Berapa biaya pembuatan blog profesional?</h3>
    <p>Biaya pembuatan blog berkisar antara Rp 100.000 hingga Rp 1.000.000 tergantung domain dan hosting.</p>
    <h3>Apakah Google Blogger gratis selamanya?</h3>
    <p>Ya, Google Blogger sepenuhnya gratis tanpa biaya bulanan.</p>
    """
    
    faqs = extract_faq_qa_pairs(sample_html)
    assert len(faqs) == 2
    assert "biaya" in faqs[0]['question'].lower()
    print(f"✓ Extracted {len(faqs)} FAQ questions accurately.")

    injected = inject_schema_if_missing(
        sample_html,
        title="Panduan Lengkap Blogger 2026",
        meta_description="Deskripsi singkat panduan lengkap",
        author_name="Pakar SEO"
    )
    assert 'application/ld+json' in injected
    assert 'schema.org' in injected
    assert 'FAQPage' in injected
    assert 'Article' in injected
    print("✓ Schema injection valid: Includes Article & FAQPage JSON-LD graph.")

def test_admin_console_api():
    print("--- Testing Superadmin Console API ---")
    
    # 1. Test as Default Admin (admin@bagustech.id)
    cj_admin = http.cookiejar.CookieJar()
    opener_admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_admin))

    # Metrics
    req = urllib.request.Request(f"{BASE_URL}/api/admin/metrics")
    with opener_admin.open(req) as res:
        metrics = json.loads(res.read().decode())
        assert "total_tenants" in metrics
        assert "mrr_idr" in metrics
        assert "tier_breakdown" in metrics
        print(f"✓ Admin Metrics: {metrics['total_tenants']} tenants | Est. MRR: Rp {metrics['mrr_idr']:,.0f}")

    # Tenants list
    req = urllib.request.Request(f"{BASE_URL}/api/admin/tenants")
    with opener_admin.open(req) as res:
        tenants_data = json.loads(res.read().decode())
        assert "tenants" in tenants_data
        assert tenants_data["count"] > 0
        print(f"✓ Admin Tenants List: Retrieved {tenants_data['count']} tenant records.")

    # 2. Register a standard non-admin subscriber to test permissions
    cj_user = http.cookiejar.CookieJar()
    opener_user = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_user))
    
    user_email = f"standard_{uuid.uuid4().hex[:6]}@domain.id"
    reg_req = urllib.request.Request(
        f"{BASE_URL}/api/saas/auth/register",
        data=json.dumps({"email": user_email, "password": "UserPassword123!", "full_name": "Standard User"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_user.open(reg_req) as res:
        reg_res = json.loads(res.read().decode())
        target_user_id = reg_res["user"]["id"]
        print(f"✓ Registered standard user: {user_email} (ID: {target_user_id})")

    # Non-admin trying to access /api/admin/metrics MUST be denied with HTTP 403
    forbidden_req = urllib.request.Request(f"{BASE_URL}/api/admin/metrics")
    try:
        with opener_user.open(forbidden_req) as res:
            assert False, "Non-admin was allowed to access admin metrics!"
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Expected HTTP 403, got {e.code}"
        print("✓ Security Guard verified: Non-admin received HTTP 403 Forbidden.")

    # 3. Admin manually upgrades standard user to 'pro'
    upgrade_payload = {"plan_tier": "pro", "credits_limit": 150}
    upg_req = urllib.request.Request(
        f"{BASE_URL}/api/admin/tenants/{target_user_id}/plan",
        data=json.dumps(upgrade_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_admin.open(upg_req) as res:
        upg_res = json.loads(res.read().decode())
        assert upg_res["success"] is True
        assert upg_res["plan_tier"] == "pro"
        assert upg_res["credits_limit"] == 150
        print(f"✓ Admin manually upgraded user {user_email} to PRO (150 credits)")

    # 4. Admin adds 25 bonus credits
    bonus_payload = {"amount": 25}
    bonus_req = urllib.request.Request(
        f"{BASE_URL}/api/admin/tenants/{target_user_id}/credits",
        data=json.dumps(bonus_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener_admin.open(bonus_req) as res:
        bonus_res = json.loads(res.read().decode())
        assert bonus_res["success"] is True
        assert bonus_res["new_limit"] == 175
        print("✓ Admin successfully granted 25 bonus credits (New limit: 175)")

    # 5. Admin toggles user status (suspend/reactivate)
    toggle_req = urllib.request.Request(
        f"{BASE_URL}/api/admin/tenants/{target_user_id}/toggle-status",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with opener_admin.open(toggle_req) as res:
        toggle_res = json.loads(res.read().decode())
        assert toggle_res["success"] is True
        assert toggle_res["is_active"] is False
        print("✓ Admin suspended user account successfully.")

    print("\n🎉 ALL ADMIN CONSOLE & SCHEMA TESTS PASSED 100%!")

if __name__ == "__main__":
    test_schema_builder()
    test_admin_console_api()

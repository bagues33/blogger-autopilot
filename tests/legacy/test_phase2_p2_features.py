"""
End-to-End Automated Test Suite for Phase 2 (P2) Enterprise Features:
1. P2-1: Enterprise Audit Logging & Activity Trail System
2. P2-2: Bring-Your-Own-Key (BYOK) LLM Provider Integration
3. P2-3: Distributed Rate Limiting & Concurrency Task Queues
4. P2-4: Subscriber & Client-Facing Analytics Dashboard with PDF/Print Export
5. P2-5: Dynamic Niche-Aware AI Keyword Clustering Engine
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar
import uuid
import time

BASE_URL = "http://127.0.0.1:8090"

def create_tenant_client():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    return opener

def test_phase2_enterprise_features():
    print("=== STARTING FULL PHASE 2 (P2) ENTERPRISE SUITE ===")
    opener = create_tenant_client()
    tenant_email = f"enterprise_{uuid.uuid4().hex[:6]}@agency.id"

    # 1. Register Enterprise Tenant
    reg_req = urllib.request.Request(
        f"{BASE_URL}/api/saas/auth/register",
        data=json.dumps({
            "email": tenant_email,
            "password": "EnterprisePassword123!",
            "full_name": "Agency Director"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(reg_req) as res:
        reg_data = json.loads(res.read().decode())
        user_id = reg_data["user"]["id"]
        print(f"✓ Registered Enterprise Tenant: {tenant_email} (ID: {user_id})")

    # 2. Add Blog
    blog_id = f"blog_ent_{uuid.uuid4().hex[:6]}"
    blog_req = urllib.request.Request(
        f"{BASE_URL}/api/blogs",
        data=json.dumps({
            "id": blog_id,
            "name": "Tech Enterprise Journal",
            "url": f"https://{blog_id}.blogspot.com",
            "account_name": "Agency Google Account"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(blog_req) as res:
        b_data = json.loads(res.read().decode())
        assert b_data["success"] is True
        print(f"✓ Connected Blog: {blog_id}")

    # --- P2-5: Dynamic Niche-Aware AI Keyword Clustering ---
    print("\n--- Testing P2-5: AI Keyword Clustering Engine ---")
    kw_req = urllib.request.Request(
        f"{BASE_URL}/api/keywords/ai-suggest",
        data=json.dumps({
            "niche_seed": "Artificial Intelligence Tools",
            "blog_id": blog_id
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(kw_req) as res:
        kw_data = json.loads(res.read().decode())
        assert kw_data["success"] is True
        assert kw_data["added_count"] >= 5
        print(f"✓ AI Keyword Engine synthesized {kw_data['added_count']} targeted keywords (Dynamic AI: {kw_data.get('dynamic_ai')})")
        print(f"   Sample keywords: {kw_data['keywords'][:3]}")

    # --- P2-2: Bring-Your-Own-Key (BYOK) Integration ---
    print("\n--- Testing P2-2: BYOK LLM Provider Integration ---")
    byok_save_req = urllib.request.Request(
        f"{BASE_URL}/api/settings/byok",
        data=json.dumps({
            "custom_gemini_key": "AIzaSyFakeKeyForEnterpriseTesting12345",
            "custom_openai_key": "sk-proj-FakeOpenAIKeyForTesting99999"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(byok_save_req) as res:
        byok_res = json.loads(res.read().decode())
        assert byok_res["success"] is True
        assert byok_res["byok_active"] is True
        print("✓ BYOK custom keys saved successfully.")

    byok_get_req = urllib.request.Request(f"{BASE_URL}/api/settings/byok")
    with opener.open(byok_get_req) as res:
        byok_info = json.loads(res.read().decode())
        assert byok_info["byok_active"] is True
        assert byok_info["has_gemini"] is True
        assert byok_info["has_openai"] is True
        assert "AIza" in byok_info["masked_gemini"]
        print(f"✓ Masked Keys Verified: Gemini={byok_info['masked_gemini']}, OpenAI={byok_info['masked_openai']}")

    # --- P2-1: Enterprise Audit Logging & Activity Trail ---
    print("\n--- Testing P2-1: Enterprise Audit Trail System ---")
    # Change Autopilot Settings to generate audit event
    ap_req = urllib.request.Request(
        f"{BASE_URL}/api/blogs/autopilot-settings",
        data=json.dumps({
            "blog_id": blog_id,
            "autopilot_enabled": True,
            "publish_mode": "published",
            "schedule": "twice_daily"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(ap_req) as res:
        assert json.loads(res.read().decode())["success"] is True

    # Retrieve Audit Logs
    audit_req = urllib.request.Request(f"{BASE_URL}/api/audit-logs")
    with opener.open(audit_req) as res:
        audit_data = json.loads(res.read().decode())
        assert audit_data["success"] is True
        assert audit_data["total"] >= 2
        events = [l["event_type"] for l in audit_data["logs"]]
        print(f"✓ Audit logs recorded successfully ({audit_data['total']} events captured):")
        for log in audit_data["logs"][:4]:
            print(f"   • Event: {log['event_type']} | Entity: {log['entity_id']} | Date: {log['created_at']}")
        assert "byok.updated" in events
        assert "blog.autopilot_updated" in events

    # --- P2-4: Subscriber & Client-Facing Analytics Dashboard & PDF Export ---
    print("\n--- Testing P2-4: Analytics & ROI Reporting Engine ---")
    # Save a sample draft article first to verify calculation
    save_art_req = urllib.request.Request(
        f"{BASE_URL}/api/articles",
        data=json.dumps({
            "title": "Analisis Tren AI Enterprise Indonesia 2026",
            "target_keyword": "Artificial Intelligence Tools",
            "meta_description": "Ulasan komprehensif mengenai strategi adopsi AI di tingkat korporasi.",
            "content_html": "<p>Kecerdasan buatan kini menjadi pilar strategis dalam transformasi operasional modern di Indonesia.</p> " * 20,
            "labels": "AI, Teknologi",
            "blog_id": blog_id
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(save_art_req) as res:
        art_res = json.loads(res.read().decode())
        art_id = art_res["id"]
        print(f"✓ Article saved for ROI testing: ID={art_id}")

    # Check ROI endpoint
    roi_req = urllib.request.Request(f"{BASE_URL}/api/analytics/roi")
    with opener.open(roi_req) as res:
        roi_data = json.loads(res.read().decode())
        assert roi_data["success"] is True
        metrics = roi_data["metrics"]
        assert metrics["total_articles"] >= 1
        assert metrics["total_words"] > 0
        assert metrics["hours_saved"] > 0
        assert metrics["cost_saved_idr"] > 0
        print(f"✓ ROI Metrics Calculated:")
        print(f"   • Total Articles: {metrics['total_articles']}")
        print(f"   • Total Words   : {metrics['total_words']:,} kata")
        print(f"   • Hours Saved   : {metrics['hours_saved']} jam kerja")
        print(f"   • Budget Saved  : {metrics['cost_saved_formatted']}")

    # Check Printable Report HTML endpoint
    report_req = urllib.request.Request(f"{BASE_URL}/api/analytics/report")
    with opener.open(report_req) as res:
        report_html = res.read().decode()
        assert res.status == 200
        assert "Laporan Kinerja & Estimasi ROI Konten" in report_html
        assert "window.print()" in report_html
        print("✓ Printable PDF/Print ROI Report generated successfully.")

    # --- P2-3: Rate Limiting Throttling Verification ---
    print("\n--- Testing P2-3: Rate Limiting & Concurrency Throttling ---")
    throttled = False
    for i in range(15):
        sync_req = urllib.request.Request(
            f"{BASE_URL}/api/blogs/{blog_id}/sync-blogger-posts",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        try:
            with opener.open(sync_req) as res:
                pass
        except urllib.error.HTTPError as e:
            if e.code == 429:
                throttled = True
                assert "Retry-After" in e.headers
                err_data = json.loads(e.read().decode())
                print(f"✓ Endpoint throttled at attempt #{i+1}: HTTP 429 - {err_data.get('detail')}")
                break

    assert throttled, "Sync endpoint was not rate-limited after 10 requests!"
    print("✓ Rate Limiting Protection on High-Cost Endpoints verified.")

    print("\n🎉 ALL PHASE 2 (P2) ENTERPRISE CAPABILITIES VERIFIED 100%!")

if __name__ == "__main__":
    test_phase2_enterprise_features()

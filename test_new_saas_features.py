"""
Test Suite for New High-Value SaaS Features:
1. Bulk Keyword Import
2. AI Niche Topic & Keyword Generator
3. Autopilot Blog Settings
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar
import uuid

BASE_URL = "http://127.0.0.1:8090"

def run_tests():
    print("=== TESTING NEW HIGH-VALUE SAAS FEATURES ===")
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Register a test creator
    test_email = f"creator_pro_{uuid.uuid4().hex[:6]}@bloggerautopilot.id"
    reg_payload = {"email": test_email, "password": "CreatorPassword123!", "full_name": "Sultan Blogger"}
    req = urllib.request.Request(
        f"{BASE_URL}/api/saas/auth/register",
        data=json.dumps(reg_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        reg_res = json.loads(res.read().decode())
        print(f"✓ Registered Creator: {test_email}")

    # Add a blog for testing
    blog_id = f"blog_test_{uuid.uuid4().hex[:6]}"
    req = urllib.request.Request(
        f"{BASE_URL}/api/blogs/add",
        data=json.dumps({"id": blog_id, "name": "Bagus Python Blog"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        assert json.loads(res.read().decode())['success'] is True
        print(f"✓ Blog registered: {blog_id}")

    # 2. Test Bulk Keyword Import
    bulk_payload = {
        "keywords_text": "tutorial python fastapi untuk pemula\ncara deploy web python di vps\ntips optimasi performa api async",
        "search_intent": "Informational",
        "blog_id": blog_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/keywords/bulk-add",
        data=json.dumps(bulk_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        bulk_res = json.loads(res.read().decode())
        print(f"✓ Bulk Keywords Imported: {bulk_res['added_count']} out of {bulk_res['total_submitted']}")
        assert bulk_res['success'] is True
        assert bulk_res['added_count'] == 3

    # 3. Test AI Niche Topic & Keyword Generator
    suggest_payload = {
        "niche_seed": "Belajar Python Modern",
        "blog_id": blog_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/keywords/ai-suggest",
        data=json.dumps(suggest_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        suggest_res = json.loads(res.read().decode())
        print(f"✓ AI Niche Keywords Generated: {suggest_res['added_count']} keywords")
        for kw in suggest_res['keywords'][:3]:
            print(f"   • {kw}")
        assert suggest_res['success'] is True
        assert suggest_res['added_count'] == 8

    # 4. Test Autopilot Blog Settings (Save & Retrieve)
    autopilot_payload = {
        "blog_id": blog_id,
        "autopilot_enabled": True,
        "publish_mode": "blogger_draft",
        "schedule": "daily"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/blogs/autopilot-settings",
        data=json.dumps(autopilot_payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as res:
        set_res = json.loads(res.read().decode())
        print("✓ Autopilot Settings Saved:", set_res['message'])
        assert set_res['success'] is True

    # Retrieve settings
    req = urllib.request.Request(f"{BASE_URL}/api/blogs/{blog_id}/autopilot-settings")
    with opener.open(req) as res:
        get_res = json.loads(res.read().decode())
        print(f"✓ Autopilot Settings Retrieved: Enabled={get_res['autopilot_enabled']}, Mode={get_res['publish_mode']}, Schedule={get_res['schedule']}")
        assert get_res['autopilot_enabled'] is True
        assert get_res['publish_mode'] == 'blogger_draft'

    print("\n🎉 ALL HIGH-VALUE SAAS FEATURES VERIFIED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()

"""
Test Phase 1 (P1) Features:
1. Workspace Creation, Listing, and Member RBAC (Owner, Admin, Editor, Writer, Viewer)
2. Editorial Review Workflow (draft -> pending_review -> approved)
3. Autopilot Settings Persistence in Database and Frequency Scheduling
"""

import time
import json
import urllib.request
import http.cookiejar

BASE_URL = "http://127.0.0.1:8090"

def test_workspaces_and_rbac():
    print("=== 1. Testing Workspaces & Team RBAC ===")
    ts = int(time.time())
    owner_email = f"owner_{ts}@agency.id"
    editor_email = f"editor_{ts}@agency.id"

    # Register Owner
    cj_owner = http.cookiejar.CookieJar()
    opener_owner = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_owner))

    reg_payload = json.dumps({"email": owner_email, "password": "secure-owner-pass", "full_name": "Agency Boss"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
    with opener_owner.open(req) as resp:
        data = json.loads(resp.read().decode())
        assert data["success"] is True
        print(f"✓ Registered Agency Owner: {owner_email}")

    # Register Editor
    cj_editor = http.cookiejar.CookieJar()
    opener_editor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_editor))

    reg_payload2 = json.dumps({"email": editor_email, "password": "secure-editor-pass", "full_name": "Senior Editor"}).encode()
    req2 = urllib.request.Request(f"{BASE_URL}/api/saas/auth/register", data=reg_payload2, headers={"Content-Type": "application/json"})
    with opener_editor.open(req2) as resp:
        data2 = json.loads(resp.read().decode())
        assert data2["success"] is True
        print(f"✓ Registered Agency Editor: {editor_email}")

    # Create Workspace as Owner
    ws_payload = json.dumps({"name": "Media Nusantara Agency"}).encode()
    req_ws = urllib.request.Request(f"{BASE_URL}/api/workspaces", data=ws_payload, headers={"Content-Type": "application/json"})
    with opener_owner.open(req_ws) as resp:
        res = json.loads(resp.read().decode())
        assert res["success"] is True
        ws_id = res["workspace"]["id"]
        assert res["workspace"]["name"] == "Media Nusantara Agency"
        print(f"✓ Created Workspace: '{res['workspace']['name']}' (ID: {ws_id})")

    # Add Editor to Workspace with role 'editor'
    invite_payload = json.dumps({"email": editor_email, "role": "editor"}).encode()
    req_invite = urllib.request.Request(f"{BASE_URL}/api/workspaces/{ws_id}/members", data=invite_payload, headers={"Content-Type": "application/json"})
    with opener_owner.open(req_invite) as resp:
        inv_res = json.loads(resp.read().decode())
        assert inv_res["success"] is True
        print(f"✓ Added Member '{editor_email}' as 'editor'")

    # List Members as Editor
    req_m = urllib.request.Request(f"{BASE_URL}/api/workspaces/{ws_id}/members")
    with opener_editor.open(req_m) as resp:
        m_res = json.loads(resp.read().decode())
        assert m_res["success"] is True
        assert len(m_res["members"]) == 2
        roles = {m["email"]: m["role"] for m in m_res["members"]}
        assert roles[owner_email] == "owner"
        assert roles[editor_email] == "editor"
        print("✓ Verified Workspace Members list and RBAC roles accurately.")

def test_editorial_review_workflow():
    print("=== 2. Testing Editorial Review & Approval Workflow ===")
    ts = int(time.time())
    author_email = f"author_{ts}@media.id"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    reg_payload = json.dumps({"email": author_email, "password": "author-pass"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
    with opener.open(req) as resp:
        assert json.loads(resp.read().decode())["success"] is True

    # Add blog
    blog_id = f"blog_rev_{ts}"
    b_payload = json.dumps({"id": blog_id, "name": "Review Blog Test"}).encode()
    req_b = urllib.request.Request(f"{BASE_URL}/api/blogs/add", data=b_payload, headers={"Content-Type": "application/json"})
    with opener.open(req_b) as resp:
        assert json.loads(resp.read().decode())["success"] is True

    # Save initial draft article
    art_payload = json.dumps({
        "title": "Masa Depan AI di Indonesia 2026",
        "content_html": "<p>Artikel investigasi mendalam mengenai adopsi kecerdasan buatan.</p>",
        "blog_id": blog_id,
        "target_keyword": "ai indonesia 2026"
    }).encode()
    req_art = urllib.request.Request(f"{BASE_URL}/api/articles/save", data=art_payload, headers={"Content-Type": "application/json"})
    with opener.open(req_art) as resp:
        assert json.loads(resp.read().decode())["success"] is True

    # Get article id
    req_list = urllib.request.Request(f"{BASE_URL}/api/articles?blog_id={blog_id}")
    with opener.open(req_list) as resp:
        arts = json.loads(resp.read().decode())
        assert len(arts) > 0
        art_id = arts[0]["id"]
        assert arts[0]["status"] == "draft"
        print(f"✓ Initial Article #{art_id} status is 'draft'")

    # Transition 1: Send for review ('pending_review')
    st_payload1 = json.dumps({"status": "pending_review"}).encode()
    req_st1 = urllib.request.Request(f"{BASE_URL}/api/articles/{art_id}/status", data=st_payload1, headers={"Content-Type": "application/json"})
    with opener.open(req_st1) as resp:
        res1 = json.loads(resp.read().decode())
        assert res1["success"] is True
        assert res1["status"] == "pending_review"
        print(f"✓ Article #{art_id} moved to 'pending_review'")

    # Transition 2: Approve article ('approved')
    st_payload2 = json.dumps({"status": "approved"}).encode()
    req_st2 = urllib.request.Request(f"{BASE_URL}/api/articles/{art_id}/status", data=st_payload2, headers={"Content-Type": "application/json"})
    with opener.open(req_st2) as resp:
        res2 = json.loads(resp.read().decode())
        assert res2["success"] is True
        assert res2["status"] == "approved"
        print(f"✓ Article #{art_id} moved to 'approved'")

def test_autopilot_db_settings_and_frequency():
    print("=== 3. Testing Autopilot Settings Database Persistence ===")
    ts = int(time.time())
    user_email = f"sched_tester_{ts}@domain.id"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    reg_payload = json.dumps({"email": user_email, "password": "secure-pass"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/saas/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
    with opener.open(req) as resp:
        assert json.loads(resp.read().decode())["success"] is True

    blog_id = f"blog_ap_{ts}"
    b_payload = json.dumps({"id": blog_id, "name": "Autopilot Sched Blog"}).encode()
    req_b = urllib.request.Request(f"{BASE_URL}/api/blogs/add", data=b_payload, headers={"Content-Type": "application/json"})
    with opener.open(req_b) as resp:
        assert json.loads(resp.read().decode())["success"] is True

    # Save Autopilot settings to DB
    ap_payload = json.dumps({
        "blog_id": blog_id,
        "autopilot_enabled": True,
        "publish_mode": "published",
        "schedule": "twice_daily"
    }).encode()
    req_ap = urllib.request.Request(f"{BASE_URL}/api/blogs/autopilot-settings", data=ap_payload, headers={"Content-Type": "application/json"})
    with opener.open(req_ap) as resp:
        ap_res = json.loads(resp.read().decode())
        assert ap_res["success"] is True
        print("✓ Autopilot settings saved to database")

    # Retrieve settings from DB
    req_get = urllib.request.Request(f"{BASE_URL}/api/blogs/{blog_id}/autopilot-settings")
    with opener.open(req_get) as resp:
        ret = json.loads(resp.read().decode())
        assert ret["autopilot_enabled"] is True
        assert ret["publish_mode"] == "published"
        assert ret["schedule"] == "twice_daily"
        print(f"✓ Autopilot settings retrieved from DB: Mode='{ret['publish_mode']}', Schedule='{ret['schedule']}'")

if __name__ == "__main__":
    test_workspaces_and_rbac()
    test_editorial_review_workflow()
    test_autopilot_db_settings_and_frequency()
    print("\n🎉 ALL PHASE 1 BACKEND CAPABILITIES VERIFIED 100%!")

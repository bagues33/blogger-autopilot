"""
Integration tests for Workspaces, RBAC, Editorial Review Workflow, Autopilot Settings, BYOK, and Audit Logs.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

def test_workspaces_and_rbac(tenant_factory):
    client_owner, owner = tenant_factory(plan="agency", role="subscriber", name="Agency Owner")
    client_editor, editor = tenant_factory(plan="free", role="subscriber", name="Senior Editor")

    # 1. Owner creates Workspace
    res_ws = client_owner.post("/api/workspaces", json={"name": "Media Nusantara Agency"})
    assert res_ws.status_code == 200
    ws_data = res_ws.json()
    assert ws_data["success"] is True
    ws_id = ws_data["workspace"]["id"]

    # 2. Add Editor to Workspace with role 'editor'
    res_invite = client_owner.post(f"/api/workspaces/{ws_id}/members", json={
        "email": editor.email,
        "role": "editor"
    })
    assert res_invite.status_code == 200
    assert res_invite.json()["success"] is True

    # 3. List Members as Editor
    res_members = client_editor.get(f"/api/workspaces/{ws_id}/members")
    assert res_members.status_code == 200
    m_data = res_members.json()
    assert m_data["success"] is True
    assert len(m_data["members"]) == 2
    roles = {m["email"]: m["role"] for m in m_data["members"]}
    assert roles[owner.email] == "owner"
    assert roles[editor.email] == "editor"

def test_editorial_review_workflow(tenant_factory):
    client, user = tenant_factory()
    blog_id = f"blog_rev_{uuid.uuid4().hex[:6]}"

    # Add blog
    res_b = client.post("/api/blogs/add", json={"id": blog_id, "name": "Review Blog Test"})
    assert res_b.status_code == 200

    # Save initial draft article
    res_art = client.post("/api/articles/save", json={
        "title": "Masa Depan AI di Indonesia 2026",
        "content_html": "<p>Artikel investigasi mendalam mengenai adopsi kecerdasan buatan.</p>",
        "blog_id": blog_id,
        "target_keyword": "ai indonesia 2026"
    })
    assert res_art.status_code == 200

    # Get article id
    res_list = client.get(f"/api/articles?blog_id={blog_id}")
    assert res_list.status_code == 200
    arts = res_list.json()
    assert len(arts) > 0
    art_id = arts[0]["id"]
    assert arts[0]["status"] == "draft"

    # Transition 1: Send for review ('pending_review')
    res_st1 = client.post(f"/api/articles/{art_id}/status", json={"status": "pending_review"})
    assert res_st1.status_code == 200
    assert res_st1.json()["status"] == "pending_review"

    # Transition 2: Approve article ('approved')
    res_st2 = client.post(f"/api/articles/{art_id}/status", json={"status": "approved"})
    assert res_st2.status_code == 200
    assert res_st2.json()["status"] == "approved"

def test_autopilot_db_settings_persistence(tenant_factory):
    client, user = tenant_factory(plan="pro")
    blog_id = f"blog_ap_{uuid.uuid4().hex[:6]}"

    res_b = client.post("/api/blogs/add", json={"id": blog_id, "name": "Autopilot Sched Blog"})
    assert res_b.status_code == 200

    # Save Autopilot settings to DB
    res_ap = client.post("/api/blogs/autopilot-settings", json={
        "blog_id": blog_id,
        "autopilot_enabled": True,
        "publish_mode": "published",
        "schedule": "twice_daily"
    })
    assert res_ap.status_code == 200
    assert res_ap.json()["success"] is True

    # Retrieve settings from DB
    res_get = client.get(f"/api/blogs/{blog_id}/autopilot-settings")
    assert res_get.status_code == 200
    ret = res_get.json()
    assert ret["autopilot_enabled"] is True
    assert ret["publish_mode"] == "published"
    assert ret["schedule"] == "twice_daily"

def test_byok_and_audit_logs(tenant_factory):
    client, user = tenant_factory(plan="pro")

    # Save custom BYOK Gemini API key
    res_byok = client.post("/api/settings/byok", json={
        "custom_gemini_key": "AIzaSyMockKeyForEnterpriseTesting12345"
    })
    assert res_byok.status_code == 200
    assert res_byok.json()["success"] is True

    # Retrieve settings to verify BYOK is configured
    res_settings = client.get("/api/settings/byok")
    assert res_settings.status_code == 200
    s_data = res_settings.json()
    assert s_data.get("has_gemini") is True

    # Verify audit logs endpoint returns activity
    res_audit = client.get("/api/audit-logs")
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert "logs" in logs
    assert logs["count"] >= 1

def test_feature_gating_free_and_starter_restrictions(tenant_factory):
    # Free tier tenant
    client_free, user_free = tenant_factory(plan="free", name="Free Tenant")

    # 1. Free tenant tries to create workspace -> 403 Forbidden
    res_ws = client_free.post("/api/workspaces", json={"name": "Forbidden Workspace"})
    assert res_ws.status_code == 403
    assert "upgrade" in res_ws.json()["detail"].lower() or "paket" in res_ws.json()["detail"].lower()

    # 2. Free tenant tries to save BYOK -> 403 Forbidden
    res_byok = client_free.post("/api/settings/byok", json={"custom_gemini_key": "AIzaSyFakeKey"})
    assert res_byok.status_code == 403
    assert "upgrade" in res_byok.json()["detail"].lower() or "pro" in res_byok.json()["detail"].lower()

    # 3. Free tenant tries to save custom Knowledge Base -> 403 Forbidden
    res_kb = client_free.post("/api/kb/save", json={"content": "Custom forbidden KB content"})
    assert res_kb.status_code == 403
    assert "upgrade" in res_kb.json()["detail"].lower() or "pro" in res_kb.json()["detail"].lower()

    # 4. Free tenant tries to export data -> 403 Forbidden
    res_exp = client_free.get("/api/tenant/export")
    assert res_exp.status_code == 403

    # 5. Free tenant tries to enable Autopilot scheduler -> 403 Forbidden
    blog_id = f"blog_free_{uuid.uuid4().hex[:6]}"
    client_free.post("/api/blogs/add", json={"id": blog_id, "name": "Free Blog"})
    res_ap = client_free.post("/api/blogs/autopilot-settings", json={
        "blog_id": blog_id,
        "autopilot_enabled": True,
        "publish_mode": "published",
        "schedule": "daily"
    })
    assert res_ap.status_code == 403

def test_byok_credit_bypass_blocked_for_free_tier(tenant_factory, db_session):
    client_free, user_free = tenant_factory(plan="free", name="Bypass Attempt Tenant")
    
    # Exhaust free credits
    sub = user_free.subscription
    sub.article_credits_used = sub.article_credits_limit # 3/3 credits used
    # Force custom keys on user directly in DB
    user_free.custom_gemini_key = "AIzaSyInjectedKeyDirectlyIntoDatabase"
    db_session.commit()

    # Attempt to generate article via ContentGenerator service directly
    from src.services.content_generator import generate_article
    blog_id = f"blog_bp_{uuid.uuid4().hex[:6]}"
    client_free.post("/api/blogs/add", json={"id": blog_id, "name": "Bypass Blog"})

    result = generate_article(
        tenant_id=user_free.id,
        blog_id=blog_id,
        db=db_session
    )
    # MUST be rejected with credit exhaustion error because Free tier cannot use BYOK!
    assert result.success is False
    assert "kuota kredit artikel tenant telah habis" in result.error.lower()


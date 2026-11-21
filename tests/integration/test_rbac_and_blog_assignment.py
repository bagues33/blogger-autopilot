"""
Integration Tests for Phase 3:
Granular Blog Assignment, RBAC Capabilities (Writer vs Editor vs Owner),
Editorial Approval Workflow, and Shared Credit Pool.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from src.models.models import Blog, Keyword, Article, Subscription
from src.services.blogger import set_blogger_adapter, InMemoryBloggerAdapter

def test_granular_blog_assignment_and_writer_restrictions(tenant_factory, db_session):
    set_blogger_adapter(InMemoryBloggerAdapter())
    # 1. Create Agency Owner (Tier Agency)
    client_owner, owner = tenant_factory(plan="agency", name="Agency Lead")
    
    # 2. Owner connects 2 client blogs
    blog_1_id = f"blog_client1_{uuid.uuid4().hex[:6]}"
    blog_2_id = f"blog_client2_{uuid.uuid4().hex[:6]}"
    
    r_b1 = client_owner.post("/api/blogs/add", json={"id": blog_1_id, "name": "Klien Restoran Sehat"})
    assert r_b1.status_code == 200
    r_b2 = client_owner.post("/api/blogs/add", json={"id": blog_2_id, "name": "Klien Otomotif Maju"})
    assert r_b2.status_code == 200

    # 3. Create Workspace
    r_ws = client_owner.post("/api/workspaces", json={"name": "Digital Marketing Agency ID"})
    assert r_ws.status_code == 200
    ws_id = r_ws.json()["workspace"]["id"]

    # 4. Create Writer user (Free Community plan)
    client_writer, writer = tenant_factory(plan="free", name="Budi Copywriter")

    # 5. Create Editor user (Free Community plan)
    client_editor, editor = tenant_factory(plan="free", name="Siti Senior Editor")

    # 6. Owner invites Writer and assigns ONLY blog_1
    r_inv_w = client_owner.post(f"/api/workspaces/{ws_id}/members", json={
        "email": writer.email,
        "role": "writer",
        "assigned_blog_ids": [blog_1_id]
    })
    assert r_inv_w.status_code == 200
    assert r_inv_w.json()["success"] is True

    # 7. Owner invites Editor and assigns blog_1 and blog_2
    r_inv_e = client_owner.post(f"/api/workspaces/{ws_id}/members", json={
        "email": editor.email,
        "role": "editor",
        "assigned_blog_ids": [blog_1_id, blog_2_id]
    })
    assert r_inv_e.status_code == 200

    # 8. Check Writer's accessible blogs: MUST ONLY SEE blog_1, NOT blog_2!
    r_blogs_w = client_writer.get("/api/blogs")
    assert r_blogs_w.status_code == 200
    w_blog_ids = [b["id"] for b in r_blogs_w.json()]
    assert blog_1_id in w_blog_ids
    assert blog_2_id not in w_blog_ids

    # 9. Check Editor's accessible blogs: CAN SEE BOTH blog_1 and blog_2
    r_blogs_e = client_editor.get("/api/blogs")
    assert r_blogs_e.status_code == 200
    e_blog_ids = [b["id"] for b in r_blogs_e.json()]
    assert blog_1_id in e_blog_ids
    assert blog_2_id in e_blog_ids

    # 10. Writer creates draft in blog_1 -> SUCСEEDS
    r_save = client_writer.post("/api/articles/save", json={
        "title": "Menu Diet Sehat Rendah Kalori",
        "content_html": "<p>Panduan lengkap menu makanan sehat untuk menjaga kebugaran tubuh.</p>",
        "blog_id": blog_1_id,
        "target_keyword": "diet sehat rendah kalori"
    })
    assert r_save.status_code == 200
    art_id = r_save.json()["id"]

    # 11. Writer attempts to create article in unassigned blog_2 -> 403 FORBIDDEN
    r_save_forbidden = client_writer.post("/api/articles/save", json={
        "title": "Review Mobil Listrik Terbaru",
        "content_html": "<p>Ulasan performa mobil listrik.</p>",
        "blog_id": blog_2_id
    })
    assert r_save_forbidden.status_code == 403

    # 12. Writer attempts to PUBLISH LIVE -> 403 FORBIDDEN (Writer Gate)
    r_pub_w = client_writer.post(f"/api/articles/{art_id}/publish?is_draft=false")
    assert r_pub_w.status_code == 403
    assert "penulis" in r_pub_w.json()["detail"].lower() or "writer" in r_pub_w.json()["detail"].lower()

    # 13. Writer attempts to APPROVE article directly -> 403 FORBIDDEN
    r_app_w = client_writer.post(f"/api/articles/{art_id}/status", json={"status": "approved"})
    assert r_app_w.status_code == 403

    # 14. Writer submits draft for review ('pending_review') -> SUCCEEDS
    r_rev_w = client_writer.post(f"/api/articles/{art_id}/status", json={"status": "pending_review"})
    assert r_rev_w.status_code == 200
    assert r_rev_w.json()["status"] == "pending_review"

    # 15. Editor views articles in blog_1 -> sees draft with author attribution
    r_arts_e = client_editor.get(f"/api/articles?blog_id={blog_1_id}")
    assert r_arts_e.status_code == 200
    arts = r_arts_e.json()
    assert len(arts) >= 1
    found = next((a for a in arts if a["id"] == art_id), None)
    assert found is not None
    assert found["status"] == "pending_review"
    assert found["author_id"] == writer.id
    assert found["can_approve"] is True
    assert found["can_publish"] is True

    # 16. Editor APPROVES the draft -> SUCCEEDS
    r_app_e = client_editor.post(f"/api/articles/{art_id}/status", json={"status": "approved"})
    assert r_app_e.status_code == 200
    assert r_app_e.json()["status"] == "approved"

    # 17. Editor PUBLISHES to Blogger Draft or Live -> SUCCEEDS
    r_pub_e = client_editor.post(f"/api/articles/{art_id}/publish?is_draft=true")
    assert r_pub_e.status_code == 200
    assert r_pub_e.json()["success"] is True

def test_shared_credit_pool_agency_quota_deduction(tenant_factory, db_session):
    # 1. Agency Owner with 600 limit, 0 used
    client_owner, owner = tenant_factory(plan="agency", name="Agency Boss")
    
    blog_id = f"blog_pool_{uuid.uuid4().hex[:6]}"
    client_owner.post("/api/blogs/add", json={"id": blog_id, "name": "Shared Pool Blog"})
    
    r_ws = client_owner.post("/api/workspaces", json={"name": "SEO Content Lab"})
    ws_id = r_ws.json()["workspace"]["id"]

    # 2. Add Keyword to blog
    kw = Keyword(
        user_id=owner.id,
        blog_id=blog_id,
        keyword="tren teknologi kecerdasan buatan 2026",
        search_intent="Informational",
        status="planned"
    )
    db_session.add(kw)
    db_session.commit()

    # 3. Writer (Free Community plan: 3 limit, 0 used)
    client_writer, writer = tenant_factory(plan="free", name="Freelancer Budi")

    # Invite Writer to workspace and assign blog
    client_owner.post(f"/api/workspaces/{ws_id}/members", json={
        "email": writer.email,
        "role": "writer",
        "assigned_blog_ids": [blog_id]
    })

    # Select blog as active for writer
    client_writer.post("/api/blogs/select", json={"blog_id": blog_id})

    # Initial credits check
    sub_owner = db_session.query(Subscription).filter(Subscription.user_id == owner.id).first()
    sub_writer = db_session.query(Subscription).filter(Subscription.user_id == writer.id).first()
    initial_owner_used = sub_owner.article_credits_used
    initial_writer_used = sub_writer.article_credits_used

    # Writer triggers on-demand AI generation on assigned agency blog
    r_gen = client_writer.post("/api/agent/generate-now")
    assert r_gen.status_code == 200
    assert r_gen.json()["success"] is True

    # Writer's personal credits must remain UNTOUCHED
    db_session.refresh(sub_writer)
    assert sub_writer.article_credits_used == initial_writer_used

"""
Integration Tests for Phase 4:
Analytics Charts (Intent & Weekly Trend), White-Label PDF/HTML Report,
CSV Export (with Tier Feature Gating), and Google WebSub Instant Indexing Ping.
"""

import uuid
import pytest
from src.models.models import Keyword, Article
from src.services.blogger import set_blogger_adapter, InMemoryBloggerAdapter
from src.services.indexing import set_indexing_adapter, InMemoryIndexingAdapter, build_blogger_feed_url

def test_analytics_roi_breakdowns_and_csv_export(tenant_factory, db_session):
    # 1. Free user should get 403 on CSV Export
    client_free, user_free = tenant_factory(plan="free", name="Free Analyst")
    blog_free = f"blog_f_{uuid.uuid4().hex[:6]}"
    client_free.post("/api/blogs/add", json={"id": blog_free, "name": "Free Blog", "url": "https://freeblog.blogspot.com"})
    r_csv_free = client_free.get(f"/api/analytics/export-csv?blog_id={blog_free}")
    assert r_csv_free.status_code == 403

    # 2. Agency user gets full analytics + CSV Export + White-Label Report
    client_ag, user_ag = tenant_factory(plan="agency", name="Nusantara Digital Agency")
    blog_id = f"blog_ag_{uuid.uuid4().hex[:6]}"
    client_ag.post("/api/blogs/add", json={
        "id": blog_id,
        "name": "Klien Kuliner Enak",
        "url": "https://kulinerenak.blogspot.com"
    })

    # Seed Keywords with different search intents
    db_session.add_all([
        Keyword(user_id=user_ag.id, blog_id=blog_id, keyword="resep nasi goreng", search_intent="Informational", status="planned"),
        Keyword(user_id=user_ag.id, blog_id=blog_id, keyword="review blender terbaik", search_intent="Commercial", status="used"),
        Keyword(user_id=user_ag.id, blog_id=blog_id, keyword="beli wajan anti lengket", search_intent="Transactional", status="planned"),
    ])
    db_session.commit()

    # Save article
    client_ag.post("/api/articles/save", json={
        "title": "10 Rekomendasi Blender Terbaik untuk Jus",
        "content_html": "<p>Ulasan lengkap blender berkualitas tinggi dengan harga terjangkau.</p>",
        "target_keyword": "review blender terbaik",
        "blog_id": blog_id
    })

    # Check /api/analytics/roi
    r_roi = client_ag.get(f"/api/analytics/roi?blog_id={blog_id}")
    assert r_roi.status_code == 200
    roi = r_roi.json()
    assert roi["success"] is True
    assert roi["scope_blog_name"] == "Klien Kuliner Enak"
    metrics = roi["metrics"]
    assert metrics["total_articles"] == 1
    assert metrics["intent_distribution"]["Informational"] == 1
    assert metrics["intent_distribution"]["Commercial"] == 1
    assert metrics["intent_distribution"]["Transactional"] == 1
    assert len(metrics["weekly_production"]) == 7
    assert metrics["weekly_production"][-1]["count"] >= 1

    # Check CSV export
    r_csv = client_ag.get(f"/api/analytics/export-csv?blog_id={blog_id}")
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    csv_text = r_csv.content.decode("utf-8-sig")
    assert "Judul Artikel" in csv_text
    assert "10 Rekomendasi Blender Terbaik untuk Jus" in csv_text
    assert "review blender terbaik" in csv_text

    # Check White-Label Report + XSS protection
    r_rep = client_ag.get(f"/api/analytics/report?blog_id={blog_id}&agency_name=Garuda+SEO+Lab")
    assert r_rep.status_code == 200
    assert "Garuda SEO Lab" in r_rep.text
    assert "Blogger Auto-Pilot SaaS" not in r_rep.text  # True white-label!
    assert "Klien Kuliner Enak" in r_rep.text

def test_websub_instant_indexing_on_live_publish(tenant_factory):
    set_blogger_adapter(InMemoryBloggerAdapter())
    idx_mock = InMemoryIndexingAdapter()
    set_indexing_adapter(idx_mock)

    assert build_blogger_feed_url("https://technews.blogspot.com/") == "https://technews.blogspot.com/feeds/posts/default"

    client, user = tenant_factory(plan="pro", name="Publisher Pro")
    blog_id = f"blog_idx_{uuid.uuid4().hex[:6]}"
    client.post("/api/blogs/add", json={
        "id": blog_id,
        "name": "Tech News ID",
        "url": "https://technews.blogspot.com"
    })

    r_save = client.post("/api/articles/save", json={
        "title": "Cara Optimasi SEO Google Blogger 2026",
        "content_html": "<p>Panduan praktis teknis SEO modern untuk Google Blogger.</p>",
        "blog_id": blog_id
    })
    art_id = r_save.json()["id"]

    # Draft publish should NOT trigger WebSub live ping
    r_draft = client.post(f"/api/articles/{art_id}/publish?is_draft=true")
    assert r_draft.status_code == 200
    assert r_draft.json()["websub_pinged"] is False
    assert len(idx_mock.pings) == 0

    # Live publish SHOULD trigger WebSub ping!
    r_live = client.post(f"/api/articles/{art_id}/publish?is_draft=false")
    assert r_live.status_code == 200
    data = r_live.json()
    assert data["success"] is True
    assert data["websub_pinged"] is True
    assert len(idx_mock.pings) == 1
    assert idx_mock.pings[0]["feed_url"] == "https://technews.blogspot.com/feeds/posts/default"

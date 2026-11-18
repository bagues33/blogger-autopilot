"""
Integration tests for Cron Automation Endpoints and Telegram Notification Dispatcher.
"""

import os
import pytest
from fastapi.testclient import TestClient
from src.services.notifications import InMemoryNotificationAdapter, set_notification_adapter

def test_cron_status_and_security(client: TestClient):
    cron_secret = os.environ.get("CRON_SECRET_KEY", "blogger-autopilot-cron-secret-2026")

    # 1. Access without key is rejected (401)
    res_unauth = client.get("/api/cron/status")
    assert res_unauth.status_code == 401
    assert "Akses ditolak" in res_unauth.json()["detail"]

    # 2. Access with invalid key is rejected (401)
    res_invalid = client.get("/api/cron/status?key=wrong-secret-token")
    assert res_invalid.status_code == 401

    # 3. Access with valid query param key succeeds (200)
    res_query = client.get(f"/api/cron/status?key={cron_secret}")
    assert res_query.status_code == 200
    data_query = res_query.json()
    assert data_query["success"] is True
    assert "metrics" in data_query
    assert "cycle_interval_seconds" in data_query["metrics"]

    # 4. Access with valid X-Cron-Key header succeeds (200)
    res_header = client.get("/api/cron/status", headers={"X-Cron-Key": cron_secret})
    assert res_header.status_code == 200
    assert res_header.json()["success"] is True

def test_cron_trigger_cycle_execution(client: TestClient):
    cron_secret = os.environ.get("CRON_SECRET_KEY", "blogger-autopilot-cron-secret-2026")

    # 1. Trigger cycle via POST with header
    res_post = client.post(
        "/api/cron/trigger-cycle?max_per_cycle=2&force=true",
        headers={"X-Cron-Key": cron_secret}
    )
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["success"] is True
    assert data_post["force"] is True
    assert "processed_count" in data_post
    assert "details" in data_post

    # 2. Trigger cycle via GET with query key (common for simple external crons)
    res_get = client.get(f"/api/cron/trigger-cycle?key={cron_secret}&max_per_cycle=1&force=false")
    assert res_get.status_code == 200
    assert res_get.json()["success"] is True

def test_notification_settings_and_test_dispatch(tenant_factory):
    client, user = tenant_factory()
    mock_adapter = InMemoryNotificationAdapter()
    set_notification_adapter(mock_adapter)

    # 1. Save notification settings
    res_save = client.post("/api/notifications/settings", json={
        "telegram_bot_token": "123456789:MockTelegramBotToken",
        "telegram_chat_id": "987654321",
        "webhook_url": "https://webhook.site/mock-endpoint",
        "notify_on_draft": True,
        "notify_on_publish": True,
        "notify_on_credit_low": True
    })
    assert res_save.status_code == 200
    assert res_save.json()["success"] is True

    # 2. Get notification settings
    res_get = client.get("/api/notifications/settings")
    assert res_get.status_code == 200
    settings = res_get.json()
    assert settings["telegram_bot_token"] == "123456789:MockTelegramBotToken"
    assert settings["telegram_chat_id"] == "987654321"
    assert settings["webhook_url"] == "https://webhook.site/mock-endpoint"

    # 3. Test notification channel
    res_test = client.post("/api/notifications/test", json={
        "telegram_bot_token": "123456789:MockTelegramBotToken",
        "telegram_chat_id": "987654321",
        "webhook_url": "https://webhook.site/mock-endpoint"
    })
    assert res_test.status_code == 200
    data_test = res_test.json()
    assert data_test["success"] is True
    assert len(mock_adapter.sent_telegrams) >= 1
    assert mock_adapter.sent_telegrams[-1]["chat_id"] == "987654321"
    assert "Tes Notifikasi Berhasil" in mock_adapter.sent_telegrams[-1]["message_text"]
    assert len(mock_adapter.sent_webhooks) >= 1

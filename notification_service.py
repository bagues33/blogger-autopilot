"""
Notification Service for Blogger Auto-Pilot SaaS
Supports Telegram Bot API and Custom Webhooks (Zapier, Discord, Slack, Make).
Zero-dependency implementation using Python urllib.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger("NotificationService")

# Fallback server-wide environment defaults
DEFAULT_TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
DEFAULT_WEBHOOK_URL = os.environ.get("GLOBAL_WEBHOOK_URL", "").strip()

def send_telegram_message(bot_token: str, chat_id: str, message_text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
    """
    Sends a message to a Telegram chat or channel via Bot API.
    """
    if not bot_token or not chat_id:
        return {"success": False, "error": "Bot token and Chat ID are required"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": data.get("ok", False), "result": data.get("result")}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        logger.error(f"Telegram HTTP Error {e.code}: {err_msg}")
        return {"success": False, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        logger.error(f"Telegram Error: {e}")
        return {"success": False, "error": str(e)}

def send_webhook_event(webhook_url: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends a JSON payload to a custom webhook URL (Zapier, Make, Slack, Discord, etc.).
    """
    if not webhook_url:
        return {"success": False, "error": "Webhook URL is missing"}

    body = {
        "event": event_type,
        "source": "blogger_autopilot_saas",
        "data": payload
    }

    req_data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "BloggerAutopilot/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            return {"success": 200 <= status < 300, "status_code": status}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def dispatch_notification(
    user_id: str,
    event_type: str,
    data: Dict[str, Any],
    db_session=None
) -> Dict[str, Any]:
    """
    Dispatches notifications to tenant's configured channels (Telegram / Webhook).
    """
    results = {"telegram": None, "webhook": None}
    
    bot_token = DEFAULT_TELEGRAM_BOT_TOKEN
    chat_id = DEFAULT_TELEGRAM_CHAT_ID
    webhook_url = DEFAULT_WEBHOOK_URL
    notify_on_draft = True
    notify_on_publish = True
    notify_on_credit_low = True

    # Look up tenant settings if db_session is provided
    if db_session and user_id:
        try:
            from models_saas import NotificationSetting
            setting = db_session.query(NotificationSetting).filter(
                NotificationSetting.user_id == user_id,
                NotificationSetting.is_active == True
            ).first()

            if setting:
                if setting.telegram_bot_token:
                    bot_token = setting.telegram_bot_token
                if setting.telegram_chat_id:
                    chat_id = setting.telegram_chat_id
                if setting.webhook_url:
                    webhook_url = setting.webhook_url
                notify_on_draft = setting.notify_on_draft
                notify_on_publish = setting.notify_on_publish
                notify_on_credit_low = setting.notify_on_credit_low
        except Exception as e:
            logger.warning(f"Could not load notification setting for user {user_id}: {e}")

    # Check event preferences
    if event_type == "draft_created" and not notify_on_draft:
        return {"success": True, "message": "Draft notifications disabled by tenant preference."}
    if event_type == "article_published" and not notify_on_publish:
        return {"success": True, "message": "Publish notifications disabled by tenant preference."}
    if event_type == "credit_low" and not notify_on_credit_low:
        return {"success": True, "message": "Credit notifications disabled by tenant preference."}

    # Format Telegram HTML message
    title = data.get("title", "Tanpa Judul")
    keyword = data.get("keyword", "-")
    blog_name = data.get("blog_name", "Blog")
    url = data.get("url", "")

    if event_type == "draft_created":
        msg = (
            f"🤖 <b>Blogger Auto-Pilot: Draf Baru Siap!</b>\n\n"
            f"📝 <b>Judul:</b> {title}\n"
            f"🔑 <b>Keyword:</b> <code>{keyword}</code>\n"
            f"🌐 <b>Blog:</b> {blog_name}\n"
            f"📊 <b>Status:</b> Tersimpan di Draf (Siap Direview & Diterbitkan)\n\n"
            f"<i>Buka dashboard untuk meninjau dan menerbitkan artikel ini.</i>"
        )
    elif event_type == "article_published":
        url_text = f"<a href='{url}'>Buka Artikel</a>" if url else "Tersedia di Blogger"
        msg = (
            f"🚀 <b>Blogger Auto-Pilot: Artikel Berhasil Terbit!</b>\n\n"
            f"📝 <b>Judul:</b> {title}\n"
            f"🔑 <b>Keyword:</b> <code>{keyword}</code>\n"
            f"🌐 <b>Blog:</b> {blog_name}\n"
            f"🔗 <b>Tautan:</b> {url_text}\n\n"
            f"✅ <i>Artikel telah live dan dapat diakses pembaca.</i>"
        )
    elif event_type == "credit_low":
        remaining = data.get("remaining_credits", 0)
        msg = (
            f"⚠️ <b>Blogger Auto-Pilot: Kuota Menipis!</b>\n\n"
            f"Sisa kuota artikel Anda: <b>{remaining} artikel</b>.\n"
            f"Segera perpanjang atau upgrade paket agar proses posting otomatis tidak terhenti."
        )
    else:
        msg = f"ℹ️ <b>Blogger Auto-Pilot Info:</b> {event_type} - {title}"

    # Dispatch to Telegram
    if bot_token and chat_id:
        results["telegram"] = send_telegram_message(bot_token, chat_id, msg)

    # Dispatch to Webhook
    if webhook_url:
        results["webhook"] = send_webhook_event(webhook_url, event_type, data)

    return {
        "success": True,
        "dispatched": bool(results["telegram"] or results["webhook"]),
        "results": results
    }

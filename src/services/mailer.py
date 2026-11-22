"""
Transactional Email Delivery Service for Blogger Auto-Pilot SaaS
Supports Resend HTTP API (RESEND_API_KEY) and standard SMTP (SMTP_HOST/PORT/USER/PASSWORD)
with a pluggable adapter interface for isolated testing. Zero extra third-party dependencies.
"""

import os
import json
import smtplib
import logging
import urllib.request
import urllib.error
from email.message import EmailMessage
from typing import Dict, Any, Optional

logger = logging.getLogger("SaasMailer")


class BaseEmailAdapter:
    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError


class LiveEmailAdapter(BaseEmailAdapter):
    """
    Production email adapter.
    Priority:
      1. Resend API (RESEND_API_KEY + EMAIL_FROM/SMTP_FROM)
      2. Standard SMTP (SMTP_HOST + SMTP_PORT + SMTP_USER + SMTP_PASSWORD + SMTP_FROM)
    Returns {"success": False, "configured": False} cleanly when neither provider is configured.
    """

    def _get_from_address(self) -> str:
        return (
            os.environ.get("EMAIL_FROM")
            or os.environ.get("SMTP_FROM")
            or os.environ.get("SMTP_USER")
            or "noreply@bloggerautopilot.id"
        ).strip()

    def _send_via_resend(self, api_key: str, to_email: str, subject: str, text_body: str, html_body: Optional[str]) -> Dict[str, Any]:
        payload = {
            "from": self._get_from_address(),
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BloggerAutopilot/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "provider": "resend", "id": body.get("id")}
        except urllib.error.HTTPError as e:
            err_detail = e.read().decode("utf-8", errors="ignore")
            logger.error(f"Resend HTTP Error {e.code}: {err_detail}")
            return {"success": False, "provider": "resend", "error": f"HTTP {e.code}"}
        except Exception as e:
            logger.error(f"Resend Error: {e}")
            return {"success": False, "provider": "resend", "error": str(e)}

    def _send_via_smtp(self, to_email: str, subject: str, text_body: str, html_body: Optional[str]) -> Dict[str, Any]:
        host = os.environ.get("SMTP_HOST", "").strip()
        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER", "").strip()
        password = os.environ.get("SMTP_PASSWORD", "").strip()
        use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() in ("true", "1", "yes")
        use_ssl = os.environ.get("SMTP_USE_SSL", "false").strip().lower() in ("true", "1", "yes") or port == 465

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._get_from_address()
        msg["To"] = to_email
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                    if user and password:
                        server.login(user, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=10) as server:
                    server.ehlo()
                    if use_tls:
                        server.starttls()
                        server.ehlo()
                    if user and password:
                        server.login(user, password)
                    server.send_message(msg)
            return {"success": True, "provider": "smtp"}
        except Exception as e:
            logger.error(f"SMTP Error: {e}")
            return {"success": False, "provider": "smtp", "error": str(e)}

    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> Dict[str, Any]:
        resend_key = os.environ.get("RESEND_API_KEY", "").strip()
        if resend_key:
            return self._send_via_resend(resend_key, to_email, subject, text_body, html_body)

        smtp_host = os.environ.get("SMTP_HOST", "").strip()
        if smtp_host:
            return self._send_via_smtp(to_email, subject, text_body, html_body)

        return {"success": False, "configured": False, "error": "No email provider configured (RESEND_API_KEY or SMTP_HOST)."}


class InMemoryEmailAdapter(BaseEmailAdapter):
    """Test adapter that captures sent emails without touching the network."""
    def __init__(self):
        self.sent_emails: list = []

    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> Dict[str, Any]:
        entry = {
            "to": to_email,
            "subject": subject,
            "text_body": text_body,
            "html_body": html_body,
        }
        self.sent_emails.append(entry)
        return {"success": True, "provider": "in_memory"}


_active_email_adapter: BaseEmailAdapter = LiveEmailAdapter()


def get_email_adapter() -> BaseEmailAdapter:
    return _active_email_adapter


def set_email_adapter(adapter: BaseEmailAdapter):
    global _active_email_adapter
    _active_email_adapter = adapter


def is_email_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip() or os.environ.get("SMTP_HOST", "").strip())


def send_password_reset_email(to_email: str, reset_token: str) -> Dict[str, Any]:
    app_url = os.environ.get("APP_BASE_URL", "https://app.bloggerautopilot.id").strip().rstrip("/")
    subject = "[Blogger Auto-Pilot] Token Reset Kata Sandi Anda"
    text_body = (
        f"Halo,\n\n"
        f"Kami menerima permintaan reset kata sandi untuk akun {to_email} di Blogger Auto-Pilot SaaS.\n\n"
        f"Token Reset (berlaku 15 menit, hanya dapat digunakan 1 kali):\n"
        f"{reset_token}\n\n"
        f"Salin token di atas dan tempel pada form 'Lupa Kata Sandi' di {app_url}.\n\n"
        f"Jika Anda tidak meminta reset kata sandi, abaikan email ini."
    )
    html_body = (
        f"<div style='font-family:sans-serif;max-width:520px;margin:0 auto;color:#0f172a'>"
        f"<h2 style='margin-bottom:8px'>Reset Kata Sandi</h2>"
        f"<p>Kami menerima permintaan reset kata sandi untuk akun <b>{to_email}</b>.</p>"
        f"<p>Gunakan token berikut (berlaku <b>15 menit</b>, hanya bisa dipakai <b>1 kali</b>):</p>"
        f"<pre style='background:#f1f5f9;padding:12px;border-radius:8px;word-break:break-all;font-size:13px'>{reset_token}</pre>"
        f"<p style='font-size:13px;color:#475569'>Tempel token pada formulir Reset Kata Sandi di <a href='{app_url}'>{app_url}</a>.</p>"
        f"<p style='font-size:12px;color:#64748b'>Abaikan email ini jika Anda tidak merasa melakukan permintaan reset kata sandi.</p>"
        f"</div>"
    )
    return get_email_adapter().send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


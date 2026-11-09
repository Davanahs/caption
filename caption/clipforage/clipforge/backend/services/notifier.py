"""
Notification Service — Phase 4
Fires webhook / email alerts when new clips are generated or a pipeline job completes.

Supported channels:
  1. Webhook POST (Discord, Slack, n8n, custom)
  2. SMTP email
"""
import json
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from backend.core.config import settings


# ── Webhook ──────────────────────────────────────────────────────────────────

def _send_webhook(payload: dict):
    """POST payload to NOTIFICATION_WEBHOOK_URL in a background thread."""
    url = settings.NOTIFICATION_WEBHOOK_URL
    if not url:
        return
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            print(f"[Notify] Webhook sent → {url} ({resp.status_code})")
    except Exception as e:
        print(f"[Notify] Webhook failed: {e}")


def send_webhook_async(payload: dict):
    """Fire-and-forget webhook POST (non-blocking)."""
    t = threading.Thread(target=_send_webhook, args=(payload,), daemon=True)
    t.start()


# ── Email ────────────────────────────────────────────────────────────────────

def _send_email(subject: str, html_body: str):
    """Send an HTML email via SMTP in a background thread."""
    if not settings.NOTIFICATION_EMAIL or not settings.SMTP_HOST:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER or "clipforge@noreply.com"
        msg["To"] = settings.NOTIFICATION_EMAIL

        part = MIMEText(html_body, "html")
        msg.attach(part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASS:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
            print(f"[Notify] Email sent → {settings.NOTIFICATION_EMAIL}")
    except Exception as e:
        print(f"[Notify] Email failed: {e}")


def send_email_async(subject: str, html_body: str):
    """Fire-and-forget email send (non-blocking)."""
    t = threading.Thread(target=_send_email, args=(subject, html_body), daemon=True)
    t.start()


# ── High-Level Notification Events ───────────────────────────────────────────

def notify_clips_generated(
    video_title: str,
    clip_count: int,
    video_id: str,
    channel_name: str = "",
    frontend_url: str = "http://localhost:3000",
):
    """
    Fire notification when the pipeline completes and clips are ready.
    Sends both webhook and email (if configured).
    """
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    clips_page = f"{frontend_url}/clips"

    # ── Discord / Slack webhook payload ──────────────────────────────────────
    webhook_payload = {
        "username": "ClipForge 🎬",
        "avatar_url": "https://em-content.zobj.net/source/animated-noto-color-emoji/356/clapper-board_1f3ac.gif",
        "embeds": [
            {
                "title": f"✂️ {clip_count} new clip{'s' if clip_count != 1 else ''} ready!",
                "description": (
                    f"**Video:** {video_title}\n"
                    + (f"**Channel:** {channel_name}\n" if channel_name else "")
                    + f"**Time:** {now}"
                ),
                "color": 0x6366F1,  # Indigo
                "fields": [
                    {"name": "Clips Generated", "value": str(clip_count), "inline": True},
                    {"name": "Video ID", "value": video_id[:8] + "...", "inline": True},
                ],
                "footer": {"text": "ClipForge — AI YouTube Automation"},
                "url": clips_page,
            }
        ],
    }
    send_webhook_async(webhook_payload)

    # ── Email ─────────────────────────────────────────────────────────────────
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; background: #0f0f11; color: #e2e8f0; padding: 32px;">
      <div style="max-width: 520px; margin: auto; background: #1a1a2e; border-radius: 12px; padding: 28px;
                  border: 1px solid #6366f120;">
        <h2 style="color: #818cf8; margin-bottom: 4px;">✂️ ClipForge — New Clips Ready</h2>
        <p style="color: #94a3b8; font-size: 14px; margin-top: 0;">{now}</p>
        <hr style="border-color: #6366f120; margin: 16px 0;">
        <p><strong>Video:</strong> {video_title}</p>
        {"<p><strong>Channel:</strong> " + channel_name + "</p>" if channel_name else ""}
        <p><strong>Clips Generated:</strong>
           <span style="color: #818cf8; font-weight: 700;">{clip_count}</span>
        </p>
        <a href="{clips_page}" style="display: inline-block; margin-top: 16px; padding: 10px 22px;
           background: #6366f1; color: #fff; border-radius: 8px; text-decoration: none;
           font-weight: 700;">View Clips →</a>
      </div>
    </body></html>
    """
    send_email_async(
        subject=f"[ClipForge] {clip_count} clip{'s' if clip_count != 1 else ''} ready from '{video_title}'",
        html_body=html_body,
    )


def notify_pipeline_failed(
    job_id: str,
    source_title: str,
    error: str,
    frontend_url: str = "http://localhost:3000",
):
    """Fire notification when a pipeline job fails."""
    webhook_payload = {
        "username": "ClipForge 🎬",
        "embeds": [
            {
                "title": "❌ Pipeline Failed",
                "description": (
                    f"**Job:** {job_id[:12]}...\n"
                    f"**Video:** {source_title}\n"
                    f"**Error:** `{error[:200]}`"
                ),
                "color": 0xEF4444,  # Red
                "footer": {"text": "ClipForge — AI YouTube Automation"},
            }
        ],
    }
    send_webhook_async(webhook_payload)

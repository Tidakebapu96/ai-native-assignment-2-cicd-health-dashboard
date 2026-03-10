import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.enabled = bool(
            settings.SMTP_HOST
            and settings.SMTP_USER
            and settings.SMTP_PASSWORD
            and settings.ALERT_EMAIL_TO
        )
        if not self.enabled:
            logger.info("Email alerting disabled — SMTP settings not configured")

    def send_failure_alert(self, pipeline) -> bool:
        """Send an email alert for a failed pipeline run."""
        if not self.enabled:
            return False

        subject = f"[CI/CD Alert] Pipeline failed: {pipeline.workflow_name}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #d9534f;">&#10060; Pipeline Failure Alert</h2>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr style="background:#f5f5f5;">
                    <td style="padding:8px 12px; font-weight:bold; width:160px;">Workflow</td>
                    <td style="padding:8px 12px;">{pipeline.workflow_name}</td>
                </tr>
                <tr>
                    <td style="padding:8px 12px; font-weight:bold;">Branch</td>
                    <td style="padding:8px 12px;">{pipeline.branch or "—"}</td>
                </tr>
                <tr style="background:#f5f5f5;">
                    <td style="padding:8px 12px; font-weight:bold;">Commit</td>
                    <td style="padding:8px 12px;">{pipeline.commit_message or "—"}</td>
                </tr>
                <tr>
                    <td style="padding:8px 12px; font-weight:bold;">Triggered by</td>
                    <td style="padding:8px 12px;">{pipeline.actor or "—"}</td>
                </tr>
                <tr style="background:#f5f5f5;">
                    <td style="padding:8px 12px; font-weight:bold;">Time</td>
                    <td style="padding:8px 12px;">{datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</td>
                </tr>
            </table>
            <br>
            <a href="{pipeline.html_url or '#'}"
               style="background:#d9534f;color:#fff;padding:10px 20px;text-decoration:none;border-radius:4px;">
               View Run on GitHub
            </a>
            <p style="margin-top:24px; color:#999; font-size:12px;">
                CI/CD Pipeline Health Dashboard — automated alert
            </p>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.ALERT_EMAIL_TO
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, settings.ALERT_EMAIL_TO, msg.as_string())
            logger.info(
                "Alert email sent for failed pipeline run_id=%s workflow='%s'",
                pipeline.github_run_id,
                pipeline.workflow_name,
            )
            return True
        except Exception as e:
            logger.error("Failed to send alert email: %s", e)
            return False

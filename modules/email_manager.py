import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EmailManager:
    def __init__(self, ms_client=None):
        self.ms_client = ms_client

    def send_email(self, to: list, subject: str, body: str, cc: list = None) -> dict:
        if not self.ms_client:
            return {"success": False, "error": "Microsoft Graph not configured. Please add MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, and MICROSOFT_USER_EMAIL to your .env file."}
        try:
            success = self.ms_client.send_email(to, subject, body, cc)
            return {"success": success, "message": "Email sent successfully" if success else "Send failed"}
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return {"success": False, "error": str(e)}

    def get_recent_emails(self, count: int = 10) -> list:
        if not self.ms_client:
            return []
        try:
            emails = self.ms_client.get_recent_emails(count)
            return [{
                "id": e.get("id"),
                "subject": e.get("subject", "(no subject)"),
                "sender": e.get("sender", {}).get("emailAddress", {}).get("address", ""),
                "received": e.get("receivedDateTime", ""),
                "is_read": e.get("isRead", False),
                "preview": e.get("bodyPreview", ""),
            } for e in emails]
        except Exception as e:
            logger.error(f"Get emails error: {e}")
            return []

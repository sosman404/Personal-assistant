import requests
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)
GRAPH_API = "https://graph.microsoft.com/v1.0"


class MicrosoftGraphClient:
    def __init__(self, client_id: str, client_secret: str, tenant_id: str, user_email: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.user_email = user_email

    def _get_token(self) -> str:
        import msal
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise RuntimeError(f"Token error: {result.get('error_description')}")
        return result["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    def get_upcoming_events(self, days: int = 7) -> list:
        start = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
        url = f"{GRAPH_API}/users/{self.user_email}/calendarView"
        r = requests.get(url, headers=self._headers(),
                         params={"startDateTime": start, "endDateTime": end, "$orderby": "start/dateTime", "$top": 50})
        r.raise_for_status()
        return r.json().get("value", [])

    def create_event(self, title: str, start: datetime, end: datetime,
                     description: str = "", location: str = "") -> dict:
        url = f"{GRAPH_API}/users/{self.user_email}/events"
        body = {
            "subject": title,
            "body": {"contentType": "text", "content": description},
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "location": {"displayName": location},
        }
        r = requests.post(url, headers=self._headers(), json=body)
        r.raise_for_status()
        return r.json()

    def delete_event(self, event_id: str) -> bool:
        url = f"{GRAPH_API}/users/{self.user_email}/events/{event_id}"
        r = requests.delete(url, headers=self._headers())
        return r.status_code == 204

    def send_email(self, to: list, subject: str, body: str, cc: list = None) -> bool:
        url = f"{GRAPH_API}/users/{self.user_email}/sendMail"
        msg = {
            "message": {
                "subject": subject,
                "body": {"contentType": "text", "content": body},
                "toRecipients": [{"emailAddress": {"address": a}} for a in to],
            },
            "saveToSentItems": True,
        }
        if cc:
            msg["message"]["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc]
        r = requests.post(url, headers=self._headers(), json=msg)
        return r.status_code == 202

    def get_recent_emails(self, count: int = 10) -> list:
        url = f"{GRAPH_API}/users/{self.user_email}/messages"
        params = {"$top": count, "$orderby": "receivedDateTime desc",
                  "$select": "id,subject,sender,receivedDateTime,isRead,bodyPreview"}
        r = requests.get(url, headers=self._headers(), params=params)
        r.raise_for_status()
        return r.json().get("value", [])

    def get_task_lists(self) -> list:
        url = f"{GRAPH_API}/users/{self.user_email}/todo/lists"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json().get("value", [])

    def create_task(self, list_id: str, title: str, due_date: Optional[datetime] = None,
                    notes: str = "") -> dict:
        url = f"{GRAPH_API}/users/{self.user_email}/todo/lists/{list_id}/tasks"
        body = {"title": title, "body": {"content": notes, "contentType": "text"}}
        if due_date:
            body["dueDateTime"] = {"dateTime": due_date.isoformat(), "timeZone": "UTC"}
        r = requests.post(url, headers=self._headers(), json=body)
        r.raise_for_status()
        return r.json()

    def get_tasks(self, list_id: str) -> list:
        url = f"{GRAPH_API}/users/{self.user_email}/todo/lists/{list_id}/tasks"
        r = requests.get(url, headers=self._headers(), params={"$filter": "status ne 'completed'"})
        r.raise_for_status()
        return r.json().get("value", [])

    def complete_task(self, list_id: str, task_id: str) -> bool:
        url = f"{GRAPH_API}/users/{self.user_email}/todo/lists/{list_id}/tasks/{task_id}"
        r = requests.patch(url, headers=self._headers(), json={"status": "completed"})
        return r.status_code == 200

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "google_token.json"
CREDENTIALS_FILE = "google_credentials.json"


class GoogleCalendarClient:
    def __init__(self):
        self.service = None

    def authenticate(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(CREDENTIALS_FILE):
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(TOKEN_FILE, "w") as f:
                        f.write(creds.to_json())
                else:
                    return False
            self.service = build("calendar", "v3", credentials=creds)
            return True
        except Exception as e:
            logger.warning(f"Google Calendar auth failed: {e}")
            return False

    def get_upcoming_events(self, days: int = 7) -> list:
        if not self.service:
            return []
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
        result = self.service.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            maxResults=50, singleEvents=True, orderBy="startTime"
        ).execute()
        return result.get("items", [])

    def create_event(self, title: str, start: datetime, end: datetime,
                     description: str = "", location: str = "") -> dict:
        if not self.service:
            return {}
        event = {
            "summary": title, "location": location, "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }
        return self.service.events().insert(calendarId="primary", body=event).execute()

    def delete_event(self, event_id: str) -> bool:
        if not self.service:
            return False
        self.service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True

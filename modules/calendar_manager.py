from datetime import datetime, timedelta
from typing import Optional
from database.connection import SessionLocal
from database.models import Event
import logging

logger = logging.getLogger(__name__)


class CalendarManager:
    def __init__(self, ms_client=None, google_client=None):
        self.ms_client = ms_client
        self.google_client = google_client

    def create_event(self, title: str, start_time: datetime, end_time: datetime = None,
                     description: str = "", location: str = "", calendar: str = "local") -> dict:
        if end_time is None:
            end_time = start_time + timedelta(hours=1)

        with SessionLocal() as db:
            event = Event(title=title, description=description, start_time=start_time,
                          end_time=end_time, location=location, calendar_source="local")

            if calendar == "microsoft" and self.ms_client:
                try:
                    ms_ev = self.ms_client.create_event(title, start_time, end_time, description, location)
                    event.external_id = ms_ev.get("id")
                    event.calendar_source = "microsoft"
                except Exception as e:
                    logger.warning(f"MS Graph sync failed: {e}")

            elif calendar == "google" and self.google_client:
                try:
                    g_ev = self.google_client.create_event(title, start_time, end_time, description, location)
                    event.external_id = g_ev.get("id")
                    event.calendar_source = "google"
                except Exception as e:
                    logger.warning(f"Google sync failed: {e}")

            db.add(event)
            db.commit()
            db.refresh(event)
            return {"id": event.id, "title": title, "start": start_time.isoformat(),
                    "end": end_time.isoformat(), "source": event.calendar_source}

    def get_upcoming_events(self, days: int = 7) -> list:
        events = []
        now = datetime.utcnow()
        end = now + timedelta(days=days)

        with SessionLocal() as db:
            local = db.query(Event).filter(Event.start_time >= now, Event.start_time <= end).order_by(Event.start_time).all()
            for e in local:
                events.append({
                    "id": e.id, "title": e.title,
                    "start": e.start_time.isoformat(),
                    "end": e.end_time.isoformat() if e.end_time else None,
                    "location": e.location or "", "description": e.description or "",
                    "source": e.calendar_source,
                })

        if self.ms_client:
            try:
                for e in self.ms_client.get_upcoming_events(days):
                    events.append({
                        "id": e.get("id"), "title": e.get("subject", ""),
                        "start": e.get("start", {}).get("dateTime", ""),
                        "end": e.get("end", {}).get("dateTime", ""),
                        "location": e.get("location", {}).get("displayName", ""),
                        "description": e.get("bodyPreview", ""), "source": "microsoft",
                    })
            except Exception as e:
                logger.warning(f"MS events fetch failed: {e}")

        if self.google_client:
            try:
                for e in self.google_client.get_upcoming_events(days):
                    events.append({
                        "id": e.get("id"), "title": e.get("summary", ""),
                        "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                        "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                        "location": e.get("location", ""),
                        "description": e.get("description", ""), "source": "google",
                    })
            except Exception as e:
                logger.warning(f"Google events fetch failed: {e}")

        events.sort(key=lambda x: x.get("start", ""))
        return events

    def delete_event(self, event_id) -> bool:
        with SessionLocal() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return False
            if event.calendar_source == "microsoft" and event.external_id and self.ms_client:
                try:
                    self.ms_client.delete_event(event.external_id)
                except Exception:
                    pass
            elif event.calendar_source == "google" and event.external_id and self.google_client:
                try:
                    self.google_client.delete_event(event.external_id)
                except Exception:
                    pass
            db.delete(event)
            db.commit()
        return True

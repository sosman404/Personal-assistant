from datetime import datetime
from typing import Optional, Callable
from database.connection import SessionLocal
from database.models import Reminder, ReminderType
import logging

logger = logging.getLogger(__name__)


class ReminderManager:
    def __init__(self, scheduler=None):
        self.scheduler = scheduler
        self._callback: Optional[Callable] = None

    def set_notification_callback(self, cb: Callable):
        self._callback = cb

    def set_reminder(self, title: str, trigger_time: datetime,
                     description: str = "", repeat: str = None) -> dict:
        with SessionLocal() as db:
            r = Reminder(title=title, description=description, trigger_time=trigger_time,
                         reminder_type=ReminderType.REMINDER,
                         repeat_interval=repeat if repeat and repeat != "none" else None)
            db.add(r)
            db.commit()
            db.refresh(r)
            if self.scheduler:
                self.scheduler.add_job(r.id, trigger_time, title, self._fire)
            return {"id": r.id, "title": r.title, "trigger_time": r.trigger_time.isoformat(), "type": "reminder"}

    def set_alarm(self, title: str, trigger_time: datetime, description: str = "") -> dict:
        with SessionLocal() as db:
            a = Reminder(title=title, description=description, trigger_time=trigger_time,
                         reminder_type=ReminderType.ALARM)
            db.add(a)
            db.commit()
            db.refresh(a)
            if self.scheduler:
                self.scheduler.add_job(a.id, trigger_time, title, self._fire)
            return {"id": a.id, "title": a.title, "trigger_time": a.trigger_time.isoformat(), "type": "alarm"}

    def get_reminders(self, include_triggered: bool = False) -> list:
        with SessionLocal() as db:
            q = db.query(Reminder).filter(Reminder.is_active == True)
            if not include_triggered:
                q = q.filter(Reminder.is_triggered == False)
            reminders = q.order_by(Reminder.trigger_time).all()
            return [{"id": r.id, "title": r.title, "description": r.description or "",
                     "trigger_time": r.trigger_time.isoformat(), "type": r.reminder_type.value,
                     "repeat": r.repeat_interval, "triggered": r.is_triggered} for r in reminders]

    def cancel_reminder(self, reminder_id: int) -> bool:
        with SessionLocal() as db:
            r = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            if not r:
                return False
            r.is_active = False
            db.commit()
        if self.scheduler:
            self.scheduler.remove_job(f"reminder_{reminder_id}")
        return True

    def _fire(self, reminder_id: int, title: str):
        with SessionLocal() as db:
            r = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            if r:
                r.is_triggered = True
                db.commit()
        if self._callback:
            self._callback(reminder_id, title)

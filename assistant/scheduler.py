from datetime import datetime
from typing import Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import logging

logger = logging.getLogger(__name__)


class AssistantScheduler:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        logger.info("Scheduler started")

    def add_job(self, reminder_id: int, trigger_time: datetime, title: str, callback: Callable):
        if trigger_time <= datetime.utcnow():
            logger.warning(f"Skipping past-due reminder {reminder_id}")
            return
        job_id = f"reminder_{reminder_id}"
        self._scheduler.add_job(callback, trigger=DateTrigger(run_date=trigger_time),
                                id=job_id, args=[reminder_id, title], replace_existing=True)

    def remove_job(self, job_id: str):
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def shutdown(self):
        self._scheduler.shutdown()

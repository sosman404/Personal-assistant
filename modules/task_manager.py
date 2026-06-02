from datetime import datetime
from typing import Optional
from database.connection import SessionLocal
from database.models import Task, TaskStatus, TaskPriority
import logging

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"low": TaskPriority.LOW, "medium": TaskPriority.MEDIUM,
                "high": TaskPriority.HIGH, "urgent": TaskPriority.URGENT}
STATUS_MAP = {"pending": TaskStatus.PENDING, "in_progress": TaskStatus.IN_PROGRESS,
              "completed": TaskStatus.COMPLETED, "cancelled": TaskStatus.CANCELLED}


class TaskManager:
    def __init__(self, ms_client=None):
        self.ms_client = ms_client
        self._ms_list_id: Optional[str] = None

    def _get_ms_list_id(self) -> Optional[str]:
        if self._ms_list_id or not self.ms_client:
            return self._ms_list_id
        try:
            lists = self.ms_client.get_task_lists()
            if lists:
                self._ms_list_id = lists[0]["id"]
        except Exception:
            pass
        return self._ms_list_id

    def create_task(self, title: str, description: str = "", priority: str = "medium",
                    due_date: Optional[datetime] = None, category: str = None) -> dict:
        with SessionLocal() as db:
            task = Task(title=title, description=description,
                        priority=PRIORITY_MAP.get(priority.lower(), TaskPriority.MEDIUM),
                        due_date=due_date, category=category)
            list_id = self._get_ms_list_id()
            if list_id and self.ms_client:
                try:
                    ms_task = self.ms_client.create_task(list_id, title, due_date, description)
                    task.external_id = ms_task.get("id")
                except Exception as e:
                    logger.warning(f"MS Task sync failed: {e}")
            db.add(task)
            db.commit()
            db.refresh(task)
            return {"id": task.id, "title": task.title, "priority": task.priority.value,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "status": task.status.value, "category": task.category}

    def get_tasks(self, status: str = None, category: str = None) -> list:
        with SessionLocal() as db:
            q = db.query(Task)
            if status and status.lower() in STATUS_MAP:
                q = q.filter(Task.status == STATUS_MAP[status.lower()])
            elif status == "all":
                pass
            else:
                q = q.filter(Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]))
            if category:
                q = q.filter(Task.category == category)
            tasks = q.order_by(Task.due_date.asc().nullslast()).all()
            return [{"id": t.id, "title": t.title, "description": t.description or "",
                     "status": t.status.value, "priority": t.priority.value,
                     "due_date": t.due_date.isoformat() if t.due_date else None,
                     "category": t.category} for t in tasks]

    def complete_task(self, task_id: int) -> bool:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return False
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            db.commit()
            return True

    def delete_task(self, task_id: int) -> bool:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return False
            db.delete(task)
            db.commit()
            return True

    def update_task(self, task_id: int, **kwargs) -> dict:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return {}
            if "title" in kwargs:
                task.title = kwargs["title"]
            if "description" in kwargs:
                task.description = kwargs["description"]
            if "priority" in kwargs:
                task.priority = PRIORITY_MAP.get(kwargs["priority"].lower(), task.priority)
            if "due_date" in kwargs:
                task.due_date = kwargs["due_date"]
            if "status" in kwargs:
                task.status = STATUS_MAP.get(kwargs["status"].lower(), task.status)
            if "category" in kwargs:
                task.category = kwargs["category"]
            db.commit()
            return {"id": task.id, "title": task.title, "status": task.status.value}

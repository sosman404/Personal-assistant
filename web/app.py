import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from assistant.brain import AssistantBrain
from assistant.scheduler import AssistantScheduler
from assistant.voice import VoiceHandler
from config import settings
from database.connection import init_db
from modules.calendar_manager import CalendarManager
from modules.email_manager import EmailManager
from modules.reminder_manager import ReminderManager
from modules.task_manager import TaskManager

logger = logging.getLogger(__name__)

app = FastAPI(title="ARIA - Virtual Personal Assistant", version="1.0.0")

init_db()
scheduler = AssistantScheduler()

ms_client = None
google_client = None

if settings.microsoft_client_id and settings.microsoft_client_secret:
    try:
        from integrations.microsoft_graph import MicrosoftGraphClient
        ms_client = MicrosoftGraphClient(
            settings.microsoft_client_id, settings.microsoft_client_secret,
            settings.microsoft_tenant_id, settings.microsoft_user_email,
        )
        logger.info("Microsoft Graph client ready")
    except Exception as e:
        logger.warning(f"Microsoft Graph init failed: {e}")

if settings.google_client_id:
    try:
        from integrations.google_calendar import GoogleCalendarClient
        google_client = GoogleCalendarClient()
        google_client.authenticate()
        logger.info("Google Calendar client ready")
    except Exception as e:
        logger.warning(f"Google Calendar init failed: {e}")

calendar_manager = CalendarManager(ms_client, google_client)
email_manager = EmailManager(ms_client)
task_manager = TaskManager(ms_client)
reminder_manager = ReminderManager(scheduler)
brain = AssistantBrain(calendar_manager, email_manager, task_manager, reminder_manager)
voice_handler = VoiceHandler()

active_ws: list[WebSocket] = []


async def broadcast(msg: dict):
    for ws in list(active_ws):
        try:
            await ws.send_json(msg)
        except Exception:
            pass


def on_reminder_fired(reminder_id: int, title: str):
    if voice_handler.available:
        voice_handler.speak(f"Reminder: {title}")
    asyncio.run(broadcast({"type": "reminder", "id": reminder_id, "title": title,
                           "fired_at": datetime.now().isoformat()}))


reminder_manager.set_notification_callback(on_reminder_fired)


# ── Models ──────────────────────────────────────────────────────────────────

class ChatMsg(BaseModel):
    message: str

class EventIn(BaseModel):
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = ""
    location: Optional[str] = ""
    calendar: Optional[str] = "local"

class TaskIn(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None
    category: Optional[str] = None

class ReminderIn(BaseModel):
    title: str
    trigger_time: str
    description: Optional[str] = ""
    reminder_type: Optional[str] = "reminder"

class EmailIn(BaseModel):
    to: list
    subject: str
    body: str
    cc: Optional[list] = None


# ── Static files ─────────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    path = os.path.join(static_dir, "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>ARIA Assistant</h1>")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    active_ws.append(ws)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            if data.get("type") == "chat":
                reply = brain.chat(data["message"])
                await ws.send_json({"type": "response", "message": reply})
                if voice_handler.available and data.get("speak", False):
                    voice_handler.speak(reply)
    except WebSocketDisconnect:
        if ws in active_ws:
            active_ws.remove(ws)


# ── Chat API ──────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(msg: ChatMsg):
    reply = brain.chat(msg.message)
    return {"response": reply}


@app.post("/api/chat/clear")
async def clear_chat():
    brain.clear_history()
    return {"success": True}


@app.get("/api/status")
async def status():
    return brain.get_status()


# ── Events ────────────────────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events(days: int = 7):
    return calendar_manager.get_upcoming_events(days)


@app.post("/api/events")
async def create_event(ev: EventIn):
    start = datetime.fromisoformat(ev.start_time)
    end = datetime.fromisoformat(ev.end_time) if ev.end_time else None
    return calendar_manager.create_event(ev.title, start, end, ev.description, ev.location, ev.calendar)


@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int):
    if not calendar_manager.delete_event(event_id):
        raise HTTPException(404, "Event not found")
    return {"success": True}


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None, category: Optional[str] = None):
    return task_manager.get_tasks(status, category)


@app.post("/api/tasks")
async def create_task(t: TaskIn):
    due = datetime.fromisoformat(t.due_date) if t.due_date else None
    return task_manager.create_task(t.title, t.description, t.priority, due, t.category)


@app.patch("/api/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    if not task_manager.complete_task(task_id):
        raise HTTPException(404, "Task not found")
    return {"success": True}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    if not task_manager.delete_task(task_id):
        raise HTTPException(404, "Task not found")
    return {"success": True}


# ── Reminders ─────────────────────────────────────────────────────────────────

@app.get("/api/reminders")
async def get_reminders():
    return reminder_manager.get_reminders()


@app.post("/api/reminders")
async def create_reminder(r: ReminderIn):
    t = datetime.fromisoformat(r.trigger_time)
    if r.reminder_type == "alarm":
        return reminder_manager.set_alarm(r.title, t, r.description)
    return reminder_manager.set_reminder(r.title, t, r.description)


@app.delete("/api/reminders/{reminder_id}")
async def cancel_reminder(reminder_id: int):
    if not reminder_manager.cancel_reminder(reminder_id):
        raise HTTPException(404, "Reminder not found")
    return {"success": True}


# ── Email ─────────────────────────────────────────────────────────────────────

@app.get("/api/emails")
async def get_emails(count: int = 10):
    return email_manager.get_recent_emails(count)


@app.post("/api/emails/send")
async def send_email(e: EmailIn):
    return email_manager.send_email(e.to, e.subject, e.body, e.cc)


# ── Voice ─────────────────────────────────────────────────────────────────────

@app.post("/api/voice/speak")
async def speak(msg: ChatMsg):
    if voice_handler.available:
        voice_handler.speak(msg.message)
        return {"success": True}
    return {"success": False, "error": "Voice not available on this server"}


@app.get("/api/voice/status")
async def voice_status():
    return {"available": voice_handler.available}

import json
import logging
from datetime import datetime
from typing import Optional, Callable
import anthropic

from config import settings
from assistant.tools import TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ARIA — Adaptive Responsive Intelligent Assistant, a friendly personal assistant.

Your capabilities:
- Calendar: create/view/delete events (local, Microsoft, Google)
- Email: send emails via Outlook, check inbox
- Tasks: create, list, complete, delete tasks with priorities and categories
- Reminders & Alarms: schedule time-based reminders and alarms
- Natural language date/time: understand "tomorrow at 3pm", "next Monday at noon", "in 2 hours"

Guidelines:
- Be concise and friendly
- Use the current datetime provided in each message to resolve relative times
- Always convert relative times (tomorrow, next week, in 2 hours) to actual ISO datetimes before calling tools
- After creating events/reminders, confirm with a clear summary
- For emails, confirm recipient and subject in your response
- Format lists cleanly with bullet points
- If an integration isn't configured, explain what's needed to set it up"""


class AssistantBrain:
    def __init__(self, calendar_manager, email_manager, task_manager, reminder_manager):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.calendar = calendar_manager
        self.email = email_manager
        self.tasks = task_manager
        self.reminders = reminder_manager
        self.history = []
        self._notification_cb: Optional[Callable] = None

    def set_notification_callback(self, cb: Callable):
        self._notification_cb = cb

    def _run_tool(self, name: str, inp: dict) -> str:
        try:
            if name == "get_current_datetime":
                return json.dumps({"datetime": datetime.now().isoformat(), "timezone": "local"})

            elif name == "get_upcoming_events":
                return json.dumps(self.calendar.get_upcoming_events(inp.get("days", 7)))

            elif name == "create_event":
                start = datetime.fromisoformat(inp["start_time"])
                end = datetime.fromisoformat(inp["end_time"]) if inp.get("end_time") else None
                return json.dumps(self.calendar.create_event(
                    inp["title"], start, end, inp.get("description", ""),
                    inp.get("location", ""), inp.get("calendar", "local")))

            elif name == "delete_event":
                return json.dumps({"success": self.calendar.delete_event(inp["event_id"])})

            elif name == "send_email":
                return json.dumps(self.email.send_email(
                    inp["to"], inp["subject"], inp["body"], inp.get("cc")))

            elif name == "get_recent_emails":
                return json.dumps(self.email.get_recent_emails(inp.get("count", 10)))

            elif name == "create_task":
                due = datetime.fromisoformat(inp["due_date"]) if inp.get("due_date") else None
                return json.dumps(self.tasks.create_task(
                    inp["title"], inp.get("description", ""), inp.get("priority", "medium"),
                    due, inp.get("category")))

            elif name == "get_tasks":
                return json.dumps(self.tasks.get_tasks(inp.get("status"), inp.get("category")))

            elif name == "complete_task":
                return json.dumps({"success": self.tasks.complete_task(inp["task_id"])})

            elif name == "delete_task":
                return json.dumps({"success": self.tasks.delete_task(inp["task_id"])})

            elif name == "set_reminder":
                t = datetime.fromisoformat(inp["trigger_time"])
                return json.dumps(self.reminders.set_reminder(
                    inp["title"], t, inp.get("description", ""), inp.get("repeat", "none")))

            elif name == "set_alarm":
                t = datetime.fromisoformat(inp["trigger_time"])
                return json.dumps(self.reminders.set_alarm(inp["title"], t, inp.get("description", "")))

            elif name == "get_reminders":
                return json.dumps(self.reminders.get_reminders(inp.get("include_triggered", False)))

            elif name == "cancel_reminder":
                return json.dumps({"success": self.reminders.cancel_reminder(inp["reminder_id"])})

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as e:
            logger.error(f"Tool {name} error: {e}")
            return json.dumps({"error": str(e)})

    def chat(self, user_message: str) -> str:
        now = datetime.now().strftime("%A, %B %d, %Y %H:%M")
        self.history.append({
            "role": "user",
            "content": f"[Current datetime: {now}]\n\n{user_message}",
        })

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )

            if response.stop_reason == "end_turn":
                text = next((b.text for b in response.content if hasattr(b, "text")), "")
                self.history.append({"role": "assistant", "content": response.content})
                return text

            elif response.stop_reason == "tool_use":
                self.history.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._run_tool(block.name, block.input)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                self.history.append({"role": "user", "content": results})
            else:
                break

        return "I encountered an issue. Please try again."

    def clear_history(self):
        self.history = []

    def get_status(self) -> dict:
        try:
            events = self.calendar.get_upcoming_events(7)
            tasks = self.tasks.get_tasks()
            reminders = self.reminders.get_reminders()
            return {
                "upcoming_events": len(events),
                "active_tasks": len(tasks),
                "pending_reminders": len(reminders),
                "next_event": events[0] if events else None,
                "urgent_tasks": [t for t in tasks if t["priority"] in ["high", "urgent"]],
            }
        except Exception as e:
            return {"error": str(e)}

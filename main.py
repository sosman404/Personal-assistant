#!/usr/bin/env python3
"""ARIA — Virtual Personal Assistant entry point."""

import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

def run_web():
    import uvicorn
    from config import settings
    if not settings.anthropic_api_key:
        print("\n[ERROR] ANTHROPIC_API_KEY not set. Copy .env.example to .env and fill it in.\n")
        sys.exit(1)
    print(f"\n  ARIA Personal Assistant")
    print(f"  Open http://localhost:{settings.web_port}  in your browser\n")
    uvicorn.run(
        "web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
        log_level="warning",
    )


def run_cli():
    """Interactive CLI fallback (no browser required)."""
    from config import settings
    if not settings.anthropic_api_key:
        print("\n[ERROR] ANTHROPIC_API_KEY not set.\n")
        sys.exit(1)

    from database.connection import init_db
    from modules.calendar_manager import CalendarManager
    from modules.email_manager import EmailManager
    from modules.task_manager import TaskManager
    from modules.reminder_manager import ReminderManager
    from assistant.brain import AssistantBrain
    from assistant.scheduler import AssistantScheduler
    from assistant.voice import VoiceHandler

    init_db()
    scheduler = AssistantScheduler()
    calendar_manager = CalendarManager()
    email_manager = EmailManager()
    task_manager = TaskManager()
    reminder_manager = ReminderManager(scheduler)
    brain = AssistantBrain(calendar_manager, email_manager, task_manager, reminder_manager)
    voice = VoiceHandler()

    print("\n  ARIA — Personal Assistant  (type 'exit' to quit, 'clear' to reset)\n")

    if voice.available:
        print("  Voice available — use the web UI for voice input.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("ARIA: Goodbye!")
            break
        if user_input.lower() == "clear":
            brain.clear_history()
            print("ARIA: Conversation cleared.\n")
            continue

        response = brain.chat(user_input)
        print(f"\nARIA: {response}\n")

    scheduler.shutdown()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "web"
    if mode == "cli":
        run_cli()
    else:
        run_web()

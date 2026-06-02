TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Get the current date and time",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_upcoming_events",
        "description": "Get upcoming calendar events for the next N days",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Days to look ahead (default 7)", "default": 7}},
        },
    },
    {
        "name": "create_event",
        "description": "Create a new calendar event",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string", "description": "ISO format: YYYY-MM-DDTHH:MM:SS"},
                "end_time": {"type": "string", "description": "ISO format (optional, defaults to +1 hour)"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "calendar": {"type": "string", "enum": ["local", "microsoft", "google"], "default": "local"},
            },
            "required": ["title", "start_time"],
        },
    },
    {
        "name": "delete_event",
        "description": "Delete a calendar event by ID",
        "input_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "integer"}},
            "required": ["event_id"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email using Outlook (Microsoft Graph API)",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email addresses"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "get_recent_emails",
        "description": "Get recent emails from Outlook inbox",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "default": 10}},
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "default": "medium"},
                "due_date": {"type": "string", "description": "ISO format date (optional)"},
                "category": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "get_tasks",
        "description": "Get task list filtered by status or category",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "all"]},
                "category": {"type": "string"},
            },
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task permanently",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder for a specific date and time",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "trigger_time": {"type": "string", "description": "ISO format datetime"},
                "description": {"type": "string"},
                "repeat": {"type": "string", "enum": ["none", "daily", "weekly"], "default": "none"},
            },
            "required": ["title", "trigger_time"],
        },
    },
    {
        "name": "set_alarm",
        "description": "Set an alarm for a specific time",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "trigger_time": {"type": "string", "description": "ISO format datetime"},
                "description": {"type": "string"},
            },
            "required": ["title", "trigger_time"],
        },
    },
    {
        "name": "get_reminders",
        "description": "Get all active reminders and alarms",
        "input_schema": {
            "type": "object",
            "properties": {"include_triggered": {"type": "boolean", "default": False}},
        },
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a reminder or alarm",
        "input_schema": {
            "type": "object",
            "properties": {"reminder_id": {"type": "integer"}},
            "required": ["reminder_id"],
        },
    },
]

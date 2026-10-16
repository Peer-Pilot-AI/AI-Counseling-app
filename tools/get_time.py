from datetime import datetime

TOOL = {
    "name": "get_time",
    "description": "Get the current local date and time. Use when the user asks what time or date it is.",
    "parameters": {"type": "object", "properties": {}},
}


def run(arguments: dict) -> str:
    return datetime.now().strftime("%A, %d %B %Y, %H:%M")
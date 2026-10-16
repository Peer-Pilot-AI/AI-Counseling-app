"""
Copy this file, rename it (no leading underscore), edit TOOL and run().
Restart the app and the model can call it.
(Need several tools in one file? Define TOOLS = [{..., "run": fn}, ...] - see web.py.)

A tool that needs to know WHICH student is asking can take a second argument:
    def run(arguments: dict, ctx: dict) -> str:   # ctx["user_id"] is the signed-in student
Then add the tool's name to the right modes in MODE_TOOLS in assistant.py.
"""

TOOL = {
    "name": "my_tool",   # snake_case, unique
    "description": (
        "One or two sentences the model reads to decide WHEN to call this. "
        "Be explicit about trigger phrases."
    ),
    "parameters": {      # standard JSON schema
        "type": "object",
        "properties": {
            "example_arg": {"type": "string", "description": "What this argument means"},
        },
        "required": [],
    },
}


def run(arguments: dict) -> str:
    """Do the work. Return a short plain-text result the model will read.
    Raising is fine - the registry catches it and tells the model."""
    example = arguments.get("example_arg", "")
    return f"Did the thing with {example!r}."
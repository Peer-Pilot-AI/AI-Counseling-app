"""Memory tools: let the AI save, correct, delete and search what it knows about THIS student."""
from core import memory


def _mem(ctx):
    uid = (ctx or {}).get("user_id")
    if not uid:
        raise RuntimeError("no student is signed in")
    mem = memory.for_user(uid)
    if not mem.enabled():
        raise RuntimeError("the student has turned memory off, so nothing can be saved or changed")
    return mem


def _remember(a, ctx):
    e = _mem(ctx).add(a.get("text", ""), strict=True)
    return f"Saved as [{e['id']}]: {e['text']}"


def _update(a, ctx):
    e = _mem(ctx).update(int(a["id"]), a.get("text", ""), strict=True)
    return f"Updated [{e['id']}]: {e['text']}"


def _forget(a, ctx):
    e = _mem(ctx).delete(int(a["id"]))
    return f"Deleted [{e['id']}]: {e['text']}"


def _search(a, ctx):
    hits = _mem(ctx).search(a.get("query", ""))
    return "\n".join(f"[{e['id']}] {e['text']}" for e in hits) or "No matching memories."


TOOLS = [
    {"name": "remember",
     "description": ("Save a durable, school-related fact or preference about the student so it is available in "
                     "future chats (favorite subjects, goals, colleges they like, how they like answers). Use when "
                     "the student shares something worth keeping or says 'remember...'. One short self-contained "
                     "sentence. Never save passwords, contact info, ID numbers, health, religion, immigration, "
                     "family or money problems."),
     "parameters": {"type": "object",
                    "properties": {"text": {"type": "string", "description": "The fact, one sentence"}},
                    "required": ["text"]},
     "run": _remember},
    {"name": "update_memory",
     "description": ("Correct or rewrite an existing memory by its [id] from the Memory list. Prefer this "
                     "over remember when a saved fact changed or was wrong."),
     "parameters": {"type": "object",
                    "properties": {"id": {"type": "integer", "description": "The memory's id"},
                                   "text": {"type": "string", "description": "The new full text"}},
                    "required": ["id", "text"]},
     "run": _update},
    {"name": "forget",
     "description": "Delete a memory by its [id]. Use when the student asks you to forget something.",
     "parameters": {"type": "object",
                    "properties": {"id": {"type": "integer", "description": "The memory's id"}},
                    "required": ["id"]},
     "run": _forget},
    {"name": "search_memory",
     "description": "Search saved memories by keywords. Use only if the Memory list says older ones were omitted.",
     "parameters": {"type": "object",
                    "properties": {"query": {"type": "string", "description": "Keywords"}},
                    "required": ["query"]},
     "run": _search},
]
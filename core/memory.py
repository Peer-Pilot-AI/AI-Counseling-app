"""
Private long-term memory for each student, stored in the app's SQLite database.
(Idea and API from the ai-starter project; there it was one shared JSON file, here every
student has their OWN list that only they and the AI helping them can see.)

  * The AI can remember / update_memory / forget / search_memory (tools/memory_tools.py).
  * The student can see, add, edit, delete, or switch memory off (Memory page in the app).
  * Deleting the account deletes the memory (ON DELETE CASCADE).
"""
from __future__ import annotations

import re
import threading

import database

MAX_ITEMS = 60
MAX_CHARS = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS student_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS student_memory_user_idx ON student_memory(user_id, id);
CREATE TABLE IF NOT EXISTS ai_prefs (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  memory_enabled INTEGER NOT NULL DEFAULT 1
);
"""

# Things the AI must never save on its own (the student can still decide what to type themselves).
SENSITIVE = re.compile(
    r"\b(password|passcode|pin number|ssn|social security|credit card|bank account"
    r"|diagnos\w*|therap\w*|depress\w*|anxiety|medicat\w*|suicid\w*|self[- ]harm|eating disorder|abuse\w*"
    r"|religio\w*|immigra\w*|visa status|undocumented|sexual\w*|gay|lesbian|transgender)\b"
    r"|\b\d{3}-\d{2}-\d{4}\b",
    re.I,
)


class MemoryError_(ValueError):
    """A friendly, safe-to-show problem (it is a ValueError so the web layer returns HTTP 400)."""


_lock = threading.Lock()
_ready_for = None


def ensure_schema() -> None:
    global _ready_for
    key = str(database.DB_PATH)
    if _ready_for == key:
        return
    with _lock:
        if _ready_for == key:
            return
        with database.connect() as conn:
            conn.executescript(SCHEMA)
        _ready_for = key


def _clean(text: str, *, strict: bool) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        raise MemoryError_("Nothing to remember.")
    if len(text) > MAX_CHARS:
        raise MemoryError_(f"Keep each memory under {MAX_CHARS} characters.")
    import assistant  # imported here to avoid a circular import at start-up
    import features

    if assistant.is_inappropriate(text):
        raise MemoryError_("Please keep memories kind and school-appropriate.")
    if features.CONTACT_PATTERN.search(text):
        raise MemoryError_("Memories can't hold emails, phone numbers, links, or social media names.")
    if strict and SENSITIVE.search(text):
        raise MemoryError_("I don't save private details like passwords, health, or personal identity info.")
    return text


def _entry(row) -> dict:
    return {"id": row["id"], "text": row["text"], "created": str(row["created_at"])[:10]}


class StudentMemory:
    def __init__(self, user_id: int):
        self.user_id = int(user_id)
        ensure_schema()

    def enabled(self) -> bool:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT memory_enabled FROM ai_prefs WHERE user_id=?", (self.user_id,)
            ).fetchone()
        return True if row is None else bool(row["memory_enabled"])

    def set_enabled(self, value: bool) -> None:
        with database.connect() as conn:
            conn.execute(
                """INSERT INTO ai_prefs(user_id,memory_enabled) VALUES(?,?)
                ON CONFLICT(user_id) DO UPDATE SET memory_enabled=excluded.memory_enabled""",
                (self.user_id, 1 if value else 0),
            )

    def all(self) -> list[dict]:
        with database.connect() as conn:
            rows = conn.execute(
                "SELECT id,text,created_at FROM student_memory WHERE user_id=? ORDER BY id", (self.user_id,)
            ).fetchall()
        return [_entry(r) for r in rows]

    def add(self, text: str, *, strict: bool = False) -> dict:
        text = _clean(text, strict=strict)
        with database.connect() as conn:
            rows = conn.execute(
                "SELECT id,text,created_at FROM student_memory WHERE user_id=?", (self.user_id,)
            ).fetchall()
            for r in rows:
                if r["text"].lower() == text.lower():
                    return _entry(r)  # already known
            if len(rows) >= MAX_ITEMS:
                raise MemoryError_(f"Memory is full ({MAX_ITEMS}). Delete or update an older one first.")
            cur = conn.execute("INSERT INTO student_memory(user_id,text) VALUES(?,?)", (self.user_id, text))
            row = conn.execute(
                "SELECT id,text,created_at FROM student_memory WHERE id=?", (cur.lastrowid,)
            ).fetchone()
        return _entry(row)

    def update(self, entry_id: int, text: str, *, strict: bool = False) -> dict:
        text = _clean(text, strict=strict)
        with database.connect() as conn:
            cur = conn.execute(
                "UPDATE student_memory SET text=? WHERE id=? AND user_id=?", (text, int(entry_id), self.user_id)
            )
            if not cur.rowcount:
                raise MemoryError_(f"No memory with id {entry_id}.")
            row = conn.execute(
                "SELECT id,text,created_at FROM student_memory WHERE id=?", (int(entry_id),)
            ).fetchone()
        return _entry(row)

    def delete(self, entry_id: int) -> dict:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT id,text,created_at FROM student_memory WHERE id=? AND user_id=?",
                (int(entry_id), self.user_id),
            ).fetchone()
            if not row:
                raise MemoryError_(f"No memory with id {entry_id}.")
            conn.execute("DELETE FROM student_memory WHERE id=? AND user_id=?", (int(entry_id), self.user_id))
        return _entry(row)

    def clear(self) -> int:
        with database.connect() as conn:
            return conn.execute("DELETE FROM student_memory WHERE user_id=?", (self.user_id,)).rowcount

    def search(self, query: str) -> list[dict]:
        words = [w for w in str(query).lower().split() if w]
        return [e for e in self.all() if all(w in e["text"].lower() for w in words)]

    def prompt_block(self, max_chars: int = 3000) -> str:
        """Text for the system prompt: every fact (newest kept if over budget)."""
        entries = self.all()
        if not entries:
            return "(nothing saved yet)"
        lines, used, omitted = [], 0, False
        for e in reversed(entries):                  # newest first, keep what fits
            line = f"[{e['id']}] {e['text']}"
            if used + len(line) > max_chars:
                omitted = True
                break
            lines.append(line)
            used += len(line) + 1
        lines.reverse()
        if omitted:
            lines.insert(0, "(older memories omitted - use search_memory to find them)")
        return "\n".join(lines)


def for_user(user_id: int) -> StudentMemory:
    return StudentMemory(user_id)
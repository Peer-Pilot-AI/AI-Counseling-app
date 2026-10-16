"""PeerPilot AI extras: peer mentors, a scholarship tracker, and one combined deadlines list.

Everything here is account-scoped and uses the same SQLite database as the rest of the app.
app.py hands any request whose path matches owns() to handle().
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
from datetime import date, datetime, timezone

import assistant
import database
from core import memory as memory_mod

SCHEMA = """
CREATE TABLE IF NOT EXISTS mentor_profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  handle TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, stage TEXT NOT NULL,
  school TEXT NOT NULL DEFAULT '', topics_json TEXT NOT NULL DEFAULT '[]',
  bio TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mentor_requests (
  id TEXT PRIMARY KEY,
  mentee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mentor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mentee_name TEXT NOT NULL DEFAULT '', mentor_name TEXT NOT NULL DEFAULT '',
  topic TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','closed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS mentor_requests_open_pair_idx
  ON mentor_requests(mentee_id, mentor_id) WHERE status IN ('pending','accepted');
CREATE INDEX IF NOT EXISTS mentor_requests_mentee_idx ON mentor_requests(mentee_id, updated_at);
CREATE INDEX IF NOT EXISTS mentor_requests_mentor_idx ON mentor_requests(mentor_id, updated_at);
CREATE TABLE IF NOT EXISTS mentor_messages (
  id INTEGER PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES mentor_requests(id) ON DELETE CASCADE,
  sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS mentor_messages_request_idx ON mentor_messages(request_id, id);
CREATE TABLE IF NOT EXISTS scholarships (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, provider TEXT NOT NULL DEFAULT '', amount TEXT NOT NULL DEFAULT '',
  due TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Interested', requirements_json TEXT NOT NULL DEFAULT '[]',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS scholarships_user_due_idx ON scholarships(user_id, due);
"""

SCHOLARSHIP_STATUSES = ["Interested", "Working on it", "Submitted", "Won", "Not selected"]
FINISHED_SCHOLARSHIP = {"submitted", "won", "not selected"}
FINISHED_APPLICATION = {"submitted", "accepted", "declined", "withdrawn", "waitlisted", "enrolled"}
MENTOR_STAGES = [
    "Grade 11",
    "Grade 12",
    "College freshman",
    "College sophomore",
    "College junior",
    "College senior",
    "Recent graduate",
]

# Chats stay inside the app: block emails, phone numbers, links, social handles and "text me" talk.
CONTACT_PATTERN = re.compile(
    r"(https?://|www\.|[\w.+-]+@[\w-]+\.[\w.]+|@\w{3,}"
    r"|(?:\+?\d[\s().-]?){9,}|\b\d{3}[-.\s]\d{4}\b"
    r"|\b(?:snap(?:chat)?|insta(?:gram)?|tiktok|whats\s?app|discord|telegram|kik|signal|venmo|cash\s?app|facetime)\b"
    r"|\b(?:text|call|dm)\s+me\b"
    r"|\bmy\s+(?:number|email|phone|address|handle|username)\b)",
    re.I,
)
CONTACT_ERROR = (
    "For everyone's safety, please keep chats inside PeerPilot AI. "
    "Don't share emails, phone numbers, links, social media names, or addresses."
)

_schema_lock = threading.Lock()
_schema_for = None
_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}


def ensure_schema() -> None:
    """Create the extra tables once per database file."""
    global _schema_for
    key = str(database.DB_PATH)
    if _schema_for == key:
        return
    with _schema_lock:
        if _schema_for == key:
            return
        with database.connect() as conn:
            conn.executescript(SCHEMA)
        memory_mod.ensure_schema()
        _schema_for = key


def _rate(key: str, limit: int, period: int) -> None:
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_buckets.get(key, []) if now - t < period]
        if len(hits) >= limit:
            _rate_buckets[key] = hits
            raise ValueError("Slow down a little and try again in a few minutes.")
        hits.append(now)
        _rate_buckets[key] = hits
        if len(_rate_buckets) > 5000:
            for k in [k for k, v in _rate_buckets.items() if not v or now - v[-1] > 3600]:
                _rate_buckets.pop(k, None)


def _check_text(text: str) -> None:
    if assistant.is_inappropriate(text):
        raise ValueError("Please keep your words kind and school-appropriate.")
    if CONTACT_PATTERN.search(text):
        raise ValueError(CONTACT_ERROR)


def _clean_date(value) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError("Dates must look like 2026-12-01.") from None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _profile(conn, uid: int) -> dict:
    row = conn.execute("SELECT data_json FROM profiles WHERE user_id=?", (uid,)).fetchone()
    value = database.json_load(row["data_json"], {}) if row else {}
    return value if isinstance(value, dict) else {}


def _display_name(conn, uid: int) -> str:
    profile = _profile(conn, uid)
    first = str(profile.get("firstName", "")).strip()[:30]
    last = str(profile.get("lastName", "")).strip()
    if not first:
        raise ValueError("Add your first name in My profile before using Peer mentors.")
    return f"{first} {last[0].upper()}." if last else first


# ---------------------------------------------------------------- deadlines


def collect_deadlines(conn, uid: int, today: date | None = None) -> list[dict]:
    today = today or date.today()
    items: list[dict] = []

    def add(kind, item_id, title, due, detail):
        try:
            d = date.fromisoformat(str(due)[:10])
        except ValueError:
            return
        days = (d - today).days
        urgency = "overdue" if days < 0 else "soon" if days <= 7 else "month" if days <= 30 else "later"
        items.append(
            {
                "kind": kind,
                "id": item_id,
                "title": title,
                "due": d.isoformat(),
                "detail": detail,
                "days_left": days,
                "urgency": urgency,
            }
        )

    for r in conn.execute(
        "SELECT id,title,due,category FROM tasks WHERE user_id=? AND done=0 AND due!=''", (uid,)
    ):
        add("task", r["id"], r["title"], r["due"], r["category"])
    for r in conn.execute(
        "SELECT id,college_name,due,status FROM applications WHERE user_id=? AND due!=''", (uid,)
    ):
        if str(r["status"]).strip().lower() not in FINISHED_APPLICATION:
            add("application", r["id"], f"{r['college_name']} application", r["due"], r["status"])
    for r in conn.execute(
        "SELECT id,name,due,status,amount FROM scholarships WHERE user_id=? AND due!=''", (uid,)
    ):
        if str(r["status"]).strip().lower() not in FINISHED_SCHOLARSHIP:
            add("scholarship", r["id"], r["name"], r["due"], r["amount"] or r["status"])
    items.sort(key=lambda x: (x["due"], x["title"].lower()))
    return items


def upcoming_for_ai(conn, uid: int) -> list[dict]:
    """A short list the AI coach can use to say what is due soon. Never raises."""
    try:
        ensure_schema()
        rows = [x for x in collect_deadlines(conn, uid) if x["days_left"] <= 60][:8]
    except Exception:
        return []
    return [
        {"what": f"{x['kind']}: {x['title']}"[:120], "due": x["due"], "days_left": x["days_left"]}
        for x in rows
    ]


def _deadlines_payload(conn, uid: int) -> dict:
    items = collect_deadlines(conn, uid)
    counts = {
        "overdue": sum(1 for x in items if x["urgency"] == "overdue"),
        "soon": sum(1 for x in items if x["urgency"] == "soon"),
        "month": sum(1 for x in items if x["urgency"] in {"soon", "month"}),
    }
    return {"deadlines": items, "counts": counts}


# -------------------------------------------------------------- scholarships


def _requirements(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:12]:
        if isinstance(item, str):
            item = {"text": item, "done": False}
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()[:120]
        if text:
            out.append({"text": text, "done": bool(item.get("done"))})
    return out


def _https(value) -> str:
    url = str(value or "").strip()[:500]
    if url and not url.startswith("https://"):
        raise ValueError("Links must start with https://")
    return url


def _scholarship_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "provider": row["provider"],
        "amount": row["amount"],
        "due": row["due"],
        "url": row["url"],
        "status": row["status"],
        "requirements": database.json_load(row["requirements_json"], []),
        "notes": row["notes"],
    }


def _scholarship_fields(data: dict, partial: bool) -> dict:
    fields: dict = {}
    if not partial or "name" in data:
        name = str(data.get("name", "")).strip()[:200]
        if not name:
            raise ValueError("Give the scholarship a name.")
        fields["name"] = name
    if "provider" in data:
        fields["provider"] = str(data["provider"]).strip()[:150]
    if "amount" in data:
        fields["amount"] = str(data["amount"]).strip()[:60]
    if "due" in data:
        fields["due"] = _clean_date(data["due"])
    if "url" in data:
        fields["url"] = _https(data["url"])
    if "status" in data:
        if data["status"] not in SCHOLARSHIP_STATUSES:
            raise ValueError("Pick a status from the list.")
        fields["status"] = data["status"]
    if "requirements" in data:
        fields["requirements_json"] = json.dumps(_requirements(data["requirements"]))
    if "notes" in data:
        fields["notes"] = str(data["notes"]).strip()[:1000]
    return fields


def _scholarships_route(conn, user, method: str, parts: list[str], data: dict):
    uid = user["id"]
    if method == "GET" and len(parts) == 2:
        rows = conn.execute(
            "SELECT * FROM scholarships WHERE user_id=? ORDER BY (due='') , due, name", (uid,)
        ).fetchall()
        return 200, {"scholarships": [_scholarship_dict(r) for r in rows], "statuses": SCHOLARSHIP_STATUSES}
    if method == "POST" and len(parts) == 2:
        count = conn.execute("SELECT COUNT(*) FROM scholarships WHERE user_id=?", (uid,)).fetchone()[0]
        if count >= 200:
            raise ValueError("You've reached the limit of 200 scholarships. Remove a few first.")
        fields = _scholarship_fields(data, partial=False)
        sid = secrets.token_hex(8)
        cols = ["id", "user_id", *fields]
        conn.execute(
            f"INSERT INTO scholarships({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
            [sid, uid, *fields.values()],
        )
        row = conn.execute("SELECT * FROM scholarships WHERE id=?", (sid,)).fetchone()
        return 201, {"scholarship": _scholarship_dict(row)}
    if method == "PUT" and len(parts) == 2:
        sid = str(data.get("id", ""))
        if not conn.execute("SELECT 1 FROM scholarships WHERE id=? AND user_id=?", (sid, uid)).fetchone():
            raise ValueError("That scholarship was not found.")
        fields = _scholarship_fields(data, partial=True)
        if fields:
            sets = ",".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE scholarships SET {sets},updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                [*fields.values(), sid, uid],
            )
        row = conn.execute("SELECT * FROM scholarships WHERE id=?", (sid,)).fetchone()
        return 200, {"scholarship": _scholarship_dict(row)}
    if method == "DELETE" and len(parts) == 3:
        conn.execute("DELETE FROM scholarships WHERE id=? AND user_id=?", (parts[2], uid))
        return 200, {"ok": True}
    return None


# ------------------------------------------------------------------ mentors


def _topic_list(value) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    seen, out = set(), []
    for item in value:
        text = re.sub(r"\s+", " ", str(item)).strip()[:40]
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out[:8]


def _profile_words(profile: dict) -> str:
    parts = [profile.get("major", ""), profile.get("career", "")]
    for key in ("interests", "colleges"):
        value = profile.get(key, [])
        if isinstance(value, list):
            parts.extend(str(v) for v in value[:30])
    return " ".join(str(p) for p in parts).lower()


def _match(topics: list[str], blob: str) -> list[str]:
    shared = []
    for topic in topics:
        low = topic.lower()
        tokens = [t for t in re.findall(r"[a-z0-9]+", low) if len(t) >= 4]
        if low in blob or any(t in blob for t in tokens):
            shared.append(topic)
    return shared


def _request_dict(row, uid: int) -> dict:
    role = "mentee" if row["mentee_id"] == uid else "mentor"
    return {
        "id": row["id"],
        "role": role,
        "other_name": row["mentor_name"] if role == "mentee" else row["mentee_name"],
        "topic": row["topic"],
        "message": row["message"],
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


def _mentor_overview(conn, uid: int) -> dict:
    profile = _profile(conn, uid)
    blob = _profile_words(profile)
    mine = conn.execute("SELECT * FROM mentor_profiles WHERE user_id=?", (uid,)).fetchone()
    open_with = {
        r["mentor_id"]: {"id": r["id"], "status": r["status"]}
        for r in conn.execute(
            "SELECT id,mentor_id,status FROM mentor_requests WHERE mentee_id=? AND status IN ('pending','accepted')",
            (uid,),
        )
    }
    mentors = []
    for r in conn.execute(
        """SELECT m.* FROM mentor_profiles m JOIN users u ON u.id=m.user_id
        WHERE m.active=1 AND u.is_active=1 AND m.user_id!=? ORDER BY m.updated_at DESC LIMIT 100""",
        (uid,),
    ):
        topics = database.json_load(r["topics_json"], [])
        shared = _match(topics, blob)
        mentors.append(
            {
                "id": r["handle"],
                "name": r["display_name"],
                "stage": r["stage"],
                "school": r["school"],
                "topics": topics,
                "bio": r["bio"],
                "shared": shared,
                "request": open_with.get(r["user_id"]),
            }
        )
    mentors.sort(key=lambda m: -len(m["shared"]))
    requests = [
        _request_dict(r, uid)
        for r in conn.execute(
            """SELECT * FROM mentor_requests WHERE mentee_id=? OR mentor_id=?
            ORDER BY updated_at DESC LIMIT 100""",
            (uid, uid),
        )
    ]
    return {
        "mentors": mentors,
        "requests": requests,
        "stages": MENTOR_STAGES,
        "name_ready": bool(str(profile.get("firstName", "")).strip()),
        "me": (
            {
                "name": mine["display_name"],
                "stage": mine["stage"],
                "school": mine["school"],
                "topics": database.json_load(mine["topics_json"], []),
                "bio": mine["bio"],
                "active": bool(mine["active"]),
            }
            if mine
            else None
        ),
    }


def _save_mentor_profile(conn, uid: int, data: dict):
    if not data.get("agree_rules"):
        raise ValueError("Please tick the box to agree to the mentor rules.")
    stage = data.get("stage")
    if stage not in MENTOR_STAGES:
        raise ValueError("Pick where you are right now.")
    topics = _topic_list(data.get("topics"))
    if not topics:
        raise ValueError("Add at least one topic you can help with.")
    bio = str(data.get("bio", "")).strip()
    if len(bio) < 20 or len(bio) > 400:
        raise ValueError("Write 20 to 400 characters about how you can help.")
    school = str(data.get("school", "")).strip()[:80]
    _check_text(" ".join([bio, school, *topics]))
    name = _display_name(conn, uid)
    active = 1 if data.get("active", True) else 0
    existing = conn.execute("SELECT 1 FROM mentor_profiles WHERE user_id=?", (uid,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE mentor_profiles SET display_name=?,stage=?,school=?,topics_json=?,bio=?,active=?,
            updated_at=CURRENT_TIMESTAMP WHERE user_id=?""",
            (name, stage, school, json.dumps(topics), bio, active, uid),
        )
    else:
        conn.execute(
            """INSERT INTO mentor_profiles(user_id,handle,display_name,stage,school,topics_json,bio,active)
            VALUES(?,?,?,?,?,?,?,?)""",
            (uid, secrets.token_urlsafe(9), name, stage, school, json.dumps(topics), bio, active),
        )
    return 200, _mentor_overview(conn, uid)


def _own_request(conn, uid: int, request_id: str):
    row = conn.execute(
        "SELECT * FROM mentor_requests WHERE id=? AND (mentee_id=? OR mentor_id=?)",
        (request_id, uid, uid),
    ).fetchone()
    if not row:
        raise ValueError("That chat was not found.")
    return row


def _mentors_route(conn, user, method: str, parts: list[str], data: dict):
    uid = user["id"]
    if method == "GET" and len(parts) == 2:
        return 200, _mentor_overview(conn, uid)
    if parts[2:3] == ["me"] and len(parts) == 3:
        if method == "PUT":
            return _save_mentor_profile(conn, uid, data)
        if method == "DELETE":
            conn.execute("DELETE FROM mentor_profiles WHERE user_id=?", (uid,))
            conn.execute(
                """UPDATE mentor_requests SET status='closed',updated_at=CURRENT_TIMESTAMP
                WHERE mentor_id=? AND status IN ('pending','accepted')""",
                (uid,),
            )
            return 200, _mentor_overview(conn, uid)
    if parts[2:3] == ["requests"] and len(parts) == 3:
        if method == "POST":
            _rate(f"mentor-request-tries:{uid}", 30, 3_600)  # typos shouldn't burn the daily allowance
            mentor = conn.execute(
                """SELECT m.* FROM mentor_profiles m JOIN users u ON u.id=m.user_id
                WHERE m.handle=? AND m.active=1 AND u.is_active=1""",
                (str(data.get("mentor", "")),),
            ).fetchone()
            if not mentor or mentor["user_id"] == uid:
                raise ValueError("That mentor isn't available.")
            topic = str(data.get("topic", "")).strip()[:60]
            message = str(data.get("message", "")).strip()
            if not topic:
                raise ValueError("Pick what you want help with.")
            if len(message) < 10 or len(message) > 500:
                raise ValueError("Write 10 to 500 characters so your mentor knows how to help.")
            _check_text(f"{topic} {message}")
            open_count = conn.execute(
                "SELECT COUNT(*) FROM mentor_requests WHERE mentee_id=? AND status IN ('pending','accepted')",
                (uid,),
            ).fetchone()[0]
            if open_count >= 5:
                raise ValueError("You have 5 open mentor chats. Close one before asking someone new.")
            if conn.execute(
                "SELECT 1 FROM mentor_requests WHERE mentee_id=? AND mentor_id=? AND status IN ('pending','accepted')",
                (uid, mentor["user_id"]),
            ).fetchone():
                raise ValueError("You already have an open chat with this mentor.")
            mentee_name = _display_name(conn, uid)
            _rate(f"mentor-request:{uid}", 5, 86_400)
            rid = secrets.token_hex(8)
            conn.execute(
                """INSERT INTO mentor_requests(id,mentee_id,mentor_id,mentee_name,mentor_name,topic,message)
                VALUES(?,?,?,?,?,?,?)""",
                (rid, uid, mentor["user_id"], mentee_name, mentor["display_name"], topic, message),
            )
            return 201, _mentor_overview(conn, uid)
        if method == "PUT":
            row = _own_request(conn, uid, str(data.get("id", "")))
            action = data.get("action")
            new_status = None
            if action in {"accept", "decline"}:
                if row["mentor_id"] != uid or row["status"] != "pending":
                    raise ValueError("Only the mentor can answer a new request.")
                new_status = "accepted" if action == "accept" else "declined"
            elif action == "close":
                if row["status"] not in {"pending", "accepted"}:
                    raise ValueError("That chat is already finished.")
                new_status = "closed"
            else:
                raise ValueError("Unknown action.")
            conn.execute(
                "UPDATE mentor_requests SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_status, row["id"]),
            )
            return 200, _mentor_overview(conn, uid)
    if parts[2:3] == ["requests"] and len(parts) == 5 and parts[4] == "messages":
        row = _own_request(conn, uid, parts[3])
        if method == "GET":
            msgs = conn.execute(
                "SELECT id,sender_id,body,created_at FROM mentor_messages WHERE request_id=? ORDER BY id DESC LIMIT 200",
                (row["id"],),
            ).fetchall()[::-1]
            return 200, {
                "request": _request_dict(row, uid),
                "messages": [
                    {
                        "id": m["id"],
                        "mine": m["sender_id"] == uid,
                        "sender": row["mentee_name"] if m["sender_id"] == row["mentee_id"] else row["mentor_name"],
                        "body": m["body"],
                        "at": m["created_at"],
                    }
                    for m in msgs
                ],
            }
        if method == "POST":
            if row["status"] != "accepted":
                raise ValueError("You can chat once the mentor says yes.")
            body = str(data.get("body", "")).strip()
            if not body or len(body) > 1000:
                raise ValueError("Write a message up to 1,000 characters.")
            _check_text(body)
            _rate(f"mentor-msg:{uid}", 30, 600)
            cur = conn.execute(
                "INSERT INTO mentor_messages(request_id,sender_id,body) VALUES(?,?,?)", (row["id"], uid, body)
            )
            conn.execute("UPDATE mentor_requests SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
            return 201, {
                "message": {"id": cur.lastrowid, "mine": True, "sender": "", "body": body, "at": _now()}
            }
    if method == "POST" and parts[2:3] == ["report"] and len(parts) == 3:
        row = _own_request(conn, uid, str(data.get("request_id", "")))
        reason = str(data.get("reason", "")).strip()
        if len(reason) < 5 or len(reason) > 500:
            raise ValueError("Tell us what happened in 5 to 500 characters.")
        conn.execute(
            "INSERT INTO user_feedback(user_id,category,details) VALUES(?,?,?)",
            (
                uid,
                "Peer mentor report",
                f"Chat {row['id']} ({row['mentee_name']} with {row['mentor_name']}): {reason}"[:2000],
            ),
        )
        conn.execute(
            "UPDATE mentor_requests SET status='closed',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('pending','accepted')",
            (row["id"],),
        )
        return 200, {"ok": True}
    return None


# ------------------------------------------------------------------- router


def owns(path: str) -> bool:
    return (
        path.startswith("/api/mentors")
        or path.startswith("/api/scholarships")
        or path.startswith("/api/memory")
        or path == "/api/deadlines"
    )


# ------------------------------------------------------------ AI memory page


def _memory_payload(mem) -> dict:
    return {
        "enabled": mem.enabled(),
        "items": mem.all(),
        "limit": memory_mod.MAX_ITEMS,
        "max_chars": memory_mod.MAX_CHARS,
    }


def _memory_route(user, method: str, parts: list[str], data: dict):
    mem = memory_mod.for_user(user["id"])
    if method == "GET" and len(parts) == 2:
        return 200, _memory_payload(mem)
    if method == "POST" and len(parts) == 2:
        mem.add(data.get("text", ""))
        return 201, _memory_payload(mem)
    if method == "PUT" and len(parts) == 2:
        try:
            entry_id = int(data.get("id"))
        except (TypeError, ValueError):
            raise ValueError("Pick a memory to change.") from None
        mem.update(entry_id, data.get("text", ""))
        return 200, _memory_payload(mem)
    if method == "PUT" and parts[2:3] == ["settings"] and len(parts) == 3:
        mem.set_enabled(bool(data.get("enabled")))
        return 200, _memory_payload(mem)
    if method == "DELETE" and len(parts) == 2:
        mem.clear()
        return 200, _memory_payload(mem)
    if method == "DELETE" and len(parts) == 3:
        try:
            entry_id = int(parts[2])
        except ValueError:
            raise ValueError("Pick a memory to delete.") from None
        mem.delete(entry_id)
        return 200, _memory_payload(mem)
    return None


def handle(handler, method: str, path: str, data: dict | None) -> None:
    user = handler.user()
    ensure_schema()
    parts = path.strip("/").split("/")
    data = data or {}
    try:
        if parts[1] == "memory":
            result = _memory_route(user, method, parts, data)
            if result is None:
                return handler.send_json(404, {"error": "Unknown route."})
            return handler.send_json(result[0], result[1])
        with database.connect() as conn:
            if parts[1] == "deadlines" and method == "GET":
                result = 200, _deadlines_payload(conn, user["id"])
            elif parts[1] == "scholarships":
                result = _scholarships_route(conn, user, method, parts, data)
            elif parts[1] == "mentors":
                result = _mentors_route(conn, user, method, parts, data)
            else:
                result = None
    except ValueError as exc:
        return handler.send_json(400, {"error": str(exc)})
    if result is None:
        return handler.send_json(404, {"error": "Unknown route."})
    return handler.send_json(result[0], result[1])
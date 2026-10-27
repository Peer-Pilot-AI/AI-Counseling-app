"""Supabase integration: Auth (GoTrue) + Postgres (PostgREST) over plain HTTPS.

Everything here runs on the server. Requests use the *signed-in user's* JWT plus the public anon key,
so Postgres Row Level Security (see supabase/migrations) decides what each user can read or write.
The optional service-role key is only used to delete an auth user and is never sent to the browser.
"""
from __future__ import annotations

import os
import time

import requests

TIMEOUT = 10
SPLIT = ("courses", "planned", "activities", "goals")  # stored in their own tables


def enabled() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY"))


def _base() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/")


def _hdr(token: str | None = None, key: str | None = None, extra: dict | None = None) -> dict:
    k = key or os.environ["SUPABASE_ANON_KEY"]
    h = {"apikey": k, "Authorization": f"Bearer {token or k}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def _session(d: dict) -> dict:
    user = d.get("user") or {}
    return {
        "user_id": user.get("id"),
        "email": (user.get("email") or "").lower(),
        "access": d.get("access_token"),
        "refresh": d.get("refresh_token"),
        "exp": int(time.time()) + int(d.get("expires_in") or 3600),
    }


# ---------- Auth ----------
def signup(email: str, password: str) -> dict:
    r = requests.post(f"{_base()}/auth/v1/signup", json={"email": email, "password": password}, headers=_hdr(), timeout=TIMEOUT)
    d = r.json() if r.content else {}
    if r.status_code >= 400:
        raise ValueError(d.get("msg") or d.get("error_description") or "Could not create the account.")
    if not d.get("access_token"):  # email confirmation is switched on in Supabase
        raise ValueError("Check your email to confirm your account, then sign in.")
    return _session(d)


def login(email: str, password: str) -> dict | None:
    r = requests.post(f"{_base()}/auth/v1/token?grant_type=password", json={"email": email, "password": password}, headers=_hdr(), timeout=TIMEOUT)
    return _session(r.json()) if r.status_code == 200 else None


def refresh(refresh_token: str) -> dict | None:
    r = requests.post(f"{_base()}/auth/v1/token?grant_type=refresh_token", json={"refresh_token": refresh_token}, headers=_hdr(), timeout=TIMEOUT)
    return _session(r.json()) if r.status_code == 200 else None


def logout(access: str) -> None:
    try:
        requests.post(f"{_base()}/auth/v1/logout", headers=_hdr(access), timeout=TIMEOUT)
    except requests.RequestException:
        pass


def recover(email: str) -> None:
    requests.post(f"{_base()}/auth/v1/recover", json={"email": email}, headers=_hdr(), timeout=TIMEOUT)


def delete_auth_user(sb_uid: str) -> bool:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        return False
    r = requests.delete(f"{_base()}/auth/v1/admin/users/{sb_uid}", headers=_hdr(key=key), timeout=TIMEOUT)
    return r.status_code < 300


# ---------- Data (RLS enforced by Postgres) ----------
def _rest(method: str, table: str, token: str, **kw):
    r = requests.request(method, f"{_base()}/rest/v1/{table}", headers=_hdr(token, extra=kw.pop("extra", None)), timeout=TIMEOUT, **kw)
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase {method} {table} failed ({r.status_code}): {r.text[:200]}")
    return r.json() if method == "GET" else None


def _replace(table: str, token: str, uid: str, rows: list[dict]) -> None:
    _rest("DELETE", table, token, params={"user_id": f"eq.{uid}"})
    if rows:
        _rest("POST", table, token, json=[{**r, "user_id": uid} for r in rows], extra={"Prefer": "return=minimal"})


def push_state(token: str, uid: str, profile: dict, completed: list[str]) -> None:
    """Write the user's profile, courses, goals, activities and roadmap progress."""
    core = {k: v for k, v in profile.items() if k not in SPLIT}
    _rest("POST", "profiles", token, json={"user_id": uid, "data": core}, extra={"Prefer": "resolution=merge-duplicates,return=minimal"})
    _replace("courses", token, uid, [{"position": i, "planned": p, "data": c} for p, key in ((False, "courses"), (True, "planned")) for i, c in enumerate(profile.get(key) or [])])
    _replace("activities", token, uid, [{"position": i, "data": a} for i, a in enumerate(profile.get("activities") or [])])
    goals = profile.get("goals")
    lines = [g for g in (goals if isinstance(goals, list) else str(goals or "").split("\n")) if str(g).strip()]
    _replace("goals", token, uid, [{"position": i, "body": str(g)} for i, g in enumerate(lines)])
    _replace("roadmap_progress", token, uid, [{"step_id": s} for s in completed])


def pull_state(token: str) -> dict | None:
    """Return {'profile', 'completed'} for the signed-in user, or None if nothing is stored yet."""
    prof = _rest("GET", "profiles", token, params={"select": "data"})
    if not prof:
        return None
    profile = dict(prof[0]["data"] or {})
    rows = lambda t: _rest("GET", t, token, params={"select": "*", "order": "position"})
    courses = rows("courses")
    profile["courses"] = [r["data"] for r in courses if not r["planned"]]
    profile["planned"] = [r["data"] for r in courses if r["planned"]]
    profile["activities"] = [r["data"] for r in rows("activities")]
    profile["goals"] = "\n".join(r["body"] for r in rows("goals"))
    done = _rest("GET", "roadmap_progress", token, params={"select": "step_id"})
    return {"profile": profile, "completed": [r["step_id"] for r in done]}


def push_messages(token: str, uid: str, msgs: list[dict]) -> None:
    rows = [{"user_id": uid, "role": m["role"], "content": m["content"], "citations": m.get("citations") or []} for m in msgs]
    if rows:
        _rest("POST", "chat_messages", token, json=rows, extra={"Prefer": "return=minimal"})


def pull_messages(token: str, limit: int = 100) -> list[dict]:
    rows = _rest("GET", "chat_messages", token, params={"select": "role,content,citations", "order": "id.desc", "limit": limit})
    return list(reversed(rows))


def delete_all(token: str, uid: str) -> None:
    for t in ("chat_messages", "roadmap_progress", "goals", "activities", "courses", "profiles"):
        _rest("DELETE", t, token, params={"user_id": f"eq.{uid}"})
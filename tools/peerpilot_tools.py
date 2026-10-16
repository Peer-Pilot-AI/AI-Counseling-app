"""PeerPilot tools: look up THIS student's dates and scholarship tracker (read-only)."""
import database
import features


def _uid(ctx):
    uid = (ctx or {}).get("user_id")
    if not uid:
        raise RuntimeError("no student is signed in")
    return uid


def _deadlines(a, ctx):
    uid = _uid(ctx)
    days = max(1, min(int(a.get("within_days") or 60), 365))
    with database.connect() as conn:
        items = [x for x in features.collect_deadlines(conn, uid) if x["days_left"] <= days]
    if not items:
        return f"Nothing due in the next {days} days (and nothing overdue)."
    lines = []
    for x in items[:25]:
        when = f"{-x['days_left']} days OVERDUE" if x["days_left"] < 0 else f"in {x['days_left']} days"
        lines.append(f"- {x['title']} ({x['kind']}) due {x['due']}, {when}")
    return "\n".join(lines)


def _scholarships(a, ctx):
    uid = _uid(ctx)
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT name,provider,amount,due,status FROM scholarships WHERE user_id=? ORDER BY (due=''), due",
            (uid,),
        ).fetchall()
    if not rows:
        return "The student has not saved any scholarships yet."
    return "\n".join(
        f"- {r['name']} ({r['provider'] or 'provider unknown'}), {r['amount'] or 'amount unknown'}, "
        f"due {r['due'] or 'no date'}, status: {r['status']}"
        for r in rows[:40]
    )


TOOLS = [
    {"name": "get_deadlines",
     "description": ("List this student's upcoming and overdue tasks, college applications and scholarship "
                     "deadlines, soonest first. Use when they ask what is due, what to do first, or to plan time."),
     "parameters": {"type": "object",
                    "properties": {"within_days": {"type": "integer", "description": "Look ahead this many days, default 60"}}},
     "run": _deadlines},
    {"name": "get_scholarship_tracker",
     "description": ("List the scholarships this student already saved (name, amount, due date, status). "
                     "Use before suggesting scholarships so you don't repeat ones they have."),
     "parameters": {"type": "object", "properties": {}},
     "run": _scholarships},
]
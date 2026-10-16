"""Owner-only tool: save every user's information to files you can open.

Run:   python admin_export.py          (basic: account + profile info)
       python admin_export.py --full   (also tasks, applications, essays, chats)

Writes into a folder called "exports". Passwords are NEVER written out,
because the app only keeps scrambled (hashed) passwords and that is on purpose.
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import database

FULL = "--full" in sys.argv
OUT = Path(__file__).resolve().parent / "exports"


def rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def as_json(text):
    try:
        return json.loads(text)
    except Exception:
        return {}


def main():
    OUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    people = []
    with database.connect() as conn:
        users = rows(conn, "SELECT id,email,is_admin,is_active,created_at FROM users ORDER BY id")
        for u in users:
            uid = u["id"]
            prof = conn.execute("SELECT data_json FROM profiles WHERE user_id=?", (uid,)).fetchone()
            legal = rows(
                conn,
                "SELECT terms_version,privacy_version,accepted_at,guardian_permission_confirmed "
                "FROM legal_acceptances WHERE user_id=? ORDER BY accepted_at DESC LIMIT 1",
                (uid,),
            )
            person = {
                "id": uid,
                "username_email": u["email"],
                "is_admin": bool(u["is_admin"]),
                "is_active": bool(u["is_active"]),
                "created_at": u["created_at"],
                "profile": as_json(prof["data_json"]) if prof else {},
                "latest_legal_acceptance": legal[0] if legal else None,
            }
            if FULL:
                person["tasks"] = rows(conn, "SELECT * FROM tasks WHERE user_id=?", (uid,))
                person["applications"] = rows(conn, "SELECT * FROM applications WHERE user_id=?", (uid,))
                person["essays"] = rows(conn, "SELECT * FROM essays WHERE user_id=?", (uid,))
                person["feedback"] = rows(conn, "SELECT * FROM user_feedback WHERE user_id=?", (uid,))
                convos = rows(conn, "SELECT * FROM conversations WHERE user_id=?", (uid,))
                for c in convos:
                    c["messages"] = rows(
                        conn,
                        "SELECT role,content,created_at FROM messages WHERE conversation_id=? ORDER BY id",
                        (c["id"],),
                    )
                person["conversations"] = convos
            people.append(person)

    json_path = OUT / f"all_users_{stamp}.json"
    json_path.write_text(json.dumps(people, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = OUT / f"all_users_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "username_email", "is_admin", "is_active", "created_at",
                    "guardian_permission_confirmed", "terms_accepted_at"])
        for p in people:
            legal = p["latest_legal_acceptance"] or {}
            w.writerow([p["id"], p["username_email"], p["is_admin"], p["is_active"], p["created_at"],
                        legal.get("guardian_permission_confirmed", ""), legal.get("accepted_at", "")])

    print(f"Saved {len(people)} users to:\n  {json_path}\n  {csv_path}")
    print("Keep these files private. Delete them when you are done.")


if __name__ == "__main__":
    main()
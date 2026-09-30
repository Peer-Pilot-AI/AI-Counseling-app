"""Local Python web app: secure accounts, private SQLite data, AI and web research."""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import assistant
import database

ROOT = Path(__file__).resolve().parent
COOKIE_NAME = "student_session"
TERMS_VERSION = "2026-09-27"
PRIVACY_VERSION = "2026-09-27"
SESSION_SECONDS = 60 * 60 * 24 * 7
RATE_LOCK = threading.Lock()
RATE_BUCKETS: dict[str, list[float]] = {}
BLANK_PROFILE = {
    "firstName": "", "lastName": "", "grade": "9", "school": "", "state": "", "gpa": "",
    "major": "", "career": "", "colleges": [], "courses": [], "planned": [], "activities": [],
    "interests": [], "goals": "", "awards": [], "competitions": [], "volunteer": [], "work": [], "internships": [],
}


def load_env() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for row in path.read_text(encoding="utf-8").splitlines():
        row = row.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def take_rate(key: str, limit: int, period: int) -> bool:
    now = time.monotonic()
    with RATE_LOCK:
        hits = [t for t in RATE_BUCKETS.get(key, []) if now - t < period]
        if len(hits) >= limit:
            RATE_BUCKETS[key] = hits
            return False
        hits.append(now)
        RATE_BUCKETS[key] = hits
        return True


def safe_profile(value) -> dict:
    result = BLANK_PROFILE.copy()
    if not isinstance(value, dict):
        return result
    for key in result:
        if key not in value:
            continue
        raw = value[key]
        if key in {"colleges", "courses", "planned", "activities", "interests", "awards", "competitions", "volunteer", "work", "internships"}:
            if isinstance(raw, list):
                result[key] = raw[:100]
        else:
            result[key] = str(raw)[:4000]
    if str(result["grade"]) not in {"9", "10", "11", "12"}:
        result["grade"] = "9"
    return result


def password_valid(value) -> bool:
    return isinstance(value, str) and 10 <= len(value) <= 200


def college_dict(row) -> dict:
    return {"id":row["slug"],"name":row["name"],"location":row["location"],"initials":"".join(x[0] for x in row["name"].split()[:2]),"majors":database.json_load(row["majors_json"],[]),"summary":row["summary"],"source":row["admissions_url"],"prepSource":row["preparation_url"],"aidSource":row["financial_aid_url"],"aid":"Check the official financial aid page for current policies and eligibility.","lastVerified":row["last_verified"] or "Not verified","verificationStatus":row["verification_status"]}


def opportunity_dict(row) -> dict:
    return {"id":row["slug"],"name":row["name"],"category":row["category"],"description":row["description"],"eligibility":row["eligibility"],"deadline":row["deadline"],"cost":row["cost"],"location":row["location"],"application":row["application_info"],"interests":database.json_load(row["interests_json"],[]),"link":row["official_url"],"source":row["source_title"] or row["name"],"verified":row["last_verified"] or "Not verified","verificationStatus":row["verification_status"]}


def init_admin() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
    if not email or not password:
        return
    with database.connect() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        if exists:
            conn.execute("UPDATE users SET is_admin=1 WHERE id=?",(exists["id"],))
        else:
            cur = conn.execute("INSERT INTO users(email,password_hash,is_admin) VALUES(?,?,1)",(email,hash_password(password)))
            conn.execute("INSERT INTO profiles(user_id,data_json) VALUES(?,?)",(cur.lastrowid,json.dumps(BLANK_PROFILE)))


class Handler(BaseHTTPRequestHandler):
    server_version = "StudentJourney/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, status: int, value: dict, cookie: str | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        if cookie is not None:
            secure_default = "true" if os.environ.get("APP_ENV", "development").lower() == "production" else "false"
            secure = "; Secure" if os.environ.get("APP_SECURE_COOKIES", secure_default).lower() == "true" else ""
            self.send_header("Set-Cookie",f"{COOKIE_NAME}={cookie}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}{secure}")
        self.end_headers()
        self.wfile.write(body)

    def clear_cookie(self) -> None:
        self.send_header("Set-Cookie",f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64_000:
            raise ValueError("Request body is empty or too large.")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value

    def origin_ok(self) -> bool:
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        origin = self.headers.get("Origin")
        return not origin or origin.rstrip("/") == f"http://{self.headers.get('Host','')}" or origin.rstrip("/") == f"https://{self.headers.get('Host','')}"

    def user(self, required=True):
        cookie = self.headers.get("Cookie", "")
        token = next((part.strip().split("=",1)[1] for part in cookie.split(";") if part.strip().startswith(COOKIE_NAME+"=")), "")
        if not token:
            if required: raise PermissionError("Sign in to continue.")
            return None
        with database.connect() as conn:
            row = conn.execute("""SELECT u.id,u.email,u.is_admin,u.is_active,s.token_hash
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?""",(token_hash(token),int(time.time()))).fetchone()
        if not row or not row["is_active"]:
            if required: raise PermissionError("Your session expired. Sign in again.")
            return None
        return row

    def do_GET(self) -> None:
        path=urlparse(self.path).path
        try:
            if path == "/api/health":
                return self.send_json(200,{"ok":True,"ai_configured":bool(os.environ.get("OPENAI_API_KEY")),"model":os.environ.get("OPENAI_MODEL","gpt-6-luna"),"reasoning_effort":os.environ.get("OPENAI_REASONING_EFFORT","high")})
            if path == "/api/auth/me":
                user=self.user(False)
                return self.send_json(200,{"user":{"id":user["id"],"email":user["email"],"is_admin":bool(user["is_admin"])} if user else None})
            if path == "/api/bootstrap":
                user=self.user()
                return self.send_json(200,self.bootstrap(user))
            if path == "/api/colleges":
                self.user()
                with database.connect() as conn:
                    rows=conn.execute("SELECT * FROM colleges ORDER BY name").fetchall()
                return self.send_json(200,{"colleges":[college_dict(r) for r in rows]})
            if path == "/api/opportunities":
                self.user()
                with database.connect() as conn:
                    rows=conn.execute("""SELECT o.*,s.title AS source_title FROM opportunities o
                        LEFT JOIN sources s ON s.id=o.source_id ORDER BY o.category,o.name""").fetchall()
                return self.send_json(200,{"opportunities":[opportunity_dict(r) for r in rows]})
            if path == "/api/applications":
                user=self.user()
                with database.connect() as conn:
                    rows=conn.execute("SELECT * FROM applications WHERE user_id=? ORDER BY due",(user["id"],)).fetchall()
                return self.send_json(200,{"applications":[dict(r) for r in rows]})
            if path == "/api/school/courses":
                user=self.user()
                with database.connect() as conn:
                    profile=conn.execute("SELECT data_json FROM profiles WHERE user_id=?",(user["id"],)).fetchone()
                    school=database.json_load(profile["data_json"],{}).get("school","") if profile else ""
                    rows=conn.execute("""SELECT c.*,s.name AS school_name FROM courses c JOIN schools s ON s.id=c.school_id
                        WHERE s.name=? AND c.verification_status='verified' ORDER BY c.grade,c.name""",(school,)).fetchall()
                return self.send_json(200,{"courses":[dict(r) for r in rows]})
            if path == "/api/admin/overview":
                user=self.user()
                if not user["is_admin"]: raise PermissionError("Administrator access required.")
                with database.connect() as conn:
                    counts={table:conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("users","schools","courses","colleges","opportunities","research_records","user_feedback")}
                return self.send_json(200,{"counts":counts})
            if path == "/api/admin/users":
                user=self.user()
                if not user["is_admin"]: raise PermissionError("Administrator access required.")
                with database.connect() as conn:
                    rows=conn.execute("SELECT id,email,is_admin,is_active,created_at FROM users ORDER BY created_at DESC LIMIT 300").fetchall()
                return self.send_json(200,{"users":[dict(r) for r in rows]})
            if path == "/api/admin/records":
                user=self.user()
                if not user["is_admin"]: raise PermissionError("Administrator access required.")
                return self.send_json(200,self.admin_records())
            return self.static(path)
        except PermissionError as exc: self.send_json(401 if str(exc)!="Administrator access required." else 403,{"error":str(exc)})
        except Exception as exc:
            print(f"GET {path}: {type(exc).__name__}")
            self.send_json(500,{"error":"The request could not be completed."})

    def bootstrap(self,user) -> dict:
        uid=user["id"]
        with database.connect() as conn:
            profile=conn.execute("SELECT data_json FROM profiles WHERE user_id=?",(uid,)).fetchone()
            prefs_row=conn.execute("SELECT state_json FROM user_state WHERE user_id=?",(uid,)).fetchone()
            tasks=conn.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY due",(uid,)).fetchall()
            college_rows=conn.execute("""SELECT c.* FROM colleges c JOIN saved_colleges s ON s.college_id=c.id WHERE s.user_id=?""",(uid,)).fetchall()
            op_rows=conn.execute("""SELECT o.*,s.title AS source_title,so.status FROM opportunities o
                JOIN saved_opportunities so ON so.opportunity_id=o.id LEFT JOIN sources s ON s.id=o.source_id
                WHERE so.user_id=?""",(uid,)).fetchall()
            custom=conn.execute("SELECT * FROM custom_colleges WHERE user_id=?",(uid,)).fetchall()
            messages=conn.execute("""SELECT m.role,m.content,m.citations_json FROM messages m JOIN conversations c ON c.id=m.conversation_id
                WHERE c.user_id=? ORDER BY m.id DESC LIMIT 100""",(uid,)).fetchall()
            apps=conn.execute("SELECT * FROM applications WHERE user_id=? ORDER BY due",(uid,)).fetchall()
            all_colleges=conn.execute("SELECT * FROM colleges ORDER BY name").fetchall()
            all_opps=conn.execute("""SELECT o.*,s.title AS source_title FROM opportunities o LEFT JOIN sources s ON s.id=o.source_id ORDER BY o.category,o.name""").fetchall()
        saved_opps={r["id"]:r["status"] for r in op_rows}
        prefs=database.json_load(prefs_row["state_json"],{}) if prefs_row else {}
        saved_custom=[c["id"] for c in custom if c["id"] in prefs.get("savedCustomColleges",[])]
        custom_items=[{"id":r["id"],"name":r["name"],"location":r["location"],"initials":"".join(x[0] for x in r["name"].split()[:2]),"majors":database.json_load(r["majors_json"],[]),"summary":"Custom college entry. Verify details with official sources.","source":r["official_url"],"prepSource":r["official_url"],"aidSource":"","lastVerified":"Not verified","verificationStatus":"unverified"} for r in custom]
        return {"user":{"id":uid,"email":user["email"],"is_admin":bool(user["is_admin"])} ,"profile":safe_profile(database.json_load(profile["data_json"],{}) if profile else {}),"tasks":[{**dict(r),"done":bool(r["done"])} for r in tasks],"colleges":[college_dict(r) for r in all_colleges],"savedColleges":[r["slug"] for r in college_rows]+saved_custom,"opportunities":[opportunity_dict(r) for r in all_opps],"savedOpportunities":[k for k,v in saved_opps.items() if v in {"saved","applied","completed"}],"appliedOpportunities":[k for k,v in saved_opps.items() if v in {"applied","completed"}],"completedOpportunities":[k for k,v in saved_opps.items() if v=="completed"],"messages":[{"role":r["role"],"text":r["content"],"citations":database.json_load(r["citations_json"],[])} for r in reversed(messages)],"savedRoadmap":prefs.get("savedRoadmap",[]),"completedRoadmap":prefs.get("completedRoadmap",[]),"applications":[dict(r) for r in apps],"customColleges":custom_items,"aiConfigured":bool(os.environ.get("OPENAI_API_KEY"))}

    def admin_records(self) -> dict:
        with database.connect() as conn:
            schools=conn.execute("SELECT * FROM schools ORDER BY name").fetchall()
            courses=conn.execute("SELECT * FROM courses ORDER BY school_id,grade,name").fetchall()
            colleges=conn.execute("SELECT * FROM colleges ORDER BY name").fetchall()
            opps=conn.execute("SELECT * FROM opportunities ORDER BY name").fetchall()
            feedback=conn.execute("SELECT id,user_id,category,details,created_at FROM user_feedback ORDER BY id DESC LIMIT 200").fetchall()
            failures=conn.execute("SELECT intent,query,error,latency_ms,created_at FROM research_records WHERE error<>'' ORDER BY id DESC LIMIT 100").fetchall()
            sources=conn.execute("SELECT title,organization,url,accessed_at,source_type FROM sources ORDER BY accessed_at DESC LIMIT 200").fetchall()
            history=conn.execute("SELECT entity_type,entity_id,title,url,verification_status,retrieved_at FROM source_history ORDER BY id DESC LIMIT 300").fetchall()
        return {"schools":[dict(r) for r in schools],"courses":[dict(r) for r in courses],"colleges":[dict(r) for r in colleges],"opportunities":[dict(r) for r in opps],"feedback":[dict(r) for r in feedback],"aiFailures":[dict(r) for r in failures],"sources":[dict(r) for r in sources],"sourceHistory":[dict(r) for r in history]}

    def static(self,path:str) -> None:
        requested=unquote(path.lstrip("/")) or "index.html"
        target=(ROOT/requested).resolve()
        if requested not in {"index.html","styles.css","app.js","legal.css","terms.html","privacy.html","assets/logo.png"} or ROOT not in target.parents or not target.is_file():
            self.send_error(404)
            return
        body=target.read_bytes()
        mime=mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","same-origin")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path=urlparse(self.path).path
        if not self.origin_ok(): return self.send_json(403,{"error":"Cross-site request rejected."})
        try:
            data=self.read_json()
            if path=="/api/auth/register": return self.register(data)
            if path=="/api/auth/login": return self.login(data)
            if path=="/api/auth/logout": return self.logout()
            if path=="/api/auth/password-reset/request": return self.reset_request(data)
            if path=="/api/auth/password-reset/complete": return self.reset_complete(data)
            user=self.user()
            if path in {"/api/assistant/chat","/api/assistant/tutor","/api/assistant/study-plan","/api/assistant/essay-feedback"}:
                mode={"/api/assistant/chat":"advisor","/api/assistant/tutor":"tutor","/api/assistant/study-plan":"study_plan","/api/assistant/essay-feedback":"essay_feedback"}[path]
                if not take_rate(f"ai:{user['id']}",20,600): return self.send_json(429,{"error":"Too many AI requests. Please wait a few minutes and try again."})
                return self.ai_request(user,data,mode)
            if path=="/api/state": return self.save_state(user,data)
            if path=="/api/tasks": return self.add_task(user,data)
            if path=="/api/feedback": return self.add_feedback(user,data)
            if path=="/api/colleges": return self.add_custom_college(user,data)
            if path=="/api/applications": return self.add_application(user,data)
            if path=="/api/essays": return self.save_essay(user,data)
            if path=="/api/essays/feedback": return self.essay_feedback(user,data)
            if path=="/api/account/delete": return self.delete_account(user,data)
            if path.startswith("/api/admin/"):
                if not user["is_admin"]: return self.send_json(403,{"error":"Administrator access required."})
                return self.admin_post(path,data,user)
            return self.send_json(404,{"error":"Unknown route."})
        except PermissionError as exc: self.send_json(401,{"error":str(exc)})
        except ValueError as exc: self.send_json(400,{"error":str(exc)})
        except sqlite3.IntegrityError as exc: self.send_json(409,{"error":"That record already exists or contains invalid data."})
        except RuntimeError as exc: self.send_json(503,{"error":str(exc)})
        except Exception as exc:
            print(f"POST {path}: {type(exc).__name__}")
            self.send_json(500,{"error":"The request could not be completed."})

    def do_PUT(self) -> None:
        if not self.origin_ok(): return self.send_json(403,{"error":"Cross-site request rejected."})
        try:
            user=self.user(); data=self.read_json(); path=urlparse(self.path).path
            if path=="/api/profile":
                profile=safe_profile(data.get("profile",data))
                with database.connect() as conn:
                    conn.execute("INSERT INTO profiles(user_id,data_json) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data_json=excluded.data_json,updated_at=CURRENT_TIMESTAMP",(user["id"],json.dumps(profile,ensure_ascii=False)))
                return self.send_json(200,{"profile":profile})
            if path=="/api/applications": return self.update_application(user,data)
            if path.startswith("/api/admin/records/"):
                if not user["is_admin"]: return self.send_json(403,{"error":"Administrator access required."})
                return self.admin_put(path,data,user)
            return self.send_json(404,{"error":"Unknown route."})
        except PermissionError as exc: self.send_json(401,{"error":str(exc)})
        except ValueError as exc: self.send_json(400,{"error":str(exc)})
        except Exception as exc:
            print(f"PUT {self.path}: {type(exc).__name__}")
            self.send_json(500,{"error":"The request could not be completed."})

    def do_DELETE(self) -> None:
        if not self.origin_ok(): return self.send_json(403,{"error":"Cross-site request rejected."})
        try:
            user=self.user(); path=urlparse(self.path).path
            if path=="/api/chat":
                with database.connect() as conn: conn.execute("DELETE FROM conversations WHERE user_id=?",(user["id"],))
                return self.send_json(200,{"ok":True})
            if path.startswith("/api/tasks/"):
                task_id=unquote(path.rsplit("/",1)[-1])
                with database.connect() as conn: conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?",(task_id,user["id"]))
                return self.send_json(200,{"ok":True})
            if path.startswith("/api/applications/"):
                app_id=unquote(path.rsplit("/",1)[-1])
                with database.connect() as conn: conn.execute("DELETE FROM applications WHERE id=? AND user_id=?",(app_id,user["id"]))
                return self.send_json(200,{"ok":True})
            if path.startswith("/api/essays/"):
                essay_id=unquote(path.rsplit("/",1)[-1])
                with database.connect() as conn: conn.execute("DELETE FROM essays WHERE id=? AND user_id=?",(essay_id,user["id"]))
                return self.send_json(200,{"ok":True})
            return self.send_json(404,{"error":"Unknown route."})
        except PermissionError as exc: self.send_json(401,{"error":str(exc)})

    def register(self,data):
        ip=self.client_address[0]
        if not take_rate(f"auth:{ip}",8,3600): return self.send_json(429,{"error":"Too many account attempts. Please try again later."})
        email=str(data.get("email","")).strip().lower()
        password=data.get("password","")
        if data.get("legal_agreement") is not True or data.get("terms_version") != TERMS_VERSION or data.get("privacy_version") != PRIVACY_VERSION:
            raise ValueError("Please review and accept the current Terms of Service and Privacy Notice.")
        if data.get("age_13_plus") is not True:
            raise ValueError("You must be at least 13 years old to create an account.")
        if data.get("guardian_permission") is not True:
            raise ValueError("If you are under 18, you must first have a parent or guardian review the documents and give permission.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email) or len(email)>254: raise ValueError("Enter a valid email address.")
        if not password_valid(password): raise ValueError("Password must be between 10 and 200 characters.")
        with database.connect() as conn:
            cur=conn.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",(email,hash_password(password)))
            uid=cur.lastrowid
            conn.execute("INSERT INTO profiles(user_id,data_json) VALUES(?,?)",(uid,json.dumps(BLANK_PROFILE)))
            conn.execute("INSERT INTO legal_acceptances(user_id,terms_version,privacy_version,accepted_at,guardian_permission_confirmed) VALUES(?,?,?,?,1)",(uid,TERMS_VERSION,PRIVACY_VERSION,utcnow()))
        self.create_session(uid,email,False)

    def login(self,data):
        if not take_rate(f"auth:{self.client_address[0]}",12,900): return self.send_json(429,{"error":"Too many sign-in attempts. Please wait and try again."})
        email=str(data.get("email","")).strip().lower(); password=data.get("password","")
        with database.connect() as conn: row=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not row or not row["is_active"] or not check_password(password,row["password_hash"]):
            return self.send_json(401,{"error":"Email or password is incorrect."})
        self.create_session(row["id"],row["email"],bool(row["is_admin"]))

    def create_session(self,uid,email,is_admin):
        token=secrets.token_urlsafe(32)
        with database.connect() as conn:
            conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",(token_hash(token),uid,int(time.time())+SESSION_SECONDS))
        self.send_json(200,{"user":{"id":uid,"email":email,"is_admin":is_admin}},token)

    def logout(self):
        user=self.user(False)
        if user:
            with database.connect() as conn: conn.execute("DELETE FROM sessions WHERE token_hash=?",(user["token_hash"],))
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Set-Cookie",f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    def reset_request(self,data):
        email=str(data.get("email","")).strip().lower()
        with database.connect() as conn: user=conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        # Email delivery is intentionally not simulated. Dev mode shows a single-use reset code.
        response={"message":"If the account exists, follow the reset instructions. For local development only, a reset code is returned when APP_ENV=development."}
        if user and os.environ.get("APP_ENV","development")=="development":
            token=secrets.token_urlsafe(28)
            with database.connect() as conn:
                conn.execute("INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES(?,?,?)",(token_hash(token),user["id"],int(time.time())+1800))
            response["development_reset_code"]=token
        self.send_json(200,response)

    def reset_complete(self,data):
        token=str(data.get("token", "")); password=data.get("password","")
        if not password_valid(password): raise ValueError("Password must be between 10 and 200 characters.")
        with database.connect() as conn:
            row=conn.execute("SELECT * FROM password_resets WHERE token_hash=? AND consumed=0 AND expires_at>?",(token_hash(token),int(time.time()))).fetchone()
            if not row: return self.send_json(400,{"error":"Reset code is invalid or expired."})
            conn.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(password),row["user_id"]))
            conn.execute("UPDATE password_resets SET consumed=1 WHERE token_hash=?",(token_hash(token),))
            conn.execute("DELETE FROM sessions WHERE user_id=?",(row["user_id"],))
        self.send_json(200,{"ok":True,"message":"Password reset. Sign in with your new password."})

    def save_state(self,user,data):
        uid=user["id"]
        with database.connect() as conn:
            if isinstance(data.get("profile"),dict):
                profile=safe_profile(data["profile"])
                conn.execute("INSERT INTO profiles(user_id,data_json) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data_json=excluded.data_json,updated_at=CURRENT_TIMESTAMP",(uid,json.dumps(profile,ensure_ascii=False)))
            if isinstance(data.get("tasks"),list):
                conn.execute("DELETE FROM tasks WHERE user_id=?",(uid,))
                for t in data["tasks"][:200]:
                    if not isinstance(t,dict) or not str(t.get("title","")).strip(): continue
                    due=str(t.get("due", ""))[:10]
                    if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}",due): due=""
                    conn.execute("INSERT INTO tasks(id,user_id,title,due,category,notes,done) VALUES(?,?,?,?,?,?,?)",(str(t.get("id") or secrets.token_hex(8))[:80],uid,str(t["title"])[:300],due,str(t.get("category","Personal task"))[:80],str(t.get("notes",""))[:1000],int(bool(t.get("done")))))
            if isinstance(data.get("messages"),list):
                self.store_messages(conn,uid,data["messages"])
            if any(k in data for k in ("completedRoadmap","savedRoadmap","savedColleges","customColleges")):
                prefrow=conn.execute("SELECT state_json FROM user_state WHERE user_id=?",(uid,)).fetchone()
                prefs=database.json_load(prefrow["state_json"],{}) if prefrow else {}
                if isinstance(data.get("completedRoadmap"),list): prefs["completedRoadmap"]=[str(x)[:80] for x in data["completedRoadmap"][:100]]
                if isinstance(data.get("savedRoadmap"),list): prefs["savedRoadmap"]=[str(x)[:80] for x in data["savedRoadmap"][:100]]
                if isinstance(data.get("savedColleges"),list): prefs["savedCustomColleges"]=[str(x)[:80] for x in data["savedColleges"] if str(x).startswith("custom-")][:100]
                conn.execute("INSERT INTO user_state(user_id,state_json) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json,updated_at=CURRENT_TIMESTAMP",(uid,json.dumps(prefs)))
            if isinstance(data.get("savedColleges"),list):
                conn.execute("DELETE FROM saved_colleges WHERE user_id=?",(uid,))
                for slug in set(map(str,data["savedColleges"][:100])):
                    conn.execute("INSERT OR IGNORE INTO saved_colleges(user_id,college_id) SELECT ?,id FROM colleges WHERE slug=?",(uid,slug))
            saved=set(map(str,data.get("savedOpportunities",[])[:100]))
            applied=set(map(str,data.get("appliedOpportunities",[])[:100]))
            completed=set(map(str,data.get("completedOpportunities",[])[:100]))
            if any(isinstance(data.get(k),list) for k in ("savedOpportunities","appliedOpportunities","completedOpportunities")):
                conn.execute("DELETE FROM saved_opportunities WHERE user_id=?",(uid,))
                for slug in saved|applied|completed:
                    status="completed" if slug in completed else "applied" if slug in applied else "saved"
                    conn.execute("INSERT OR IGNORE INTO saved_opportunities(user_id,opportunity_id,status) SELECT ?,id,? FROM opportunities WHERE slug=?",(uid,status,slug))
            if isinstance(data.get("customColleges"),list):
                conn.execute("DELETE FROM custom_colleges WHERE user_id=?",(uid,))
                for c in data["customColleges"][:100]:
                    if not isinstance(c,dict) or not str(c.get("name","")).strip(): continue
                    url=str(c.get("source", ""))[:1000]
                    if url and not url.startswith("https://"): url=""
                    majors=[str(m)[:100] for m in c.get("majors",[])[:20]] if isinstance(c.get("majors"),list) else []
                    conn.execute("INSERT INTO custom_colleges(id,user_id,name,location,majors_json,official_url) VALUES(?,?,?,?,?,?)",(str(c.get("id") or secrets.token_hex(8))[:80],uid,str(c["name"])[:300],str(c.get("location",""))[:300],json.dumps(majors),url))
        return self.send_json(200,{"ok":True})

    def store_messages(self,conn,uid,messages):
        row=conn.execute("SELECT id FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",(uid,)).fetchone()
        cid=row["id"] if row else secrets.token_urlsafe(16)
        if not row: conn.execute("INSERT INTO conversations(id,user_id) VALUES(?,?)",(cid,uid))
        # Replace the active transcript, strictly within the authenticated user's conversation.
        conn.execute("DELETE FROM messages WHERE conversation_id=?",(cid,))
        for m in messages[-100:]:
            if not isinstance(m,dict) or m.get("role") not in {"user","assistant"}: continue
            content=str(m.get("text",m.get("content", "")))[:8000]
            citations=m.get("citations",[]) if isinstance(m.get("citations"),list) else []
            safe_sources=[{k:str(s.get(k,""))[:1000] for k in ("title","url","accessed_at")} for s in citations[:12] if isinstance(s,dict) and str(s.get("url","")).startswith("https://")]
            conn.execute("INSERT INTO messages(conversation_id,role,content,citations_json) VALUES(?,?,?,?)",(cid,m["role"],content,json.dumps(safe_sources,ensure_ascii=False)))
        conn.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(cid,))

    def add_task(self,user,data):
        if not str(data.get("title","")).strip(): raise ValueError("Task title is required.")
        task={"id":str(data.get("id") or secrets.token_hex(8)),"title":str(data["title"])[:300],"due":str(data.get("due",""))[:10],"category":str(data.get("category","Personal task"))[:80],"notes":str(data.get("notes",""))[:1000],"done":False}
        with database.connect() as conn: conn.execute("INSERT INTO tasks(id,user_id,title,due,category,notes) VALUES(?,?,?,?,?,?)",(task["id"],user["id"],task["title"],task["due"],task["category"],task["notes"]))
        self.send_json(201,{"task":task})

    def add_custom_college(self,user,data):
        name=str(data.get("name","")).strip()
        if not name: raise ValueError("College name is required.")
        url=str(data.get("url", ""))[:1000]
        if url and not url.startswith("https://"): raise ValueError("Use an official HTTPS URL.")
        cid="custom-"+secrets.token_hex(8)
        majors=data.get("majors",[]) if isinstance(data.get("majors"),list) else []
        with database.connect() as conn: conn.execute("INSERT INTO custom_colleges(id,user_id,name,location,majors_json,official_url) VALUES(?,?,?,?,?,?)",(cid,user["id"],name[:300],str(data.get("location",""))[:300],json.dumps([str(x)[:100] for x in majors[:20]]),url))
        self.send_json(201,{"id":cid})

    def add_application(self,user,data):
        name=str(data.get("college_name", "")).strip()
        if not name: raise ValueError("College name is required.")
        status=str(data.get("status","Not Started"))
        if status not in {"Not Started","In Progress","Submitted","Complete"}: raise ValueError("Choose a valid application status.")
        app_id=str(data.get("id") or secrets.token_hex(12))
        with database.connect() as conn: conn.execute("INSERT INTO applications(id,user_id,college_name,due,status,notes) VALUES(?,?,?,?,?,?)",(app_id,user["id"],name[:300],str(data.get("due",""))[:10],status,str(data.get("notes",""))[:1000]))
        self.send_json(201,{"id":app_id})

    def update_application(self,user,data):
        app_id=str(data.get("id","")); status=str(data.get("status","Not Started"))
        if status not in {"Not Started","In Progress","Submitted","Complete"}: raise ValueError("Choose a valid application status.")
        with database.connect() as conn: conn.execute("UPDATE applications SET status=?,due=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(status,str(data.get("due",""))[:10],str(data.get("notes",""))[:1000],app_id,user["id"]))
        self.send_json(200,{"ok":True})

    def add_feedback(self,user,data):
        category=str(data.get("category","Other"))
        if category not in {"Incorrect information","Outdated information","Missing source","Bad recommendation","Other"}: raise ValueError("Choose a feedback category.")
        details=str(data.get("details",""))[:4000]
        with database.connect() as conn: conn.execute("INSERT INTO user_feedback(user_id,category,details) VALUES(?,?,?)",(user["id"],category,details))
        self.send_json(201,{"ok":True})

    def ai_request(self,user,data,mode):
        started=time.perf_counter(); uid=user["id"]
        with database.connect() as conn:
            row=conn.execute("SELECT data_json FROM profiles WHERE user_id=?",(uid,)).fetchone()
            profile=safe_profile(database.json_load(row["data_json"],{}) if row else {})
        try:
            result=assistant.answer(data,profile,mode)
            latency=int((time.perf_counter()-started)*1000)
            if mode=="essay_feedback" and data.get("essay_id"):
                with database.connect() as conn: conn.execute("UPDATE essays SET feedback=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(result["answer"],str(data["essay_id"]),uid))
            with database.connect() as conn:
                prior=data.get("history",[]) if isinstance(data.get("history"),list) else []
                transcript=prior[-98:]+[{"role":"user","text":str(data.get("message",""))},{"role":"assistant","text":result["answer"],"citations":result["sources"]}]
                self.store_messages(conn,uid,transcript)
                conn.execute("INSERT INTO research_records(user_id,intent,query,sources_json,researched,latency_ms) VALUES(?,?,?,?,?,?)",(uid,result["intent"],str(data.get("message",""))[:8000],json.dumps(result["sources"]),int(result["researched"]),latency))
                for source in result["sources"]:
                    conn.execute("INSERT OR IGNORE INTO sources(title,organization,url,accessed_at) VALUES(?,?,?,?)",(source["title"],source["title"],source["url"],source["accessed_at"]))
            return self.send_json(200,{**result,"latency_ms":latency})
        except Exception as exc:
            with database.connect() as conn:
                conn.execute("INSERT INTO research_records(user_id,intent,query,error,latency_ms) VALUES(?,?,?,?,?)",(uid,assistant.classify(str(data.get("message","")),mode)["intent"],str(data.get("message",""))[:8000],str(exc)[:500],int((time.perf_counter()-started)*1000)))
            raise

    def save_essay(self,user,data):
        title=str(data.get("title","Essay draft")).strip()[:250]
        body=str(data.get("body",""))
        if not body.strip() or len(body)>30_000: raise ValueError("Essay must contain text and stay under 30,000 characters.")
        essay_id=str(data.get("id") or secrets.token_hex(12))
        with database.connect() as conn:
            conn.execute("""INSERT INTO essays(id,user_id,title,prompt,body) VALUES(?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,prompt=excluded.prompt,body=excluded.body,updated_at=CURRENT_TIMESTAMP
                WHERE essays.user_id=excluded.user_id""",(essay_id,user["id"],title,str(data.get("prompt",""))[:4000],body))
        self.send_json(200,{"id":essay_id})

    def essay_feedback(self,user,data):
        essay_id=str(data.get("essay_id",""))
        with database.connect() as conn: row=conn.execute("SELECT * FROM essays WHERE id=? AND user_id=?",(essay_id,user["id"])).fetchone()
        if not row: raise ValueError("Essay was not found in your account.")
        message=f"Give coaching feedback on this student essay. Do not rewrite it. Prompt: {row['prompt']}\nEssay title: {row['title']}\nDraft:\n{row['body']}"
        return self.ai_request(user,{"message":message,"history":[],"essay_id":essay_id},"essay_feedback")

    def delete_account(self,user,data):
        with database.connect() as conn: row=conn.execute("SELECT password_hash FROM users WHERE id=?",(user["id"],)).fetchone()
        if not row or not check_password(str(data.get("password","")),row["password_hash"]): raise PermissionError("Password is incorrect.")
        with database.connect() as conn: conn.execute("DELETE FROM users WHERE id=?",(user["id"],))
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Set-Cookie",f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    def record_source_history(self,conn,entity_type,entity_id,title,url,status,user_id=None):
        if not url: return
        conn.execute("INSERT INTO source_history(entity_type,entity_id,title,url,verification_status,retrieved_at,verified_by) VALUES(?,?,?,?,?,?,?)",(entity_type,entity_id,title[:300],url,status,utcnow(),user_id if status=="verified" else None))
        conn.execute("INSERT OR IGNORE INTO sources(title,organization,url,accessed_at) VALUES(?,?,?,?)",(title[:300],title[:300],url,utcnow()))

    def admin_put(self,path,data,user):
        match=re.fullmatch(r"/api/admin/records/(college|school|course|opportunity)/(\d+)",path)
        if not match: return self.send_json(404,{"error":"Unknown administrator record."})
        kind,record_id=match.group(1),int(match.group(2))
        verified=bool(data.get("verified")); status="verified" if verified else "unverified"; checked=date.today().isoformat() if verified else None
        with database.connect() as conn:
            if kind=="college":
                source=str(data.get("source", "")); self.check_https(source)
                conn.execute("UPDATE colleges SET name=?,location=?,majors_json=?,summary=?,admissions_url=?,preparation_url=?,financial_aid_url=?,verification_status=?,last_verified=? WHERE id=?",(str(data.get("name",""))[:300],str(data.get("location",""))[:300],json.dumps(data.get("majors",[])[:30]),str(data.get("summary",""))[:2000],source,str(data.get("preparation_url","")),str(data.get("financial_aid_url","")),status,checked,record_id))
            elif kind=="school":
                url=str(data.get("catalog_url","")); self.check_https(url)
                conn.execute("UPDATE schools SET name=?,location=?,website=?,catalog_url=?,verification_status=?,last_verified=? WHERE id=?",(str(data.get("name",""))[:300],str(data.get("location",""))[:300],str(data.get("website","")),url,status,checked,record_id))
            elif kind=="course":
                url=str(data.get("source_url","")); self.check_https(url)
                conn.execute("UPDATE courses SET name=?,level=?,grade=?,prerequisites=?,credits=?,description=?,source_url=?,verification_status=?,last_verified=? WHERE id=?",(str(data.get("name",""))[:300],str(data.get("level","Standard"))[:80],str(data.get("grade",""))[:20],str(data.get("prerequisites",""))[:500],float(data["credits"]) if data.get("credits") not in (None,"") else None,str(data.get("description",""))[:2000],url,status,checked,record_id))
            else:
                url=str(data.get("official_url","")); self.check_https(url)
                conn.execute("UPDATE opportunities SET name=?,category=?,description=?,eligibility=?,deadline=?,cost=?,location=?,application_info=?,official_url=?,verification_status=?,last_verified=? WHERE id=?",(str(data.get("name",""))[:300],str(data.get("category","Programs"))[:100],str(data.get("description",""))[:2000],str(data.get("eligibility",""))[:1000],str(data.get("deadline","Check official site"))[:200],str(data.get("cost","Check official source"))[:200],str(data.get("location",""))[:300],str(data.get("application_info",""))[:1000],url,status,checked,record_id))
            title=str(data.get("name",kind.title()))[:300]; source_url=str(data.get("source",data.get("catalog_url",data.get("source_url",data.get("official_url","")))))
            self.record_source_history(conn,kind,str(record_id),title,source_url,status,user_id=user["id"])
        return self.send_json(200,{"ok":True,"verification_status":status,"last_verified":checked})

    def admin_post(self,path,data,user):
        if path=="/api/admin/records/college":
            name=str(data.get("name"," ")).strip()
            if not name: raise ValueError("College name is required.")
            slug=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")[:100]
            source=str(data.get("source","")); self.check_https(source)
            with database.connect() as conn:
                cur=conn.execute("INSERT INTO colleges(slug,name,location,majors_json,summary,admissions_url,preparation_url,financial_aid_url,verification_status,last_verified) VALUES(?,?,?,?,?,?,?,?,?,?)",(slug,name[:300],str(data.get("location",""))[:300],json.dumps(data.get("majors",[])),str(data.get("summary",""))[:2000],source,str(data.get("preparation_url","")),str(data.get("financial_aid_url","")),"verified" if data.get("verified") else "unverified",date.today().isoformat() if data.get("verified") else None))
                self.record_source_history(conn,"college",str(cur.lastrowid),name,source,"verified" if data.get("verified") else "unverified",user["id"])
            return self.send_json(201,{"ok":True})
        if path=="/api/admin/records/school":
            name=str(data.get("name"," ")).strip(); source=str(data.get("catalog_url","")); self.check_https(source)
            if not name: raise ValueError("School name is required.")
            with database.connect() as conn:
                cur=conn.execute("INSERT INTO schools(name,location,website,catalog_url,verification_status,last_verified) VALUES(?,?,?,?,?,?)",(name[:300],str(data.get("location",""))[:300],str(data.get("website","")),source,"verified" if data.get("verified") else "unverified",date.today().isoformat() if data.get("verified") else None))
                self.record_source_history(conn,"school",str(cur.lastrowid),name,source,"verified" if data.get("verified") else "unverified",user["id"])
            return self.send_json(201,{"ok":True})
        if path=="/api/admin/records/course":
            source=str(data.get("source_url","")); self.check_https(source)
            with database.connect() as conn:
                school=conn.execute("SELECT id FROM schools WHERE id=?",(int(data.get("school_id",0)),)).fetchone()
                if not school: raise ValueError("Choose an existing school.")
                cur=conn.execute("INSERT INTO courses(school_id,name,level,grade,prerequisites,credits,description,source_url,verification_status,last_verified) VALUES(?,?,?,?,?,?,?,?,?,?)",(school["id"],str(data.get("name",""))[:300],str(data.get("level","Standard"))[:80],str(data.get("grade",""))[:20],str(data.get("prerequisites",""))[:500],float(data["credits"]) if data.get("credits") not in (None,"") else None,str(data.get("description",""))[:2000],source,"verified" if data.get("verified") else "unverified",date.today().isoformat() if data.get("verified") else None))
                self.record_source_history(conn,"course",str(cur.lastrowid),str(data.get("name","Course")),source,"verified" if data.get("verified") else "unverified",user["id"])
            return self.send_json(201,{"ok":True})
        if path=="/api/admin/records/opportunity":
            name=str(data.get("name"," ")).strip(); url=str(data.get("official_url","")); self.check_https(url)
            if not name: raise ValueError("Opportunity name is required.")
            slug=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")[:100]
            with database.connect() as conn:
                src=conn.execute("INSERT OR IGNORE INTO sources(title,organization,url,accessed_at) VALUES(?,?,?,?)",(name,str(data.get("organization",name))[:200],url,utcnow()))
                source=conn.execute("SELECT id FROM sources WHERE url=?",(url,)).fetchone()
                conn.execute("INSERT INTO opportunities(slug,name,category,description,eligibility,deadline,cost,location,application_info,interests_json,official_url,source_id,verification_status,last_verified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(slug,name[:300],str(data.get("category","Programs"))[:100],str(data.get("description",""))[:2000],str(data.get("eligibility",""))[:1000],str(data.get("deadline","Check official site"))[:200],str(data.get("cost","Check official source"))[:200],str(data.get("location",""))[:300],str(data.get("application_info",""))[:1000],json.dumps(data.get("interests",[])[:30]),url,source["id"],"verified" if data.get("verified") else "unverified",date.today().isoformat() if data.get("verified") else None))
                rid=conn.execute("SELECT id FROM opportunities WHERE slug=?",(slug,)).fetchone()["id"]
                self.record_source_history(conn,"opportunity",str(rid),name,url,"verified" if data.get("verified") else "unverified",user["id"])
            return self.send_json(201,{"ok":True})
        match=re.fullmatch(r"/api/admin/users/(\d+)/active",path)
        if match:
            with database.connect() as conn: conn.execute("UPDATE users SET is_active=? WHERE id=?",(int(bool(data.get("active"))),int(match.group(1))))
            return self.send_json(200,{"ok":True})
        return self.send_json(404,{"error":"Unknown administrator route."})

    @staticmethod
    def check_https(url):
        if url and (not url.startswith("https://") or len(url)>1500): raise ValueError("Source URLs must use HTTPS.")


def main() -> None:
    load_env()
    database.DB_PATH=Path(os.environ.get("APP_DATABASE",database.ROOT / "student_guidance.sqlite3")).resolve()
    database.init_db()
    init_admin()
    host=os.environ.get("APP_HOST","127.0.0.1")
    port=int(os.environ.get("APP_PORT","8000"))
    server=ThreadingHTTPServer((host,port),Handler)
    print(f"Student guidance app at http://{host}:{port}")
    print(f"AI: {'configured' if os.environ.get('OPENAI_API_KEY') else 'local planner mode (set OPENAI_API_KEY to enable AI/research)'}")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nShutting down.")
    finally: server.server_close()


if __name__=="__main__": main()

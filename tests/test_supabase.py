"""End-to-end test of the Supabase integration against local stand-ins (no network, stdlib only).

IMPORTANT: this uses a *simulated* Supabase (GoTrue + PostgREST) and a simulated Gemini endpoint.
The simulated PostgREST filters rows by the caller's JWT, mimicking the RLS policies in
supabase/migrations/001_init.sql. It verifies the server's behaviour (which token it sends, what it
syncs, that users never see each other's data) but cannot prove the SQL policies themselves --
see SUPABASE_SETUP.md for the two-user check to run against your real project.
"""
import json, os, secrets, subprocess, sys, tempfile, threading, time, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANON = "anon-key-123"
SERVICE = "service-role-key-SECRET"
DB = {"users": {}, "access": {}, "refresh": {}, "rows": {}, "recover": [], "deleted": [], "auth_log": []}
LOCK = threading.Lock()


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj=None):
        body = json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null") if n else None
    def _uid(self):  # identity comes ONLY from the bearer token, like Postgres auth.uid()
        tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        return DB["access"].get(tok)
    def _session(self, email):
        u = DB["users"][email]
        a, r = "at-" + secrets.token_hex(8), "rt-" + secrets.token_hex(8)
        DB["access"][a] = u["id"]; DB["refresh"][r] = email
        return {"access_token": a, "refresh_token": r, "expires_in": 3600, "user": {"id": u["id"], "email": email}}
    def do_POST(self): self.route("POST")
    def do_GET(self): self.route("GET")
    def do_DELETE(self): self.route("DELETE")
    def route(self, method):
        p = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(p.query); path = p.path
        body = self._body() if method == "POST" else None
        with LOCK:
            if self.headers.get("apikey") not in (ANON, SERVICE): return self._send(401, {"msg": "bad apikey"})
            if path == "/auth/v1/signup":
                if body["email"] in DB["users"]: return self._send(422, {"msg": "User already registered"})
                DB["users"][body["email"]] = {"id": secrets.token_hex(8), "password": body["password"]}
                return self._send(200, self._session(body["email"]))
            if path == "/auth/v1/token":
                if q["grant_type"][0] == "password":
                    u = DB["users"].get(body["email"])
                    if not u or u["password"] != body["password"]: return self._send(400, {"error": "invalid_grant"})
                    return self._send(200, self._session(body["email"]))
                email = DB["refresh"].pop(body["refresh_token"], None)
                return self._send(200, self._session(email)) if email else self._send(400, {"error": "bad refresh"})
            if path == "/auth/v1/logout": return self._send(204)
            if path == "/auth/v1/recover": DB["recover"].append(body["email"]); return self._send(200)
            if path.startswith("/auth/v1/admin/users/"):
                if self.headers.get("apikey") != SERVICE: return self._send(403)
                DB["deleted"].append(path.rsplit("/", 1)[1]); return self._send(200)
            if path.startswith("/rest/v1/"):
                table = path.rsplit("/", 1)[1]; uid = self._uid(); rows = DB["rows"].setdefault(table, [])
                if not uid: return self._send(401, {"message": "JWT required"})   # anon role has no grants
                if method == "GET":
                    mine = [r for r in rows if r["user_id"] == uid]               # RLS: using (auth.uid() = user_id)
                    key = (q.get("order") or ["id"])[0]
                    if key == "position": mine.sort(key=lambda r: r.get("position", 0))
                    if key == "id.desc": mine.sort(key=lambda r: -r["id"])
                    if q.get("limit"): mine = mine[: int(q["limit"][0])]
                    return self._send(200, mine)
                if method == "POST":
                    items = body if isinstance(body, list) else [body]
                    if any(i.get("user_id") != uid for i in items): return self._send(403, {"message": "RLS with check violated"})
                    for i in items:
                        if table == "profiles": rows[:] = [r for r in rows if r["user_id"] != uid]
                        i["id"] = len(DB["rows"][table]) + 1 + int(time.time() * 1000) % 100000 + secrets.randbelow(10**6)
                        rows.append(i)
                    return self._send(201)
                if method == "DELETE":
                    target = (q.get("user_id") or [""])[0].replace("eq.", "")
                    rows[:] = [r for r in rows if not (r["user_id"] == uid and r["user_id"] == target)]
                    return self._send(204)
        self._send(404)


class Gemini(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        DB["auth_log"].append(self.headers.get("Authorization"))
        body = json.dumps({"id": "x", "object": "chat.completion", "model": "fake", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Here is a plan: start with your next roadmap step."}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


def serve(handler):
    s = ThreadingHTTPServer(("127.0.0.1", 0), handler); threading.Thread(target=s.serve_forever, daemon=True).start(); return s, s.server_address[1]


def start_app(port, sb_port, gem_port, tmp, name):
    env = dict(os.environ, APP_DATABASE=str(tmp / f"{name}.sqlite3"), APP_PORT=str(port), APP_HOST="127.0.0.1", APP_ENV="development",
               SUPABASE_URL=f"http://127.0.0.1:{sb_port}", SUPABASE_ANON_KEY=ANON, SUPABASE_SERVICE_ROLE_KEY=SERVICE,
               GEMINI_API_KEY="gem-key", GEMINI_BASE_URL=f"http://127.0.0.1:{gem_port}", GEMINI_MODELS="fake")
    p = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(60):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); return p
        except Exception: time.sleep(0.2)
    raise RuntimeError("app did not start")


class Client:
    def __init__(self, port): self.base, self.cookie = f"http://127.0.0.1:{port}", ""
    def call(self, path, data=None, method=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, method=method or ("POST" if data is not None else "GET"), headers={"Content-Type": "application/json", "Cookie": self.cookie})
        try:
            r = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            r = e
        sc = r.headers.get("Set-Cookie")
        if sc and "student_session=" in sc and "student_session=;" not in sc: self.cookie = sc.split(";")[0]
        raw = r.read().decode() or "{}"
        return r.status, json.loads(raw)
    REG = dict(legal_agreement=True, terms_version=None, privacy_version=None, age_13_plus=True, guardian_permission=True)


def wait(cond, what, t=6):
    end = time.time() + t
    while time.time() < end:
        if cond(): return
        time.sleep(0.1)
    raise AssertionError("timed out: " + what)


def main():
    tmp = Path(tempfile.mkdtemp()); sbs, sb_port = serve(Fake); gem, gem_port = serve(Gemini)
    procs = []
    ok = lambda c, m: (print(("PASS " if c else "FAIL ") + m), bool(c))[1]
    results = []
    try:
        procs.append(start_app(8231, sb_port, gem_port, tmp, "a"))
        terms = open(ROOT / "app.py", encoding="utf-8").read()
        import re
        tv = re.search(r'TERMS_VERSION\s*=\s*"([^"]+)"', terms).group(1); pv = re.search(r'PRIVACY_VERSION\s*=\s*"([^"]+)"', terms).group(1)
        reg = dict(Client.REG, terms_version=tv, privacy_version=pv)
        alice, bob = Client(8231), Client(8231)

        s, _ = alice.call("/api/auth/register", dict(reg, email="alice@example.com", password="alice-password-1"))
        results.append(ok(s == 200 and "alice@example.com" in DB["users"], "register creates the user in Supabase Auth"))
        results.append(ok(all(u["password"] != "" for u in DB["users"].values()) and not any("password" in json.dumps(r) for t in DB["rows"].values() for r in t), "no passwords stored in data tables"))
        s, _ = Client(8231).call("/api/auth/register", dict(reg, email="alice@example.com", password="alice-password-1"))
        results.append(ok(s in (400, 422), "duplicate registration is rejected"))
        s, _ = Client(8231).call("/api/auth/login", dict(email="alice@example.com", password="wrong-password-xx"))
        results.append(ok(s == 401, "wrong password is rejected (401)"))
        s, me = alice.call("/api/auth/me"); results.append(ok(s == 200 and me["user"]["email"] == "alice@example.com", "session cookie authenticates"))

        state = {"profile": {"firstName": "Alice", "grade": "10", "courses": [{"name": "Algebra II", "year": 10}], "planned": [{"name": "Calculus", "year": 12}], "activities": ["Robotics club"], "goals": "Study engineering\nGet a scholarship"}, "completedRoadmap": ["9-0", "9-1"]}
        s, _ = alice.call("/api/state", state)
        wait(lambda: any(r["user_id"] for r in DB["rows"].get("roadmap_progress", [])), "state sync")
        wait(lambda: len(DB["rows"].get("goals", [])) == 2, "goals sync")
        aid = DB["users"]["alice@example.com"]["id"]
        results.append(ok(s == 200 and all(r["user_id"] == aid for t in DB["rows"].values() for r in t), "state saved; every Supabase row carries alice's user_id"))
        results.append(ok(len(DB["rows"]["courses"]) == 2 and len(DB["rows"]["activities"]) == 1 and len(DB["rows"]["roadmap_progress"]) == 2, "courses, activities, roadmap steps stored in their own tables"))

        s, r = Client(8231).call("/api/assistant/chat", {"message": "hi"})
        results.append(ok(s == 401, "AI endpoint rejects anonymous requests"))
        s, r = alice.call("/api/assistant/chat", {"message": "What should I do next?"})
        results.append(ok(s == 200 and "plan" in json.dumps(r).lower(), f"AI reply works for a Supabase user (status {s})"))
        wait(lambda: len(DB["rows"].get("chat_messages", [])) >= 2, "chat sync")
        results.append(ok(all(r["user_id"] == aid for r in DB["rows"]["chat_messages"]), "chat history stored under alice"))
        results.append(ok(all(a == "Bearer gem-key" for a in DB["auth_log"]) and DB["auth_log"], "AI key is used server-side only"))

        s, _ = bob.call("/api/auth/register", dict(reg, email="bob@example.com", password="bob-password-123"))
        s, b = bob.call("/api/bootstrap")
        results.append(ok(s == 200 and "Algebra" not in json.dumps(b) and "Robotics" not in json.dumps(b) and "What should I do" not in json.dumps(b), "bob's bootstrap contains none of alice's data"))
        s, r = bob.call("/api/assistant/chat", {"message": "Hello from bob"}); wait(lambda: any(m["content"] == "Hello from bob" for m in DB["rows"].get("chat_messages", [])), "bob chat")
        bid = DB["users"]["bob@example.com"]["id"]
        results.append(ok(all(m["user_id"] == bid for m in DB["rows"]["chat_messages"] if "bob" in m["content"]), "bob's messages are stored under bob"))
        # simulated RLS: bob's JWT cannot read or write alice's rows
        bob_tok = [t for t, u in DB["access"].items() if u == bid][-1]
        def rest(method, table, tok, body=None, qs=""):
            req = urllib.request.Request(f"http://127.0.0.1:{sb_port}/rest/v1/{table}{qs}", data=json.dumps(body).encode() if body is not None else None, method=method, headers={"apikey": ANON, "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
            try: r = urllib.request.urlopen(req); return r.status, json.loads(r.read() or b"[]")
            except urllib.error.HTTPError as e: return e.code, None
        s, rows = rest("GET", "courses", bob_tok); results.append(ok(s == 200 and rows == [], "(simulated RLS) bob cannot read alice's courses"))
        s, _ = rest("POST", "courses", bob_tok, [{"user_id": aid, "data": {}}]); results.append(ok(s == 403, "(simulated RLS) bob cannot insert rows as alice"))
        s, _ = rest("GET", "courses", ANON); results.append(ok(s == 401, "(simulated RLS) anon key alone cannot read data"))
        leaked = [f for f in ("index.html", "app.js", "peerpilot.js", "pathway.js", "styles.css") if (ROOT / f).exists() and any(k in (ROOT / f).read_text(encoding="utf-8", errors="ignore") for k in ("SUPABASE_", "service_role", "gem-key"))]
        results.append(ok(not leaked, f"no Supabase keys referenced in frontend files {leaked}"))

        # new device: fresh local database, same Supabase project -> data comes back after login
        procs.append(start_app(8232, sb_port, gem_port, tmp, "b")); dev2 = Client(8232)
        s, _ = dev2.call("/api/auth/login", dict(email="alice@example.com", password="alice-password-1"))
        s, b2 = dev2.call("/api/bootstrap"); txt = json.dumps(b2)
        results.append(ok(s == 200 and "Algebra II" in txt and "Robotics club" in txt and "9-1" in txt, "login on a new device restores profile, courses, activities, roadmap"))
        results.append(ok("What should I do next?" in txt, "AI chat history restored on the new device"))
        s, _ = dev2.call("/api/auth/password-reset/request", dict(email="alice@example.com")); wait(lambda: DB["recover"], "recover")
        results.append(ok(DB["recover"] == ["alice@example.com"], "password reset is delegated to Supabase (emailed link)"))
        s, _ = dev2.call("/api/account/delete", dict(password="alice-password-1"))
        results.append(ok(s == 200 and aid in DB["deleted"] and not [r for t in DB["rows"].values() for r in t if r["user_id"] == aid], "account deletion removes alice's Supabase data and auth user"))
        results.append(ok(any(r["user_id"] == bid for t in DB["rows"].values() for r in t), "...and leaves bob's data untouched"))
    finally:
        for p in procs: p.terminate()
        sbs.shutdown(); gem.shutdown()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
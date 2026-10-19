import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import assistant
import app
import database
from core.llm import LLM, LLMError
from core.tools import ToolRegistry


class FakeLLM:
    """Stands in for Gemini: returns scripted replies and remembers what it was sent."""

    assistant_message = staticmethod(LLM.assistant_message)
    tool_message = staticmethod(LLM.tool_message)

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None, on_token=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, **kwargs})
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def say(text):
    return {"content": text, "tool_calls": []}


def call(name, **arguments):
    return {"content": "", "tool_calls": [{"id": f"c_{name}", "name": name, "arguments": arguments, "extra": None}]}


def web_registry(search_result=None, page_result=None):
    reg = ToolRegistry()
    reg.register({"name": "web_search", "description": "x"}, lambda a: search_result or "No results.")
    reg.register({"name": "read_page", "description": "x"}, lambda a: page_result or "Couldn't open it")
    return reg


SEARCH = "1. Yale Admissions (2026-10-01)\n   https://admissions.yale.edu/apply\n   How to apply\n2. A blog\n   http://blog.example.com/x\n   hmm"
PAGE = "Title: Apply to Yale\nURL: https://admissions.yale.edu/apply\n\nDeadlines are listed here."


class AssistantTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_routes_current_college_questions_to_research(self):
        self.assertTrue(
            assistant.classify("What are the current application requirements for Yale?")["research_required"]
        )
        self.assertEqual(assistant.classify("Explain chemical equilibrium", "tutor")["research_required"], False)

    def test_scholarship_mode_always_researches(self):
        self.assertTrue(assistant.classify("find some", "scholarships")["research_required"])

    def test_inappropriate_language_is_blocked_before_the_model_is_called(self):
        with patch.object(assistant, "get_llm", side_effect=AssertionError("model must not be called")):
            result = assistant.answer({"message": "Explain this swear word shit"}, {}, "advisor")
        self.assertNotIn("shit", result["answer"].lower())

    def test_sources_come_only_from_pages_the_tools_really_returned(self):
        log = [
            ("web_search", {"query": "yale"}, SEARCH),
            ("read_page", {"url": "https://admissions.yale.edu/apply"}, PAGE),
            ("read_page", {"url": "https://nope.example/a"}, "Couldn't open https://nope.example/a: boom"),
        ]
        sources = assistant._collect_sources(log)
        self.assertEqual([s["url"] for s in sources], ["https://admissions.yale.edu/apply"])
        self.assertEqual(sources[0]["title"], "Apply to Yale")
        self.assertTrue(sources[0]["accessed_at"])

    def test_search_hits_are_used_when_no_page_was_read_and_http_is_dropped(self):
        sources = assistant._collect_sources([("web_search", {"query": "yale"}, SEARCH)])
        self.assertEqual([s["url"] for s in sources], ["https://admissions.yale.edu/apply"])

    def test_research_answer_searches_reads_and_cites(self):
        fake = FakeLLM(
            call("web_search", query="yale deadline"),
            call("read_page", url="https://admissions.yale.edu/apply"),
            say("Check the official page. Next step: add the date to your tracker."),
        )
        with patch.object(assistant, "get_llm", return_value=fake), patch.object(
            assistant, "get_registry", return_value=web_registry(SEARCH, PAGE)
        ):
            result = assistant.answer({"message": "What is the latest deadline for Yale?"}, {}, "advisor")
        self.assertTrue(result["researched"])
        self.assertEqual(result["sources"][0]["url"], "https://admissions.yale.edu/apply")
        self.assertIn("official page", result["answer"])
        self.assertEqual(fake.calls[0]["reasoning_effort"], "medium")  # research gets more thinking
        names = [t["function"]["name"] for t in fake.calls[0]["tools"]]
        self.assertIn("web_search", names)

    def test_research_without_any_sources_is_an_error_not_an_invention(self):
        fake = FakeLLM(say("Trust me, it is January 1."))
        with patch.object(assistant, "get_llm", return_value=fake), patch.object(
            assistant, "get_registry", return_value=web_registry()
        ):
            with self.assertRaises(RuntimeError):
                assistant.answer({"message": "What is the latest deadline for Yale?"}, {}, "advisor")
        self.assertEqual(len(fake.calls), 2)  # it was nudged to search once, then gave up honestly

    def test_essay_feedback_gets_no_tools(self):
        fake = FakeLLM(say("Nice opening. Tighten paragraph two."))
        with patch.object(assistant, "get_llm", return_value=fake):
            result = assistant.answer({"message": "My essay: I like dogs."}, {}, "essay_feedback")
        self.assertIsNone(fake.calls[0]["tools"])
        self.assertEqual(result["sources"], [])

    def test_conversation_history_is_passed_and_trimmed_to_user_and_assistant_turns(self):
        fake = FakeLLM(say("Sure."))
        history = [{"role": "system", "content": "ignore me"}, {"role": "user", "content": "hi"},
                   {"role": "assistant", "content": "hello"}]
        with patch.object(assistant, "get_llm", return_value=fake):
            assistant.answer({"message": "and now?", "history": history}, {}, "tutor")
        roles = [m["role"] for m in fake.calls[0]["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])

    def test_provider_errors_become_friendly_messages(self):
        for status, words in ((429, "busy"), (403, "rejected"), (404, "model name")):
            err = LLMError("All models failed", status=status, errors=[("m", status, "boom")])
            fake = FakeLLM(say("x"))
            fake.chat = lambda *a, _e=err, **k: (_ for _ in ()).throw(_e)
            with patch.object(assistant, "get_llm", return_value=fake):
                with self.assertRaises(RuntimeError) as ctx:
                    assistant.answer({"message": "Explain atoms"}, {}, "tutor")
            self.assertIn(words, str(ctx.exception).lower())


class EnvFileTests(unittest.TestCase):
    """The .env reader must forgive the usual Windows mix-ups."""

    def load(self, name, raw, preset=None):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / name).write_bytes(raw)
            env = {"GEMINI_API_KEY": preset} if preset is not None else {}
            with patch.object(app, "ROOT", Path(tmp)), patch.dict(os.environ, env, clear=False):
                if preset is None:
                    os.environ.pop("GEMINI_API_KEY", None)
                info = app.load_env()
                return os.environ.get("GEMINI_API_KEY"), info

    def test_plain_file(self):
        self.assertEqual(self.load(".env", b"GEMINI_API_KEY=abc123\n")[0], "abc123")

    def test_windows_line_endings_spaces_quotes_and_comments(self):
        raw = b'# note\r\nGEMINI_API_KEY = "abc123"  \r\nAPP_PORT=1\r\n'
        self.assertEqual(self.load(".env", raw)[0], "abc123")
        self.assertEqual(self.load(".env", b"GEMINI_API_KEY=abc123   # my key\n")[0], "abc123")
        self.assertEqual(self.load(".env", b"export GEMINI_API_KEY=abc123\n")[0], "abc123")

    def test_hidden_byte_order_mark_and_utf16(self):
        self.assertEqual(self.load(".env", b"\xef\xbb\xbfGEMINI_API_KEY=abc123\n")[0], "abc123")
        self.assertEqual(self.load(".env", "GEMINI_API_KEY=abc123\n".encode("utf-16"))[0], "abc123")

    def test_dot_env_dot_txt_is_used_with_a_hint(self):
        key, info = self.load(".env.txt", b"GEMINI_API_KEY=abc123\n")
        self.assertEqual(key, "abc123")
        self.assertIn("rename", info["note"])

    def test_an_empty_setting_on_the_computer_does_not_block_the_file(self):
        self.assertEqual(self.load(".env", b"GEMINI_API_KEY=abc123\n", preset="")[0], "abc123")

    def test_a_real_setting_on_the_computer_wins(self):
        self.assertEqual(self.load(".env", b"GEMINI_API_KEY=abc123\n", preset="from-computer")[0], "from-computer")

    def test_missing_file_is_fine(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "ROOT", Path(tmp)):
            self.assertIsNone(app.load_env()["path"])

    def test_the_key_check_explains_problems_in_plain_words(self):
        class Fake:
            def __init__(self, names=None, error=None):
                self.names, self.error = names, error

            def list_models(self):
                if self.error:
                    raise self.error
                return self.names

        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "GEMINI_MODELS": "gemini-x"}):
            with patch.object(assistant, "get_llm", return_value=Fake(["gemini-x"])):
                self.assertTrue(assistant.check_key()[0])
            with patch.object(assistant, "get_llm", return_value=Fake(["gemini-9-flash", "gemini-9-flash-image"])):
                ok, msg = assistant.check_key()
                self.assertFalse(ok)
                self.assertIn("GEMINI_MODELS=gemini-9-flash", msg)
                self.assertNotIn("image", msg)
            bad = Exception("401")
            bad.response = type("R", (), {"status_code": 403})()
            with patch.object(assistant, "get_llm", return_value=Fake(error=bad)):
                self.assertIn("rejected", assistant.check_key()[1])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            self.assertEqual(assistant.check_key(), (False, "No key was found."))


class ApiIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(cls.temp.name) / "test.sqlite3"
        database.init_db()
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def setUp(self):
        with app.RATE_LOCK:
            app.RATE_BUCKETS.clear()
        with database.connect() as conn:
            conn.execute("DELETE FROM users")

    def request(self, method, path, payload=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        body = json.dumps(payload) if payload is not None else None
        headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read() or b"{}")
        cookie_header = response.getheader("Set-Cookie", "")
        conn.close()
        return response.status, data, cookie_header

    def register(self, email):
        status, data, header = self.request(
            "POST",
            "/api/auth/register",
            {
                "email": email,
                "password": "secure-password-123",
                "legal_agreement": True,
                "terms_version": app.TERMS_VERSION,
                "privacy_version": app.PRIVACY_VERSION,
                "age_13_plus": True,
                "guardian_permission": True,
            },
        )
        self.assertEqual(status, 200, data)
        return header.split(";", 1)[0]

    def test_private_profile_isolation(self):
        cookie_a = self.register("first@example.edu")
        cookie_b = self.register("second@example.edu")
        self.assertEqual(
            self.request("PUT", "/api/profile", {"profile": {"firstName": "Ari", "grade": "11"}}, cookie_a)[
                0
            ],
            200,
        )
        self.assertEqual(
            self.request("PUT", "/api/profile", {"profile": {"firstName": "Bo", "grade": "10"}}, cookie_b)[0],
            200,
        )
        _, a, _ = self.request("GET", "/api/bootstrap", cookie=cookie_a)
        _, b, _ = self.request("GET", "/api/bootstrap", cookie=cookie_b)
        self.assertEqual(a["profile"]["firstName"], "Ari")
        self.assertEqual(b["profile"]["firstName"], "Bo")

    def test_private_endpoints_require_authentication(self):
        status, _, _ = self.request("GET", "/api/bootstrap")
        self.assertEqual(status, 401)

    def test_account_creation_requires_current_consent_and_age_acknowledgements(self):
        status, data, _ = self.request(
            "POST",
            "/api/auth/register",
            {"email": "no-consent@example.edu", "password": "secure-password-123"},
        )
        self.assertEqual(status, 400)
        self.assertIn("Terms of Service", data["error"])

    def test_college_and_opportunity_catalogs_are_retrievable(self):
        cookie = self.register("catalog-user@example.edu")
        status, colleges, _ = self.request("GET", "/api/colleges", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(any(c["name"] == "Harvard University" for c in colleges["colleges"]))
        status, opps, _ = self.request("GET", "/api/opportunities", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertGreater(len(opps["opportunities"]), 0)

    def test_course_profile_and_deadline_persist(self):
        cookie = self.register("planner-user@example.edu")
        self.request(
            "PUT",
            "/api/profile",
            {
                "profile": {
                    "school": "Example High",
                    "grade": "10",
                    "major": "Engineering",
                    "courses": [{"name": "Algebra II", "year": "10", "level": "Honors"}],
                }
            },
            cookie,
        )
        status, _, _ = self.request(
            "POST",
            "/api/tasks",
            {"title": "Ask about course plan", "due": "2026-10-01", "category": "Course planning"},
            cookie,
        )
        self.assertEqual(status, 201)
        _, profile, _ = self.request("GET", "/api/bootstrap", cookie=cookie)
        self.assertEqual(profile["profile"]["courses"][0]["name"], "Algebra II")
        self.assertEqual(profile["tasks"][0]["due"], "2026-10-01")

    def test_essay_records_cannot_be_feedback_requested_by_another_account(self):
        owner = self.register("essay-owner@example.edu")
        other = self.register("essay-other@example.edu")
        status, saved, _ = self.request(
            "POST", "/api/essays", {"title": "Draft", "body": "A short student draft."}, owner
        )
        self.assertEqual(status, 200)
        status, result, _ = self.request("POST", "/api/essays/feedback", {"essay_id": saved["id"]}, other)
        self.assertEqual(status, 400)
        self.assertIn("not found", result["error"])

    def test_tutor_response_uses_ai_layer(self):
        cookie = self.register("tutor-user@example.edu")
        with patch.object(
            assistant,
            "answer",
            return_value={
                "answer": "Try this first step.",
                "sources": [],
                "intent": "academic",
                "researched": False,
            },
        ):
            status, result, _ = self.request(
                "POST", "/api/assistant/tutor", {"message": "Explain equilibrium", "history": []}, cookie
            )
        self.assertEqual(status, 200)
        self.assertIn("first step", result["answer"])

    def test_admin_source_history_records_verification(self):
        cookie = self.register("admin@example.edu")
        with database.connect() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE email=?", ("admin@example.edu",))
        status, _, _ = self.request(
            "POST",
            "/api/admin/records/school",
            {
                "name": "Catalog High",
                "location": "CT",
                "catalog_url": "https://school.example.edu/catalog",
                "verified": True,
            },
            cookie,
        )
        self.assertEqual(status, 201)
        status, result, _ = self.request("GET", "/api/admin/records", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(
            any(
                row["url"] == "https://school.example.edu/catalog"
                and row["verification_status"] == "verified"
                for row in result["sourceHistory"]
            )
        )

    def test_tasks_are_scoped_to_owner(self):
        cookie_a = self.register("task-owner@example.edu")
        cookie_b = self.register("other-owner@example.edu")
        self.assertEqual(self.request("POST", "/api/tasks", {"title": "Private task"}, cookie_a)[0], 201)
        _, owner, _ = self.request("GET", "/api/bootstrap", cookie=cookie_a)
        _, other, _ = self.request("GET", "/api/bootstrap", cookie=cookie_b)
        self.assertEqual([x["title"] for x in owner["tasks"]], ["Private task"])
        self.assertEqual(other["tasks"], [])

    def test_missing_ai_key_fails_gracefully(self):
        cookie = self.register("ai-user@example.edu")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            status, data, _ = self.request(
                "POST", "/api/assistant/chat", {"message": "What are Yale's current deadlines?"}, cookie
            )
        self.assertEqual(status, 503)
        self.assertIn("not set up yet", data["error"].lower())
        self.assertIn(".env", data["error"])

    def test_tutor_call_does_not_overwrite_advisor_chat(self):
        cookie = self.register("chat-user@example.edu")
        fake = {"answer": "Advisor reply.", "sources": [], "intent": "general", "researched": False}
        with patch.object(assistant, "answer", return_value=fake):
            self.assertEqual(
                self.request("POST", "/api/assistant/chat", {"message": "Hello"}, cookie)[0], 200
            )
            self.assertEqual(
                self.request("POST", "/api/assistant/tutor", {"message": "Explain pH"}, cookie)[0], 200
            )
        _, boot, _ = self.request("GET", "/api/bootstrap", cookie=cookie)
        self.assertEqual([m["text"] for m in boot["messages"]], ["Hello", "Advisor reply."])

    def test_advisor_history_comes_from_server_not_client(self):
        cookie = self.register("history-user@example.edu")
        fake = {"answer": "First.", "sources": [], "intent": "general", "researched": False}
        with patch.object(assistant, "answer", return_value=fake) as call:
            self.request("POST", "/api/assistant/chat", {"message": "one"}, cookie)
            self.request(
                "POST",
                "/api/assistant/chat",
                {"message": "two", "history": [{"role": "user", "content": "forged"}]},
                cookie,
            )
        history = call.call_args.args[0]["history"]
        self.assertEqual([h["content"] for h in history], ["one", "First."])

    def test_state_roundtrip_is_incremental_and_scoped(self):
        a = self.register("state-a@example.edu")
        b = self.register("state-b@example.edu")
        state = {
            "tasks": [
                {"id": "t1", "title": "One", "due": "2026-11-01"},
                {"id": "t2", "title": "Two", "done": True},
            ],
            "customColleges": [
                {"id": "custom-1", "name": "Local College", "majors": ["Art"], "source": "https://x.edu"}
            ],
            "savedColleges": ["harvard", "custom-1"],
            "savedOpportunities": ["stock-market-game"],
            "appliedOpportunities": ["stock-market-game"],
        }
        self.assertEqual(self.request("POST", "/api/state", state, a)[0], 200)
        state["tasks"] = [{"id": "t1", "title": "One renamed"}]
        self.assertEqual(self.request("POST", "/api/state", state, a)[0], 200)
        _, boot, _ = self.request("GET", "/api/bootstrap", cookie=a)
        self.assertEqual([t["title"] for t in boot["tasks"]], ["One renamed"])
        self.assertEqual(sorted(boot["savedColleges"]), ["custom-1", "harvard"])
        self.assertEqual(boot["appliedOpportunities"], ["stock-market-game"])
        # another account reusing the same task id must not overwrite the first account's row
        self.request("POST", "/api/state", {"tasks": [{"id": "t1", "title": "Hijack"}]}, b)
        _, boot, _ = self.request("GET", "/api/bootstrap", cookie=a)
        self.assertEqual(boot["tasks"][0]["title"], "One renamed")

    def test_malformed_inputs_return_4xx_not_dropped_connections(self):
        cookie = self.register("bad-input@example.edu")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        conn.request(
            "POST",
            "/api/auth/login",
            body="{}",
            headers={"Content-Length": "abc", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()
        self.assertEqual(
            self.request("POST", "/api/state", {"savedOpportunities": None, "tasks": "nope"}, cookie)[0], 200
        )
        self.assertEqual(self.request("DELETE", "/api/tasks/missing", cookie=cookie)[0], 200)

    def test_admin_edits_refresh_catalog_cache_and_validate_types(self):
        cookie = self.register("admin2@example.edu")
        with database.connect() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE email=?", ("admin2@example.edu",))
        _, before, _ = self.request("GET", "/api/colleges", cookie=cookie)
        body = {"name": "Cache College", "source": "https://cache.example.edu", "majors": "not-a-list"}
        self.assertEqual(self.request("POST", "/api/admin/records/college", body, cookie)[0], 201)
        _, after, _ = self.request("GET", "/api/colleges", cookie=cookie)
        self.assertEqual(len(after["colleges"]), len(before["colleges"]) + 1)
        bad = {"name": "X", "source": 5}
        self.assertEqual(self.request("POST", "/api/admin/records/college", bad, cookie)[0], 400)

    def test_static_assets_support_etag_and_gzip(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        conn.request("GET", "/app.js", headers={"Accept-Encoding": "gzip"})
        r = conn.getresponse()
        etag = r.getheader("ETag")
        self.assertEqual((r.status, r.getheader("Content-Encoding")), (200, "gzip"))
        r.read()
        conn.request("GET", "/app.js", headers={"If-None-Match": etag})
        self.assertEqual(conn.getresponse().status, 304)
        conn.close()

    def test_logout_clears_cookie_and_session(self):
        cookie = self.register("logout@example.edu")
        status, _, header = self.request("POST", "/api/auth/logout", {}, cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", header)
        self.assertEqual(self.request("GET", "/api/bootstrap", cookie=cookie)[0], 401)


if __name__ == "__main__":
    unittest.main()
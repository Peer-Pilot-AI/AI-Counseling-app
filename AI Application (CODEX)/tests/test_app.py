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


class AssistantTests(unittest.TestCase):
    def test_routes_current_college_questions_to_research(self):
        self.assertTrue(assistant.classify("What are the current application requirements for Yale?")["research_required"])
        self.assertEqual(assistant.classify("Explain chemical equilibrium", "tutor")["research_required"], False)

    def test_inappropriate_language_is_blocked_before_provider_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(assistant.urllib.request, "urlopen") as call:
            result = assistant.answer({"message": "Explain this swear word shit"}, {}, "advisor")
        call.assert_not_called()
        self.assertNotIn("shit", result["answer"].lower())

    def test_citations_are_only_https_search_results(self):
        result = {"output": [{"type": "web_search_call", "action": {"sources": [
            {"title": "Official source", "url": "https://example.edu/admissions"},
            {"title": "Unsafe", "url": "http://example.com"},
        ]}}]}
        sources = assistant._extract_sources(result)
        self.assertEqual([s["url"] for s in sources], ["https://example.edu/admissions"])
        self.assertTrue(sources[0]["accessed_at"])

    def test_does_not_invent_citations_when_none_were_returned(self):
        self.assertEqual(assistant._extract_sources({"output": [{"type": "message", "content": [{"type": "output_text", "text": "A factual claim with a made-up URL https://fake.example"}]}]}), [])

    def test_high_reasoning_and_research_limits_are_sent(self):
        fake_response = {"output_text": "Check the official admissions page.", "output": [{"type": "web_search_call", "action": {"sources": [{"title": "Official", "url": "https://example.edu"}]}}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return json.dumps(fake_response).encode()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_REASONING_EFFORT": "high"}), patch.object(assistant.urllib.request, "urlopen", return_value=Response()) as call:
            result = assistant.answer({"message": "What are the current application requirements for Yale?"}, {}, "advisor")
        payload = json.loads(call.call_args.args[0].data)
        self.assertEqual(payload["reasoning"]["effort"], "high")
        self.assertEqual(payload["tool_choice"], "required")
        self.assertLessEqual(payload["max_tool_calls"], 4)
        self.assertTrue(result["sources"])


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
        if cookie: headers["Cookie"] = cookie
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read() or b"{}")
        cookie_header = response.getheader("Set-Cookie", "")
        conn.close()
        return response.status, data, cookie_header

    def register(self, email):
        status, data, header = self.request("POST", "/api/auth/register", {"email": email, "password": "secure-password-123", "legal_agreement": True, "terms_version": app.TERMS_VERSION, "privacy_version": app.PRIVACY_VERSION, "age_13_plus": True, "guardian_permission": True})
        self.assertEqual(status, 200, data)
        return header.split(";", 1)[0]

    def test_private_profile_isolation(self):
        cookie_a = self.register("first@example.edu")
        cookie_b = self.register("second@example.edu")
        self.assertEqual(self.request("PUT", "/api/profile", {"profile": {"firstName": "Ari", "grade": "11"}}, cookie_a)[0], 200)
        self.assertEqual(self.request("PUT", "/api/profile", {"profile": {"firstName": "Bo", "grade": "10"}}, cookie_b)[0], 200)
        _, a, _ = self.request("GET", "/api/bootstrap", cookie=cookie_a)
        _, b, _ = self.request("GET", "/api/bootstrap", cookie=cookie_b)
        self.assertEqual(a["profile"]["firstName"], "Ari")
        self.assertEqual(b["profile"]["firstName"], "Bo")

    def test_private_endpoints_require_authentication(self):
        status, _, _ = self.request("GET", "/api/bootstrap")
        self.assertEqual(status, 401)

    def test_account_creation_requires_current_consent_and_age_acknowledgements(self):
        status, data, _ = self.request("POST", "/api/auth/register", {"email": "no-consent@example.edu", "password": "secure-password-123"})
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
        self.request("PUT", "/api/profile", {"profile": {"school": "Example High", "grade": "10", "major": "Engineering", "courses": [{"name": "Algebra II", "year": "10", "level": "Honors"}]}}, cookie)
        status, _, _ = self.request("POST", "/api/tasks", {"title": "Ask about course plan", "due": "2026-10-01", "category": "Course planning"}, cookie)
        self.assertEqual(status, 201)
        _, profile, _ = self.request("GET", "/api/bootstrap", cookie=cookie)
        self.assertEqual(profile["profile"]["courses"][0]["name"], "Algebra II")
        self.assertEqual(profile["tasks"][0]["due"], "2026-10-01")

    def test_essay_records_cannot_be_feedback_requested_by_another_account(self):
        owner = self.register("essay-owner@example.edu")
        other = self.register("essay-other@example.edu")
        status, saved, _ = self.request("POST", "/api/essays", {"title": "Draft", "body": "A short student draft."}, owner)
        self.assertEqual(status, 200)
        status, result, _ = self.request("POST", "/api/essays/feedback", {"essay_id": saved["id"]}, other)
        self.assertEqual(status, 400)
        self.assertIn("not found", result["error"])

    def test_tutor_response_uses_ai_layer(self):
        cookie = self.register("tutor-user@example.edu")
        with patch.object(assistant, "answer", return_value={"answer": "Try this first step.", "sources": [], "intent": "academic", "researched": False}):
            status, result, _ = self.request("POST", "/api/assistant/tutor", {"message": "Explain equilibrium", "history": []}, cookie)
        self.assertEqual(status, 200)
        self.assertIn("first step", result["answer"])

    def test_admin_source_history_records_verification(self):
        cookie = self.register("admin@example.edu")
        with database.connect() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE email=?", ("admin@example.edu",))
        status, _, _ = self.request("POST", "/api/admin/records/school", {"name": "Catalog High", "location": "CT", "catalog_url": "https://school.example.edu/catalog", "verified": True}, cookie)
        self.assertEqual(status, 201)
        status, result, _ = self.request("GET", "/api/admin/records", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(any(row["url"] == "https://school.example.edu/catalog" and row["verification_status"] == "verified" for row in result["sourceHistory"]))

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
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            status, data, _ = self.request("POST", "/api/assistant/chat", {"message": "What are Yale's current deadlines?"}, cookie)
        self.assertEqual(status, 503)
        self.assertIn("not configured", data["error"].lower())


if __name__ == "__main__":
    unittest.main()

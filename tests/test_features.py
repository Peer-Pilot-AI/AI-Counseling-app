import http.client
import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path

import app
import database
import features


class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(cls.temp.name) / "features.sqlite3"
        database.init_db()
        features.ensure_schema()
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
        features._rate_buckets.clear()
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
        conn.close()
        return response.status, data

    def register(self, email, first="Ari", last="Lopez"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        conn.request(
            "POST",
            "/api/auth/register",
            body=json.dumps(
                {
                    "email": email,
                    "password": "secure-password-123",
                    "legal_agreement": True,
                    "terms_version": app.TERMS_VERSION,
                    "privacy_version": app.PRIVACY_VERSION,
                    "age_13_plus": True,
                    "guardian_permission": True,
                }
            ),
            headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        response = conn.getresponse()
        response.read()
        cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        conn.close()
        status, _ = self.request(
            "PUT", "/api/profile", {"profile": {"firstName": first, "lastName": last, "grade": "11", "major": "Computer Science"}}, cookie
        )
        self.assertEqual(status, 200)
        return cookie

    def make_mentor(self, cookie, **over):
        body = {
            "stage": "College freshman",
            "topics": ["Computer Science", "Essays"],
            "bio": "I applied last year and can share what worked for me.",
            "active": True,
            "agree_rules": True,
            **over,
        }
        return self.request("PUT", "/api/mentors/me", body, cookie)

    # ---------------------------------------------------------- scholarships
    def test_scholarship_crud_and_privacy(self):
        a = self.register("a@example.edu")
        b = self.register("b@example.edu")
        status, data = self.request(
            "POST",
            "/api/scholarships",
            {"name": "Local Rotary", "amount": "$1,000", "due": "2026-12-01", "url": "https://example.org/apply",
             "requirements": ["Essay", {"text": "Transcript", "done": True}]},
            a,
        )
        self.assertEqual(status, 201, data)
        sid = data["scholarship"]["id"]
        self.assertEqual(len(data["scholarship"]["requirements"]), 2)
        status, data = self.request("PUT", "/api/scholarships", {"id": sid, "status": "Submitted"}, a)
        self.assertEqual(data["scholarship"]["status"], "Submitted")
        self.assertEqual(self.request("GET", "/api/scholarships", None, b)[1]["scholarships"], [])
        self.assertEqual(self.request("PUT", "/api/scholarships", {"id": sid, "status": "Won"}, b)[0], 400)
        self.request("DELETE", f"/api/scholarships/{sid}", None, b)
        self.assertEqual(len(self.request("GET", "/api/scholarships", None, a)[1]["scholarships"]), 1)
        self.request("DELETE", f"/api/scholarships/{sid}", None, a)
        self.assertEqual(self.request("GET", "/api/scholarships", None, a)[1]["scholarships"], [])

    def test_scholarship_validation(self):
        a = self.register("v@example.edu")
        self.assertEqual(self.request("POST", "/api/scholarships", {"name": ""}, a)[0], 400)
        self.assertEqual(self.request("POST", "/api/scholarships", {"name": "X", "due": "tomorrow"}, a)[0], 400)
        self.assertEqual(self.request("POST", "/api/scholarships", {"name": "X", "url": "http://x.org"}, a)[0], 400)
        self.assertEqual(self.request("POST", "/api/scholarships", {"name": "X", "status": "Bogus"}, a)[0], 400)

    def test_requires_sign_in(self):
        self.assertEqual(self.request("GET", "/api/scholarships")[0], 401)
        self.assertEqual(self.request("GET", "/api/mentors")[0], 401)
        self.assertEqual(self.request("GET", "/api/deadlines")[0], 401)

    # ------------------------------------------------------------- deadlines
    def test_deadlines_merge_and_sort(self):
        a = self.register("d@example.edu")
        today = date.today()
        soon = (today + timedelta(days=3)).isoformat()
        late = (today - timedelta(days=2)).isoformat()
        far = (today + timedelta(days=90)).isoformat()
        self.request("POST", "/api/tasks", {"title": "Ask counselor", "due": soon}, a)
        self.request("POST", "/api/applications", {"college_name": "Rice", "due": far}, a)
        self.request("POST", "/api/scholarships", {"name": "Old one", "due": late}, a)
        self.request("POST", "/api/scholarships", {"name": "Done one", "due": soon, "status": "Submitted"}, a)
        status, data = self.request("GET", "/api/deadlines", None, a)
        self.assertEqual(status, 200)
        titles = [x["title"] for x in data["deadlines"]]
        self.assertEqual(titles, ["Old one", "Ask counselor", "Rice application"])
        self.assertEqual(data["counts"]["overdue"], 1)
        self.assertEqual(data["counts"]["soon"], 1)
        self.assertEqual(data["deadlines"][0]["urgency"], "overdue")

    # --------------------------------------------------------------- mentors
    def test_mentor_flow_end_to_end(self):
        mentor = self.register("mentor@example.edu", "Sam", "Rivera")
        mentee = self.register("mentee@example.edu", "Ari", "Lopez")
        status, data = self.make_mentor(mentor)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["me"]["name"], "Sam R.")
        status, data = self.request("GET", "/api/mentors", None, mentee)
        self.assertEqual(len(data["mentors"]), 1)
        listed = data["mentors"][0]
        self.assertEqual(listed["name"], "Sam R.")
        self.assertIn("Computer Science", listed["shared"])  # matches the mentee's major
        self.assertNotIn("email", json.dumps(listed))
        status, data = self.request(
            "POST", "/api/mentors/requests",
            {"mentor": listed["id"], "topic": "Essays", "message": "Can you look at how I start my essay?"}, mentee)
        self.assertEqual(status, 201, data)
        rid = data["requests"][0]["id"]
        # cannot chat before accepting
        self.assertEqual(self.request("POST", f"/api/mentors/requests/{rid}/messages", {"body": "hi"}, mentee)[0], 400)
        # mentee can't accept their own request
        self.assertEqual(self.request("PUT", "/api/mentors/requests", {"id": rid, "action": "accept"}, mentee)[0], 400)
        self.assertEqual(self.request("PUT", "/api/mentors/requests", {"id": rid, "action": "accept"}, mentor)[0], 200)
        self.assertEqual(
            self.request("POST", f"/api/mentors/requests/{rid}/messages", {"body": "Sure, send me the first lines."}, mentor)[0], 201)
        status, data = self.request("GET", f"/api/mentors/requests/{rid}/messages", None, mentee)
        self.assertEqual(status, 200)
        self.assertEqual(data["messages"][0]["sender"], "Sam R.")
        self.assertFalse(data["messages"][0]["mine"])
        # a stranger cannot read the chat
        stranger = self.register("stranger@example.edu")
        self.assertEqual(self.request("GET", f"/api/mentors/requests/{rid}/messages", None, stranger)[0], 400)

    def test_contact_info_is_blocked(self):
        mentor = self.register("m2@example.edu", "Sam", "Rivera")
        mentee = self.register("e2@example.edu")
        self.make_mentor(mentor)
        handle = self.request("GET", "/api/mentors", None, mentee)[1]["mentors"][0]["id"]
        for bad in ["email me at kid@example.com please", "call me 555 123 4567", "find me on snapchat", "see https://x.com/me", "my number is private"]:
            status, data = self.request(
                "POST", "/api/mentors/requests", {"mentor": handle, "topic": "Essays", "message": bad + " thanks"}, mentee)
            self.assertEqual(status, 400, bad)
            self.assertIn("inside PeerPilot", data["error"], bad)
        self.assertEqual(self.make_mentor(mentor, bio="Text me on my phone for tips and tricks.")[0], 400)
        # scores and years are not phone numbers
        ok = self.request(
            "POST", "/api/mentors/requests",
            {"mentor": handle, "topic": "Essays", "message": "I got a 1450 SAT in 2026, what should I fix?"}, mentee)
        self.assertEqual(ok[0], 201, ok)

    def test_mentor_rules_and_limits(self):
        mentor = self.register("m3@example.edu", "Sam", "Rivera")
        nameless = self.register("nn@example.edu", first="", last="")
        self.assertEqual(self.make_mentor(mentor, agree_rules=False)[0], 400)
        self.assertEqual(self.make_mentor(mentor, stage="Grade 3")[0], 400)
        self.assertEqual(self.make_mentor(mentor, topics=[])[0], 400)
        self.assertEqual(self.make_mentor(mentor, bio="short")[0], 400)
        self.assertEqual(self.make_mentor(nameless)[0], 400)  # needs a first name
        self.make_mentor(mentor)
        handle = self.request("GET", "/api/mentors", None, nameless)[1]["mentors"][0]["id"]
        status, data = self.request(
            "POST", "/api/mentors/requests", {"mentor": handle, "topic": "Essays", "message": "Please help me start."}, nameless)
        self.assertEqual(status, 400)
        self.assertIn("first name", data["error"])
        # can't request yourself
        me_handle = self.request("GET", "/api/mentors", None, mentor)[1]["mentors"]
        self.assertEqual(me_handle, [])
        # duplicate open request blocked
        mentee = self.register("e3@example.edu")
        body = {"mentor": handle, "topic": "Essays", "message": "Can you help with my essay?"}
        self.assertEqual(self.request("POST", "/api/mentors/requests", body, mentee)[0], 201)
        self.assertEqual(self.request("POST", "/api/mentors/requests", body, mentee)[0], 400)

    def test_report_closes_chat_and_reaches_admin_feedback(self):
        mentor = self.register("m4@example.edu", "Sam", "Rivera")
        mentee = self.register("e4@example.edu")
        self.make_mentor(mentor)
        handle = self.request("GET", "/api/mentors", None, mentee)[1]["mentors"][0]["id"]
        rid = self.request(
            "POST", "/api/mentors/requests", {"mentor": handle, "topic": "Essays", "message": "Can you help with my essay?"}, mentee
        )[1]["requests"][0]["id"]
        self.assertEqual(self.request("POST", "/api/mentors/report", {"request_id": rid, "reason": "They were rude to me."}, mentee)[0], 200)
        status, data = self.request("GET", f"/api/mentors/requests/{rid}/messages", None, mentee)
        self.assertEqual(data["request"]["status"], "closed")
        with database.connect() as conn:
            row = conn.execute("SELECT category FROM user_feedback").fetchone()
        self.assertEqual(row["category"], "Peer mentor report")

    def test_removing_mentor_profile_closes_chats(self):
        mentor = self.register("m5@example.edu", "Sam", "Rivera")
        mentee = self.register("e5@example.edu")
        self.make_mentor(mentor)
        handle = self.request("GET", "/api/mentors", None, mentee)[1]["mentors"][0]["id"]
        rid = self.request(
            "POST", "/api/mentors/requests", {"mentor": handle, "topic": "Essays", "message": "Can you help with my essay?"}, mentee
        )[1]["requests"][0]["id"]
        self.assertEqual(self.request("DELETE", "/api/mentors/me", None, mentor)[0], 200)
        self.assertEqual(self.request("GET", "/api/mentors", None, mentee)[1]["mentors"], [])
        self.assertEqual(self.request("GET", f"/api/mentors/requests/{rid}/messages", None, mentee)[1]["request"]["status"], "closed")

    # ------------------------------------------------------------ AI memory
    def test_memory_api_flow(self):
        a = self.register("mem@example.edu")
        status, data = self.request("GET", "/api/memory", None, a)
        self.assertEqual((status, data["enabled"], data["items"]), (200, True, []))
        status, data = self.request("POST", "/api/memory", {"text": "Wants to study biology"}, a)
        self.assertEqual(status, 201)
        item = data["items"][0]
        status, data = self.request("PUT", "/api/memory", {"id": item["id"], "text": "Wants to study marine biology"}, a)
        self.assertEqual(data["items"][0]["text"], "Wants to study marine biology")
        status, data = self.request("PUT", "/api/memory/settings", {"enabled": False}, a)
        self.assertFalse(data["enabled"])
        status, data = self.request("DELETE", f"/api/memory/{item['id']}", None, a)
        self.assertEqual(data["items"], [])
        self.request("POST", "/api/memory", {"text": "one"}, a)
        self.request("POST", "/api/memory", {"text": "two"}, a)
        self.assertEqual(self.request("DELETE", "/api/memory", None, a)[1]["items"], [])

    def test_memory_is_private_and_validated(self):
        a = self.register("m1@example.edu")
        b = self.register("m2@example.edu")
        item = self.request("POST", "/api/memory", {"text": "Likes physics"}, a)[1]["items"][0]
        self.assertEqual(self.request("GET", "/api/memory", None, b)[1]["items"], [])
        self.assertEqual(self.request("DELETE", f"/api/memory/{item['id']}", None, b)[0], 400)
        self.assertEqual(self.request("PUT", "/api/memory", {"id": item["id"], "text": "hacked"}, b)[0], 400)
        self.assertEqual(self.request("GET", "/api/memory", None, a)[1]["items"][0]["text"], "Likes physics")
        self.assertEqual(self.request("POST", "/api/memory", {"text": "email me at x@y.com"}, a)[0], 400)
        self.assertEqual(self.request("POST", "/api/memory", {"text": ""}, a)[0], 400)
        self.assertEqual(self.request("GET", "/api/memory")[0], 401)

    def test_deleting_an_account_deletes_its_memory(self):
        a = self.register("gone@example.edu")
        self.request("POST", "/api/memory", {"text": "Likes physics"}, a)
        with database.connect() as conn:
            conn.execute("DELETE FROM users WHERE email='gone@example.edu'")
            left = conn.execute("SELECT COUNT(*) FROM student_memory").fetchone()[0]
        self.assertEqual(left, 0)


if __name__ == "__main__":
    unittest.main()
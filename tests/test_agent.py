import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import assistant
import database
import features
from core import memory
from core.agent import Agent
from core.llm import LLM
from core.tools import ToolRegistry
from tools import web  # noqa: F401  (also proves the web tool imports)


class FakeLLM:
    assistant_message = staticmethod(LLM.assistant_message)
    tool_message = staticmethod(LLM.tool_message)

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, tools=None, on_token=None, **kwargs):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def tool_call(name, **args):
    return {"content": "", "tool_calls": [{"id": "c1", "name": name, "arguments": args, "extra": None}]}


class DbCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(cls.temp.name) / "agent.sqlite3"
        database.init_db()
        features.ensure_schema()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        with database.connect() as conn:
            conn.execute("DELETE FROM users")
            self.a = conn.execute("INSERT INTO users(email,password_hash) VALUES('a@x.edu','x')").lastrowid
            self.b = conn.execute("INSERT INTO users(email,password_hash) VALUES('b@x.edu','x')").lastrowid


class MemoryTests(DbCase):
    def test_each_student_has_a_private_memory(self):
        memory.for_user(self.a).add("Wants to study biology")
        self.assertEqual([e["text"] for e in memory.for_user(self.a).all()], ["Wants to study biology"])
        self.assertEqual(memory.for_user(self.b).all(), [])
        mine = memory.for_user(self.a).all()[0]["id"]
        with self.assertRaises(memory.MemoryError_):
            memory.for_user(self.b).delete(mine)  # can't touch someone else's memory
        with self.assertRaises(memory.MemoryError_):
            memory.for_user(self.b).update(mine, "hacked")
        self.assertEqual(len(memory.for_user(self.a).all()), 1)

    def test_duplicates_limits_and_cleanup(self):
        m = memory.for_user(self.a)
        first = m.add("Likes   short answers")
        self.assertEqual(m.add("likes short answers")["id"], first["id"])
        with self.assertRaises(memory.MemoryError_):
            m.add("x" * 201)
        for i in range(memory.MAX_ITEMS - 1):
            m.add(f"fact {i}")
        with self.assertRaises(memory.MemoryError_):
            m.add("one too many")
        self.assertEqual(m.clear(), memory.MAX_ITEMS)
        self.assertEqual(m.all(), [])

    def test_contact_info_and_bad_words_are_never_saved(self):
        m = memory.for_user(self.a)
        for bad in ["email me at kid@example.com", "call me 555 123 4567", "find me on snapchat", "this is shit"]:
            with self.assertRaises(memory.MemoryError_, msg=bad):
                m.add(bad)

    def test_the_ai_refuses_sensitive_facts_but_the_student_may_type_their_own(self):
        m = memory.for_user(self.a)
        for bad in ["Has anxiety about tests", "My password is hunter2", "Is undocumented", "SSN 123-45-6789"]:
            with self.assertRaises(memory.MemoryError_, msg=bad):
                m.add(bad, strict=True)
        m.add("Prefers evening study sessions", strict=True)
        m.add("Test anxiety is hard for me")  # the student's own choice, not the AI's

    def test_memory_can_be_switched_off(self):
        m = memory.for_user(self.a)
        self.assertTrue(m.enabled())
        m.set_enabled(False)
        self.assertFalse(m.enabled())
        self.assertTrue(memory.for_user(self.b).enabled())  # only this student's setting changed

    def test_prompt_block_shows_ids_and_notes_omissions(self):
        m = memory.for_user(self.a)
        self.assertEqual(m.prompt_block(), "(nothing saved yet)")
        for i in range(5):
            m.add(f"fact number {i} " + "y" * 150)
        block = m.prompt_block(max_chars=400)
        self.assertIn("older memories omitted", block)
        self.assertRegex(block, r"\[\d+\] fact number 4")


class ToolTests(DbCase):
    def registry(self):
        reg = ToolRegistry()
        self.assertEqual(reg.discover(Path(__file__).resolve().parent.parent / "tools"), [])
        return reg

    def test_all_tools_load_and_old_style_tools_still_work(self):
        reg = self.registry()
        self.assertEqual(
            set(reg.names()),
            {"calculator", "get_time", "web_search", "read_page", "remember", "update_memory", "forget",
             "search_memory", "get_deadlines", "get_scholarship_tracker"},
        )
        self.assertEqual(reg.execute("calculator", {"expression": "(12.5 * 4) / 2"}), "25.0")

    def test_memory_tools_work_on_the_right_student_only(self):
        reg = self.registry()
        out = reg.execute("remember", {"text": "Loves chemistry"}, {"user_id": self.a})
        self.assertIn("Saved", out)
        self.assertEqual(len(memory.for_user(self.a).all()), 1)
        self.assertEqual(memory.for_user(self.b).all(), [])
        other_id = memory.for_user(self.a).all()[0]["id"]
        self.assertIn("failed", reg.execute("forget", {"id": other_id}, {"user_id": self.b}))
        self.assertIn("failed", reg.execute("remember", {"text": "Has anxiety"}, {"user_id": self.a}))
        self.assertEqual(len(memory.for_user(self.a).all()), 1)
        memory.for_user(self.a).set_enabled(False)
        self.assertIn("turned memory off", reg.execute("remember", {"text": "More"}, {"user_id": self.a}))

    def test_a_tool_outside_the_allowed_list_is_refused(self):
        reg = self.registry()
        out = reg.execute("remember", {"text": "x"}, {"user_id": self.a}, allowed={"calculator"})
        self.assertIn("unknown tool", out)
        self.assertEqual([s["function"]["name"] for s in reg.schemas({"calculator"})], ["calculator"])

    def test_deadline_and_scholarship_tools(self):
        reg = self.registry()
        with database.connect() as conn:
            conn.execute("INSERT INTO tasks(id,user_id,title,due) VALUES('t1',?,?,?)", (self.a, "Ask counselor", "2000-01-01"))
            conn.execute("INSERT INTO scholarships(id,user_id,name,due) VALUES('s1',?,?,?)", (self.a, "Rotary", "2999-01-01"))
        out = reg.execute("get_deadlines", {"within_days": 365}, {"user_id": self.a})
        self.assertIn("Ask counselor", out)
        self.assertIn("OVERDUE", out)
        self.assertNotIn("Rotary", out)  # too far away
        self.assertIn("Rotary", reg.execute("get_scholarship_tracker", {}, {"user_id": self.a}))
        self.assertIn("Nothing due", reg.execute("get_deadlines", {}, {"user_id": self.b}))

    def test_web_tool_refuses_private_addresses_and_odd_schemes(self):
        for url in ["http://127.0.0.1:8000/api/admin", "http://localhost/", "file:///etc/passwd", "http://192.168.1.1/"]:
            with self.assertRaises(ValueError, msg=url):
                web._check_public(url)
        self.assertIn("Couldn't open", web.read_page({"url": "http://127.0.0.1/"}))


class AgentLoopTests(DbCase):
    def test_tool_loop_runs_tools_logs_them_and_returns_the_final_text(self):
        reg = ToolRegistry()
        reg.register({"name": "get_time", "description": "t"}, lambda a: "Friday")
        fake = FakeLLM(tool_call("get_time"), {"content": "It is Friday!", "tool_calls": []})
        agent = Agent(fake, reg, "Be brief.")
        self.assertEqual(agent.respond("what day is it?"), "It is Friday!")
        self.assertEqual(agent.tool_log, [("get_time", {}, "Friday")])
        roles = [m["role"] for m in agent.history]
        self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])

    def test_the_last_round_forces_a_written_answer(self):
        reg = ToolRegistry()
        reg.register({"name": "get_time", "description": "t"}, lambda a: "Friday")
        fake = FakeLLM(tool_call("get_time"))  # would loop forever if allowed
        agent = Agent(fake, reg, "x", max_tool_rounds=2)
        agent.respond("loop")
        self.assertIsNone(fake.calls[-1]["tools"])
        self.assertLessEqual(len(fake.calls), 3)

    def test_system_prompt_has_date_and_this_students_memory_only(self):
        memory.for_user(self.a).add("Wants to be a nurse")
        memory.for_user(self.b).add("Wants to be a pilot")
        fake = FakeLLM({"content": "ok", "tool_calls": []})
        Agent(fake, ToolRegistry(), "Be kind.", memory=memory.for_user(self.a)).respond("hi")
        system = fake.calls[0]["messages"][0]["content"]
        self.assertIn("Be kind.", system)
        self.assertIn("Current date and time", system)
        self.assertIn("nurse", system)
        self.assertNotIn("pilot", system)

    def test_memory_section_is_left_out_when_the_student_turned_it_off(self):
        m = memory.for_user(self.a)
        m.add("Wants to be a nurse")
        m.set_enabled(False)
        fake = FakeLLM({"content": "ok", "tool_calls": []})
        Agent(fake, ToolRegistry(), "Be kind.", memory=m).respond("hi")
        self.assertNotIn("nurse", fake.calls[0]["messages"][0]["content"])

    def test_assistant_hides_memory_tools_when_memory_is_off(self):
        fake = FakeLLM({"content": "Hello!", "tool_calls": []})
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k"}), patch.object(assistant, "get_llm", return_value=fake):
            assistant.answer({"message": "Hi there"}, {}, "advisor", user_id=self.a)
            names_on = {t["function"]["name"] for t in fake.calls[-1]["tools"]}
            memory.for_user(self.a).set_enabled(False)
            assistant.answer({"message": "Hi again"}, {}, "advisor", user_id=self.a)
            names_off = {t["function"]["name"] for t in fake.calls[-1]["tools"]}
        self.assertIn("remember", names_on)
        self.assertNotIn("remember", names_off)
        self.assertIn("web_search", names_off)


if __name__ == "__main__":
    unittest.main()
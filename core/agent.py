"""
The agent loop: student's message in -> (model <-> tools)* -> final reply out.
(From the ai-starter project, reshaped for a web server: one short-lived Agent per request.)

It builds each turn's system prompt (instructions + today's date + the student's saved memory),
runs tool calls side by side, and keeps a log of every tool call so the caller can build a
trustworthy Sources list from what was REALLY searched and read.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable

from .llm import LLM
from .tools import ToolRegistry


class Agent:
    def __init__(self, llm: LLM, tools: ToolRegistry, system_prompt: str, *,
                 memory=None, ctx: dict | None = None, allowed_tools: set[str] | None = None,
                 history: list[dict] | None = None, max_tool_rounds: int = 6,
                 reasoning_effort: str | None = None, max_tokens: int | None = None):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.memory = memory
        self.ctx = ctx or {}
        self.allowed = allowed_tools
        self.max_tool_rounds = max_tool_rounds
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.history: list[dict] = [
            {"role": h["role"], "content": h["content"]} for h in (history or [])
            if h.get("role") in {"user", "assistant"} and h.get("content")
        ]
        self.tool_log: list[tuple[str, dict, str]] = []   # (tool name, arguments, result)

    def respond(self, user_text: str,
                on_token: Callable[[str], None] | None = None,
                on_tool: Callable[[str, dict, str], None] | None = None) -> str:
        """Run one student turn and return the assistant's final text."""
        self.history.append({"role": "user", "content": user_text})
        schemas = self.tools.schemas(self.allowed) or None
        reply = ""
        for round_number in range(self.max_tool_rounds + 1):
            last_round = round_number == self.max_tool_rounds
            out = self.llm.chat(self._messages(), None if last_round else schemas, on_token,
                                reasoning_effort=self.reasoning_effort, max_tokens=self.max_tokens)
            self.history.append(self.llm.assistant_message(out["content"], out["tool_calls"]))
            reply = out["content"]
            if not out["tool_calls"]:
                break
            results = self._run_tools(out["tool_calls"])
            for call, result in zip(out["tool_calls"], results):
                self.tool_log.append((call["name"], call["arguments"], result))
                if on_tool:
                    on_tool(call["name"], call["arguments"], result)
                self.history.append(self.llm.tool_message(call, result))
        return reply or "I couldn't finish that one. Could you try asking it a different way?"

    # ── internals ─────────────────────────────────────────────────────────
    def _run_tools(self, calls: list[dict]) -> list[str]:
        """Run tool calls side by side (searches and page reads are slow, network-bound)."""
        def one(c):
            return self.tools.execute(c["name"], c["arguments"], self.ctx, self.allowed)
        if len(calls) == 1:
            return [one(calls[0])]
        with ThreadPoolExecutor(max_workers=min(len(calls), 6)) as pool:
            return list(pool.map(one, calls))

    def _system(self) -> str:
        parts = [self.system_prompt,
                 f"Current date and time: {datetime.now().strftime('%A, %d %B %Y, %H:%M')}"]
        if self.memory is not None and self.memory.enabled():
            parts.append("# Memory (saved facts, shown as [id] text)\n" + self.memory.prompt_block())
        return "\n\n".join(parts)

    def _messages(self) -> list[dict]:
        return [{"role": "system", "content": self._system()}] + self.history
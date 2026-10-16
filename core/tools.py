"""
Tool registry with drop-in discovery (from the ai-starter project).

Every .py file in tools/ (not starting with "_") defines either one tool:

    TOOL = {"name": ..., "description": ..., "parameters": {JSON-schema object}}
    def run(arguments: dict) -> str: ...

or several at once:

    TOOLS = [{"name": ..., "description": ..., "parameters": {...}, "run": fn}, ...]

PeerPilot AI addition: a tool function may take a second argument, `ctx`, a dict like
{"user_id": 7}. That is how a tool knows WHICH student it is working for.

    def run(arguments: dict, ctx: dict) -> str: ...

Add a file, restart, and the model can use it. Nothing else to edit.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
MAX_RESULT_CHARS = 14_000


def _takes_ctx(fn) -> bool:
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    except (TypeError, ValueError):
        return False
    return len(params) >= 2


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[dict, callable, bool]] = {}

    def register(self, spec: dict, fn) -> None:
        name = spec.get("name", "")
        if not _NAME_RE.match(name):
            raise ValueError(f"Bad tool name: {name!r}")
        if not spec.get("description"):
            raise ValueError(f"Tool '{name}' needs a description")
        self._tools[name] = (spec, fn, _takes_ctx(fn))

    def discover(self, folder: Path) -> list[str]:
        """Load every tool in a folder. Returns a list of problems (empty = all good)."""
        problems = []
        for path in sorted(Path(folder).glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"tools.{path.stem}", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "TOOLS"):
                    for entry in mod.TOOLS:
                        self.register(entry, entry["run"])
                else:
                    self.register(mod.TOOL, mod.run)
            except Exception as e:  # one broken tool must not break the rest
                problems.append(f"{path.name}: {e}")
        return problems

    def schemas(self, allowed: set[str] | None = None) -> list[dict]:
        """Tool list in the OpenAI function-calling format (optionally only some tools)."""
        return [
            {"type": "function", "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s.get("parameters") or {"type": "object", "properties": {}},
            }}
            for name, (s, _, _) in self._tools.items()
            if allowed is None or name in allowed
        ]

    def names(self) -> list[str]:
        return list(self._tools)

    def execute(self, name: str, arguments: dict, ctx: dict | None = None,
                allowed: set[str] | None = None) -> str:
        if name not in self._tools or (allowed is not None and name not in allowed):
            return f"Error: unknown tool '{name}'."
        _, fn, wants_ctx = self._tools[name]
        try:
            out = str(fn(arguments or {}, ctx or {}) if wants_ctx else fn(arguments or {}))
        except Exception as e:  # report to the model so it can recover
            return f"Error: tool '{name}' failed: {e}"
        return out[:MAX_RESULT_CHARS]
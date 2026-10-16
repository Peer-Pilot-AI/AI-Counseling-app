"""
LLM client for Gemini (free tier) or any OpenAI-compatible server.
(From the ai-starter project; PeerPilot AI changes: per-call overrides, structured errors.)

  "gemini" -> Google Gemini through its OpenAI-compatible endpoint
              (key from https://aistudio.google.com/apikey, read from
              api_key in config.json or the GEMINI_API_KEY env var)
  "openai" -> any other OpenAI-compatible server (set "url" and "api_key")

`chat()` returns the same shape every time:

    {"content": str, "tool_calls": [{"id", "name", "arguments": dict, "extra": dict|None}]}

Speed
  * streaming: pass on_token and text arrives chunk by chunk
  * minimal thinking: reasoning_effort="minimal" keeps Gemini 3's hidden
    reasoning pass short (it can't be switched off entirely on Gemini 3). If a
    model rejects the setting we step down: minimal -> low -> omit.
  * one pooled HTTP session, so no new TLS handshake on every call

Reliability
  * list several models in config["models"]: if one fails (rate limit, retired
    name, outage) it cools down for a minute and the next one takes the call.
  * Gemini 3 "thought signatures": each tool call comes back with a signature
    that must be echoed back in history or Google answers 400. We keep it in
    call["extra"] and send it back untouched.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Callable, Iterator
import requests

COOLDOWN_SECONDS = 60
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
SKIP_SIGNATURE = "skip_thought_signature_validator"   # Google's documented bypass value
_EFFORT_DOWNGRADE = {"minimal": "low", "medium": "low", "high": "low", "low": None, "none": None}


class LLMError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None, errors: list | None = None):
        super().__init__(msg)
        self.status = status          # HTTP status of the most recent failure, if there was one
        self.errors = errors or []    # [(model, status, short text), ...] one per model tried


class LLM:
    def __init__(self, cfg: dict):
        provider = (cfg.get("provider") or "gemini").lower()
        if provider not in ("gemini", "openai"):
            raise LLMError(f"Unknown provider '{provider}' (use 'gemini' or 'openai')")
        self.api_key = cfg.get("api_key") or ""
        if provider == "gemini":
            self.api_key = self.api_key or os.environ.get("GEMINI_API_KEY", "")
            if not self.api_key:
                raise LLMError("Gemini needs a key: set GEMINI_API_KEY or api_key in config.json "
                               "(free at https://aistudio.google.com/apikey)")
            default_url, default_model, default_effort = GEMINI_URL, "gemini-3.5-flash-lite", "minimal"
        else:
            default_url, default_model, default_effort = "http://localhost:1234", "local-model", ""

        self.url = (cfg.get("url") or default_url).rstrip("/")
        models = cfg.get("models") or [cfg.get("model", default_model)]
        self.models: list[str] = [models] if isinstance(models, str) else list(models)
        self.timeout = cfg.get("timeout", 60)
        self.temperature = cfg.get("temperature", 0.6)
        self.max_tokens = cfg.get("max_tokens", 2048)
        self.reasoning_effort = cfg.get("reasoning_effort", default_effort) or None

        self._http = requests.Session()
        self._cool_until: dict[str, float] = {}
        self._effort: dict[tuple, str | None] = {}   # (model, wanted effort) -> effort that worked

    # ── public ────────────────────────────────────────────────────────────
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             on_token: Callable[[str], None] | None = None, *,
             reasoning_effort: str | None = None, max_tokens: int | None = None) -> dict:
        """Send a conversation, get back {"content", "tool_calls"}.

        on_token: if given, the reply streams and each text chunk is passed to it.
        reasoning_effort / max_tokens: override the defaults for this one call.
        """
        errors, last_status = [], None
        for model in self._ladder():
            try:
                return self._call(model, messages, tools, on_token, reasoning_effort, max_tokens)
            except Exception as e:  # noqa: BLE001 - any failure falls through to the next model
                last_status = getattr(e, "status", None)
                errors.append((model, last_status, str(e)[:220]))
                self._cool_until[model] = time.time() + COOLDOWN_SECONDS
        raise LLMError("All models failed -> " + " | ".join(f"{m}: {t}" for m, _, t in errors),
                       status=last_status, errors=errors)

    def list_models(self) -> list[str]:
        """Model names this key can call (GET /models). Handy when a name gets retired."""
        resp = self._http.get(f"{self._base()}/models", headers=self._headers(), timeout=15)
        resp.raise_for_status()
        ids = [m.get("id", "").removeprefix("models/") for m in resp.json().get("data", [])]
        return sorted(i for i in ids if i)

    @staticmethod
    def assistant_message(content: str, tool_calls: list[dict]) -> dict:
        """The assistant turn to append to history after a reply."""
        msg: dict = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = []
            for c in tool_calls:
                entry = {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                if c.get("extra"):
                    entry["extra_content"] = c["extra"]    # Gemini 3 thought signature
                msg["tool_calls"].append(entry)
        return msg

    @staticmethod
    def tool_message(call: dict, result: str) -> dict:
        """The tool-result turn that answers a tool call."""
        return {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": result}

    # ── internals ─────────────────────────────────────────────────────────
    def _ladder(self) -> list[str]:
        now = time.time()
        live = [m for m in self.models if self._cool_until.get(m, 0) <= now]
        return live or self.models  # all cooling? try them anyway

    def _base(self) -> str:
        return self.url if self.url.endswith(("/v1", "/openai")) else f"{self.url}/v1"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, payload: dict, stream: bool):
        try:
            resp = self._http.post(f"{self._base()}/chat/completions", json=payload,
                                   headers=self._headers(), timeout=self.timeout, stream=stream)
            resp.raise_for_status()
            return resp
        except requests.ConnectionError:
            raise LLMError(f"Cannot reach {self.url}. Check your internet connection.")
        except requests.Timeout:
            raise LLMError(f"Timed out after {self.timeout}s")
        except requests.HTTPError as e:
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:400]}",
                           status=e.response.status_code)

    def _call(self, model, messages, tools, on_token, reasoning_effort=None, max_tokens=None) -> dict:
        stream = on_token is not None
        base = {"model": model, "stream": stream,
                "temperature": self.temperature, "max_tokens": max_tokens or self.max_tokens}
        if tools:
            base["tools"] = tools
            base["tool_choice"] = "auto"

        wanted = reasoning_effort or self.reasoning_effort
        effort = self._effort.get((model, wanted), wanted)
        start_effort, dummy_sigs = effort, False
        for _ in range(4):
            payload = dict(base, messages=_with_skip_signatures(messages) if dummy_sigs else messages)
            if effort:
                payload["reasoning_effort"] = effort
            try:
                resp = self._post(payload, stream)
                break
            except LLMError as e:
                if e.status != 400:
                    raise
                text = str(e).lower()
                if "thought_signature" in text or "thought signature" in text:
                    if dummy_sigs:
                        raise
                    dummy_sigs = True       # e.g. history holds another model's signatures
                    continue
                if not effort:
                    raise
                effort = _EFFORT_DOWNGRADE.get(effort)   # unsupported setting -> step down
        else:
            raise LLMError("Request kept failing after retries.")
        if effort != start_effort:
            self._effort[(model, wanted)] = effort       # remember what this model accepts
        return self._read_stream(resp, on_token) if stream else self._parse_full(resp.json())

    def _parse_full(self, data: dict) -> dict:
        msg = (data.get("choices") or [{}])[0].get("message", {})
        calls = [self._norm_call(t.get("id"), t["function"]["name"], t["function"].get("arguments"),
                                 t.get("extra_content"))
                 for t in msg.get("tool_calls") or []]
        return {"content": (msg.get("content") or "").strip(), "tool_calls": calls}

    def _read_stream(self, resp, on_token) -> dict:
        text: list[str] = []
        slots: list[dict] = []   # partial tool calls, in order of arrival
        by_index: dict[int, dict] = {}

        for chunk in self._events(resp):
            delta = (chunk.get("choices") or [{}])[0].get("delta", {})
            if delta.get("content"):
                text.append(delta["content"])
                on_token(delta["content"])
            for t in delta.get("tool_calls") or []:
                fn = t.get("function") or {}
                idx = t.get("index")      # Gemini omits this; OpenAI-style servers send it
                if idx is not None and idx in by_index:
                    slot = by_index[idx]
                elif idx is None and slots and not fn.get("name"):
                    slot = slots[-1]                      # continuation of the last call
                else:
                    slot = {"id": None, "name": "", "args": "", "extra": None}   # a new call
                    slots.append(slot)
                    if idx is not None:
                        by_index[idx] = slot
                slot["id"] = t.get("id") or slot["id"]
                slot["name"] += fn.get("name") or ""
                slot["args"] += fn.get("arguments") or ""
                slot["extra"] = t.get("extra_content") or slot["extra"]

        calls = [self._norm_call(s["id"], s["name"], s["args"], s["extra"]) for s in slots if s["name"]]
        return {"content": "".join(text).strip(), "tool_calls": calls}

    @staticmethod
    def _events(resp) -> Iterator[dict]:
        for raw in resp.iter_lines():
            if not raw:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if raw.startswith("data:"):
                raw = raw[5:].strip()
                if raw == "[DONE]":
                    return
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                continue

    @staticmethod
    def _norm_call(call_id, name, arguments, extra=None) -> dict:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                arguments = {}
        return {"id": call_id or f"call_{uuid.uuid4().hex[:8]}", "name": name,
                "arguments": arguments or {}, "extra": extra}


def _with_skip_signatures(messages: list[dict]) -> list[dict]:
    """Copy of the history where every tool call carries Google's documented
    'skip validation' signature. Used only as a fallback when Gemini rejects the real ones."""
    out = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            m = dict(m, tool_calls=[
                dict(tc, extra_content={"google": {"thought_signature": SKIP_SIGNATURE}})
                for tc in m["tool_calls"]])
        out.append(m)
    return out
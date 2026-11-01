"""Adaptador para APIs compatíveis com OpenAI (OpenAI, Groq, Ollama, etc.).

Exemplos no .env:
  Groq (tem plano gratuito):  OPENAI_BASE_URL=https://api.groq.com/openai/v1
  Ollama (local, grátis):     OPENAI_BASE_URL=http://localhost:11434/v1  e OPENAI_API_KEY=ollama
"""

from __future__ import annotations

import json
from typing import Any

from ..schemas import LLMResponse, ToolCall
from ..tools import ToolSpec
from .base import LLM, Message


def to_openai_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)},
                    }
                    for tc in m["tool_calls"]
                ]
            out.append(msg)
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
    return out


class OpenAICompatibleLLM(LLM):
    def __init__(self, model: str, base_url: str | None = None, max_tokens: int = 512) -> None:
        from openai import OpenAI

        if not model:
            raise ValueError("Defina LLM_MODEL para o provedor openai")
        self.model = model
        self.max_tokens = max_tokens
        self._client = OpenAI(base_url=base_url) if base_url else OpenAI()

    def chat(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(system, messages),
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        usage = resp.usage
        return LLMResponse(
            msg.content or "",
            calls,
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )

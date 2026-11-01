"""Interface comum para provedores de LLM.

Formato interno de mensagens (independente de provedor):
  {"role": "user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": list[ToolCall]}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}
Cada adaptador converte isso para o formato da sua API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..schemas import LLMResponse
from ..tools import ToolSpec

Message = dict[str, Any]


class LLM(ABC):
    model: str

    @abstractmethod
    def chat(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse: ...

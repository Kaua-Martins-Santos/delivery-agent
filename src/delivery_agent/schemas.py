"""Tipos compartilhados entre os módulos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class UnknownTenantError(LookupError):
    """Restaurante (tenant) inexistente."""


class TenantRequiredError(ValueError):
    """Tentativa de acessar dados sem informar o tenant. Falha fechada."""


@dataclass(frozen=True)
class Restaurant:
    id: str
    nome: str
    canarios: tuple[str, ...] = ()  # termos exclusivos deste restaurante, usados nos evals de vazamento


@dataclass
class Chunk:
    tenant_id: str
    source: str   # ex.: "faq.md#horario"
    text: str


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AgentResult:
    answer: str
    tenant_id: str
    model: str
    sources: list[str] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    context: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    blocked: str | None = None       # motivo do bloqueio, se houver
    pii_masked: bool = False
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

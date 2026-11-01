"""Orquestração: guardrails -> RAG por tenant -> LLM com ferramentas -> checagem de saída."""

from __future__ import annotations

import json
import time
from typing import Any

from . import guardrails
from .config import Settings
from .embeddings import Embedder
from .llm.base import LLM, Message
from .orders import OrderRepository
from .prompts import build_system_prompt, format_context
from .schemas import AgentResult, Restaurant, UnknownTenantError
from .store import VectorStore
from .tools import TOOL_SPECS, ToolContext, execute_tool

STEP_LIMIT_ANSWER = "Não consegui resolver isso agora. Quer que eu te transfira para um atendente?"


class Agent:
    def __init__(
        self,
        llm: LLM,
        embedder: Embedder,
        store: VectorStore,
        orders: OrderRepository,
        restaurants: dict[str, Restaurant],
        settings: Settings,
    ) -> None:
        self.llm = llm
        self.embedder = embedder
        self.store = store
        self.orders = orders
        self.restaurants = restaurants
        self.settings = settings
        self.canary = guardrails.new_canary()

    def run(self, tenant_id: str, message: str, history: list[Message] | None = None) -> AgentResult:
        start = time.perf_counter()
        restaurant = self.restaurants.get(tenant_id)
        if restaurant is None:
            raise UnknownTenantError(tenant_id)

        result = AgentResult(answer="", tenant_id=tenant_id, model=self.llm.model)

        # 1. Guardrail de entrada: bloqueia sem gastar chamada de LLM.
        if guardrails.looks_like_injection(message):
            result.answer = guardrails.BLOCKED_ANSWER
            result.blocked = "prompt_injection"
            return self._finish(result, start)

        clean, result.pii_masked = guardrails.mask_pii(message)

        # 2. Recuperação SEMPRE filtrada pelo tenant da requisição.
        query_vec = self.embedder.embed([clean])[0]
        hits = [
            h
            for h in self.store.search(tenant_id, query_vec, self.settings.top_k)
            if h.score >= self.settings.min_score
        ]
        result.sources = [h.chunk.source for h in hits]
        result.retrieval_scores = [round(h.score, 3) for h in hits]
        result.context = format_context(hits)

        # 3. Loop de ferramentas com limite de passos (evita loop infinito e custo descontrolado).
        system = build_system_prompt(restaurant, hits, self.canary)
        messages: list[Message] = [
            {"role": m["role"], "content": guardrails.mask_pii(m["content"])[0]} for m in (history or [])
        ]
        messages.append({"role": "user", "content": f"<mensagem_cliente>{clean}</mensagem_cliente>"})
        ctx = ToolContext(tenant_id=tenant_id, orders=self.orders)

        answer = STEP_LIMIT_ANSWER
        for _ in range(self.settings.max_steps):
            resp = self.llm.chat(system, messages, TOOL_SPECS)
            result.input_tokens += resp.input_tokens
            result.output_tokens += resp.output_tokens
            if not resp.tool_calls:
                answer = resp.text.strip() or STEP_LIMIT_ANSWER
                break
            messages.append({"role": "assistant", "content": resp.text, "tool_calls": resp.tool_calls})
            for call in resp.tool_calls:
                output = execute_tool(call, ctx)
                result.tool_calls.append({"name": call.name, "arguments": call.arguments, "result": output})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(output, ensure_ascii=False, default=str),
                    }
                )

        # 4. Guardrail de saída: se o código secreto do prompt aparecer, houve vazamento do system prompt.
        if guardrails.leaks_canary(answer, self.canary):
            answer = guardrails.BLOCKED_ANSWER
            result.blocked = "system_prompt_leak"

        result.answer = answer
        return self._finish(result, start)

    def _finish(self, result: AgentResult, start: float) -> AgentResult:
        result.latency_ms = round((time.perf_counter() - start) * 1000, 1)
        s = self.settings
        result.cost_usd = round(
            result.input_tokens / 1e6 * s.price_input_per_mtok + result.output_tokens / 1e6 * s.price_output_per_mtok,
            6,
        )
        return result

    def describe(self) -> dict[str, Any]:
        return {
            "model": self.llm.model,
            "embedder": self.embedder.name,
            "store": type(self.store).__name__,
            "top_k": self.settings.top_k,
            "min_score": self.settings.min_score,
        }

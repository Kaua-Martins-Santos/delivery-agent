"""LLM falso, determinístico e gratuito.

Serve para três coisas:
  1. Rodar testes e evals no CI sem API key e sem custo.
  2. Ser um BASELINE EXTRATIVO: ele só copia as frases do contexto mais parecidas com a
     pergunta. Comparar o LLM real contra ele mostra quanto o modelo agrega de verdade.
  3. Exercitar o loop de ferramentas (tool calling) de forma previsível.
"""

from __future__ import annotations

import json
import re

import numpy as np

from ..embeddings import HashEmbedder
from ..schemas import LLMResponse, ToolCall
from ..text import normalize
from ..tools import ToolSpec
from .base import LLM, Message

ORDER_CODE_RE = re.compile(r"\b([A-Za-z]{2,4}-\d{4})\b")
HANDOFF_RE = re.compile(r"(atendente|humano|pessoa de verdade|reclama|reembolso|estorno|veio errado|veio frio|faltou)")
FALLBACK = "Não tenho essa informação aqui. Quer que eu te transfira para um atendente?"


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class FakeLLM(LLM):
    def __init__(self, model: str = "fake-extrativo", min_sentence_score: float = 0.2) -> None:
        self.model = model
        self.min_sentence_score = min_sentence_score
        self._embedder = HashEmbedder()
        self._ids = 0

    def _next_id(self) -> str:
        self._ids += 1
        return f"call_{self._ids}"

    def chat(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        prompt_size = _approx_tokens(system + json.dumps(messages, default=str, ensure_ascii=False))
        last = messages[-1]
        tool_names = {t.name for t in tools}

        if last["role"] == "tool":
            text = self._answer_from_tools(messages)
            return LLMResponse(text, [], prompt_size, _approx_tokens(text))

        question = re.sub(r"</?mensagem_cliente>", "", last["content"])
        code = ORDER_CODE_RE.search(question)
        if code and "consultar_pedido" in tool_names:
            call = ToolCall(self._next_id(), "consultar_pedido", {"codigo_pedido": code.group(1).upper()})
            return LLMResponse("", [call], prompt_size, 10)
        if HANDOFF_RE.search(normalize(question)) and "transferir_para_atendente" in tool_names:
            call = ToolCall(self._next_id(), "transferir_para_atendente", {"motivo": question[:120]})
            return LLMResponse("", [call], prompt_size, 10)

        text = self._extract(question, system)
        return LLMResponse(text, [], prompt_size, _approx_tokens(text))

    def _extract(self, question: str, system: str) -> str:
        # O bloco de contexto fica em linhas próprias no fim do prompt (as regras também citam a tag).
        match = re.search(r"^<contexto>\n(.*?)\n</contexto>$", system, re.S | re.M)
        if not match:
            return FALLBACK
        # Títulos de seção não têm pontuação final; só frases completas viram candidatas.
        lines = [ln for ln in match.group(1).splitlines() if "." in ln and not ln.startswith("[fonte")]
        sentences = [s.strip() for ln in lines for s in re.split(r"(?<=[.!?])\s+", ln) if len(s.strip()) > 3]
        if not sentences:
            return FALLBACK
        vectors = self._embedder.embed([question] + sentences)
        scores = vectors[1:] @ vectors[0]
        best = [i for i in np.argsort(-scores)[:2] if scores[i] >= self.min_sentence_score]
        if not best:
            return FALLBACK
        return " ".join(sentences[i] for i in sorted(best))

    @staticmethod
    def _answer_from_tools(messages: list[Message]) -> str:
        parts: list[str] = []
        for m in reversed(messages):
            if m["role"] != "tool":
                break
            data = json.loads(m["content"])
            if data.get("transferido"):
                parts.append(f"Certo! Vou te transferir para um atendente. Seu protocolo é {data['protocolo']}.")
            elif data.get("encontrado"):
                prev = f" Previsão: {data['previsao']}." if data.get("previsao") else ""
                parts.append(f"Seu pedido {data['codigo']} está: {data['status']}.{prev}")
            elif "encontrado" in data:
                parts.append(f"Não encontrei o pedido {data.get('codigo', '')} neste restaurante. Pode conferir o código?")
            else:
                parts.append("Tive um problema para consultar agora. Quer falar com um atendente?")
        return " ".join(reversed(parts))

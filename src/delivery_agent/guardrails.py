"""Guardrails de entrada e saída.

São heurísticas baratas que rodam ANTES do LLM (economizam custo e reduzem risco).
Não são perfeitas: a proteção real contra vazamento entre restaurantes está na
arquitetura (o LLM nunca escolhe o tenant). Os evals medem o quanto isso segura.
"""

from __future__ import annotations

import re
import secrets

from .text import normalize

_INJECTION_PATTERNS = [
    r"ignor\w* (\w+ ){0,3}(instruc|regra|orientac|prompt)",
    r"ignore (all |the )?(previous|above|prior) (instructions|rules)",
    r"(desconsider|esquec)\w* (\w+ ){0,3}(instruc|regra)",
    r"(mostr|revel|exib|imprim|repit)\w* (\w+ ){0,3}(prompt|instruc|regras do sistema)",
    r"system prompt",
    r"(voce agora e|a partir de agora voce e|finja (que )?(ser|e)|aja como|act as)",
    r"modo (desenvolvedor|dev|admin|deus)",
    r"(todos|todas|outros|outras) (os |as )?(restaurante|pedido|cliente|loja)s? (do sistema|da plataforma|cadastrad)",
    r"\b(jailbreak|dan mode)\b",
]
_INJECTION_RE = [re.compile(p) for p in _INJECTION_PATTERNS]

_PII_PATTERNS = {
    "CPF": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "TELEFONE": re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b"),
    "CARTAO": re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
}

BLOCKED_ANSWER = (
    "Desculpe, não posso ajudar com isso. Posso tirar dúvidas sobre o cardápio, "
    "entrega ou o status do seu pedido."
)


def looks_like_injection(message: str) -> bool:
    text = normalize(message)
    return any(p.search(text) for p in _INJECTION_RE)


def mask_pii(message: str) -> tuple[str, bool]:
    """Mascara dados pessoais antes de mandar para o LLM e para os logs."""
    masked = message
    for label, pattern in _PII_PATTERNS.items():
        masked = pattern.sub(f"[{label}]", masked)
    return masked, masked != message


def new_canary() -> str:
    """Token secreto colocado no system prompt. Se aparecer na resposta, o prompt vazou."""
    return f"CNRY-{secrets.token_hex(4)}"


def leaks_canary(answer: str, canary: str) -> bool:
    return canary.lower() in answer.lower()

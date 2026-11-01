"""API HTTP.

Rodar:  uvicorn delivery_agent.api:app --reload
Docs:   http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .agent import Agent
from .container import build_agent
from .schemas import UnknownTenantError

log = logging.getLogger("delivery_agent")
app = FastAPI(title="Delivery Agent", version="0.1.0")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    historico: list[Turn] = Field(default_factory=list, max_length=20)


class ChatOut(BaseModel):
    resposta: str
    fontes: list[str]
    ferramentas: list[dict[str, Any]]
    bloqueado: str | None
    latencia_ms: float
    tokens: dict[str, int]
    custo_usd: float
    modelo: str


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    return build_agent()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", **get_agent().describe()}


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, x_tenant_id: str = Header(..., description="Em produção viria do token (JWT), nunca do texto")):
    try:
        r = get_agent().run(x_tenant_id, body.mensagem, [t.model_dump() for t in body.historico])
    except UnknownTenantError:
        raise HTTPException(status_code=404, detail="restaurante não encontrado")

    # Log estruturado sem o texto do cliente (privacidade); só métricas.
    log.info(
        "chat tenant=%s latency_ms=%s tools=%s blocked=%s tokens_in=%s tokens_out=%s",
        r.tenant_id, r.latency_ms, [t["name"] for t in r.tool_calls], r.blocked, r.input_tokens, r.output_tokens,
    )
    return ChatOut(
        resposta=r.answer,
        fontes=r.sources,
        ferramentas=[{"nome": t["name"], "argumentos": t["arguments"]} for t in r.tool_calls],
        bloqueado=r.blocked,
        latencia_ms=r.latency_ms,
        tokens={"entrada": r.input_tokens, "saida": r.output_tokens},
        custo_usd=r.cost_usd,
        modelo=r.model,
    )

"""Ferramentas que o LLM pode chamar.

Decisão de segurança importante: o tenant NUNCA vem dos argumentos do LLM.
Ele vem do ToolContext, montado a partir da requisição autenticada. Assim,
mesmo que um cliente convença o modelo a pedir o pedido de outro restaurante,
a consulta continua presa ao restaurante da conversa.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from .orders import OrderRepository
from .schemas import ToolCall


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolContext:
    tenant_id: str
    orders: OrderRepository
    _protocols: itertools.count = field(default_factory=lambda: itertools.count(1))


TOOL_SPECS = [
    ToolSpec(
        name="consultar_pedido",
        description=(
            "Consulta o status e a previsão de entrega de um pedido deste restaurante. "
            "Use quando o cliente informar um código de pedido (ex.: NON-1001)."
        ),
        parameters={
            "type": "object",
            "properties": {"codigo_pedido": {"type": "string", "description": "Código do pedido"}},
            "required": ["codigo_pedido"],
        },
    ),
    ToolSpec(
        name="transferir_para_atendente",
        description=(
            "Transfere a conversa para um atendente humano. Use quando o cliente pedir, "
            "quando houver reclamação, reembolso, pedido errado ou algo que você não consegue resolver."
        ),
        parameters={
            "type": "object",
            "properties": {"motivo": {"type": "string", "description": "Resumo curto do motivo"}},
            "required": ["motivo"],
        },
    ),
]


def consultar_pedido(ctx: ToolContext, codigo_pedido: str = "", **_ignored: Any) -> dict[str, Any]:
    # **_ignored descarta argumentos extras que o modelo invente (ex.: "tenant_id").
    codigo = (codigo_pedido or "").strip().upper()
    if not codigo:
        return {"encontrado": False, "erro": "código não informado"}
    order = ctx.orders.get(ctx.tenant_id, codigo)
    if order is None:
        # Mesma resposta se o pedido não existe OU se é de outro restaurante:
        # não revelamos nem a existência de dados de outro tenant.
        return {"encontrado": False, "codigo": codigo}
    return {
        "encontrado": True,
        "codigo": order["codigo"],
        "status": order["status"],
        "previsao": order.get("previsao"),
        "itens": order.get("itens"),
        "total": order.get("total"),
    }


def transferir_para_atendente(ctx: ToolContext, motivo: str = "", **_ignored: Any) -> dict[str, Any]:
    protocolo = f"ATD-{ctx.tenant_id[:3].upper()}-{next(ctx._protocols):04d}"
    return {"transferido": True, "protocolo": protocolo, "motivo": motivo[:200]}


_REGISTRY = {
    "consultar_pedido": consultar_pedido,
    "transferir_para_atendente": transferir_para_atendente,
}


def execute_tool(call: ToolCall, ctx: ToolContext) -> dict[str, Any]:
    fn = _REGISTRY.get(call.name)
    if fn is None:
        return {"erro": f"ferramenta desconhecida: {call.name}"}
    try:
        return fn(ctx, **(call.arguments or {}))
    except Exception as exc:  # erro de ferramenta vira dado para o modelo, não derruba a API
        return {"erro": f"falha ao executar {call.name}: {type(exc).__name__}"}

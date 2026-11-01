"""Isolamento entre restaurantes: o requisito que mais importa num sistema multi-tenant."""

import numpy as np
import pytest

from delivery_agent.schemas import Chunk, TenantRequiredError, ToolCall
from delivery_agent.store import InMemoryStore
from delivery_agent.tools import ToolContext, execute_tool

TENANTS = ["cantina-nonna", "sushi-kaze", "burguer-do-ze"]


@pytest.mark.parametrize("tenant", TENANTS)
def test_busca_so_retorna_chunks_do_proprio_tenant(agent, tenant):
    for pergunta in ["cupom de desconto", "horário", "taxa de entrega", "temaki", "lasanha", "smash"]:
        vec = agent.embedder.embed([pergunta])[0]
        hits = agent.store.search(tenant, vec, k=10)
        assert hits, "deveria recuperar algo"
        assert all(h.chunk.tenant_id == tenant for h in hits)


@pytest.mark.parametrize("tenant", ["", "   ", None])
def test_busca_sem_tenant_falha_fechado(tenant):
    store = InMemoryStore()
    with pytest.raises(TenantRequiredError):
        store.search(tenant, np.zeros(384), k=3)


def test_nao_aceita_chunk_de_outro_tenant_na_ingestao():
    store = InMemoryStore()
    with pytest.raises(ValueError):
        store.add("cantina-nonna", [Chunk("sushi-kaze", "x.md#y", "texto")], np.zeros((1, 384)))


def test_ferramenta_nao_encontra_pedido_de_outro_restaurante(agent):
    ctx = ToolContext(tenant_id="cantina-nonna", orders=agent.orders)
    out = execute_tool(ToolCall("1", "consultar_pedido", {"codigo_pedido": "SUS-2001"}), ctx)
    assert out == {"encontrado": False, "codigo": "SUS-2001"}


def test_tenant_injetado_pelo_llm_nos_argumentos_e_ignorado(agent):
    """Mesmo se o modelo for manipulado a mandar outro tenant_id, a ferramenta usa o da requisição."""
    ctx = ToolContext(tenant_id="cantina-nonna", orders=agent.orders)
    call = ToolCall("1", "consultar_pedido", {"codigo_pedido": "SUS-2001", "tenant_id": "sushi-kaze"})
    assert execute_tool(call, ctx)["encontrado"] is False


def test_resposta_de_pedido_alheio_nao_revela_dados(agent):
    r = agent.run("sushi-kaze", "status do pedido NON-1001")
    assert "saiu para entrega" not in r.answer.lower()
    assert "lasanha" not in r.answer.lower()

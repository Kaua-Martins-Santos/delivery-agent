"""Conversão do formato interno para o formato de cada provedor (sem chamar API)."""

from delivery_agent.llm.anthropic_llm import to_anthropic_messages
from delivery_agent.llm.openai_llm import to_openai_messages
from delivery_agent.schemas import ToolCall

CONVERSA = [
    {"role": "user", "content": "cadê o NON-1001?"},
    {"role": "assistant", "content": "", "tool_calls": [ToolCall("t1", "consultar_pedido", {"codigo_pedido": "NON-1001"})]},
    {"role": "tool", "tool_call_id": "t1", "name": "consultar_pedido", "content": '{"status": "em preparo"}'},
]


def test_formato_anthropic():
    msgs = to_anthropic_messages(CONVERSA)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"][0] == {
        "type": "tool_use", "id": "t1", "name": "consultar_pedido", "input": {"codigo_pedido": "NON-1001"},
    }
    assert msgs[2]["content"][0]["type"] == "tool_result" and msgs[2]["content"][0]["tool_use_id"] == "t1"


def test_formato_anthropic_agrupa_resultados_de_varias_ferramentas():
    conversa = CONVERSA + [{"role": "tool", "tool_call_id": "t2", "name": "x", "content": "{}"}]
    msgs = to_anthropic_messages(conversa)
    assert len(msgs) == 3 and len(msgs[2]["content"]) == 2


def test_formato_openai():
    msgs = to_openai_messages("sistema", CONVERSA)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    call = msgs[2]["tool_calls"][0]
    assert call["function"]["name"] == "consultar_pedido"
    assert '"NON-1001"' in call["function"]["arguments"]
    assert msgs[3]["tool_call_id"] == "t1"

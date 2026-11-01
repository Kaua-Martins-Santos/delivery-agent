from fastapi.testclient import TestClient

from delivery_agent.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_ok():
    r = client.post("/chat", json={"mensagem": "Qual a taxa de entrega?"}, headers={"X-Tenant-ID": "burguer-do-ze"})
    assert r.status_code == 200
    body = r.json()
    assert "5,90" in body["resposta"]
    assert body["fontes"]


def test_chat_sem_tenant_e_rejeitado():
    r = client.post("/chat", json={"mensagem": "oi"})
    assert r.status_code == 422


def test_chat_tenant_desconhecido_404():
    r = client.post("/chat", json={"mensagem": "oi"}, headers={"X-Tenant-ID": "restaurante-fantasma"})
    assert r.status_code == 404


def test_mensagem_vazia_rejeitada():
    r = client.post("/chat", json={"mensagem": ""}, headers={"X-Tenant-ID": "sushi-kaze"})
    assert r.status_code == 422

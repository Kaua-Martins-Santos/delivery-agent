"""Testes de integração do Row-Level Security no Postgres.

Rodam só com o banco no ar:
  docker compose up -d
  python -m delivery_agent.ingest   (com STORE=postgres e DATABASE_URL no .env)
  TEST_DATABASE_URL=postgresql://app_user:app_user_dev@localhost:5432/delivery pytest tests/test_pg_rls.py
"""

import os

import pytest

DB_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL não definido")


def _count(conn, table: str, tenant: str | None, where_tenant: str) -> int:
    with conn.transaction():
        if tenant is not None:
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        return conn.execute(f"SELECT count(*) FROM {table} WHERE tenant_id = %s", (where_tenant,)).fetchone()[0]


@pytest.fixture
def conn():
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DB_URL) as c:
        yield c


@pytest.mark.parametrize("table", ["documents", "orders"])
def test_rls_esconde_linhas_de_outro_tenant_mesmo_pedindo_explicitamente(conn, table):
    assert _count(conn, table, "cantina-nonna", "cantina-nonna") > 0
    assert _count(conn, table, "cantina-nonna", "sushi-kaze") == 0


@pytest.mark.parametrize("table", ["documents", "orders"])
def test_rls_sem_tenant_definido_nao_retorna_nada(conn, table):
    assert _count(conn, table, None, "cantina-nonna") == 0


def test_rls_impede_inserir_em_outro_tenant(conn):
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():
            conn.execute("SELECT set_config('app.tenant_id', 'cantina-nonna', true)")
            conn.execute(
                "INSERT INTO orders (codigo, tenant_id, status) VALUES ('HACK-0001', 'sushi-kaze', 'x')"
            )

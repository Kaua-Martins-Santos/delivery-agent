"""Repositório de pedidos — sempre consultado com o tenant da requisição."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .store import require_tenant


class OrderRepository(Protocol):
    def get(self, tenant_id: str, codigo: str) -> dict[str, Any] | None: ...


class InMemoryOrderRepository:
    def __init__(self, orders: list[dict[str, Any]]) -> None:
        self._orders = {(o["tenant_id"], o["codigo"].upper()): o for o in orders}

    @classmethod
    def from_file(cls, path: Path) -> "InMemoryOrderRepository":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def get(self, tenant_id: str, codigo: str) -> dict[str, Any] | None:
        require_tenant(tenant_id)
        return self._orders.get((tenant_id, codigo.strip().upper()))


class PgOrderRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def get(self, tenant_id: str, codigo: str) -> dict[str, Any] | None:
        import psycopg
        from psycopg.rows import dict_row

        require_tenant(tenant_id)
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn, conn.transaction():
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
            row = conn.execute(
                "SELECT codigo, tenant_id, status, previsao, itens, total FROM orders "
                "WHERE tenant_id = %s AND codigo = %s",
                (tenant_id, codigo.strip().upper()),
            ).fetchone()
        if row and row.get("total") is not None:
            row["total"] = float(row["total"])
        return row

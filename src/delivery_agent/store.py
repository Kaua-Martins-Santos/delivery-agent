"""Armazenamento vetorial com isolamento por tenant.

Regra de ouro: NÃO existe método de busca sem tenant_id. Se o tenant vier vazio,
a operação falha (fail closed) em vez de buscar em todos os restaurantes.

No Postgres o isolamento tem duas camadas (defesa em profundidade):
  1. WHERE tenant_id = %s na query
  2. Row-Level Security no banco (db/init.sql) — mesmo que alguém esqueça o WHERE,
     o banco só devolve linhas do tenant definido em app.tenant_id.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Protocol

import numpy as np

from .schemas import Chunk, RetrievedChunk, TenantRequiredError


def require_tenant(tenant_id: str | None) -> str:
    if not tenant_id or not tenant_id.strip():
        raise TenantRequiredError("tenant_id é obrigatório")
    return tenant_id


class VectorStore(Protocol):
    def add(self, tenant_id: str, chunks: list[Chunk], vectors: np.ndarray) -> None: ...

    def search(self, tenant_id: str, query: np.ndarray, k: int) -> list[RetrievedChunk]: ...


class InMemoryStore:
    """Usado em testes, evals e demo. Cada tenant tem sua própria 'partição'."""

    def __init__(self) -> None:
        self._chunks: dict[str, list[Chunk]] = defaultdict(list)
        self._vectors: dict[str, list[np.ndarray]] = defaultdict(list)

    def add(self, tenant_id: str, chunks: list[Chunk], vectors: np.ndarray) -> None:
        require_tenant(tenant_id)
        for chunk, vec in zip(chunks, vectors, strict=True):
            if chunk.tenant_id != tenant_id:
                raise ValueError("chunk de outro tenant")
            self._chunks[tenant_id].append(chunk)
            self._vectors[tenant_id].append(vec)

    def search(self, tenant_id: str, query: np.ndarray, k: int) -> list[RetrievedChunk]:
        require_tenant(tenant_id)
        if not self._vectors.get(tenant_id):
            return []
        matrix = np.stack(self._vectors[tenant_id])
        scores = matrix @ query  # vetores já normalizados -> cosseno
        top = np.argsort(-scores)[:k]
        return [RetrievedChunk(self._chunks[tenant_id][i], float(scores[i])) for i in top]


class PgVectorStore:
    """Postgres + pgvector com RLS. Requer: pip install -e '.[postgres]'."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    @staticmethod
    def _set_tenant(conn, tenant_id: str) -> None:
        # is_local=true: vale só para a transação atual (seguro com pool de conexões)
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))

    def add(self, tenant_id: str, chunks: list[Chunk], vectors: np.ndarray) -> None:
        require_tenant(tenant_id)
        with self._connect() as conn, conn.transaction():
            self._set_tenant(conn, tenant_id)
            for chunk, vec in zip(chunks, vectors, strict=True):
                conn.execute(
                    "INSERT INTO documents (tenant_id, source, content, embedding) VALUES (%s, %s, %s, %s)",
                    (tenant_id, chunk.source, chunk.text, np.asarray(vec, dtype=np.float32)),
                )

    def search(self, tenant_id: str, query: np.ndarray, k: int) -> list[RetrievedChunk]:
        require_tenant(tenant_id)
        q = np.asarray(query, dtype=np.float32)
        with self._connect() as conn, conn.transaction():
            self._set_tenant(conn, tenant_id)
            rows = conn.execute(
                """
                SELECT tenant_id, source, content, 1 - (embedding <=> %s) AS score
                FROM documents
                WHERE tenant_id = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (q, tenant_id, q, k),
            ).fetchall()
        return [RetrievedChunk(Chunk(r[0], r[1], r[2]), float(r[3])) for r in rows]

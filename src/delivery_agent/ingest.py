"""Ingestão: lê os .md de cada restaurante, quebra em chunks por seção e indexa.

Uso (Postgres):  python -m delivery_agent.ingest
Na memória a ingestão acontece automaticamente ao subir o agente.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import DATA_DIR, Settings
from .embeddings import Embedder, build_embedder
from .schemas import Chunk, Restaurant
from .store import VectorStore
from .text import normalize


def load_restaurants(data_dir: Path = DATA_DIR) -> dict[str, Restaurant]:
    raw = json.loads((data_dir / "restaurants.json").read_text(encoding="utf-8"))
    return {r["id"]: Restaurant(r["id"], r["nome"], tuple(r.get("canarios", []))) for r in raw}


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(title)).strip("-")


def chunk_markdown(tenant_id: str, filename: str, markdown: str) -> list[Chunk]:
    """Um chunk por seção '## '. Seções curtas de FAQ cabem inteiras, o que mantém o contexto coeso."""
    chunks: list[Chunk] = []
    for section in re.split(r"(?m)^## ", markdown):
        section = section.strip()
        if not section or section.startswith("# "):
            continue
        title, _, body = section.partition("\n")
        text = f"{title.strip()}\n{body.strip()}".strip()
        chunks.append(Chunk(tenant_id, f"{filename}#{_slug(title)}", text))
    return chunks


def load_chunks(tenant_id: str, data_dir: Path = DATA_DIR) -> list[Chunk]:
    folder = data_dir / "restaurants" / tenant_id
    chunks: list[Chunk] = []
    for path in sorted(folder.glob("*.md")):
        chunks.extend(chunk_markdown(tenant_id, path.name, path.read_text(encoding="utf-8")))
    return chunks


def index_all(store: VectorStore, embedder: Embedder, restaurants: dict[str, Restaurant], data_dir: Path = DATA_DIR) -> int:
    total = 0
    for tenant_id in restaurants:
        chunks = load_chunks(tenant_id, data_dir)
        if chunks:
            store.add(tenant_id, chunks, embedder.embed([c.text for c in chunks]))
            total += len(chunks)
    return total


def main() -> None:
    settings = Settings.from_env()
    if settings.store != "postgres" or not settings.database_url:
        raise SystemExit("Defina STORE=postgres e DATABASE_URL para ingerir no banco.")

    import psycopg

    from .store import PgVectorStore

    restaurants = load_restaurants()
    orders = json.loads((DATA_DIR / "orders.json").read_text(encoding="utf-8"))
    with psycopg.connect(settings.database_url) as conn:
        for r in restaurants.values():
            conn.execute(
                "INSERT INTO restaurants (id, nome) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome",
                (r.id, r.nome),
            )
        for o in orders:
            with conn.transaction():
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (o["tenant_id"],))
                conn.execute(
                    "INSERT INTO orders (codigo, tenant_id, status, previsao, itens, total) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (codigo) DO NOTHING",
                    (o["codigo"], o["tenant_id"], o["status"], o.get("previsao"), json.dumps(o.get("itens", [])), o.get("total")),
                )
        for tenant_id in restaurants:
            with conn.transaction():
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
                conn.execute("DELETE FROM documents WHERE tenant_id = %s", (tenant_id,))

    total = index_all(PgVectorStore(settings.database_url), build_embedder(settings.embedder), restaurants)
    print(f"{total} chunks e {len(orders)} pedidos indexados para {len(restaurants)} restaurantes.")


if __name__ == "__main__":
    main()

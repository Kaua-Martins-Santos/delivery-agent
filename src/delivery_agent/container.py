"""Monta o agente a partir das configurações (injeção de dependências simples)."""

from __future__ import annotations

from .agent import Agent
from .config import DATA_DIR, Settings
from .embeddings import build_embedder
from .ingest import index_all, load_restaurants
from .llm import build_llm
from .orders import InMemoryOrderRepository, PgOrderRepository
from .store import InMemoryStore, PgVectorStore


def build_agent(settings: Settings | None = None) -> Agent:
    settings = settings or Settings.from_env()
    restaurants = load_restaurants()
    embedder = build_embedder(settings.embedder)

    if settings.store == "postgres":
        if not settings.database_url:
            raise ValueError("STORE=postgres exige DATABASE_URL")
        store = PgVectorStore(settings.database_url)
        orders = PgOrderRepository(settings.database_url)
    else:
        store = InMemoryStore()
        index_all(store, embedder, restaurants)
        orders = InMemoryOrderRepository.from_file(DATA_DIR / "orders.json")

    return Agent(build_llm(settings), embedder, store, orders, restaurants, settings)

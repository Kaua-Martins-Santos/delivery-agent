"""Configuração via variáveis de ambiente (veja .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Leitor mínimo de .env para não precisar de dependência extra."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    llm_provider: str          # fake | anthropic | openai
    llm_model: str
    openai_base_url: str | None
    embedder: str              # hash | local
    store: str                 # memory | postgres
    database_url: str | None
    top_k: int
    min_score: float
    max_steps: int
    price_input_per_mtok: float   # US$ por milhão de tokens de entrada
    price_output_per_mtok: float  # US$ por milhão de tokens de saída

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        provider = os.getenv("LLM_PROVIDER", "fake").lower()
        default_model = {"anthropic": "claude-haiku-5-5", "fake": "fake-extrativo"}.get(provider, "")
        return cls(
            llm_provider=provider,
            llm_model=os.getenv("LLM_MODEL", default_model),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            embedder=os.getenv("EMBEDDER", "hash").lower(),
            store=os.getenv("STORE", "memory").lower(),
            database_url=os.getenv("DATABASE_URL") or None,
            top_k=int(os.getenv("TOP_K", "4")),
            min_score=float(os.getenv("MIN_SCORE", "0.12")),
            max_steps=int(os.getenv("MAX_STEPS", "3")),
            price_input_per_mtok=float(os.getenv("PRICE_INPUT_PER_MTOK", "0")),
            price_output_per_mtok=float(os.getenv("PRICE_OUTPUT_PER_MTOK", "0")),
        )

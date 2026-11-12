"""Embeddings.

- HashEmbedder: determinístico e sem download (palavras + n-gramas de caracteres com hashing).
  É o baseline usado nos testes e no CI.
- LocalEmbedder: sentence-transformers multilíngue (semântico, roda local e de graça).
- E5Embedder: família multilingual-e5 (padrão: small), que exige prefixos "query: " / "passage: ".

Por padrão todos geram vetores de 384 dimensões, que cabem na coluna do pgvector. O E5_MODEL
pode apontar para modelos maiores (ex.: multilingual-e5-base, 768 dim) só para comparação:
esses vetores funcionam no InMemoryStore, mas NÃO cabem na coluna vector(384) do Postgres.

Perguntas e documentos têm métodos separados (embed_query / embed_documents) porque
alguns modelos (E5) tratam os dois lados de forma assimétrica.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol

import numpy as np

from .text import tokenize

DIM = 384
E5_DEFAULT_MODEL = "intfloat/multilingual-e5-small"


def _device() -> str:
    """GPU se houver (Kaggle, Colab), senão CPU."""
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class Embedder(Protocol):
    dim: int
    name: str

    def embed_query(self, texts: list[str]) -> np.ndarray: ...

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...


class _SymmetricMixin:
    """Modelos simétricos: pergunta e documento são codificados do mesmo jeito."""

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return self.embed(texts)  # type: ignore[attr-defined]

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self.embed(texts)  # type: ignore[attr-defined]


class HashEmbedder(_SymmetricMixin):
    name = "hash-ngram"

    def __init__(self, dim: int = DIM, ngram: int = 4, ngram_weight: float = 0.5):
        self.dim = dim
        self.ngram = ngram
        self.ngram_weight = ngram_weight

    def _index(self, feature: str) -> tuple[int, float]:
        h = int.from_bytes(hashlib.md5(feature.encode()).digest()[:8], "little")
        return h % self.dim, (1.0 if (h >> 63) & 1 else -1.0)

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for word in tokenize(text):
            idx, sign = self._index("w:" + word)
            vec[idx] += sign
            padded = f"^{word}$"
            for i in range(max(1, len(padded) - self.ngram + 1)):
                idx, sign = self._index("c:" + padded[i : i + self.ngram])
                vec[idx] += sign * self.ngram_weight
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vector(t) for t in texts]) if texts else np.zeros((0, self.dim))


class LocalEmbedder(_SymmetricMixin):
    name = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # import tardio: dependência opcional

        self._model = SentenceTransformer(f"sentence-transformers/{self.name}", device=_device())
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


class E5Embedder:
    """multilingual-e5: pede prefixo "query: " / "passage: ".

    O modelo vem de E5_MODEL (padrão: small, 384 dim). O base tem 768 dim.
    """

    def __init__(self, model: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer  # import tardio: dependência opcional

        model_id = model or os.getenv("E5_MODEL") or E5_DEFAULT_MODEL
        if "/" not in model_id:
            model_id = f"intfloat/{model_id}"
        self.name = model_id.split("/")[-1]
        self._model = SentenceTransformer(model_id, device=_device())
        self.dim = self._model.get_sentence_embedding_dimension()

    def _encode(self, prefix: str, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self._model.encode([prefix + t for t in texts], normalize_embeddings=True), dtype=np.float32
        )

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return self._encode("query: ", texts)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode("passage: ", texts)


def build_embedder(kind: str) -> Embedder:
    if kind == "hash":
        return HashEmbedder()
    if kind == "local":
        return LocalEmbedder()
    if kind == "e5":
        return E5Embedder()
    raise ValueError(f"EMBEDDER desconhecido: {kind}")

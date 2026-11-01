"""Normalização de texto em português (sem dependências)."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "e", "em", "no", "na",
    "nos", "nas", "ao", "aos", "para", "pra", "por", "com", "que", "se", "eu", "me", "meu",
    "minha", "voce", "voces", "vc", "vcs", "qual", "quais", "como", "quando", "onde", "ate",
    "tem", "ter", "sao", "ser", "esta", "estao", "isso", "esse", "essa", "ou", "oi", "ola",
    "pode", "posso", "queria", "quero", "gostaria", "saber", "favor", "ai", "la", "aqui",
    "the", "is", "it",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    return strip_accents(text.lower())


def stem(word: str) -> str:
    """Stemmer bem leve: só remove plural simples."""
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", normalize(text))
    return [stem(w) for w in words if len(w) >= 2 and w not in STOPWORDS]

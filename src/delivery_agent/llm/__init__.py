from __future__ import annotations

from ..config import Settings
from .base import LLM
from .fake import FakeLLM


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "fake":
        return FakeLLM(settings.llm_model or "fake-extrativo")
    if settings.llm_provider == "anthropic":
        from .anthropic_llm import AnthropicLLM

        return AnthropicLLM(settings.llm_model)
    if settings.llm_provider == "openai":
        from .openai_llm import OpenAICompatibleLLM

        return OpenAICompatibleLLM(settings.llm_model, settings.openai_base_url)
    raise ValueError(f"LLM_PROVIDER desconhecido: {settings.llm_provider}")


__all__ = ["LLM", "FakeLLM", "build_llm"]

"""LLM router — picks the right brain for the right task.

Uses weights from config/llm_providers.yaml.  The agent orchestrator
calls `router.for_role("planning")` to obtain the best available
provider.  Falls back gracefully if a provider is unreachable.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from ..settings import get_settings
from ..utils.logger import get_logger
from .base import BaseLLMProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

log = get_logger("llm.router")

Role = Literal["planning", "execution", "parsing", "reporting"]

PROVIDER_CLASSES: dict[str, type[BaseLLMProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


class LLMRouter:
    def __init__(self):
        self.settings = get_settings()
        self._catalog = self.settings.load_yaml("llm_providers.yaml")
        self._routing = self._catalog.get("routing", {})
        self._providers: dict[str, BaseLLMProvider] = {}

    # ── public API ───────────────────────────────────
    def available_providers(self) -> list[str]:
        providers = self._catalog.get("providers", {})
        names: list[str] = []
        for key, cfg in providers.items():
            if not cfg.get("enabled", True):
                continue
            if self._is_configured(key):
                names.append(key)
        return names

    def get(self, name: str, model: str | None = None) -> BaseLLMProvider:
        cache_key = f"{name}:{model or 'default'}"
        if cache_key not in self._providers:
            cls = PROVIDER_CLASSES.get(name)
            if not cls:
                raise ValueError(f"Unknown LLM provider: {name}")
            self._providers[cache_key] = cls(model=model) if model else cls()
        return self._providers[cache_key]

    def for_role(self, role: Role) -> BaseLLMProvider:
        """Pick the best available provider for the given role."""
        preferences = self._routing.get(role, {}).get("prefer", [self.settings.default_llm_provider])
        for name in preferences:
            if self._is_configured(name):
                try:
                    return self.get(name)
                except Exception as e:
                    log.warning("router: provider %s unavailable: %s", name, e)
        # last-resort default
        return self.get(self.settings.default_llm_provider)

    def catalog(self) -> dict:
        return self._catalog

    # ── helpers ──────────────────────────────────────
    def _is_configured(self, name: str) -> bool:
        s = self.settings
        if name == "claude":
            return bool(s.anthropic_api_key)
        if name == "openai":
            return bool(s.openai_api_key)
        if name == "gemini":
            return bool(s.google_api_key)
        if name == "ollama":
            return bool(s.ollama_host)
        return False


@lru_cache
def get_router() -> LLMRouter:
    return LLMRouter()

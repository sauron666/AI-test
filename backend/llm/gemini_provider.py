"""Google Gemini provider."""
from __future__ import annotations

from typing import Any, AsyncIterator

from ..settings import get_settings
from ..utils.logger import get_logger
from .base import BaseLLMProvider, LLMMessage, LLMResponse

log = get_logger("llm.gemini")


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, model: str | None = None):
        settings = get_settings()
        super().__init__(model or settings.google_model)
        self._api_key = settings.google_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError as e:
                raise RuntimeError("google-generativeai is not installed") from e
            if not self._api_key:
                raise RuntimeError("GOOGLE_API_KEY is not configured")
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def _to_gemini_history(self, messages: list[LLMMessage]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        history: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            elif m.role == "assistant":
                history.append({"role": "model", "parts": [m.content]})
            elif m.role == "user":
                history.append({"role": "user", "parts": [m.content]})
            elif m.role == "tool":
                history.append({"role": "user", "parts": [f"[tool_result] {m.content}"]})
        return "\n\n".join(system_parts), history

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._get_client()
        system, history = self._to_gemini_history(messages)
        # Gemini SDK is sync — run in executor for simplicity.
        import asyncio

        loop = asyncio.get_running_loop()

        def _call() -> Any:
            chat = client.start_chat(history=history[:-1] if history else [])
            last = history[-1]["parts"][0] if history else ""
            return chat.send_message(
                (system + "\n\n" if system else "") + last,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
            )

        resp = await loop.run_in_executor(None, _call)
        text = getattr(resp, "text", "") or ""
        return LLMResponse(content=text, model=self.model, raw=resp)

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        r = await self.complete(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)
        yield r.content

"""Ollama local provider — perfect for WhiteRabbitNeo in air-gapped mode."""
from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from ..settings import get_settings
from ..utils.logger import get_logger
from .base import BaseLLMProvider, LLMMessage, LLMResponse

log = get_logger("llm.ollama")


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None):
        settings = get_settings()
        super().__init__(model or settings.ollama_model)
        self._host = (host or settings.ollama_host).rstrip("/")

    def _to_ollama_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            role = m.role
            if role == "tool":
                role = "user"
                content = f"[tool_result id={m.tool_call_id or ''}] {m.content}"
            else:
                content = m.content
            out.append({"role": role, "content": content})
        return out

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_ollama_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(f"{self._host}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()

        msg = data.get("message", {})
        content = msg.get("content", "")
        tool_calls = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": fn.get("arguments", {}),
            })
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason", "stop"),
            model=self.model,
            raw=data,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": self._to_ollama_messages(messages),
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self._host}/api/chat", json=payload) as r:
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        import json
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    piece = (data.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break

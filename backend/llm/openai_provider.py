"""OpenAI GPT provider."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..settings import get_settings
from ..utils.logger import get_logger
from .base import BaseLLMProvider, LLMMessage, LLMResponse

log = get_logger("llm.openai")


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None):
        settings = get_settings()
        super().__init__(model or settings.openai_model)
        self._api_key = settings.openai_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise RuntimeError("openai SDK is not installed") from e
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    def _to_openai_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "tool":
                out.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content,
                })
            else:
                msg: dict[str, Any] = {"role": m.role, "content": m.content}
                if m.tool_calls:
                    msg["tool_calls"] = m.tool_calls
                out.append(msg)
        return out

    def _wrap_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [{"type": "function", "function": t} for t in tools]

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=self.model,
            messages=self._to_openai_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=self._wrap_tools(tools),
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            model=self.model,
            usage={
                "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
            raw=resp,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        stream = await client.chat.completions.create(
            model=self.model,
            messages=self._to_openai_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=self._wrap_tools(tools),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

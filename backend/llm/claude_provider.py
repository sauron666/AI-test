"""Anthropic Claude provider."""
from __future__ import annotations

from typing import Any, AsyncIterator

from ..settings import get_settings
from ..utils.logger import get_logger
from .base import BaseLLMProvider, LLMMessage, LLMResponse

log = get_logger("llm.claude")


class ClaudeProvider(BaseLLMProvider):
    name = "claude"

    def __init__(self, model: str | None = None):
        settings = get_settings()
        super().__init__(model or settings.anthropic_model)
        self._api_key = settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise RuntimeError("anthropic SDK is not installed") from e
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured")
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def _split_messages(self, messages: list[LLMMessage]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        msgs: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            elif m.role == "tool":
                msgs.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id or "",
                        "content": m.content,
                    }],
                })
            else:
                msgs.append({"role": m.role, "content": m.content})
        return "\n\n".join(system_parts), msgs

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._get_client()
        system, msgs = self._split_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        resp = await client.messages.create(**kwargs)
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in resp.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return LLMResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=resp.stop_reason or "stop",
            model=self.model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
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
        system, msgs = self._split_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

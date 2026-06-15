"""
AnthropicProvider — async Anthropic (Claude) inference, routed through Aegis
when an aegis instance is supplied (Phase 6).

When aegis is provided, every request flows through AegisTransport,
which gates via aegis.network() with capability network.outbound.api.anthropic.com.
Separates system message from user messages per Anthropic's API contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore

from nexus.inference.provider import InferenceProvider

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class AnthropicProvider(InferenceProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514",
                 aegis: "Aegis | None" = None):
        self._api_key = api_key
        self._model = model
        self._aegis = aegis
        if AsyncAnthropic is None:
            self._client = None
            return
        if aegis is not None:
            from nexus.inference.kernel_http_client import AegisTransport
            sdk_client = httpx.AsyncClient(transport=AegisTransport(aegis=aegis))
            self._client = AsyncAnthropic(api_key=api_key, http_client=sdk_client)
        else:
            self._client = AsyncAnthropic(api_key=api_key)

    async def infer(self, messages: list[dict], max_tokens: int = 1024,
                    temperature: float = 0.7) -> str:
        if self._client is None:
            return "[Anthropic SDK not installed]"
        try:
            system_msg = None
            non_system = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    non_system.append(msg)

            kwargs: dict = {
                "model": self._model,
                "messages": non_system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = await self._client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Inference error: {e}]"

    async def infer_stream(self, messages: list[dict], max_tokens: int = 1024,
                           temperature: float = 0.7):
        """Stream text deltas via the Anthropic SDK's messages.stream()."""
        if self._client is None:
            yield "[Anthropic SDK not installed]"
            return
        try:
            system_msg = None
            non_system = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    non_system.append(msg)

            kwargs: dict = {
                "model": self._model,
                "messages": non_system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_msg:
                kwargs["system"] = system_msg

            async with self._client.messages.stream(**kwargs) as stream:
                async for token in stream.text_stream:
                    if token:
                        yield token
        except Exception as e:
            yield f"[Inference error: {e}]"

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.messages.count_tokens(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            try:
                # Fallback: minimal completion if count_tokens unavailable
                await self._client.messages.create(
                    model=self._model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                return True
            except Exception:
                return False

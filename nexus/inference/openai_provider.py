"""
OpenAIProvider — async OpenAI inference, routed through Aegis when an
aegis instance is supplied (Phase 6).

When aegis is provided, every request flows through AegisTransport,
which gates via aegis.network() with capability network.outbound.api.openai.com.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore

from nexus.inference.provider import InferenceProvider

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class OpenAIProvider(InferenceProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 aegis: "Aegis | None" = None):
        self._api_key = api_key
        self._model = model
        self._aegis = aegis
        if AsyncOpenAI is None:
            self._client = None
            return
        if aegis is not None:
            from nexus.inference.kernel_http_client import AegisTransport
            sdk_client = httpx.AsyncClient(transport=AegisTransport(aegis=aegis))
            self._client = AsyncOpenAI(api_key=api_key, http_client=sdk_client)
        else:
            self._client = AsyncOpenAI(api_key=api_key)

    async def infer(self, messages: list[dict], max_tokens: int = 1024,
                    temperature: float = 0.7) -> str:
        if self._client is None:
            return "[OpenAI SDK not installed]"
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
            }
            # Newer OpenAI models (o1, o3, gpt-4.1) require max_completion_tokens
            # instead of max_tokens. Try the new param first, fall back to legacy.
            try:
                kwargs["max_completion_tokens"] = max_tokens
                response = await self._client.chat.completions.create(**kwargs)
            except Exception:
                del kwargs["max_completion_tokens"]
                kwargs["max_tokens"] = max_tokens
                response = await self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

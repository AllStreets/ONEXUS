"""
LocalProvider — inference via a local llama.cpp-compatible HTTP server.

Phase 6: routes through KernelHttpClient when one is provided, so every
outbound HTTP byte goes through aegis.network() with the current agent's
declared network capability. Falls back to a direct httpx call when no
client is attached (kernel-internal use, tests).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nexus.inference.provider import InferenceProvider

if TYPE_CHECKING:
    from nexus.inference.kernel_http_client import KernelHttpClient


class LocalProvider(InferenceProvider):
    name = "local"

    def __init__(
        self,
        base_url: str = "http://localhost:8384",
        http_client: "KernelHttpClient | None" = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    def _messages_to_chatml(self, messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_response(raw: str) -> str:
        cleaned = re.sub(r"<\|[^>]+\|>", "", raw)
        return cleaned.strip()

    async def infer(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        prompt = self._messages_to_chatml(messages)
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": ["<|im_end|>", "<|end|>"],
        }
        if self._http is not None:
            resp = await self._http.post(f"{self._base_url}/completion", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data.get("content", ""))
        # Fallback: direct httpx (kernel-internal use, tests without aegis context)
        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base_url}/completion", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data.get("content", ""))

    async def health(self) -> bool:
        try:
            if self._http is not None:
                resp = await self._http.get(f"{self._base_url}/health")
                return resp.status_code == 200
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

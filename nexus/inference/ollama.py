"""
OllamaProvider — inference via a local Ollama server.

Ollama exposes a REST API on http://localhost:11434 by default and pulls
models on demand. The kernel auto-detects Ollama at boot: if the daemon
is reachable and at least one model is installed, the Cortex routes its
LLM-classification + module fallback through Ollama. Otherwise the
provider silently degrades to "unavailable" and routing falls back to
the pattern-matched classifier.

Why Ollama specifically: it's the easiest local LLM runtime to install
on a Mac (`brew install ollama`), it caches models locally so the
kernel.network = ∅ guarantee still holds (no outbound traffic after the
initial pull), and it accepts an OpenAI-style chat-messages payload at
its `/api/chat` endpoint — same shape every other InferenceProvider in
the kernel uses.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from nexus.inference.provider import InferenceProvider

if TYPE_CHECKING:
    from nexus.inference.kernel_http_client import KernelHttpClient


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"


class OllamaProvider(InferenceProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        http_client: "KernelHttpClient | None" = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http = http_client

    @property
    def model(self) -> str:
        """The currently active local model name."""
        return self._model

    def set_model(self, name: str) -> str:
        """Switch the active local model at runtime. The previously active model
        stays installed in Ollama and can be switched back to — only the active
        selection changes. Returns the previous model name."""
        previous = self._model
        self._model = name
        return previous

    async def infer(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Send OpenAI-style messages to Ollama's /api/chat and return the
        assistant's reply text. Ollama returns a JSON object per request
        when ``stream=False`` with the full response in ``message.content``.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if self._http is not None:
            resp = await self._http.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message") or {}).get("content", "").strip()
        # Fallback: direct httpx (kernel-internal use, tests).
        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message") or {}).get("content", "").strip()

    async def infer_stream(self, messages: list[dict], max_tokens: int = 1024,
                           temperature: float = 0.7):
        """Stream tokens from Ollama's /api/chat (stream=True → NDJSON lines).

        When an Aegis-gated KernelHttpClient is attached we fall back to the
        non-streaming base implementation so every outbound byte keeps going
        through aegis.network(); the direct path streams for real.
        """
        if self._http is not None:
            async for chunk in super().infer_stream(messages, max_tokens=max_tokens, temperature=temperature):
                yield chunk
            return
        import json as _json
        import httpx
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = _json.loads(line)
                    except Exception:
                        continue
                    token = (data.get("message") or {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        return

    async def health(self) -> bool:
        """Return True if Ollama is running AND has at least one model pulled
        that we can call. The endpoint /api/tags lists installed models;
        we don't insist on the specific default model so the kernel works
        with whatever the user has."""
        try:
            if self._http is not None:
                resp = await self._http.get(f"{self._base_url}/api/tags")
            else:
                import httpx
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{self._base_url}/api/tags")
            if resp.status_code != 200:
                return False
            data = resp.json()
            models = data.get("models") or []
            return len(models) > 0
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return the names of all installed Ollama models, or empty list."""
        try:
            if self._http is not None:
                resp = await self._http.get(f"{self._base_url}/api/tags")
            else:
                import httpx
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{self._base_url}/api/tags")
            if resp.status_code != 200:
                return []
            return [m["name"] for m in (resp.json().get("models") or [])]
        except Exception:
            return []

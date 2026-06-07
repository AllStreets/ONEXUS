"""
KernelHttpClient — a drop-in httpx.AsyncClient that routes through
`Aegis.network()` when an agent context is active.

When `aegis` is None or no agent is currently in context, falls back
to a real httpx.AsyncClient (preserves test paths and direct kernel
code that legitimately doesn't go through Aegis).

AegisTransport is an httpx.AsyncBaseTransport for injection into
OpenAI/Anthropic SDKs so their underlying httpx clients are also
gated through Aegis.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

import httpx

from nexus.context import current_agent_slug

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class KernelHttpClient:
    """A drop-in subset of httpx.AsyncClient that gates through Aegis."""

    def __init__(self, *, aegis: "Aegis | None" = None,
                 timeout: float | httpx.Timeout = 30.0):
        self._aegis = aegis
        self._fallback = httpx.AsyncClient(timeout=timeout)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        agent_slug = current_agent_slug()
        if self._aegis is None or agent_slug is None:
            return await self._fallback.request(method, url, **kwargs)
        # Route through aegis.network() (raises PermissionDenied if disallowed)
        return await self._aegis.network(agent_slug, url, method=method, **kwargs)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs):
        # streaming bypasses aegis for now (Phase 7 polish)
        return self._fallback.stream(method, url, **kwargs)

    async def aclose(self) -> None:
        await self._fallback.aclose()

    # Make it usable as an `httpx.AsyncClient` argument for SDKs
    # by exposing the same async-context-manager interface.
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()


class AegisTransport(httpx.AsyncBaseTransport):
    """
    An httpx.AsyncBaseTransport that gates requests through Aegis.

    Inject into OpenAI/Anthropic SDKs as:
        OpenAI(http_client=httpx.AsyncClient(transport=AegisTransport(aegis=aegis)))
        Anthropic(http_client=httpx.AsyncClient(transport=AegisTransport(aegis=aegis)))

    When no agent is in context OR aegis is None, falls back to the
    standard httpx transport (httpx.AsyncHTTPTransport).
    """

    def __init__(self, *, aegis: "Aegis | None" = None,
                 timeout: float | httpx.Timeout = 30.0):
        self._aegis = aegis
        self._fallback = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        agent_slug = current_agent_slug()
        url = str(request.url)

        if self._aegis is None or agent_slug is None:
            return await self._fallback.handle_async_request(request)

        # Route through aegis.network() for capability check + rate limit
        return await self._aegis.network(
            agent_slug,
            url,
            method=request.method,
            headers=dict(request.headers),
            content=request.content,
        )

    async def aclose(self) -> None:
        await self._fallback.aclose()

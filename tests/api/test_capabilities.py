"""Truthful capability grounding — builder unit tests + route-level wiring."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from nexus.api.capabilities import (
    GROUNDING_MARKER,
    build_capability_context,
    ground_persona,
)


# ── fakes ─────────────────────────────────────────────────────────────────────

class FakeProviderRouter:
    def __init__(self, names):
        self._names = names

    def list_providers(self):
        return list(self._names)


class FakeCatalog:
    def __init__(self, n):
        self._n = n

    def count(self):
        return self._n


class FakeCodebaseRegistry:
    def __init__(self, n):
        self._n = n

    def list(self, workspace_id=None):
        return [object()] * self._n


def _app_state(providers=None, catalog_count=None, codebase_roots=0):
    kernel = SimpleNamespace(
        provider_router=FakeProviderRouter(providers) if providers is not None else None,
    )
    return SimpleNamespace(
        kernel=kernel,
        agent_catalog=FakeCatalog(catalog_count) if catalog_count is not None else None,
        codebase_registry=FakeCodebaseRegistry(codebase_roots),
    )


# ── builder unit tests ────────────────────────────────────────────────────────

def test_grounding_lists_configured_providers():
    out = build_capability_context(_app_state(providers=["ollama", "anthropic"]))
    assert GROUNDING_MARKER in out
    assert "LLM providers configured: anthropic, ollama." in out
    assert "No LLM providers" not in out


def test_grounding_truthful_when_nothing_configured():
    out = build_capability_context(_app_state())
    assert "No LLM providers are configured" in out
    assert "No agent catalog is attached" in out


def test_grounding_reports_catalog_count():
    out = build_capability_context(_app_state(catalog_count=590))
    assert "590 agents installed" in out
    assert "No agent catalog" not in out


def test_grounding_lists_in_os_tools_and_codebase_roots():
    out = build_capability_context(_app_state(codebase_roots=3))
    assert "Workshop code execution" in out
    assert "web search" in out
    assert "file uploads" in out
    assert "codebase" in out and "(3 registered)" in out


def test_grounding_always_denies_unlisted_integrations():
    for state in (_app_state(), _app_state(providers=["openai"], catalog_count=10)):
        out = build_capability_context(state)
        assert "no GitHub integration" in out
        assert "no OAuth" in out
        assert "does not exist yet" in out


def test_grounding_survives_broken_app_state():
    # Missing kernel / catalog / registry attributes must not raise.
    out = build_capability_context(SimpleNamespace())
    assert GROUNDING_MARKER in out
    assert "no GitHub integration" in out


def test_ground_persona_appends_exactly_once():
    state = _app_state(providers=["ollama"])
    persona = "You are Oracle, an agent in the ONEXUS operating system."
    grounded = ground_persona(persona, state)
    assert grounded.startswith(persona)
    assert grounded.count(GROUNDING_MARKER) == 1
    # Idempotent: grounding an already-grounded persona is a no-op.
    assert ground_persona(grounded, state) == grounded
    assert ground_persona(grounded, state).count(GROUNDING_MARKER) == 1


# ── route-level wiring: the grounding reaches the provider prompt ────────────

class CapturingRouter:
    """Stub provider router that records every prompt it is sent."""

    def __init__(self, response="stubbed reply"):
        self.calls: list[list[dict]] = []
        self._response = response

    def list_providers(self):
        return ["stub"]

    async def infer(self, messages, max_tokens=1024, temperature=0.7, provider=None):
        self.calls.append(messages)
        return self._response

    async def infer_stream(self, messages, max_tokens=1024, temperature=0.7, provider=None):
        self.calls.append(messages)
        yield self._response


@pytest.mark.asyncio
async def test_stream_endpoint_prompt_is_grounded(client, kernel):
    """POST /api/messages/stream — the persona system prompt the provider
    receives carries the capability grounding, computed from live state."""
    kernel.provider_router = CapturingRouter()
    await client.post("/api/messages/stream", json={"message": "hello"})

    assert kernel.provider_router.calls, "provider never received a prompt"
    system = kernel.provider_router.calls[0][0]
    assert system["role"] == "system"
    assert GROUNDING_MARKER in system["content"]
    assert "LLM providers configured: stub." in system["content"]
    assert "no GitHub integration" in system["content"]
    assert system["content"].count(GROUNDING_MARKER) == 1


@pytest.mark.asyncio
async def test_cortex_continue_prompt_is_grounded(kernel):
    """POST /api/cortex/continue — built-in personas resolved for the
    launcher conversation path carry the grounding too."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from nexus.api.routes.cortex import router as cortex_router

    kernel.provider_router = CapturingRouter()
    app = FastAPI()
    app.state.kernel = kernel
    app.include_router(cortex_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/cortex/continue", json={
            "module": "council", "history": [], "message": "what can you do?",
        })
    assert r.status_code == 200

    system = kernel.provider_router.calls[0][0]
    assert system["role"] == "system"
    assert "You are Council" in system["content"]
    assert GROUNDING_MARKER in system["content"]
    assert "no GitHub integration" in system["content"]
    assert system["content"].count(GROUNDING_MARKER) == 1

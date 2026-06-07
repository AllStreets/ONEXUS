# NEXUS Phase 6 — Network Gateway Rewire Implementation Plan (Phase 6 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Honour the local-first promise literally. **Every** outbound byte from inside NEXUS — LLM inference calls (OpenAI / Anthropic / local llama.cpp), federation peer requests, anything else — flows through `aegis.network()`, which already gates on the agent's declared `network.outbound.<domain>` capability, rate-limits, and logs to Chronicle. After Phase 6, the kernel modules themselves remain untouchable-by-network; the runtime layer is the only thing that can reach outside.

**Architecture:**
- A `nexus.context.current_agent` `contextvars.ContextVar` holds the slug of the agent currently executing a tool call. `InProcessAgent.call_tool` and `MCPAgent.call_tool` set it before dispatch; restore it on exit.
- `nexus.inference.kernel_http_client.KernelHttpClient` is a drop-in `httpx.AsyncClient` whose `.request()` delegates to `aegis.network()` when both an Aegis instance and a current agent context are available. When neither is set (test paths, direct kernel use), it falls back to a real `httpx.AsyncClient` so existing tests pass.
- `OpenAIProvider` and `AnthropicProvider` accept an optional `http_client` and forward it into the SDK (`OpenAI(http_client=...)`, `Anthropic(http_client=...)`).
- `LocalProvider` rewrites its `urllib.request` calls to use the same KernelHttpClient.
- `nexus.federation.*` HTTP calls (discovery, protocol) route through Aegis with capability `network.federation.<peer-id>`.
- `LLMClient` / `ProviderRouter` accept an optional `aegis` reference and create a KernelHttpClient if attached.

**Tech Stack:** Python 3.11+, httpx (already core dep), contextvars (stdlib), pydantic. No new deps.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` §4.5 (Aegis network gateway), §15 (Federation & local-first boundary).

**Prior phase:** `phase-5-aurora-surfaces` tag.

---

## Pre-flight

- Branch from `phase-5-aurora-surfaces` into `nexus-phase-6` (worktree `.worktrees/nexus-phase-6`).
- Baseline = **936 passing**.
- `source .venv/bin/activate` for every Bash invocation.

---

## Task 1 · `current_agent` contextvar + helpers

**Why:** `aegis.network()` is keyed by `agent_slug`. The provider/federation code paths don't know the slug directly — but the agent runtime does. A contextvar threads that information through async call stacks without changing every call signature.

**Files:**
- Create: `nexus/context.py`
- Create: `tests/test_context.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the current_agent contextvar helpers."""
from __future__ import annotations

import asyncio
import pytest

from nexus.context import current_agent_slug, set_current_agent


def test_default_is_none():
    assert current_agent_slug() is None


def test_set_and_get():
    token = set_current_agent("aider")
    try:
        assert current_agent_slug() == "aider"
    finally:
        # Restore the previous value (None)
        from nexus.context import reset_current_agent
        reset_current_agent(token)
    assert current_agent_slug() is None


@pytest.mark.asyncio
async def test_isolated_across_tasks():
    """Each asyncio task sees its own current_agent value (contextvars semantics)."""
    from nexus.context import reset_current_agent

    seen: dict[str, str | None] = {}

    async def actor(name: str):
        token = set_current_agent(name)
        try:
            await asyncio.sleep(0.01)
            seen[name] = current_agent_slug()
        finally:
            reset_current_agent(token)

    await asyncio.gather(actor("a"), actor("b"), actor("c"))
    assert seen == {"a": "a", "b": "b", "c": "c"}


@pytest.mark.asyncio
async def test_contextmanager_helper():
    """`as_agent(slug)` async context manager: sets and restores cleanly."""
    from nexus.context import as_agent

    assert current_agent_slug() is None
    async with as_agent("council"):
        assert current_agent_slug() == "council"
    assert current_agent_slug() is None
```

- [ ] **Step 2: Run; verify failure** — `tests/test_context.py` will fail (ImportError).

- [ ] **Step 3: Implement `nexus/context.py`**

```python
"""
Per-task context for the currently-executing agent.

Set by InProcessAgent.call_tool / MCPAgent.call_tool before dispatch.
Read by KernelHttpClient + aegis.network() to determine which agent's
network policy applies.
"""
from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from typing import Optional

_current_agent: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "nexus_current_agent", default=None,
)


def current_agent_slug() -> Optional[str]:
    """Return the slug of the agent currently dispatching a tool call, or None."""
    return _current_agent.get()


def set_current_agent(slug: Optional[str]) -> contextvars.Token:
    """Set the current agent. Returns a token; pass it to reset_current_agent()."""
    return _current_agent.set(slug)


def reset_current_agent(token: contextvars.Token) -> None:
    """Restore the previous agent context."""
    _current_agent.reset(token)


@asynccontextmanager
async def as_agent(slug: Optional[str]):
    """Async context manager wrapping set/reset."""
    token = set_current_agent(slug)
    try:
        yield
    finally:
        reset_current_agent(token)
```

- [ ] **Step 4: Run + regression + commit**

```bash
pytest tests/test_context.py -v                                        # 4 passed
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3       # 940 passing
git add nexus/context.py tests/test_context.py
git commit -m "feat(context): add current_agent contextvar for cross-layer agent identity"
```

---

## Task 2 · Wire context var into agent adapters

**Why:** When `InProcessAgent.call_tool("handle", ...)` dispatches to the module, every network call the module makes (via providers, federation, or anything else) should see the right `agent_slug`.

**Files:**
- Modify: `nexus/agents/in_process_agent.py`
- Modify: `nexus/agents/mcp_agent.py`
- Create: `tests/agents/test_agent_context.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests that agent adapters set the current_agent contextvar during dispatch."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.context import current_agent_slug
from nexus.kernel.aegis import Aegis
from nexus.modules.base import NexusModule


class _Probe(NexusModule):
    name = "probe"
    description = "records the current_agent during dispatch"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "probe", "name": "probe",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:probe", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return current_agent_slug() or "<none>"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_Probe.manifest())
    return a


@pytest.mark.asyncio
async def test_in_process_call_sets_agent_context(aegis):
    """The module sees current_agent_slug() == its slug during dispatch."""
    agent = InProcessAgent(_Probe(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "x", "context": {}})
    assert result == "probe"


@pytest.mark.asyncio
async def test_in_process_call_restores_context_after(aegis):
    """After the call returns, current_agent_slug() is back to None."""
    agent = InProcessAgent(_Probe(), aegis=aegis)
    await agent.call_tool("handle", {"message": "x", "context": {}})
    assert current_agent_slug() is None
```

- [ ] **Step 2: Modify `nexus/agents/in_process_agent.py`**

Find `call_tool`. Wrap the dispatch body in `async with as_agent(self.slug):`. Specifically: place it AFTER the existing gate (`await self._gate(...)`) and around BOTH the `tool_name == "handle"` branch AND the `else` fallback dispatch.

```python
    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        # ... existing pause/unknown/gate checks ...

        from nexus.context import as_agent
        async with as_agent(self.slug):
            if tool_name == "handle":
                message = args.get("message", "")
                context = args.get("context", {})
                return await self._module.handle(message, context)
            method = getattr(self._module, tool_name, None)
            if method is None:
                raise AttributeError(...)
            method_args = {k: v for k, v in args.items() if k != "workspace_id"}
            return await method(**method_args)
```

- [ ] **Step 3: Modify `nexus/agents/mcp_agent.py`**

Same pattern for the MCPAgent's `call_tool`. After the gate, wrap the `self._session.call_tool(...)` call:

```python
    async def call_tool(self, tool_name: str, args):
        if self._paused:
            raise RuntimeError(...)
        if self._session is None:
            raise RuntimeError(...)
        from nexus.agents._gating import gate_tool_call
        await gate_tool_call(self.slug, self._manifest, tool_name, args, self._aegis, self._inbox)
        from nexus.context import as_agent
        async with as_agent(self.slug):
            return await self._session.call_tool(tool_name, arguments=args)
```

- [ ] **Step 4: Run + regression + commit**

```bash
pytest tests/agents/test_agent_context.py -v                            # 2 passed
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3        # 942 passing
git add nexus/agents/in_process_agent.py nexus/agents/mcp_agent.py tests/agents/test_agent_context.py
git commit -m "feat(agents): set current_agent contextvar around tool dispatch"
```

---

## Task 3 · `KernelHttpClient` — the drop-in httpx wrapper

**Why:** A single shared http client that providers + federation use. When an aegis is attached AND a current_agent is set, it routes through `aegis.network()`. Otherwise it falls back to a real `httpx.AsyncClient` (preserves test paths + direct kernel use).

**Files:**
- Create: `nexus/inference/kernel_http_client.py`
- Create: `tests/inference/test_kernel_http_client.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for KernelHttpClient: aegis-gated when context is set, passthrough otherwise."""
from __future__ import annotations

import pytest
import httpx
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.kernel.aegis import Aegis, PermissionDenied


def _agent_with_domain(slug, domain):
    return Manifest.model_validate({
        "manifest_version": 1, "slug": slug, "name": slug,
        "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": [f"network.outbound.{domain}"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_agent_with_domain("aider", "api.openai.com"))
    a.grant("aider", "network.outbound.api.openai.com")  # global
    return a


@pytest.mark.asyncio
async def test_passthrough_without_aegis_or_context(respx_mock):
    """Without aegis or context, behaves like a normal httpx.AsyncClient."""
    respx_mock.get("https://example.com/").mock(return_value=httpx.Response(200, json={"ok": True}))
    client = KernelHttpClient()
    r = await client.request("GET", "https://example.com/")
    assert r.status_code == 200
    await client.aclose()


@pytest.mark.asyncio
async def test_routes_through_aegis_when_attached(aegis, respx_mock):
    """When aegis + agent context are set, the call must be gated by aegis."""
    respx_mock.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    client = KernelHttpClient(aegis=aegis)
    async with as_agent("aider"):
        r = await client.request("GET", "https://api.openai.com/v1/models")
    assert r.status_code == 200
    await client.aclose()


@pytest.mark.asyncio
async def test_denies_undeclared_domain(aegis):
    """Aegis blocks an undeclared domain."""
    client = KernelHttpClient(aegis=aegis)
    async with as_agent("aider"):
        with pytest.raises(PermissionDenied):
            await client.request("GET", "https://evil.example.com/")
    await client.aclose()


@pytest.mark.asyncio
async def test_no_context_falls_back_to_passthrough(aegis, respx_mock):
    """If aegis is attached but no agent is in context, passes through (kernel paths)."""
    respx_mock.get("https://anywhere.com/").mock(return_value=httpx.Response(204))
    client = KernelHttpClient(aegis=aegis)
    r = await client.request("GET", "https://anywhere.com/")
    assert r.status_code == 204
    await client.aclose()
```

- [ ] **Step 2: Implement `nexus/inference/kernel_http_client.py`**

```python
"""
KernelHttpClient — a drop-in httpx.AsyncClient that routes through
`Aegis.network()` when an agent context is active.

When `aegis` is None or no agent is currently in context, falls back
to a real httpx.AsyncClient (preserves test paths and direct kernel
code that legitimately doesn't go through Aegis).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs):
        # streaming bypasses aegis for now (Phase 7 polish)
        return await self._fallback.stream(method, url, **kwargs)

    async def aclose(self) -> None:
        await self._fallback.aclose()

    # Make it usable as an `httpx.AsyncClient` argument for SDKs
    # by exposing the same async-context-manager interface.
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()
```

- [ ] **Step 3: Run + regression + commit**

```bash
pytest tests/inference/test_kernel_http_client.py -v                    # 4 passed
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3        # 946 passing
git add nexus/inference/kernel_http_client.py tests/inference/test_kernel_http_client.py
git commit -m "feat(inference): KernelHttpClient — httpx wrapper that gates through Aegis"
```

---

## Task 4 · Local provider → KernelHttpClient

**Why:** The Local provider currently uses `urllib.request` (sync). Rewriting it to use the kernel client preserves the local-first claim and removes the only urllib dependency.

**Files:**
- Modify: `nexus/inference/local.py`
- Create: `tests/inference/test_local_provider_kernel_client.py`

- [ ] **Step 1: Inspect the current local.py**

```bash
cat nexus/inference/local.py
```

It currently uses `urllib.request.Request` + `urlopen`. Replace those with a `KernelHttpClient` instance (held as a class attribute or constructor arg).

- [ ] **Step 2: Write the failing test**

```python
"""Tests that LocalProvider routes its inference HTTP through KernelHttpClient."""
from __future__ import annotations

import pytest
import httpx
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.inference.local import LocalProvider
from nexus.kernel.aegis import Aegis, PermissionDenied


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "echo", "name": "echo",
        "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:echo", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": ["network.outbound.localhost"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "in_process"},
    }))
    a.grant("echo", "network.outbound.localhost")
    return a


@pytest.mark.asyncio
async def test_local_provider_gates_through_aegis(aegis, respx_mock):
    respx_mock.post("http://localhost:8384/completion").mock(
        return_value=httpx.Response(200, json={"content": "hi"})
    )
    http = KernelHttpClient(aegis=aegis)
    provider = LocalProvider(base_url="http://localhost:8384", http_client=http)
    async with as_agent("echo"):
        out = await provider.infer([{"role": "user", "content": "hello"}], max_tokens=5)
    assert "hi" in out
    await http.aclose()


@pytest.mark.asyncio
async def test_local_provider_denied_when_undeclared(aegis):
    """Switch to a domain the agent doesn't declare — must raise PermissionDenied."""
    http = KernelHttpClient(aegis=aegis)
    provider = LocalProvider(base_url="http://other-host.invalid:8384", http_client=http)
    async with as_agent("echo"):
        with pytest.raises(PermissionDenied):
            await provider.infer([{"role": "user", "content": "x"}], max_tokens=5)
    await http.aclose()
```

- [ ] **Step 3: Rewrite `nexus/inference/local.py`**

```python
"""
Local llama.cpp HTTP provider — Phase 6: routes through KernelHttpClient
so the local-first promise holds (all outbound HTTP gates through Aegis).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nexus.inference.provider import InferenceProvider

if TYPE_CHECKING:
    from nexus.inference.kernel_http_client import KernelHttpClient


class LocalProvider(InferenceProvider):
    name = "local"

    def __init__(self, base_url: str = "http://localhost:8384",
                 http_client: "KernelHttpClient | None" = None):
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

    async def infer(self, messages: list[dict], max_tokens: int = 1024,
                    temperature: float = 0.7) -> str:
        if self._http is None:
            # Fallback for direct kernel use: a vanilla httpx call
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/completion",
                    json={
                        "prompt": self._messages_to_chatml(messages),
                        "n_predict": max_tokens,
                        "temperature": temperature,
                    },
                )
        else:
            resp = await self._http.post(
                f"{self._base_url}/completion",
                json={
                    "prompt": self._messages_to_chatml(messages),
                    "n_predict": max_tokens,
                    "temperature": temperature,
                },
            )
        resp.raise_for_status()
        body = resp.json()
        return self._parse_response(body.get("content", ""))

    async def health(self) -> bool:
        try:
            if self._http is None:
                import httpx
                async with httpx.AsyncClient(timeout=2.0) as client:
                    r = await client.get(f"{self._base_url}/health")
            else:
                r = await self._http.get(f"{self._base_url}/health")
            return r.status_code == 200
        except Exception:
            return False
```

The existing class might have slightly different method signatures — read it first and preserve the abstract `infer` / `health` contract. The above is a rewrite; if the existing code has `query`, `complete`, etc., keep those names.

- [ ] **Step 4: Run + regression + commit**

```bash
pytest tests/inference/test_local_provider_kernel_client.py -v          # 2 passed
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3        # 948 passing
git add nexus/inference/local.py tests/inference/test_local_provider_kernel_client.py
git commit -m "feat(inference): LocalProvider routes through KernelHttpClient"
```

---

## Task 5 · OpenAI provider → KernelHttpClient

**Why:** The OpenAI SDK accepts a `http_client` parameter; injecting KernelHttpClient routes every OpenAI request through Aegis.

**Files:**
- Modify: `nexus/inference/openai_provider.py`
- Create: `tests/inference/test_openai_provider_kernel_client.py`

- [ ] **Step 1: Inspect the current provider**

Read `nexus/inference/openai_provider.py`. Today's signature is `OpenAIProvider(api_key, model)`. Add `http_client: KernelHttpClient | None = None` kwarg; if provided, pass it to `OpenAI(api_key=..., http_client=http_client._fallback)` (the SDK wants an `httpx.AsyncClient`, not a wrapper — but we need to gate via aegis, so we either wrap the SDK or route via aegis.network() manually).

The cleanest approach: bypass the SDK's transport when an aegis context exists. Override the SDK's behaviour:

Option A — replace the SDK's underlying httpx client with one whose transport sends through Aegis. Complex but preserves the SDK's interface.

Option B — when `http_client` is provided, use our own HTTP calls to OpenAI's REST API instead of the SDK. Less idiomatic but avoids fighting the SDK.

**Recommend Option A** for fidelity. Use `httpx.AsyncClient(transport=AegisTransport(aegis, http_client))` where `AegisTransport` is a custom transport that calls `aegis.network()` per request. Add this transport to `nexus/inference/kernel_http_client.py`:

```python
class AegisTransport(httpx.AsyncBaseTransport):
    """Custom httpx transport that delegates to Aegis.network()."""

    def __init__(self, kernel_client: KernelHttpClient):
        self._kernel = kernel_client
        # Fall-back direct transport for when no context is set
        self._inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        agent_slug = current_agent_slug()
        if self._kernel._aegis is None or agent_slug is None:
            return await self._inner.handle_async_request(request)
        # Build the call via aegis.network()
        url = str(request.url)
        body = request.content
        try:
            return await self._kernel._aegis.network(
                agent_slug, url,
                method=request.method,
                headers=dict(request.headers),
                content=body,
            )
        except Exception:
            # Aegis denied or otherwise failed — propagate
            raise
```

Then in `OpenAIProvider.__init__`:

```python
def __init__(self, api_key, model="gpt-4o-mini", http_client=None):
    self._api_key = api_key
    self._model = model
    if http_client is not None:
        # Inject an httpx.AsyncClient using our AegisTransport
        from nexus.inference.kernel_http_client import AegisTransport
        sdk_client = httpx.AsyncClient(transport=AegisTransport(http_client))
        self._client = AsyncOpenAI(api_key=api_key, http_client=sdk_client)
    else:
        self._client = OpenAI(api_key=api_key)
```

If the SDK requires sync, switch to `AsyncOpenAI` and adapt the `infer` method.

This task is complex — if it gets stuck, **STOP and report BLOCKED**. The fallback is Option B (custom REST calls instead of SDK), which the implementer can adopt.

- [ ] **Step 2-4:** Write tests + run + commit.

```bash
git commit -m "feat(inference): OpenAIProvider routes through Aegis when http_client supplied"
```

---

## Task 6 · Anthropic provider → KernelHttpClient

Same pattern as Task 5. The Anthropic SDK accepts `http_client`; inject our AegisTransport-backed httpx client.

If the same blocker hits, report BLOCKED — Option B fallback applies.

Commit: `feat(inference): AnthropicProvider routes through Aegis when http_client supplied`.

---

## Task 7 · Federation HTTP → `aegis.network()`

**Why:** Federation peers are just another network destination. Phase 6 routes them through Aegis with capability `network.federation.<peer-id>` per spec §15.

**Files:**
- Modify: `nexus/federation/discovery.py` (3 httpx.AsyncClient blocks)
- Modify: `nexus/federation/protocol.py` (5 httpx.AsyncClient blocks)
- Create: `tests/federation/test_federation_gating.py`

- [ ] **Step 1: Inspect both files**

```bash
grep -n "httpx.AsyncClient" nexus/federation/discovery.py nexus/federation/protocol.py
```

Each call passes a peer URL; the peer's id is available from the surrounding code via `peer.peer_id` or similar.

- [ ] **Step 2: Convert each `async with httpx.AsyncClient(...) as client: ... client.request(...)` to use Aegis**

The pattern:

```python
# before
async with httpx.AsyncClient(timeout=10.0) as client:
    r = await client.post(url, json=payload)
```

```python
# after — assuming the surrounding code has `aegis` and `peer.peer_id`
capability = f"network.federation.{peer.peer_id}"
# Federation's "agent slug" is conventionally "federation" — register a manifest at boot
r = await aegis.network("federation", url, method="POST", json=payload)
```

For the manifest: add a built-in `federation` agent to the registry (alongside the 10 cognitive agents). Its manifest declares `network.federation.*` capabilities matching the configured peers. The catalog manifest:

```python
{
    "manifest_version": 1,
    "slug": "federation",
    "name": "federation",
    "tagline": "ONEXUS-to-ONEXUS peer mesh.",
    "version": "0.1.0",
    "system": True,
    "publisher": {"type": "org", "handle": "nexus"},
    "category": "federation",
    "identity": {"mark": {"kind": "builtin:agents", "gradient": ["#c8c8ff", "#3a3a8c"]}},
    "intents": [],
    "capabilities": {"tools": [], "declared": {
        "Routine": [], "Notable": ["network.federation.*"],
        "Sensitive": [], "Privileged": [],
    }},
    "runtime": {"transport": "in_process"},
}
```

Federation calls happen outside the agent-runtime context, so they need to set `current_agent` explicitly:

```python
from nexus.context import as_agent
async with as_agent("federation"):
    r = await aegis.network("federation", url, method="POST", json=payload)
```

If `aegis` isn't available at the call site, accept it as a constructor argument or pass via the existing federation manager.

This is invasive. **If a subagent hits scope blockage, STOP and split this into 7a (discovery) + 7b (protocol).**

Commit message: `feat(federation): route peer HTTP through Aegis with network.federation.<peer-id> capability`.

---

## Task 8 · End-to-end Phase 6 smoke

**Files:**
- Create: `tests/inference/test_phase_6_smoke.py`

End-to-end: an agent with a declared `network.outbound.api.openai.com` + grant invokes a provider that goes through OpenAI's SDK → Aegis sees the request → Chronicle records it.

Mock the actual OpenAI response via respx.

Commit: `test(inference): end-to-end Phase 6 smoke (provider → aegis.network → chronicle)`.

---

## Task 9 · Docs + tag

- Update `docs/agents/foundation.md` (or create `docs/agents/network-gateway.md`) describing:
  - `current_agent_slug()` contextvar
  - `KernelHttpClient` / `AegisTransport`
  - How providers consume it
  - How federation uses `network.federation.<peer-id>`
  - The "kernel does zero direct network I/O" invariant + how to verify (grep for `import httpx` / `urllib` in kernel)

Tag:

```bash
git tag -a phase-6-network-gateway -m "Phase 6 network gateway complete: all outbound HTTP routes through aegis.network()

- current_agent contextvar threads agent identity through async stacks
- KernelHttpClient drop-in httpx wrapper with AegisTransport
- LocalProvider, OpenAIProvider, AnthropicProvider routed through Aegis when http_client is supplied
- Federation peer HTTP gated by network.federation.<peer-id>
- Built-in 'federation' agent manifest registered at boot
- All outbound bytes logged to Chronicle

Suite: <count> passing.
Failure set byte-identical to baseline."
```

Phase 6 done. Phase 7 (polish + accessibility audit + test rot cleanup + WebSockets) follows.

---

## Self-review

| Spec section | Implementing task | Notes |
|---|---|---|
| §4.5 Aegis network gateway | Tasks 1, 2, 3 | KernelHttpClient + contextvar |
| §15 Local-first preserved | Tasks 4, 5, 6 | All providers route through Aegis |
| §15 Federation gateway | Task 7 | network.federation.<peer-id> |

**Open issues for Phase 7:**
- WebSocket streams (mood/pulse/permissions push)
- 28 baseline failures + 65 collection error cleanup
- Accessibility audit pass on the Aurora surfaces
- Time-of-day mood modulation
- Final integration test sweep

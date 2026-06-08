# Network Gateway (Phase 6)

The local-first promise — *"the kernel never touches the network"* —
is now enforced literally. Every outbound byte flows through
`aegis.network()`, which gates against the agent's declared
`network.outbound.<domain>` capability, rate-limits per agent, and
logs the request to Chronicle.

A static invariant test enforces this: no kernel module *except Aegis*
imports `httpx`, `urllib`, or `requests` directly. See
`tests/inference/test_phase_6_smoke.py::test_kernel_never_directly_imports_httpx_in_kernel_modules`.

## How it works

```
agent's tool method
  └─> uses LocalProvider / OpenAIProvider / AnthropicProvider / federation client
       └─> KernelHttpClient.request() or AegisTransport.handle_async_request()
            └─> aegis.network(agent_slug, url, method, ...)
                 └─> check_capability("network.outbound.<host>")
                 ├─> rate limit check
                 ├─> httpx.AsyncClient performs the actual HTTP
                 └─> chronicle.log("aegis", "network_request", {...})
```

## Key types

| Symbol | Module | Purpose |
|---|---|---|
| `current_agent_slug()` | `nexus.context` | Returns the slug of the currently-executing agent (None if not in an agent context) |
| `set_current_agent(slug)` / `reset_current_agent(token)` | `nexus.context` | Low-level setters |
| `as_agent(slug)` | `nexus.context` | Async context manager: `async with as_agent("aider"): ...` |
| `KernelHttpClient` | `nexus.inference.kernel_http_client` | Drop-in httpx wrapper; routes through aegis.network() when context + aegis are set |
| `AegisTransport` | `nexus.inference.kernel_http_client` | `httpx.AsyncBaseTransport` subclass for SDK injection |

## Provider migration pattern

Every provider accepts a `KernelHttpClient` (or `aegis` reference) and
injects it as the SDK's `http_client` (OpenAI/Anthropic) or uses it
directly (Local, federation):

```python
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.inference.local import LocalProvider

http = KernelHttpClient(aegis=aegis)
provider = LocalProvider(base_url="http://localhost:8384", http_client=http)
```

When the agent runtime dispatches the call, `as_agent(slug)` is set
automatically by `InProcessAgent` / `MCPAgent`, so the provider's
internal HTTP calls inherit that agent's identity.

## Agent adapter wiring

`InProcessAgent.call_tool` and `MCPAgent.call_tool` wrap their
dispatch bodies in `async with as_agent(self.slug):`. Anything the
module does — including provider calls deep in the call stack —
inherits the agent's identity via the contextvar.

## Federation

Per spec §15, federation peers use the capability
`network.federation.<peer-id>`. `FederationDiscovery` and
`FederationProtocol` accept an optional `http_client` (a
`KernelHttpClient`) at construction. When the server enables federation,
it instantiates them with a `KernelHttpClient(aegis=...)` and
registers a built-in `federation` agent manifest at boot.

## What's NOT in Phase 6

- WebSocket streams for the surfaces (Phase 7).
- Federation calls wrapped in `as_agent("federation")` for full gating
  (Phase 7 — the infrastructure is in place; the wrapping is the last mile).
- Cleanup of the 28 pre-existing baseline failures + 65 collection
  errors (Phase 7 dedicated pass).

## Verification

Run the kernel-local-first invariant test any time the kernel changes:

```bash
pytest tests/inference/test_phase_6_smoke.py -v
```

`test_kernel_never_directly_imports_httpx_in_kernel_modules` will fail
if a kernel module other than Aegis grows a direct outbound HTTP
dependency.

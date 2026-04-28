---
title: Modules
description: NexusModule base class, lifecycle hooks, context object, and how all 26 modules are structured.
sidebar:
  order: 3
---

## NexusModule Base Class

Every module in NEXUS — all 29 of them — is a subclass of `NexusModule`. The interface is minimal by design.

```python
from nexus.module import NexusModule

class MyModule(NexusModule):
    name = "my_module"
    description = "One sentence describing what this module does."
    version = "1.0.0"

    async def handle(self, message: str, context: dict) -> str:
        return f"Echo: {message}"
```

Three class attributes are required:

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique identifier used for routing, trust tracking, and audit logs |
| `description` | `str` | Human-readable description shown in `nexus status` |
| `version` | `str` | Semantic version string |

## Lifecycle Hooks

Modules can optionally implement two lifecycle methods:

```python
async def on_load(self, context: dict) -> None:
    """Called once when the module is enabled. Set up subscriptions here."""
    await context["pulse"].subscribe("file.*", self._on_file_event)

async def on_unload(self, context: dict) -> None:
    """Called when the module is disabled via `nexus deny`. Clean up here."""
    await context["pulse"].unsubscribe("file.*", self._on_file_event)
```

`on_load` and `on_unload` are not abstract — they default to no-ops. Only implement them if the module needs setup or teardown.

## Context Object

Every call to `handle()`, `on_load()`, and `on_unload()` receives a `context` dictionary with references to all kernel components:

| Key | Type | Description |
|-----|------|-------------|
| `context["llm"]` | `LLMClient` | HTTP client for the configured llama.cpp server |
| `context["engram"]` | `Engram` | Three-tier memory store (working, episodic, semantic) |
| `context["chronicle"]` | `Chronicle` | Append-only audit log, queryable |
| `context["pulse"]` | `Pulse` | Async pub/sub event bus |

Modules access kernel services only through this context. They do not import kernel classes directly. This keeps modules testable in isolation — pass a mock context and the module has no external dependencies.

## Module Tiers

The 26 modules are grouped by functional tier. All use the same `NexusModule` interface regardless of tier.

| Tier | Modules | Role |
|------|---------|------|
| Perception | Oracle, Sentry | Observe the environment and detect anomalies |
| Intelligence | Atlas, Prism, Cipher | Analyze, reason, and decode using LLM |
| Action | Wraith, Echo, Sigil, Herald, Weave | Execute tasks, remember, sign, notify, orchestrate |
| Advanced | Specter, Chronos, Dreamweaver, Serendipity, Forge | Red-team, branch timelines, synthesize, discover, negotiate |
| Orchestration | Council, Autonomic | Multi-agent deliberation, earned autonomous action |
| Network | Collective, Legacy | Federated learning, knowledge crystallization |
| Differentiation | Dream Loop, Adversarial, Tripwire, Provenance, Sandbox, Symbiosis, Consciousness, Emergence, Ethical Prism | Self-reflection, stress-testing, ethical analysis, pattern discovery |
| Community | User-contributed | Third-party modules via `community/modules/` |
| Core | General | Catch-all fallback for unrouted messages |

## Minimal Module Example

A complete, functional module with LLM usage, memory storage, and Pulse event emission:

```python
from nexus.module import NexusModule


class SummaryModule(NexusModule):
    name = "summary"
    description = "Summarizes text using the local LLM and stores it in episodic memory."
    version = "1.0.0"

    async def handle(self, message: str, context: dict) -> str:
        # Call the LLM
        prompt = f"Summarize the following in two sentences:\n\n{message}"
        summary = await context["llm"].complete(prompt)

        # Store in episodic memory for later retrieval
        await context["engram"].store_episodic(
            source=self.name,
            content=summary,
            tags=["summary"],
        )

        # Notify other modules
        await context["pulse"].publish("summary.created", {"text": summary})

        return summary
```

To register routing keywords so Cortex dispatches messages to this module, add an entry to `Cortex._MODULE_KEYWORDS`:

```python
_MODULE_KEYWORDS = {
    ...
    "summary": ["summarize", "tldr", "brief", "overview"],
}
```

See [Building a Module](/guides/building-a-module/) for the full step-by-step guide including tests.

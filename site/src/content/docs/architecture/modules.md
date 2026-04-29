---
title: Modules & Agents
description: NexusModule and AgentModule base classes, lifecycle hooks, context object, graduated sovereignty, and how all 51 components are structured.
sidebar:
  order: 3
---

## NexusModule Base Class

NEXUS has two kinds of intelligence: 26 modules (persistent intelligence components) and 25 agents (task specialists with graduated sovereignty). Both share a common base. Every module is a subclass of `NexusModule`. The interface is minimal by design.

```python
from nexus.module import NexusModule

class MyModule(NexusModule):
    name = "my_module"
    description = "One sentence describing what this module does."
    version = "1.0.0"

    async def handle(self, message: str, context: dict) -> str:
        return f"Echo: {message}"
```

Three class attributes are required, one is optional:

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique identifier used for routing, trust tracking, and audit logs |
| `description` | `str` | Human-readable description shown in `nexus status` |
| `version` | `str` | Semantic version string |
| `requires_network` | `bool` | Default `False`. Set `True` for modules that connect to external endpoints. Aegis enforces a separate `--network` consent gate for these modules, and Chronicle logs every outbound data event. |

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

## Data Pipelines

Six modules subscribe to `cortex.response` Pulse events in their `on_load()` hook to automatically collect data from the conversation flow:

| Module | What It Collects | Source |
|--------|-----------------|--------|
| Prism | Cross-domain observations | Every module response, tagged by module name |
| Serendipity | Focus areas + knowledge entries | User messages and module responses |
| Cipher | Source profiles + claims | Module outputs with auto-assigned trust scores |
| Atlas | Temporal facts | Extracts subject from user query, stores response as fact |
| Weave | Contact mentions + interactions | Proper nouns detected in user messages |
| Legacy | Decision records | Responses from Council, Ethical Prism, and Autonomic |

These modules require no manual data entry. They build their internal stores passively from system activity, becoming more useful the longer NEXUS runs.

## AgentModule Base Class

The 25 agents extend `NexusModule` through `AgentModule`, which adds graduated sovereignty. Agents start as passive skills and earn autonomy through demonstrated reliability.

```python
from nexus.agents.base import AgentModule, TrustTier

class MyAgent(AgentModule):
    name = "my_agent"
    description = "What this agent does."
    version = "1.0.0"

    watch_events = ["relevant.event"]        # Pulse topics at MONITOR+
    coordination_targets = ["other_agent"]   # Agents to coordinate with at SOVEREIGN

    async def analyze(self, message: str, context: dict) -> str:
        """Core logic. Runs at every trust level."""
        return f"Analysis: {message}"

    async def suggest(self, message: str, context: dict) -> str:
        """Proactive suggestions. ADVISOR+ trust."""
        return "You might also want to check..."

    async def monitor(self, event: dict, context: dict) -> str | None:
        """Background event watching. MONITOR+ trust."""
        return "Detected anomaly in event stream"

    async def coordinate(self, analysis_result: str, context: dict) -> str:
        """Cross-agent routing. SOVEREIGN trust only."""
        cortex = context.get("cortex")
        return await cortex.route("other_agent", analysis_result, context)
```

### Trust Tiers

| Tier | Score | Behavior |
|------|-------|----------|
| **SKILL** | 0-24 | User invokes explicitly. No initiative. |
| **ADVISOR** | 25-49 | Suggests actions when relevant context detected. |
| **MONITOR** | 50-74 | Proactively watches Pulse events and reports findings. |
| **AUTONOMOUS** | 75-99 | Acts within defined boundaries without asking. |
| **SOVEREIGN** | 100 | Coordinates with other agents independently. |

Trust is tracked by Aegis and can be revoked at any time. The `AgentModule.handle()` method routes through these tiers automatically -- agents only implement the tier-specific methods they support.

## Component Tiers

The 51 components are grouped by functional tier. Modules use `NexusModule`, agents use `AgentModule`.

| Tier | Components | Interface |
|------|-----------|-----------|
| Perception | Oracle, Sentry | NexusModule |
| Intelligence | Atlas, Prism, Cipher | NexusModule |
| Action | Wraith, Echo, Sigil, Herald, Weave | NexusModule |
| Advanced | Specter, Serendipity, Forge | NexusModule |
| Orchestration | Council, Autonomic | NexusModule |
| Network | Collective, Legacy | NexusModule |
| Differentiation | Dream Loop, Adversarial, Tripwire, Provenance, Sandbox, Symbiosis, Consciousness, Ethical Prism | NexusModule |
| Agents (Code) | Vex, Arbiter, Carve, Remedy, Scaffold, Axiom, Rune | AgentModule |
| Agents (Data) | Flux, Vigil, Gauge, Quarry, Loom | AgentModule |
| Agents (Business) | Ledger, Tally, Mint, Redline, Mandate | AgentModule |
| Agents (Content) | Scribe, Kindle, Thesis, Compass | AgentModule |
| Agents (Ops) | Bastion, Dispatch, Sentinel, Mnemonic | AgentModule |
| Community | User-contributed | NexusModule |
| Core | General | NexusModule |

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

See [Building a Module](/NEXUS/guides/building-a-module/) for the full step-by-step guide including tests.

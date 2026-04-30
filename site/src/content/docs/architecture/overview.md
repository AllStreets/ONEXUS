---
title: Overview
description: NEXUS microkernel architecture — 5 components, 51 modules, one message loop.
sidebar:
  order: 1
---

## Microkernel Design

NEXUS is a microkernel. The kernel is approximately 500 lines of Python across 5 files. It handles routing, memory, messaging, auditing, and trust — nothing else. All intelligence lives in modules that run on top of it.

```
nexus/kernel/
├── cortex.py      # message router + permission gate
├── engram.py      # three-tier memory store
├── pulse.py       # async pub/sub message bus
├── chronicle.py   # immutable audit log
└── aegis.py       # trust scoring engine
```

This separation means the kernel is stable and testable independently of the modules. Adding a new capability never requires touching the kernel.

## Message Flow

Every user input follows the same path through the kernel before a module ever sees it:

```
1.  User types message
2.  Cortex receives it, parses routing keywords
3.  Aegis checks trust score for the target module (must be > 0)
4.  Chronicle logs the inbound message (timestamp, source, content hash)
5.  Engram stores the message in working memory
6.  Module receives (message, context) and executes
7.  Engram stores the response in episodic memory
8.  Chronicle logs the response and outcome
9.  Pulse emits a completion event (other modules may subscribe)
```

No step is skipped. Every message — including internal module-to-module calls via Pulse — runs through the same trust gate and audit path.

## Design Constraints

These constraints are architectural commitments, not guidelines:

**Local-first.** The kernel never touches the network. No telemetry, no central server, no cloud dependency — architecturally enforced, not just policy. Two modules (Collective and Herald) can optionally connect peer-to-peer, but they are blocked by default and require explicit `nexus allow --network` consent. Even then, every outbound event is logged to Chronicle. There is no central server. Every machine owns its own data.

**Lightweight kernel.** The kernel runs standalone without any LLM. Connect a model when you're ready — local open-source models via llama.cpp, Ollama, or vLLM, or cloud providers like OpenAI and Anthropic. Providers can be registered at runtime via the API.

**Model-agnostic.** The kernel communicates with any LLM over a standard HTTP API. Swap models by changing the provider configuration — no code changes required. Use open-source models for full sovereignty, or cloud APIs for convenience.

**Apache 2.0 throughout.** Every model recommended in the default configuration is MIT or Apache 2.0 licensed. NEXUS itself is Apache 2.0. It is legally redistributable in commercial products.

**Append-only audit.** Chronicle uses SQLite WAL mode with no DELETE or UPDATE operations. The audit record is immutable by design, not by convention.

## Module Tiers

Intelligence modules use the `NexusModule` interface. Agents use the `AgentModule` interface, which extends `NexusModule` with graduated sovereignty -- five trust tiers that unlock progressively more capable behavior.

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
| Community | User-contributed modules via `community/modules/` | NexusModule |
| Core | General | NexusModule |

## Testing

NEXUS ships with 804 tests covering all kernel components, modules, agents, inference providers, messaging bridges, community ecosystem, and differentiation modules. The test suite requires no running LLM — all LLM calls are mocked. Run with:

```bash
pytest tests/ -v
```

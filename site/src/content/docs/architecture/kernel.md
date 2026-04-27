---
title: Kernel
description: The five kernel components — Cortex, Engram, Pulse, Chronicle, Aegis — and how they interact.
sidebar:
  order: 2
---

The NEXUS kernel is five components. Each has a single responsibility. They communicate only through well-defined interfaces, not by importing each other's internals.

## Cortex — Message Router

Cortex is the entry point for all messages. It does two things: route messages to modules, and enforce permission gates.

**Routing** is keyword-based. Each module registers a set of trigger words in `Cortex._MODULE_KEYWORDS`. When a message arrives, Cortex scans it for matches and dispatches to the highest-confidence module. If no keywords match, the message falls through to the General module.

**Permission enforcement** happens before dispatch. Cortex asks Aegis whether the target module has a trust score above zero. A module with zero trust is silently bypassed. This is not a hard error — the user sees no output for denied modules.

Cortex does not parse intent, classify semantics, or call an LLM. It is a deterministic dispatch table.

## Engram — Three-Tier Memory

Engram provides persistent, queryable memory across three tiers backed by a single SQLite database.

**Working memory** is an ephemeral key-value store. Values expire at session end or when explicitly cleared. Modules use it for transient state — e.g., holding the current file being analyzed mid-conversation.

**Episodic memory** stores timestamped records of every message and response. It is indexed with SQLite FTS5 (full-text search), so modules can query `"what did I say about X last week"` efficiently without an LLM.

**Semantic memory** stores vector embeddings alongside text. It uses `sqlite-vec`, a SQLite extension for approximate nearest-neighbor search. When a module stores something semantically, it can later retrieve the most relevant records by embedding similarity rather than keyword match.

All three tiers are accessible through the context object passed to every module:

```python
context["engram"].store_working("current_file", path)
context["engram"].store_episodic("atlas", summary, tags=["code", "review"])
context["engram"].store_semantic("research", text, embedding=vec)
```

## Pulse — Async Pub/Sub Bus

Pulse is the inter-module event bus. Modules publish events and subscribe to topic patterns. Subscriptions support wildcards (`file.*` matches `file.changed`, `file.deleted`, etc.).

Messages on Pulse are prioritized. High-priority events (security alerts from Sentry, trust changes from Aegis) are processed before standard messages.

Pulse is fully asynchronous using Python `asyncio`. A module's `handle()` method can emit events without waiting for subscribers to process them.

```python
# Publishing
await context["pulse"].publish("file.changed", {"path": str(path)})

# Subscribing (in on_load)
await context["pulse"].subscribe("file.*", self._on_file_event)
```

## Chronicle — Immutable Audit Log

Chronicle records every event the kernel processes — inbound messages, routing decisions, module responses, trust score changes, permission grants and denials.

It uses SQLite in WAL (Write-Ahead Log) mode. The schema has no UPDATE or DELETE operations. Records are append-only. This is enforced at the application layer, not by database constraints, but the design makes it auditable: a SHA-256 chain links each record to the previous one.

Chronicle supports compliance use cases. The append-only log with timestamps and content hashes satisfies the evidence requirements for SOC 2 Type II, HIPAA audit controls, and GDPR Article 17 (right to erasure — Chronicle can demonstrate what was deleted from Engram while retaining the deletion event itself).

Modules can query Chronicle directly through the context:

```python
recent = context["chronicle"].query(module="atlas", limit=10)
```

## Aegis — Trust Engine

Aegis maintains a trust score between 0 and 100 for every module. New modules start at 50.

Trust is not static. Aegis adjusts scores based on outcomes:

- **Positive outcome** (user accepts response, module completes task): +1 to +3
- **Negative outcome** (user rejects, error thrown, policy violation): -2 to -10
- **Extended inactivity**: slow decay toward 50 (regression to mean)

A module with trust below a configurable threshold (default: 1) is denied by Cortex. A module above a high threshold (default: 80) may be granted elevated capabilities by future policy rules.

Trust scores persist in `aegis.db` across sessions. They accumulate over time — a module that has been reliable for months has a meaningfully different trust profile than one enabled yesterday.

```python
score = context["aegis"].get_trust("atlas")        # float 0-100
await context["aegis"].record_outcome("atlas", positive=True)
```

---
title: Design Philosophy
description: The four principles behind NEXUS — local-first, anti-fragile, compounding value, and model-agnostic.
sidebar:
  order: 4
---

## Local-First

NEXUS makes no outbound network connections except to the LLM endpoint you configure, which defaults to `localhost:8080`. No telemetry. No cloud sync. No third-party APIs.

This is not just a privacy preference — it is an architectural constraint. The kernel has no HTTP client for external services. Modules that need external data (Oracle reading the filesystem, Sentry monitoring processes) operate on local resources. The intelligence tier uses only the locally running LLM.

The practical consequence: NEXUS works without internet access. It works on air-gapped machines. It works when the cloud is down. Your data never leaves your machine unless you explicitly write a module that sends it somewhere.

## Anti-Fragile

A fragile system degrades gracefully. An anti-fragile system gets stronger under stress.

Four modules embody this directly:

**Specter** is the adversarial red-team module. It attacks the system's own reasoning — looking for gaps, inconsistencies, and failure modes in plans before they execute. When Specter finds a flaw, the system is better for it.

**Serendipity** is the anti-optimization engine. It deliberately surfaces low-probability, high-value connections that a purely goal-directed system would prune. Unexpected associations are features, not noise.

**Cipher** handles anomaly detection and pattern analysis. It gets better at recognizing threats as it accumulates more examples of normal behavior to compare against.

**Sigil** provides cryptographic signing for outputs that require integrity guarantees. Outputs signed by Sigil can be verified even outside NEXUS.

Together, these modules mean that adversarial input, unexpected data, and failure cases are handled as inputs to improvement rather than conditions to be avoided.

## Compounding Value

The most important design decision in NEXUS is shared memory. All modules read from and write to the same Engram instance. This creates compounding value over time.

**Echo** remembers. It stores user preferences, recurring patterns, and behavioral context in episodic memory. The longer you use NEXUS, the better Echo's context becomes.

**Legacy** crystallizes knowledge. It distills episodic memory into durable semantic representations — converting the raw record of what happened into reusable knowledge about what it means.

**Engram** itself compounds. A semantic memory built over months of use across multiple modules contains connections that no single interaction could have produced. Atlas analyzing code, Sentry flagging anomalies, and Dreamweaver synthesizing overnight — all of it feeds into a shared knowledge base that grows more valuable the longer the system runs.

This is the inverse of most AI tools, which start fresh on every session. NEXUS sessions compound.

## Microkernel, Not Monolith

The kernel is approximately 500 lines of Python. It does five things: route, remember, message, audit, and evaluate trust. It does nothing else.

Everything else is a module. This matters for several reasons:

- **Stability:** The kernel changes rarely. Modules change often. Kernel bugs affect everything; module bugs affect one capability.
- **Testability:** Each module is independently testable with a mocked context. The kernel is independently testable without any modules loaded.
- **Extensibility:** Adding a new capability is adding a file. It requires no changes to the kernel.
- **Auditability:** 500 lines is readable by a human in an afternoon. You can understand exactly what the kernel does by reading it.

## Model-Agnostic

NEXUS communicates with LLMs through a thin HTTP client that speaks the llama.cpp API. Any model served over that API works without code changes.

Switch from Qwen 3 8B to DeepSeek-R1 by pointing `NEXUS_LLM_HOST:NEXUS_LLM_PORT` at a different server. Use Ollama instead of llama.cpp. Run the model on a remote machine. Use a faster model for quick tasks and a larger model for complex ones by switching environment variables between sessions.

The system is not coupled to any specific model, provider, or inference backend. As better models become available, you adopt them by changing a config value.

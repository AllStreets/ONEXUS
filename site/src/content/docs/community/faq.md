---
title: "FAQ"
description: "Common questions about NEXUS -- hardware, privacy, models, and getting started"
sidebar:
  order: 5
---

## Frequently Asked Questions

---

### General

**What is NEXUS?**

A modular AI operating system that runs entirely on your machine. Five kernel components handle routing, memory, messaging, auditing, and trust. Fifty-one modules plug into that kernel to provide intelligence, analysis, automation, and 25 narrow AI agents for specific tasks.

**Do I need a GPU?**

No. All inference runs on CPU via llama.cpp. A GPU accelerates inference but is not required. The 8GB RAM minimum assumes CPU-only operation.

**Do I need an internet connection?**

Only for the initial setup (cloning the repo, downloading a model). After that, NEXUS runs fully offline. Two modules (Collective and Herald) can optionally connect peer-to-peer, but they're blocked by default.

**What models does NEXUS support?**

Any GGUF model served over the llama.cpp HTTP API. Recommended: Qwen 3 8B (default), DeepSeek-R1 7B, Phi-4 Mini. Cloud providers (OpenAI, Anthropic) are also supported when API keys are configured.

**Can I use NEXUS without any LLM at all?**

Yes. The 25 narrow AI agents work using pattern-based analysis -- regex, heuristics, and rules. They provide useful results without any model. The intelligence tier modules (Atlas, Prism, Cipher) and differentiation modules require an LLM for full functionality.

---

### Privacy & Security

**Where is my data stored?**

Everything lives in `~/.local/share/nexus/` -- three SQLite databases (memory, audit, trust). Nothing leaves your machine unless you explicitly enable a network module.

**Does NEXUS phone home?**

No. The kernel is architecturally incapable of network access. There is no telemetry, no analytics, no update checking. The code is open source -- verify this yourself.

**What about the network modules?**

Collective (federated learning) and Herald (agent-to-agent communication) can connect to other NEXUS instances peer-to-peer. They are blocked by default. Enabling them requires explicit `nexus allow --network <module>` consent. Even enabled, Collective shares only noise-injected aggregates (never raw data), and Herald logs every outbound message to Chronicle.

**Can I export or delete my data?**

`nexus forget --yes` clears all memory (Engram). Delete `~/.local/share/nexus/` to remove everything. The audit trail in Chronicle is append-only by design -- deleting the database file is the only way to remove it.

**Is NEXUS SOC 2 / HIPAA compatible?**

Chronicle's immutable audit trail is designed for compliance export. Every routing decision, permission check, module response, trust adjustment, and outbound data event is logged. Whether your specific deployment meets compliance requirements depends on your broader infrastructure.

---

### Modules & Agents

**What's the difference between a module and an agent?**

Nothing technically -- both are `NexusModule` subclasses with the same interface. "Agent" is a label for the 25 narrow AI task specialists (Vex, Scribe, Ledger, etc.) that solve focused problems. "Module" is the broader term covering kernel-adjacent intelligence components (Atlas, Prism, Council, etc.).

**How do I know which agent to use?**

See the [Use Cases](/NEXUS/community/use-cases/) page for problem-first guidance, or the [Agent Discovery](/NEXUS/community/agents/) page to browse all 25 agents by category.

**Can agents work together?**

Yes. See the [Agent Workflows](/NEXUS/guides/agent-workflows/) guide for three patterns: sequential chaining via Cortex, event-driven pipelines via Pulse, and multi-agent deliberation via Council.

**Can I build my own module?**

Yes. The [Building a Module](/NEXUS/guides/building-a-module/) guide covers the full workflow. Subclass `NexusModule`, implement `handle()`, add routing keywords to Cortex, write tests, submit a PR.

**How does trust scoring work?**

Every module starts at trust level 0. Aegis adjusts trust based on outcomes -- positive results increase trust, failures decrease it. Trust is per-module, per-domain, enforced on every call. See [Earned Autonomy](/NEXUS/concepts/earned-autonomy/) for details.

---

### Technical

**What Python version do I need?**

Python 3.11 or later. The codebase uses `asyncio`, type hints, and `dataclasses` features from 3.11+.

**How do I run the tests?**

```bash
pytest tests/ -v
```

804 tests, no network, no running LLM required. See [Running Tests](/NEXUS/guides/running-tests/) for targeting specific tests and writing new ones.

**What's the database schema?**

NEXUS uses three SQLite databases:
- **engram.db** -- working memory (ephemeral), episodic memory (FTS5 full-text search), semantic memory (sqlite-vec vector embeddings)
- **chronicle.db** -- append-only audit log in WAL mode
- **aegis.db** -- per-module trust scores and outcome history

**Can I use NEXUS in a commercial product?**

Yes. NEXUS is Apache 2.0 licensed. All recommended models are MIT or Apache 2.0. See the [LICENSE](https://github.com/AllStreets/NEXUS/blob/main/LICENSE) for details.

**How do I update NEXUS?**

```bash
cd nexus
git pull origin main
pip install -e .
```

Your data directory is separate from the code -- updates don't affect stored memory, audit logs, or trust scores.

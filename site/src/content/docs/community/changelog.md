---
title: "Changelog"
description: "NEXUS release history -- what shipped, when, and why"
sidebar:
  order: 6
---

## Changelog

All notable changes to NEXUS, ordered newest first.

---

### v0.1.0 -- Initial Release

**Narrow AI Agents (25 agents)**

Twenty-five task-specialist agents, each working standalone with pattern-based analysis and enhancing with LLM when available. Built in five batches:

- **Code & Development:** Vex (vulnerability scanner), Arbiter (code review), Carve (refactoring assistant), Remedy (error diagnoser), Scaffold (boilerplate generator), Axiom (test generator), Rune (regex builder)
- **Data & Analysis:** Flux (NL-to-SQL), Vigil (log analysis), Gauge (performance metrics), Quarry (web data extraction), Loom (ETL pipeline builder)
- **Business & Finance:** Ledger (transaction categorizer), Tally (financial projections), Mint (invoice generator), Redline (contract risk analyzer), Mandate (compliance gap analysis)
- **Content & Communication:** Scribe (meeting summarizer), Kindle (content expansion), Thesis (paper analyzer), Compass (learning roadmaps)
- **Infrastructure & Ops:** Bastion (API security scanner), Dispatch (notification router), Sentinel (cron monitor), Mnemonic (knowledge base)

Every agent credits the open source projects that inspired it.

**Community Ecosystem**

- ModuleValidator -- validates structure, manifest, and kernel import restrictions
- ModuleRegistry -- JSON-backed searchable catalog
- ModuleInstaller -- install/uninstall with automatic Cortex keyword registration
- GitHub CI workflows for PR validation and registry rebuild

**NEXUS Documentation Site**

- Full Astro/Starlight documentation site at allstreets.github.io/NEXUS
- 74 pages covering setup, architecture, concepts, guides, community, and reference
- Agent Discovery page with all 25 agents organized by category
- Reference pages for all 51 modules

**Differentiation Layer (8 modules)**

- Dream Loop -- background pattern discovery
- Adversarial -- self-improvement red-teaming
- Tripwire -- contradiction detection
- Provenance -- reasoning chain tracer
- Sandbox -- hypothetical simulation
- Symbiosis -- module pathway mapping
- Consciousness -- self-reflective awareness and emergent goal detection
- Ethical Prism -- seven-framework ethical analysis

**Infrastructure**

- Multi-Provider inference routing (OpenAI, Anthropic, local llama.cpp) with automatic fallback
- Telegram and Discord two-way messaging bridges
- BridgeManager lifecycle with Cortex routing and Pulse event forwarding

**Orchestration (2 modules)**

- Council -- multi-agent deliberation with structured debate and preserved dissent
- Autonomic -- earned autonomous action with per-domain trust boundaries

**Network Layer (2 modules)**

- Collective -- distributed state sync with noise-injected privacy
- Legacy -- knowledge crystallization into frameworks and playbooks

**Advanced Intelligence (3 modules)**

- Specter -- pre-decision stress testing with adversarial analysis
- Serendipity -- anti-optimization for cross-domain connection discovery
- Forge -- autonomous negotiation with escalation guardrails

**Action Layer (5 modules)**

- Wraith -- ephemeral async micro-agent spawner with death clocks
- Echo -- behavioral fingerprinting per domain
- Sigil -- severity-prioritized ambient threat radar
- Herald -- A2A agent communication with reputation tracking (requires `--network`)
- Weave -- social graph intelligence with relationship health tracking

**Intelligence Layer (3 modules)**

- Atlas -- SQLite-backed temporal knowledge graph with confidence decay
- Prism -- tag-based cross-domain synthesis
- Cipher -- source trust registry with provenance chains and conflict detection

**Perception Layer (2 modules)**

- Oracle -- keyword-weighted anticipatory trigger engine
- Sentry -- real-time cognitive state model

**Kernel (5 components)**

- Cortex -- keyword-scored message router with permission enforcement
- Engram -- three-tier memory (working, episodic FTS5, semantic vector)
- Pulse -- async pub/sub message bus with priority queuing
- Chronicle -- immutable append-only audit trail (SQLite WAL)
- Aegis -- graduated trust engine (0-100) with outcome-based adjustment

804 tests. Apache 2.0 licensed.

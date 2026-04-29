---
title: "Roadmap"
description: "Where NEXUS is headed -- planned features, priorities, and open questions"
sidebar:
  order: 7
---

## Roadmap

NEXUS v0.1.0 ships with 51 modules, 804 tests, and a documentation site. Here's what's next.

---

### Near Term

**Plugin System Hardening**

The community module ecosystem (Validator, Registry, Installer) is functional but needs stress testing with real third-party modules. Priorities:

- Sandboxed module execution -- prevent community modules from accessing kernel internals at runtime, not just import time
- Dependency declaration in manifests -- modules that need `numpy` or `requests` should declare it
- Version conflict resolution when multiple community modules share dependencies

**Agent Enhancement**

The 25 agents work with pattern-based analysis and enhance with LLM. Next steps:

- Structured output formats (JSON, CSV) for agents that currently return plain text
- Agent-to-agent piping syntax in the CLI (`nexus pipe vex arbiter < code.py`)
- Confidence scoring on pattern-based results so users know when LLM enhancement would help

**Memory Improvements**

- Engram garbage collection -- working memory grows unbounded, needs TTL-based cleanup
- Semantic memory indexing performance for databases over 100K entries
- Memory export/import for backup and migration between machines

---

### Medium Term

**Web Interface**

A local web UI served from the NEXUS process. Not a cloud dashboard -- a localhost page for:

- Module status and trust scores at a glance
- Memory browser for Engram (search, browse, delete entries)
- Chronicle log viewer with filtering by module, severity, and date range
- Agent results viewer with formatted output

**Voice Interface**

Local speech-to-text (Whisper) and text-to-speech for hands-free operation. NEXUS already runs locally -- adding voice keeps the local-first property intact.

**Mobile Companion**

A lightweight mobile app that connects to your NEXUS instance over local network. Read-only initially -- check status, browse memory, review agent results. No cloud relay.

---

### Long Term

**Federated Module Marketplace**

Extend the community ecosystem into a decentralized marketplace where NEXUS instances can discover and install modules from a peer network. No central server. Module reputation scored by usage data shared via Collective.

**Distributed Workflows**

Multiple NEXUS instances collaborating on tasks -- one instance runs Vex, another runs Arbiter, results are merged. Uses Herald for coordination and Collective for state sync. Requires `--network` consent on all participating instances.

**Domain-Specific Agent Packs**

Curated collections of agents for specific domains:

- **DevOps Pack:** Vex + Bastion + Vigil + Sentinel + Gauge -- full infrastructure monitoring and security scanning
- **Finance Pack:** Ledger + Tally + Mint + Redline + Mandate -- transaction analysis through compliance
- **Research Pack:** Thesis + Flux + Quarry + Kindle + Compass -- literature review through publication

---

### Open Questions

These are design decisions that haven't been locked yet. Community input is welcome.

**Should agents be able to modify files directly?**
Currently, agents analyze and report. Wraith can execute commands, but the 25 narrow agents are read-only. Should Scaffold write files to disk? Should Carve apply refactoring suggestions? The safety tradeoff is real.

**How should multi-tenant work?**
One NEXUS instance per user, or shared instances with per-user memory partitions? The current architecture assumes single-user. Multi-tenant would need Engram partitioning, per-user Aegis trust, and Chronicle access controls.

**What's the right granularity for trust?**
Aegis currently scores trust per module. Should trust be per module per domain (e.g., Wraith trusted for file operations but not for network)? The Autonomic module already implements per-domain trust internally -- should this move to the kernel?

---

### Contributing to the Roadmap

If you want to work on any of these, or have ideas for what's missing, open an issue on [GitHub](https://github.com/AllStreets/NEXUS/issues) or jump into the discussion. Tag issues with `roadmap` for visibility.

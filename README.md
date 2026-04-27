<p align="center">
  <img src="https://img.shields.io/badge/NEXUS-v0.1.0-0d1117?style=for-the-badge&labelColor=0d1117&color=58a6ff" alt="Version"/>
  <img src="https://img.shields.io/badge/Python-3.11+-0d1117?style=for-the-badge&logo=python&logoColor=58a6ff&labelColor=0d1117" alt="Python"/>
  <img src="https://img.shields.io/badge/License-Apache_2.0-0d1117?style=for-the-badge&labelColor=0d1117&color=3fb950" alt="License"/>
  <img src="https://img.shields.io/badge/RAM-8GB_Min-0d1117?style=for-the-badge&labelColor=0d1117&color=d29922" alt="RAM"/>
  <img src="https://img.shields.io/badge/Tests-157_Passing-0d1117?style=for-the-badge&labelColor=0d1117&color=3fb950" alt="Tests"/>
  <img src="https://img.shields.io/badge/Modules-16_Built-0d1117?style=for-the-badge&labelColor=0d1117&color=58a6ff" alt="Modules"/>
</p>

<h1 align="center">N E X U S</h1>
<p align="center"><strong>Neural Executive for Unified Superintelligence</strong></p>
<p align="center"><em>An autonomous intelligence operating system that runs on your hardware, answers to no cloud, and gets smarter the longer it runs.</em></p>

---

## The Idea

Most AI tools are wrappers around an API. You send text up, you get text back, someone else stores your data.

NEXUS is the opposite. It's a microkernel — a small, stable core that loads specialized intelligence modules on demand. Everything runs locally. Your conversations, your memory, your audit trail — all on your machine, in a single SQLite database. The smallest useful configuration fits in 8GB of RAM.

Nineteen modules are planned. Sixteen are built — five kernel components, five perception/intelligence modules, and six action-layer modules with graduated trust. The architecture is designed so that a single developer can understand the entire system, and a single machine can run it.

---

## Architecture

```
                              ┌──────────┐
                              │  U S E R │
                              └────┬─────┘
                                   │
    ╔══════════════════════════════╪══════════════════════════════╗
    ║                         NEXUS KERNEL                       ║
    ║                              │                             ║
    ║                        ┌─────▼─────┐                       ║
    ║                  ┌─────┤  CORTEX   ├─────┐                 ║
    ║                  │     │ (router)   │     │                 ║
    ║                  │     └─────┬─────┘     │                 ║
    ║    ┌─────────────┼───────────┼───────────┼──────────┐      ║
    ║    │             │           │           │          │      ║
    ║  ┌─▼──────┐  ┌──▼───┐  ┌───▼─────┐  ┌──▼────┐  ┌─▼───┐  ║
    ║  │ ENGRAM │  │PULSE │  │CHRONICLE│  │ AEGIS │  │ LLM │  ║
    ║  │(memory)│  │(bus) │  │ (audit) │  │(trust)│  │(inf.)│  ║
    ║  └─┬──┬─┬─┘  └──────┘  └─────────┘  └───────┘  └─────┘  ║
    ║    │  │ │                                                  ║
    ║  ┌─▼┐┌▼──┐┌─▼───┐        Trust: 0━━━━━━━━━━━100          ║
    ║  │W ││Ep.││Sem. │        Earned autonomy per module       ║
    ║  │  ││FTS││ vec │        Outcome-based adjustment          ║
    ║  └──┘└───┘└─────┘        Logged to Chronicle              ║
    ╚════════════════════════════════════════════════════════════╝
         │           │           │           │           │
    ┌────▼────┐ ┌────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
    │PERCEPT. │ │ INTELL. │ │ ACTION │ │ SOCIAL │ │DEFENSE │
    │         │ │         │ │        │ │        │ │        │
    │ Oracle  │ │ Atlas   │ │ Wraith │ │ Herald │ │ Sigil  │
    │ Sentry  │ │ Prism   │ │ Echo   │ │ Weave  │ │        │
    │         │ │ Cipher  │ │        │ │        │ │        │
    └─────────┘ └─────────┘ └────────┘ └────────┘ └────────┘
```

The kernel is five components, each with one job:

| Component | Role | Storage |
|-----------|------|---------|
| **Cortex** | Keyword-scored routing to 11+ modules, permission enforcement | — |
| **Engram** | Three-tier memory: working (ephemeral), episodic (FTS5), semantic (vector) | SQLite |
| **Pulse** | Async pub/sub message bus with priority queuing and wildcards | In-memory |
| **Chronicle** | Immutable audit trail — every route, response, denial, trust change | SQLite WAL |
| **Aegis** | Graduated trust engine (0-100) with outcome-based adjustment and history | SQLite |

Modules are loaded into this kernel. They don't know about each other. They communicate through Pulse. They're constrained by Aegis. They're remembered by Engram. They're accountable to Chronicle.

---

## What's Built

### Perception

| Module | What it does |
|--------|-------------|
| **Oracle** | Keyword-weighted trigger rules that fire when pattern density exceeds thresholds |
| **Sentry** | Real-time cognitive state model — focus, fatigue, stress, flow detection |

### Intelligence

| Module | What it does |
|--------|-------------|
| **Atlas** | SQLite-backed temporal knowledge graph with confidence decay on every fact |
| **Prism** | Tag-based cross-domain synthesis — finds connections across calendar, email, finance, weather |
| **Cipher** | Source trust registry, provenance chains, automatic conflict detection between sources |

### Action

| Module | What it does |
|--------|-------------|
| **Wraith** | Spawns ephemeral async micro-agents with death clocks — auto-terminate on completion or timeout |
| **Echo** | Behavioral fingerprinting — learns your writing style per domain, scores new text for voice match |
| **Sigil** | Severity-prioritized threat radar — CRITICAL through INFO, acknowledge/filter, early warning |
| **Herald** | A2A agent communication — external agent registry, reputation tracking, message history |
| **Weave** | Social graph — contact mapping, interaction tracking, relationship health, reconnection suggestions |

---

## Module Roadmap

```
    KERNEL (Batch 1) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Cortex ·········· router & orchestrator
    ├── Engram ·········· three-tier memory
    ├── Pulse ··········· priority message bus
    ├── Chronicle ······· immutable audit trail
    └── Aegis ··········· earned autonomy engine

    PERCEPTION + INTELLIGENCE (Batch 2) ━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Oracle ·········· anticipatory trigger engine
    ├── Sentry ·········· cognitive load model
    ├── Atlas ··········· living world model (knowledge graph)
    ├── Prism ··········· cross-domain synthesis
    └── Cipher ·········· trust-scored information

    ACTION (Batch 3) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Wraith ·········· phantom agent spawner (death clocks)
    ├── Echo ············ behavioral fingerprinting
    ├── Sigil ··········· ambient threat radar
    ├── Herald ·········· A2A agent communication
    ├── Weave ··········· social graph intelligence
    └── Aegis ·········· graduated trust (0-100, outcome-based)

    ADVANCED INTELLIGENCE (Batch 4) ━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Specter ········· adversarial red-teaming
    ├── Chronos ········· temporal branching
    ├── Dreamweaver ····· overnight synthesis
    ├── Serendipity ····· anti-optimization engine
    └── Forge ··········· autonomous negotiation

    NETWORK + PLATFORM (Batch 5) ━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Collective ······ federated learning
    ├── Legacy ·········· knowledge crystallization
    └── Nexus Site ······ community & documentation
```

---

## Quickstart

```bash
# Clone and install
git clone https://github.com/AllStreets/NEXUS.git
cd NEXUS
pip install -e .

# Run (offline mode — no GPU required)
nexus run

# With a local LLM for full capability
llama-server -m models/qwen3-8b-q4_k_m.gguf -c 4096 --port 8384
nexus run
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `nexus run` | Start an interactive session |
| `nexus status` | Show system state — DB, model, port |
| `nexus allow <module>` | Grant a module permission to operate |
| `nexus deny <module>` | Revoke a module's permission |
| `nexus forget --yes` | Erase all data (GDPR Art. 17) |

---

## Hardware

NEXUS was designed for machines people actually own.

| RAM | What you get |
|-----|-------------|
| **8 GB** | Kernel + 3 modules, Qwen 3 8B Q4_K_M (~4.5 GB model) |
| **16 GB** | Kernel + 10 modules, larger context windows |
| **32 GB+** | All 19 modules, bigger models, concurrent agents |

The inference layer talks to llama.cpp over HTTP. Swap in any GGUF model. Swap in Ollama. Swap in a remote endpoint. The kernel doesn't care — it speaks one protocol.

---

## The Stack

```
    ╔══════════════════════════════════════════════════╗
    ║  Python 3.11+  ·  No heavy frameworks            ║
    ╠══════════════════════════════════════════════════╣
    ║  llama.cpp ············ local LLM inference       ║
    ║  SQLite + FTS5 ········ memory, search, audit     ║
    ║  sqlite-vec ··········· vector similarity         ║
    ║  smolagents ··········· agent orchestration       ║
    ║  Click ················ CLI interface             ║
    ║  OpenTelemetry ········ structured telemetry      ║
    ║  asyncio ·············· phantom agent lifecycle   ║
    ╠══════════════════════════════════════════════════╣
    ║  MCP ·················· local module protocol     ║
    ║  Google A2A ··········· inter-agent protocol      ║
    ╠══════════════════════════════════════════════════╣
    ║  Models: Qwen 3 · DeepSeek · Phi · Gemma         ║
    ║  (MIT / Apache 2.0 only — no Llama)               ║
    ╚══════════════════════════════════════════════════╝
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

157 tests. Under a second. No network, no mocks of external services, no flaky anything.

---

## Project Structure

```
nexus/
├── __init__.py ·········· version
├── config.py ············ XDG paths, env overrides
├── cli.py ··············· Click entry point
├── kernel/
│   ├── cortex.py ········ keyword-scored router
│   ├── engram.py ········ three-tier memory
│   ├── pulse.py ········· priority message bus
│   ├── chronicle.py ····· immutable audit trail
│   └── aegis.py ········· graduated trust engine
├── inference/
│   └── llm.py ··········· llama.cpp HTTP client
└── modules/
    ├── base.py ·········· abstract NexusModule
    ├── general.py ······· default conversation handler
    ├── oracle.py ········ anticipatory trigger engine
    ├── sentry.py ········ cognitive load model
    ├── atlas.py ········· living world model
    ├── prism.py ········· cross-domain synthesis
    ├── cipher.py ········ trust-scored information
    ├── wraith.py ········ phantom agent spawner
    ├── echo.py ·········· behavioral fingerprinting
    ├── sigil.py ········· ambient threat radar
    ├── herald.py ········ A2A agent communication
    └── weave.py ········· social graph intelligence
```

---

## Design Principles

**Local-first.** Your data never leaves your machine unless you tell it to.

**Earned autonomy.** Modules start at trust level 0. Every action outcome adjusts trust — positive results earn latitude, failures revoke it. This isn't a binary switch. It's a continuous score, per module, per domain, enforced on every call by Aegis and logged permanently by Chronicle.

**Microkernel, not monolith.** The kernel is ~500 lines across five files. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on.

**Immutable audit.** Chronicle logs every routing decision, every permission check, every module response, every trust adjustment. SOC 2 and HIPAA exportable by design. You can always answer: *why did the system do that?*

**Model-agnostic.** Qwen, DeepSeek, Phi, Gemma — anything served over HTTP works. No vendor lock-in. No API keys required.

**Anti-fragile.** The system includes a threat radar (Sigil), behavioral fingerprinting (Echo), trust-scored information (Cipher), and an upcoming adversarial red-team agent (Specter). NEXUS is designed to make the user more robust, not more dependent.

---

## License

Apache 2.0. Use it, fork it, ship it. The core will always be open.

Optional modules with GPL dependencies (like Forge/NegMAS) ship as separate packages to keep the core clean.

---

<p align="center"><sub>Built by <a href="https://github.com/AllStreets">Connor Evans</a></sub></p>

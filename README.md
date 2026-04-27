<p align="center">
  <img src="https://img.shields.io/badge/NEXUS-v0.1.0-0d1117?style=for-the-badge&labelColor=0d1117&color=58a6ff" alt="Version"/>
  <img src="https://img.shields.io/badge/Python-3.11+-0d1117?style=for-the-badge&logo=python&logoColor=58a6ff&labelColor=0d1117" alt="Python"/>
  <img src="https://img.shields.io/badge/License-Apache_2.0-0d1117?style=for-the-badge&labelColor=0d1117&color=3fb950" alt="License"/>
  <img src="https://img.shields.io/badge/RAM-8GB_Min-0d1117?style=for-the-badge&labelColor=0d1117&color=d29922" alt="RAM"/>
  <img src="https://img.shields.io/badge/Tests-49_Passing-0d1117?style=for-the-badge&labelColor=0d1117&color=3fb950" alt="Tests"/>
</p>

<h1 align="center">N E X U S</h1>
<p align="center"><strong>Neural Executive for Unified Superintelligence</strong></p>
<p align="center"><em>An autonomous intelligence operating system that runs on your hardware, answers to no cloud, and gets smarter the longer it runs.</em></p>

---

## The Idea

Most AI tools are wrappers around an API. You send text up, you get text back, someone else stores your data.

NEXUS is the opposite. It's a microkernel — a small, stable core that loads specialized intelligence modules on demand. Everything runs locally. Your conversations, your memory, your audit trail — all on your machine, in a single SQLite database. The smallest useful configuration fits in 8GB of RAM.

Nineteen modules are planned. Five kernel components are built. The architecture is designed so that a single developer can understand the entire system, and a single machine can run it.

---

## Architecture

```
                         ┌─────────────────────────────────┐
                         │            U S E R              │
                         └────────────────┬────────────────┘
                                          │
                                    ┌─────▼─────┐
                              ┌─────┤  CORTEX   ├─────┐
                              │     │  (router)  │     │
                              │     └─────┬─────┘     │
                    ┌─────────┼───────────┼───────────┼─────────┐
                    │         │           │           │         │
              ┌─────▼────┐ ┌──▼───┐ ┌────▼────┐ ┌───▼───┐ ┌──▼───┐
              │  ENGRAM  │ │PULSE │ │CHRONICLE│ │ AEGIS │ │ LLM  │
              │ (memory) │ │(bus) │ │ (audit) │ │(trust)│ │(infer)│
              └──┬──┬──┬─┘ └──────┘ └─────────┘ └───────┘ └──────┘
                 │  │  │
        ┌────────┘  │  └────────┐
        │           │           │
   ┌────▼────┐ ┌───▼────┐ ┌───▼─────┐
   │Working  │ │Episodic│ │Semantic │
   │ Memory  │ │ Memory │ │ Memory  │
   │ (dict)  │ │ (FTS5) │ │(vectors)│
   └─────────┘ └────────┘ └─────────┘
```

The kernel is five components, each with one job:

| Component | Role | Storage |
|-----------|------|---------|
| **Cortex** | Routes input to the right module, enforces permissions | — |
| **Engram** | Three-tier memory: working (ephemeral), episodic (searchable), semantic (vector) | SQLite + FTS5 |
| **Pulse** | Async pub/sub message bus with priority queuing and wildcards | In-memory |
| **Chronicle** | Immutable audit trail for every action the system takes | SQLite WAL |
| **Aegis** | Permission gating — modules must earn the right to act | SQLite |

Modules are loaded into this kernel. They don't know about each other. They communicate through Pulse. They're constrained by Aegis. They're remembered by Engram. They're accountable to Chronicle.

---

## Module Roadmap

```
    KERNEL (Batch 1) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Cortex ·········· router & orchestrator
    ├── Engram ·········· three-tier memory
    ├── Pulse ··········· priority message bus
    ├── Chronicle ······· immutable audit trail
    └── Aegis ··········· earned autonomy engine

    PERCEPTION (Batch 2) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Oracle ·········· anticipatory intelligence
    ├── Sentry ·········· emotional state detection
    ├── Echo ············ behavioral fingerprinting
    └── Sigil ··········· ambient threat radar

    INTELLIGENCE (Batch 3) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Prism ··········· cross-domain synthesis
    ├── Chronos ········· temporal branching
    ├── Atlas ··········· persistent world model
    ├── Cipher ·········· trust-scored information
    └── Dreamweaver ····· overnight synthesis

    ACTION (Batch 4) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Specter ········· adversarial red-teaming
    ├── Wraith ·········· phantom task agents
    ├── Forge ··········· autonomous negotiation
    └── Serendipity ····· anti-optimization engine

    NETWORK (Batch 5) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    ├── Herald ·········· A2A agent communication
    ├── Weave ··········· social graph intelligence
    ├── Collective ······ federated learning
    └── Legacy ·········· knowledge crystallization
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
    ╔══════════════════════════════════════════╗
    ║  Python 3.11+  ·  No heavy frameworks    ║
    ╠══════════════════════════════════════════╣
    ║  llama.cpp ········ local inference       ║
    ║  SQLite + FTS5 ···· memory & search       ║
    ║  sqlite-vec ······· vector similarity     ║
    ║  smolagents ······· agent orchestration   ║
    ║  Click ············ CLI interface         ║
    ║  OpenTelemetry ···· structured telemetry  ║
    ╠══════════════════════════════════════════╣
    ║  MCP ·············· local protocol        ║
    ║  Google A2A ······· inter-agent protocol  ║
    ╠══════════════════════════════════════════╣
    ║  Models: Qwen 3 · DeepSeek · Phi · Gemma ║
    ║  (MIT / Apache 2.0 only — no Llama)       ║
    ╚══════════════════════════════════════════╝
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

49 tests. Under a second. No network, no mocks of external services, no flaky anything.

---

## Project Structure

```
nexus/
├── __init__.py ·········· version
├── config.py ············ XDG paths, env overrides
├── cli.py ··············· Click entry point
├── kernel/
│   ├── cortex.py ········ router & orchestrator
│   ├── engram.py ········ three-tier memory
│   ├── pulse.py ········· priority message bus
│   ├── chronicle.py ····· immutable audit trail
│   └── aegis.py ········· permission engine
├── inference/
│   └── llm.py ··········· llama.cpp HTTP client
└── modules/
    ├── base.py ·········· abstract NexusModule
    └── general.py ······· default conversation handler
```

---

## Design Principles

**Local-first.** Your data never leaves your machine unless you tell it to.

**Earned autonomy.** Modules start with zero trust. They prove reliability before the system grants them more latitude. This isn't a safety theater checkbox — it's a runtime property enforced by Aegis on every call.

**Microkernel, not monolith.** The kernel is ~500 lines across five files. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on.

**Immutable audit.** Chronicle logs every routing decision, every permission check, every module response. SOC 2 and HIPAA exportable by design. You can always answer the question: *why did the system do that?*

**Model-agnostic.** Qwen, DeepSeek, Phi, Gemma — anything served over HTTP works. No vendor lock-in. No API keys required.

---

## License

Apache 2.0. Use it, fork it, ship it. The core will always be open.

Optional modules with GPL dependencies (like Forge/NegMAS) ship as separate packages to keep the core clean.

---

<p align="center"><sub>Built by <a href="https://github.com/AllStreets">Connor Evans</a></sub></p>

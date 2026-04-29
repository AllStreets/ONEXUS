<p align="center">
  <img src="https://img.shields.io/badge/NEXUS-v0.1.0-blue?style=for-the-badge" alt="Version"/>&nbsp;<img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>&nbsp;<img src="https://img.shields.io/badge/License-Apache_2.0-green?style=for-the-badge" alt="License"/>&nbsp;<img src="https://img.shields.io/badge/RAM-8GB_Min-yellow?style=for-the-badge" alt="RAM"/>&nbsp;<img src="https://img.shields.io/badge/Tests-1300+-green?style=for-the-badge" alt="Tests"/>&nbsp;<img src="https://img.shields.io/badge/Modules-51_Built-blue?style=for-the-badge" alt="Modules"/>
</p>

<p align="center">
  <a href="https://allstreets.github.io/NEXUS/">
    <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=700&size=64&duration=1&pause=99999&color=00D4FF&center=true&vCenter=true&width=650&height=100&lines=N+E+X+U+S" alt="NEXUS"/>
  </a>
</p>
<p align="center"><strong>Neural Executive for Unified Superintelligence</strong></p>
<p align="center"><em>An autonomous intelligence operating system that runs on your hardware, answers to no cloud, and gets smarter the longer it runs.</em></p>

---

## The Idea

Most AI tools are wrappers around an API. You send text up, you get text back, someone else stores your data.

NEXUS is the opposite. It's a microkernel -- a small, stable core that loads specialized intelligence on demand. Everything runs local. Your conversations, your memory, your audit trail -- all on your machine, in a single SQLite database. The smallest useful configuration fits in 8GB of RAM.

The system has two kinds of intelligence: **modules** and **agents**.

**Modules** are persistent intelligence components -- perception, reasoning, memory, social awareness. They run continuously, subscribe to system events, and maintain state across sessions. They are the nervous system. Twenty-six modules handle everything from anticipatory triggering (Oracle) to self-reflective awareness (Consciousness) to seven-framework ethical analysis (Ethical Prism).

**Agents** are task specialists with **graduated sovereignty** -- the first AI architecture where agents start as passive, invocable skills and *earn* autonomy through demonstrated reliability. Every agent begins at trust level 0 (SKILL: user must invoke explicitly). As Aegis observes consistent, accurate results, trust rises through five tiers: SKILL, ADVISOR (proactive suggestions), MONITOR (background event watching), AUTONOMOUS (acts within boundaries without asking), and SOVEREIGN (coordinates with other agents independently). Trust is always revocable. One bad outcome and Aegis dials it back. Twenty-five agents cover code analysis, data pipelines, financial modeling, content generation, and infrastructure monitoring -- each works standalone using pattern-based analysis (no LLM required) and enhances with LLM when available.

This is not prompt chaining, not tool use, not a wrapper around someone else's API. This is an operating system for intelligence with earned autonomy baked into every layer -- a design that has no direct precedent in open-source AI. The architecture is designed so that a single developer can understand the entire system, and a single machine can run it.

---

## Architecture

```
                          ┌──────────┐
                          │   USER   │
                          └────┬─────┘
                               │
  ╔═════════════════════════════════════════════════════════╗
  ║                     NEXUS KERNEL                        ║
  ║                            │                            ║
  ║                      ┌─────V─────┐                      ║
  ║                ┌─────┤  CORTEX   ├─────┐                ║
  ║                │     │ (router)  │     │                ║
  ║                │     └─────┬─────┘     │                ║
  ║  ┌─────────────┼───────────┼───────────┼──────┐         ║
  ║  │             │           │           │      │         ║
  ║  ┌───────┐ ┌───────┐ ┌─────────┐ ┌──────┐ ┌─────┐       ║
  ║  │ENGRAM │ │ PULSE │ │CHRONICL.│ │AEGIS │ │ LLM │       ║
  ║  │ (mem) │ │ (bus) │ │ (audit) │ │(trst)│ │(inf)│       ║
  ║  └───────┘ └───────┘ └─────────┘ └──────┘ └─────┘       ║
  ║  ┌──┐┌───┐┌─────┐   Trust: 0━━━━━━━━━━━100              ║
  ║  │W ││Ep.││Sem. │   Earned autonomy per module          ║
  ║  │  ││FTS││ vec │   Outcome-based adjustment            ║
  ║  └──┘└───┘└─────┘   Logged to Chronicle                 ║
  ╚═════════════════════════════════════════════════════════╝
       │           │          │          │          │
  ┌────V───┐  ┌────V───┐ ┌────V───┐ ┌────V───┐ ┌────V───┐
  │PERCEPT.│  │INTELL. │ │ ACTION │ │ SOCIAL │ │DEFENSE │
  │        │  │        │ │        │ │        │ │        │
  │ Oracle │  │ Atlas  │ │ Wraith │ │ Herald │ │ Sigil  │
  │ Sentry │  │ Prism  │ │  Echo  │ │ Weave  │ │        │
  │        │  │ Cipher │ │        │ │        │ │        │
  └────────┘  └────────┘ └────────┘ └────────┘ └────────┘
       │           │          │
  ┌────V───────────V──────────V────────────────────────────┐
  │              ADVANCED INTELLIGENCE                     │
  │                                                        │
  │  Specter ·········· pre-decision stress test           │
  │  Serendipity ······ anti-optimization                  │
  │  Forge ············ autonomous negotiation             │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │                  ORCHESTRATION                         │
  │                                                        │
  │  Council ·········· multi-agent debate                 │
  │  Autonomic ········ earned autonomy                    │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │              NETWORK + PLATFORM                        │
  │                                                        │
  │  Collective ······· distributed state sync             │
  │  Legacy ··········· knowledge crystallization          │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │                DIFFERENTIATION                         │
  │                                                        │
  │  Dream Loop ······ background pattern discovery        │
  │  Adversarial ····· self-improvement red-teaming        │
  │  Tripwire ········ contradiction detection             │
  │  Provenance ······ reasoning chain tracer              │
  │  Sandbox ········· hypothetical simulation             │
  │  Symbiosis ······· module pathway mapping              │
  │  Consciousness ··· self-reflective awareness           │
  │  Ethical Prism ··· seven-framework ethical analysis    │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │           INFRASTRUCTURE + COMMUNITY                   │
  │                                                        │
  │  Multi-Provider ·· OpenAI, Anthropic, local fallback   │
  │  Messaging ······· Telegram, Discord two-way bridges   │
  │  Community ······· validated third-party modules       │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │              PLATFORM SERVICES                         │
  │                                                        │
  │  API Server ······ REST + WebSocket (FastAPI)          │
  │  MCP Server ······ every module as an MCP tool         │
  │  Dashboard ······· real-time dark-themed web UI        │
  │  Terminal UI ····· Rich split-pane TUI                 │
  │  Workflow Engine · DAG pipelines (YAML + Python)       │
  │  Time-Travel ····· Chronicle replay + snapshots        │
  │  Federation ······ peer-to-peer NEXUS mesh             │
  │  Multi-Modal ····· image, audio, document pipelines    │
  │  Benchmarks ······ automated accuracy testing          │
  │  Plugin SDK ······ nexus create + validator            │
  │  Marketplace ····· reputation + ratings + discovery    │
  └────────────────────────────────────────────────────────┘
       │           │
  ┌────V───────────V───────────────────────────────────────┐
  │         GRADUATED SOVEREIGNTY AGENTS (25)              │
  │         Trust: SKILL > ADVISOR > MONITOR >             │
  │                AUTONOMOUS > SOVEREIGN                  │
  │                                                        │
  │  Code ············ Vex  Arbiter  Carve  Remedy         │
  │                    Scaffold  Axiom  Rune               │
  │  Data ············ Flux  Vigil  Gauge  Quarry  Loom    │
  │  Business ········ Ledger  Tally  Mint  Redline        │
  │                    Mandate                             │
  │  Content ········· Scribe  Kindle  Thesis  Compass     │
  │  Ops ············· Bastion  Dispatch  Sentinel         │
  │                    Mnemonic                            │
  └────────────────────────────────────────────────────────┘
```

The kernel is five components, each with one job:

| Component | Role | Storage |
|-----------|------|---------|
| **Cortex** | Keyword-scored routing to 51 modules, permission enforcement | -- |
| **Engram** | Three-tier memory: working (ephemeral), episodic (FTS5), semantic (vector) | SQLite |
| **Pulse** | Async pub/sub message bus with priority queuing and wildcards | In-memory |
| **Chronicle** | Immutable audit trail -- every route, response, denial, trust change | SQLite WAL |
| **Aegis** | Graduated trust engine (0-100) with outcome-based adjustment and history | SQLite |

Modules and agents are loaded into this kernel. They don't know about each other. They communicate through Pulse. They're constrained by Aegis. They're remembered by Engram. They're accountable to Chronicle. Agents additionally earn autonomy through graduated sovereignty -- Aegis tracks each agent's trust score independently and unlocks capabilities tier by tier.

---

## What's Built

### Perception

| Module | What it does |
|--------|-------------|
| **Oracle** | Keyword-weighted trigger rules that fire when pattern density exceeds thresholds |
| **Sentry** | Real-time cognitive state model -- focus, fatigue, stress, flow detection |

### Intelligence

| Module | What it does |
|--------|-------------|
| **Atlas** | SQLite-backed temporal knowledge graph with confidence decay on every fact |
| **Prism** | Tag-based cross-domain synthesis -- finds connections across calendar, email, finance, weather |
| **Cipher** | Source trust registry, provenance chains, automatic conflict detection between sources |

### Action

| Module | What it does |
|--------|-------------|
| **Wraith** | Spawns ephemeral async micro-agents with death clocks -- auto-terminate on completion or timeout |
| **Echo** | Behavioral fingerprinting -- learns your writing style per domain, scores new text for voice match |
| **Sigil** | Severity-prioritized threat radar -- CRITICAL through INFO, acknowledge/filter, early warning |
| **Herald** | A2A agent communication -- external agent registry, reputation tracking, message history (requires `--network`) |
| **Weave** | Social graph -- contact mapping, interaction tracking, relationship health, reconnection suggestions |

### Advanced Intelligence

| Module | What it does |
|--------|-------------|
| **Specter** | Pre-decision stress test -- counter-arguments, failure modes, hidden assumptions, worst-case scenarios |
| **Serendipity** | Anti-optimization -- inverted relevance scoring to surface surprising cross-domain connections |
| **Forge** | Autonomous negotiation -- multi-round structured bargaining with escalation guardrails |

### Orchestration

| Module | What it does |
|--------|-------------|
| **Council** | Multi-agent deliberation -- structured multi-round debate across modules with synthesized recommendations and preserved dissent |
| **Autonomic** | Earned autonomous action -- observes patterns, learns routines, and acts within per-domain trust boundaries with retreat on failure |

### Network + Platform (requires `--network` consent)

| Module | What it does |
|--------|-------------|
| **Collective** | Distributed state synchronization -- peer registry with local model aggregation and noise-injected privacy. Shares only noise-injected aggregates, never raw data. |
| **Legacy** | Knowledge crystallization -- distills decisions into frameworks, playbooks, and exportable artifacts (local-only) |

### Multi-Provider Inference

| Component | What it does |
|-----------|-------------|
| **InferenceProvider** | Abstract base -- any provider implements `infer()` and `health()` |
| **LocalProvider** | llama.cpp HTTP client, ChatML conversion, zero-dependency local inference |
| **OpenAIProvider** | OpenAI SDK wrapper, native messages format, configurable model |
| **AnthropicProvider** | Anthropic SDK wrapper, system message separation per API contract |
| **ProviderRouter** | Named provider registry, per-request routing, automatic fallback on unhealthy |

Set `NEXUS_DEFAULT_PROVIDER`, `NEXUS_OPENAI_KEY`, `NEXUS_ANTHROPIC_KEY` to configure. Local provider is always available as fallback.

### Messaging Integrations

| Component | What it does |
|-----------|-------------|
| **MessageBridge** | Abstract base for platform integrations -- start, stop, send, on_message |
| **TelegramBridge** | Two-way Telegram messaging with chat ID allowlisting |
| **DiscordBridge** | Two-way Discord messaging with channel ID allowlisting, bot loop prevention |
| **BridgeManager** | Lifecycle manager -- routes inbound to Cortex, forwards Pulse `notify.*` events outbound |

Set `NEXUS_TELEGRAM_TOKEN`, `NEXUS_TELEGRAM_CHAT_IDS`, `NEXUS_DISCORD_TOKEN`, `NEXUS_DISCORD_CHANNEL_IDS` to configure.

### Differentiation

| Module | What it does |
|--------|-------------|
| **Dream Loop** | Background pattern discovery -- replays recent memories through the LLM to find recurring themes and insights |
| **Adversarial** | Red-teams the system's own behavior -- analyzes Chronicle logs for failures, blind spots, and improvement opportunities |
| **Tripwire** | Cognitive tripwires -- monitors decision history for contradictions, inconsistencies, and drift |
| **Provenance** | Reasoning chain tracer -- reconstructs the full reasoning path behind any past decision from Chronicle events |
| **Sandbox** | Temporal sandbox -- simulates hypothetical scenarios without modifying real memory or state |
| **Symbiosis** | Module pathway mapping -- tracks which modules route to each other and discovers emergent collaboration patterns |
| **Consciousness** | Self-reflective awareness -- journal introspection on cognitive state plus emergent goal detection |
| **Ethical Prism** | Seven-framework ethical analysis -- evaluates decisions through Utilitarian, Deontological, Virtue Ethics, Care Ethics, Contractualist, Rights-Based, and Pragmatic Ethics lenses with synthesis |

### Community Ecosystem

| Component | What it does |
|-----------|-------------|
| **ModuleValidator** | Validates community module structure, manifest schema, file layout, and kernel import restrictions |
| **ModuleRegistry** | JSON-backed module catalog with search by name, author, description, and keywords |
| **ModuleInstaller** | Installs/uninstalls community modules, registers routing keywords in Cortex automatically |
| **GitHub CI** | PR validation and post-merge registry rebuild workflows |

Community modules live in `community/modules/<author>/<name>/` with a manifest, module code, tests, and README. See `community/CONTRIBUTING.md`.

### Graduated Sovereignty Agents

Twenty-five task-specialist agents built on the AgentModule base class. Each starts as a passive skill (trust 0) and earns autonomy through demonstrated reliability. Every agent implements four tier methods: `analyze()` (always), `suggest()` (ADVISOR+), `monitor()` (MONITOR+), and `coordinate()` (SOVEREIGN). Each works standalone using pattern-based analysis (no LLM required) and enhances with LLM when available.

#### Code & Development

| Agent | What it does |
|-------|-------------|
| **Vex** | Scans code for 28 vulnerability patterns -- injection, XSS, credentials, deserialization |
| **Arbiter** | Reviews code diffs and source for quality issues, style violations, anti-patterns |
| **Carve** | Measures complexity, finds long functions, deep nesting, duplicate code |
| **Remedy** | Diagnoses error messages and stack traces, suggests fixes for 17 common types |
| **Scaffold** | Generates Python, FastAPI, CLI project boilerplate from templates |
| **Axiom** | Generates test case stubs with edge cases from function signatures |
| **Rune** | Builds, explains, and tests regex patterns from natural language descriptions |

#### Data & Analysis

| Agent | What it does |
|-------|-------------|
| **Flux** | Converts natural language questions into SQL queries with schema awareness |
| **Vigil** | Parses log files, detects anomaly patterns, generates incident timelines |
| **Gauge** | Analyzes performance metrics, identifies bottlenecks in latency/CPU/memory |
| **Quarry** | Extracts structured data from HTML -- links, headings, tables, metadata |
| **Loom** | Defines ETL pipelines with dependency resolution and topological ordering |

#### Business & Finance

| Agent | What it does |
|-------|-------------|
| **Ledger** | Categorizes bank transactions, generates spending summaries, flags anomalies |
| **Tally** | Builds financial projections with revenue modeling and runway calculation |
| **Mint** | Generates invoices from line items with tax calculation and formatting |
| **Redline** | Scans contracts for 15 risky clause patterns and missing protections |
| **Mandate** | Assesses compliance against GDPR, SOC2, HIPAA, PCI-DSS with gap analysis |

#### Content & Communication

| Agent | What it does |
|-------|-------------|
| **Scribe** | Summarizes meeting transcripts -- participants, action items, decisions |
| **Kindle** | Expands bullet points into polished blog posts, docs, reports, emails |
| **Thesis** | Analyzes academic papers -- claims, methodology, limitations, gaps |
| **Compass** | Generates personalized learning roadmaps for programming languages |

#### Infrastructure & Ops

| Agent | What it does |
|-------|-------------|
| **Bastion** | Scans API endpoints for BOLA, auth gaps, mass assignment, OWASP risks |
| **Dispatch** | Routes notifications to email, Slack, webhook, SMS by priority rules |
| **Sentinel** | Monitors cron jobs, explains expressions, detects missed runs |
| **Mnemonic** | Personal knowledge base with keyword search and auto-tagging |

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

    ADVANCED INTELLIGENCE (Batch 4) ━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Specter ········· pre-decision stress test
    ├── Serendipity ····· anti-optimization engine
    └── Forge ··········· autonomous negotiation

    NETWORK + PLATFORM (Batch 5) ━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Collective ······ distributed state sync
    └── Legacy ·········· knowledge crystallization

    ORCHESTRATION (Batch 6) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Council ·········· multi-agent deliberation
    └── Autonomic ········ earned autonomous action

    INFRASTRUCTURE (Batch 7a) ━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Multi-Provider ·· OpenAI, Anthropic, local fallback
    └── Messaging ······· Telegram, Discord two-way bridges

    DIFFERENTIATION (Batch 7b) ━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Dream Loop ······ background pattern discovery
    ├── Adversarial ····· self-improvement red-teaming
    ├── Tripwire ········ contradiction detection
    ├── Provenance ······ reasoning chain tracer
    ├── Sandbox ········· hypothetical simulation
    ├── Symbiosis ······· module pathway mapping
    ├── Consciousness ··· self-reflective awareness + goal detection
    └── Ethical Prism ··· seven-framework ethical analysis

    COMMUNITY ECOSYSTEM (Batch 7b) ━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Validator ······· manifest + structure checks
    ├── Registry ········ searchable module catalog
    ├── Installer ······· install/uninstall + keyword wiring
    └── GitHub CI ······· PR validation + registry rebuild

    GRADUATED SOVEREIGNTY AGENTS (Batch 8) ━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Scribe ·········· meeting transcript summarizer
    ├── Vex ············· static vulnerability scanner
    ├── Ledger ·········· financial transaction categorizer
    ├── Arbiter ········· AI code review agent
    ├── Thesis ·········· academic paper analyzer
    ├── Scaffold ········ project boilerplate generator
    ├── Remedy ·········· error & stack trace diagnoser
    ├── Compass ········· learning roadmap generator
    ├── Tally ··········· financial projection builder
    ├── Redline ········· contract risk analyzer
    ├── Carve ··········· code refactoring assistant
    ├── Vigil ··········· log analysis agent
    ├── Mandate ········· compliance gap analyzer
    ├── Flux ············ natural language to SQL
    ├── Kindle ·········· content expansion agent
    ├── Quarry ·········· web data extraction
    ├── Bastion ········· API security scanner
    ├── Dispatch ········ multi-channel notification router
    ├── Gauge ··········· performance metrics analyzer
    ├── Mnemonic ········ knowledge base agent
    ├── Sentinel ········ scheduled task monitor
    ├── Mint ············ invoice generator
    ├── Axiom ··········· test case generator
    ├── Loom ············ data pipeline builder
    └── Rune ············ regex builder & explainer

    PLATFORM SERVICES (Batch 9) ━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── API Server ······ REST + WebSocket (FastAPI)
    ├── Dashboard ······· real-time dark-themed web UI
    ├── Terminal UI ····· Rich split-pane TUI
    ├── MCP Server ······ every module as an MCP tool
    ├── Workflow Engine · DAG pipelines (YAML + Python)
    ├── Time-Travel ····· Chronicle replay + snapshots
    ├── Federation ······ peer-to-peer NEXUS mesh
    ├── Multi-Modal ····· image, audio, document pipelines
    ├── Benchmarks ······ automated accuracy testing (51 cases)
    ├── Plugin SDK ······ nexus create + validator
    └── Marketplace ····· reputation + ratings + discovery

    NEXUS SITE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    └── Community site ·· documentation & module catalog
```

---

## Quickstart

```bash
# Clone and install
git clone https://github.com/AllStreets/NEXUS.git
cd NEXUS
pip install -e .

# Run (offline mode -- no GPU required)
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
| `nexus tui` | Launch the Rich terminal UI |
| `nexus serve` | Start the REST/WebSocket API server |
| `nexus status` | Show system state -- DB, model, port |
| `nexus allow <module>` | Grant a module permission to operate |
| `nexus deny <module>` | Revoke a module's permission |
| `nexus forget --yes` | Erase all data (GDPR Art. 17) |
| `nexus benchmark` | Run agent accuracy benchmarks |
| `nexus create module <name>` | Scaffold a new module |
| `nexus create agent <name>` | Scaffold a new agent |
| `nexus validate <path>` | Validate a module/agent package |
| `nexus install <author/module>` | Install a community module |
| `nexus uninstall <module>` | Uninstall a community module |
| `nexus community list` | List available community modules |
| `nexus community search <query>` | Search community modules |
| `nexus community browse` | Browse the marketplace |
| `nexus community info <name>` | Package details and ratings |
| `nexus community rate <name> <n>` | Rate a package (1-5) |
| `nexus community stats` | Marketplace statistics |

---

## Build Your Own

NEXUS has two extensibility paths -- modules and agents. Both get full kernel access (memory, audit, trust, events, inference). Both use keyword routing through Cortex. The difference is how they earn autonomy.

### Build a Module

Modules are persistent intelligence components. Extend `NexusModule`, implement `handle()`, register routing keywords in Cortex.

```python
from nexus.modules.base import NexusModule

class SummarizerModule(NexusModule):
    name = "summarizer"
    description = "Summarizes text using the local LLM."
    version = "1.0.0"

    async def handle(self, message: str, context: dict) -> str:
        prompt = f"Summarize concisely:\n\n{message}"
        return await context["llm"].complete(prompt)
```

Five steps: create the file, register keywords, write tests, run tests, `nexus allow summarizer`. Full guide: [Build a Module](https://allstreets.github.io/NEXUS/guides/building-a-module/).

### Build an Agent

Agents are task specialists with graduated sovereignty. Extend `AgentModule`, implement four tier methods. Agents start at trust 0 and earn autonomy through demonstrated reliability.

```python
from nexus.agents.base import AgentModule, TrustTier

class ScannerAgent(AgentModule):
    name = "scanner"
    description = "Scans directories for file patterns."
    version = "0.1.0"

    watch_events = ["filesystem.changed"]
    coordination_targets = ["vigil", "vex"]

    async def analyze(self, message, context):
        """Core logic. Runs at every trust level."""
        return f"[scanner] Scanning: {message}"

    async def suggest(self, message, context):
        """Proactive suggestions at ADVISOR+ trust (25+)."""
        return "Consider filtering by file extension."

    async def monitor(self, event, context):
        """Background event watching at MONITOR+ trust (50+)."""
        return "Detected file change activity"

    async def coordinate(self, result, context):
        """Cross-agent routing at SOVEREIGN trust (100)."""
        return ""
```

Trust tiers unlock progressively: SKILL (0) -- ADVISOR (25) -- MONITOR (50) -- AUTONOMOUS (75) -- SOVEREIGN (100). Trust is always revocable. Full guide: [Build an Agent](https://allstreets.github.io/NEXUS/guides/building-an-agent/).

---

## Platform Services

Eleven systems that turn NEXUS from a CLI tool into infrastructure.

### API Server

`nexus serve` starts a FastAPI server exposing the full kernel over REST + WebSocket. Every kernel operation has an endpoint: message routing, module management, memory queries, trust scoring, Chronicle audit, and real-time Pulse event streaming over WebSocket. CORS-enabled for dashboard access.

### Live Dashboard

A dark-themed real-time web dashboard at `/dashboard`. Trust gauges with animated SVG arcs and glow effects, live Pulse event stream over WebSocket, Chronicle audit timeline, module status panel, and an interactive message console. Glassmorphism cards, cyan/purple accents, JetBrains Mono typography. No React, no npm, no build step -- pure vanilla HTML/CSS/JS.

### Terminal UI

`nexus tui` launches a Rich-based split-pane terminal interface. Four quadrants: active modules with colored trust bars, conversation history, live Pulse events, and Chronicle entries. Dark theme with the same color system as the dashboard. An alternative to the basic `nexus run` prompt.

### MCP Server

Every NEXUS module and agent exposed as an MCP tool. Connect Claude Desktop, Cursor, VS Code, or any MCP client and NEXUS becomes the backend brain. Twelve tools (`nexus_message`, `nexus_route`, `nexus_memory_store`, `nexus_memory_query`, `nexus_trust_check`, and more), four resources (`nexus://modules`, `nexus://agents`, `nexus://trust`, `nexus://config`), and three built-in prompts.

### Workflow Engine

DAG-based pipelines that chain modules and agents into multi-step workflows. Define in YAML or Python. Steps reference outputs of dependencies via `{step_name.output}`, support conditional execution, three error policies (stop/skip/continue), and timeout enforcement. Four built-in workflows: `security_scan`, `code_review`, `data_pipeline`, `incident_response`. Full Chronicle logging and Pulse events at every step.

### Time-Travel Replay

Pick any point in NEXUS history and reconstruct the exact system state: which modules were active, what trust scores were, how messages were routed, what memory was accessed. Snapshot diffs compare two points in time. Session replay reconstructs full conversations. Trust history shows every score change with tier transitions highlighted. All powered by Chronicle's existing audit data -- stores nothing new.

### Federation

NEXUS-to-NEXUS peer communication. Instances discover each other (manual URL or local network scan), exchange capability listings, and route requests across the mesh. HMAC-SHA256 request signing, per-peer rate limiting, peer trust independent from module trust. All outbound data logged to Chronicle. Disabled by default -- opt-in via `NEXUS_FEDERATION_ENABLED=true`.

### Multi-Modal Input

Image, audio, and document processing pipelines that convert non-text inputs into text representations for module routing. PNG/JPEG header parsing, WAV/FLAC metadata extraction, CSV/JSON/HTML/PDF text extraction -- all using stdlib only (no external dependencies). LLM-enhanced when a vision or speech model is available. `MultiModalCortex` bridges processing with Cortex routing.

### Benchmarks

Automated accuracy testing across 51 benchmark cases covering 10 agents. Three suites (security, code, data) measure pattern detection accuracy, response time (`time.perf_counter()`), and memory usage (`tracemalloc`). Reports in terminal, Markdown, or JSON. `nexus benchmark --suite security --format markdown`.

### Plugin SDK

`nexus create module <name>` and `nexus create agent <name>` generate complete file structures: code with proper base class, manifest.json, test stubs, README. `nexus validate <path>` catches missing files, wrong base class, kernel imports, insufficient tests. Zero-friction path from idea to submittable PR.

### Agent Marketplace

Enhanced community registry with reputation scores, download tracking, star ratings, trending detection, and recommendations. Browse by category, sort by downloads/rating/trust, search with filters. `nexus community browse --category code --sort downloads`. Reputation calculated from weighted formula: 40% rating, 30% downloads, 20% trust score, 10% freshness. Badges: verified, popular, trusted, top-rated, new.

---

## Hardware

NEXUS was designed for machines people actually own.

| RAM | What you get |
|-----|-------------|
| **8 GB** | Kernel + 3 modules, Qwen 3 8B Q4_K_M (~4.5 GB model) |
| **16 GB** | Kernel + 10 modules, larger context windows |
| **32 GB+** | All 51 modules, bigger models, concurrent agents |

The inference layer supports multiple providers. Local models run via llama.cpp over HTTP. Cloud providers (OpenAI, Anthropic) are available when API keys are configured. The kernel routes to whichever provider you choose, with automatic fallback if one goes down.

---

## The Stack

```
  ╔════════════════════════════════════════════════════════════╗
  ║  Python 3.11+  ·  No heavy frameworks                      ║
  ╠════════════════════════════════════════════════════════════╣
  ║  llama.cpp ············ local LLM inference                ║
  ║  SQLite + FTS5 ········ memory, search, audit              ║
  ║  sqlite-vec ··········· vector similarity                  ║
  ║  smolagents ··········· agent orchestration                ║
  ║  Click ················ CLI interface                      ║
  ║  Rich ················· terminal UI + formatting           ║
  ║  OpenTelemetry ········ structured telemetry               ║
  ║  asyncio ·············· phantom agent lifecycle            ║
  ╠════════════════════════════════════════════════════════════╣
  ║  FastAPI ·············· REST + WebSocket API server        ║
  ║  Pydantic ············· request/response validation        ║
  ║  uvicorn ·············· ASGI server                        ║
  ╠════════════════════════════════════════════════════════════╣
  ║  OpenAI SDK ··········· cloud inference (GPT-4o, etc.)     ║
  ║  Anthropic SDK ········ cloud inference (Claude, etc.)     ║
  ║  python-telegram-bot ·· Telegram bridge                    ║
  ║  discord.py ··········· Discord bridge                     ║
  ╠════════════════════════════════════════════════════════════╣
  ║  MCP SDK ·············· Model Context Protocol server      ║
  ║  Google A2A ··········· inter-agent protocol               ║
  ║  HMAC-SHA256 ·········· federation request signing         ║
  ╠════════════════════════════════════════════════════════════╣
  ║  Local: Qwen 3 · DeepSeek · Phi · Gemma (Apache 2.0)       ║
  ║  Cloud: GPT-4o · Claude · any OpenAI/Anthropic-compat.     ║
  ╚════════════════════════════════════════════════════════════╝
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

1300+ tests across 119 test files. No network, no mocks of external services, no flaky anything.

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
│   ├── provider.py ······ InferenceProvider ABC
│   ├── local.py ········· llama.cpp HTTP client
│   ├── openai_provider.py OpenAI SDK wrapper
│   ├── anthropic_provider.py Anthropic SDK wrapper
│   ├── router.py ········ ProviderRouter with fallback
│   └── llm.py ··········· LLMClient (delegates to router)
├── messaging/
│   ├── bridge.py ········ MessageBridge ABC
│   ├── telegram.py ······ Telegram two-way bridge
│   ├── discord_bridge.py  Discord two-way bridge
│   └── manager.py ······· BridgeManager lifecycle
├── modules/
│   ├── base.py ·········· abstract NexusModule
│   ├── general.py ······· default conversation handler
│   ├── oracle.py ········ anticipatory trigger engine
│   ├── sentry.py ········ cognitive load model
│   ├── atlas.py ········· living world model
│   ├── prism.py ········· cross-domain synthesis
│   ├── cipher.py ········ trust-scored information
│   ├── wraith.py ········ phantom agent spawner
│   ├── echo.py ·········· behavioral fingerprinting
│   ├── sigil.py ········· ambient threat radar
│   ├── herald.py ········ A2A agent communication
│   ├── weave.py ········· social graph intelligence
│   ├── specter.py ······· pre-decision stress test
│   ├── serendipity.py ··· anti-optimization engine
│   ├── forge.py ········· autonomous negotiation
│   ├── collective.py ···· distributed state sync
│   ├── legacy.py ········ knowledge crystallization
│   ├── council.py ······· multi-agent deliberation
│   ├── autonomic.py ····· earned autonomous action
│   ├── dream_loop.py ···· background pattern discovery
│   ├── adversarial.py ··· self-improvement red-teaming
│   ├── tripwire.py ······ contradiction detection
│   ├── provenance.py ···· reasoning chain tracer
│   ├── sandbox.py ······· hypothetical simulation
│   ├── symbiosis.py ····· module pathway mapping
│   ├── consciousness.py · self-reflective awareness
│   └── ethical_prism.py · seven-framework ethical analysis
├── agents/
│   ├── base.py ·········· AgentModule + TrustTier (graduated sovereignty)
│   ├── vex.py ··········· static vulnerability scanner
│   ├── arbiter.py ······· AI code review agent
│   ├── carve.py ········· code refactoring assistant
│   ├── remedy.py ········ error & stack trace diagnoser
│   ├── scaffold.py ······ project boilerplate generator
│   ├── axiom.py ········· test case generator
│   ├── rune.py ·········· regex builder & explainer
│   ├── flux.py ·········· natural language to SQL
│   ├── vigil.py ········· log analysis agent
│   ├── gauge.py ········· performance metrics analyzer
│   ├── quarry.py ········ web data extraction
│   ├── loom.py ·········· data pipeline builder
│   ├── ledger.py ········ financial transaction categorizer
│   ├── tally.py ········· financial projection builder
│   ├── mint.py ·········· invoice generator
│   ├── redline.py ······· contract risk analyzer
│   ├── mandate.py ······· compliance gap analyzer
│   ├── scribe.py ········ meeting transcript summarizer
│   ├── kindle.py ········ content expansion agent
│   ├── thesis.py ········ academic paper analyzer
│   ├── compass.py ······· learning roadmap generator
│   ├── bastion.py ······· API security scanner
│   ├── dispatch.py ······ multi-channel notification router
│   ├── sentinel.py ······ scheduled task monitor
│   └── mnemonic.py ······ knowledge base agent
├── api/
│   ├── server.py ········ FastAPI app factory
│   ├── models.py ········ Pydantic request/response types
│   └── routes/
│       ├── messages.py ·· message routing endpoints
│       ├── modules.py ··· module management
│       ├── memory.py ···· Engram access
│       ├── chronicle.py · audit log queries
│       ├── trust.py ····· Aegis trust endpoints
│       ├── events.py ···· WebSocket Pulse streaming
│       ├── system.py ···· status + health checks
│       ├── dashboard.py · static file serving
│       ├── replay.py ···· time-travel endpoints
│       ├── federation.py  federation endpoints
│       ├── marketplace.py marketplace endpoints
│       └── multimodal.py  file processing endpoints
├── dashboard/
│   ├── index.html ······· single-page application
│   ├── styles.css ······· dark theme + glassmorphism
│   ├── app.js ··········· 6 live components
│   └── icons.js ········· 18 inline SVG icons
├── tui/
│   ├── app.py ··········· Rich Layout + Live display
│   ├── panels.py ········ 5 panel renderers
│   ├── theme.py ········· color system + trust bars
│   └── input_handler.py · keyboard input + history
├── mcp/
│   ├── server.py ········ MCP server + stdio transport
│   ├── tools.py ········· 12 MCP tool handlers
│   ├── resources.py ····· 4 MCP resources
│   └── prompts.py ······· 3 MCP prompts
├── workflow/
│   ├── engine.py ········ DAG executor (topological sort)
│   ├── models.py ········ Workflow + Step + Result types
│   ├── parser.py ········ YAML workflow loader + validator
│   ├── conditions.py ···· safe condition evaluator
│   └── builtins.py ······ 4 pre-built workflows
├── replay/
│   ├── engine.py ········ snapshot reconstruction + diffs
│   ├── models.py ········ Timeline + Snapshot + Session types
│   └── formatter.py ····· terminal + API output formatting
├── federation/
│   ├── protocol.py ······ handshake + routing + heartbeat
│   ├── peer.py ·········· peer registry + discovery
│   ├── discovery.py ····· network scanning + manual add
│   ├── security.py ······ HMAC signing + rate limiting
│   └── models.py ········ Peer + Request + Response types
├── multimodal/
│   ├── processor.py ····· auto-detect + dispatch
│   ├── image.py ········· PNG/JPEG header parsing
│   ├── audio.py ········· WAV/FLAC metadata extraction
│   ├── document.py ······ CSV/JSON/HTML/PDF text extraction
│   ├── integration.py ··· MultiModalCortex bridge
│   └── models.py ········ ProcessedInput + result types
├── benchmarks/
│   ├── runner.py ········ async benchmark executor
│   ├── report.py ········ terminal/markdown/JSON reports
│   ├── models.py ········ Case + Result + Suite types
│   └── suites/
│       ├── security.py ·· 20 cases (Vex, Redline, Mandate)
│       ├── code.py ······ 17 cases (Carve, Arbiter, Rune, Remedy)
│       └── data.py ······ 14 cases (Flux, Vigil, Gauge)
├── sdk/
│   ├── module_template.py module scaffolding generator
│   ├── agent_template.py  agent scaffolding generator
│   └── validator.py ····· package validation engine
├── community/
│   ├── validator.py ····· module validation engine
│   ├── registry.py ······ searchable module catalog
│   ├── installer.py ····· install/uninstall manager
│   ├── marketplace.py ··· browse + search + trending
│   ├── reputation.py ···· weighted scoring + badges
│   └── models.py ········ MarketplaceEntry + stats types
community/
├── modules/ ············· community module submissions
├── agents/ ·············· community agent submissions
├── registry.json ········ module/agent catalog (25 seeded)
└── CONTRIBUTING.md ······ submission guide (modules + agents)
site/
└── src/content/docs/ ···· Astro + Starlight documentation (82 pages)
tests/
├── kernel/ ·············· kernel component tests
├── modules/ ············· module tests
├── agents/ ·············· agent tests
├── api/ ················· API server tests
├── mcp/ ················· MCP server tests
├── workflow/ ············ workflow engine tests
├── replay/ ·············· time-travel tests
├── federation/ ·········· federation tests
├── multimodal/ ·········· multi-modal tests
├── benchmarks/ ·········· benchmark framework tests
├── sdk/ ················· plugin SDK tests
├── tui/ ················· terminal UI tests
└── community/ ··········· marketplace + registry tests
```

---

## Design Principles

**Local-first.** The kernel never touches the network. No telemetry, no central server, no cloud dependency -- architecturally enforced, not just policy. Your conversations, memory, and audit trail live on your machine in a single SQLite database.

**Data sovereignty.** Two modules (Collective and Herald) can optionally connect to other NEXUS instances peer-to-peer. They are blocked by default. Enabling them requires explicit `nexus allow --network <module>` consent. Even then: Collective shares only noise-injected model aggregates, never raw data. Herald logs every outbound message to Chronicle. There is no central server collecting anything from anyone. Every machine owns its own data.

**Earned autonomy.** Every component starts at trust level 0. Every action outcome adjusts trust -- positive results earn latitude, failures revoke it. This isn't a binary switch. It's a continuous score, per module, per domain, enforced on every call by Aegis and logged permanently by Chronicle. Agents take this further with graduated sovereignty: five trust tiers (SKILL, ADVISOR, MONITOR, AUTONOMOUS, SOVEREIGN) that unlock progressively more capable behavior as the agent proves itself reliable.

**Microkernel, not monolith.** The kernel is ~500 lines across five files. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on.

**Immutable audit.** Chronicle logs every routing decision, every permission check, every module response, every trust adjustment, and every outbound data event. SOC 2 and HIPAA exportable by design. You can always answer: *what left my machine, when, and where did it go?*

**Model-agnostic.** Qwen, DeepSeek, Phi, Gemma -- anything served over HTTP works. Cloud providers (OpenAI, Anthropic) available when configured. No vendor lock-in. No API keys required for local operation.

**Anti-fragile.** The system includes a threat radar (Sigil), behavioral fingerprinting (Echo), trust-scored information (Cipher), adversarial red-teaming (Specter), and engineered serendipity to break filter bubbles. NEXUS is designed to make the user more robust, not more dependent.

**Adversarial by design.** Specter stress-tests your decisions before you make them. Serendipity fights the optimization trap by surfacing connections from fields you aren't looking at. Forge negotiates within boundaries you set, escalating when it hits limits. The system argues with itself so you don't have to.

**Compounding value.** Through behavioral fingerprinting (Echo), knowledge crystallization (Legacy), and long-term memory (Engram), NEXUS becomes more valuable over months and years. It does not reset between sessions. It builds a persistent, evolving model of your world, your patterns, and your accumulated wisdom.

---

## License

Apache 2.0. Use it, fork it, ship it. The core will always be open.

---

<p align="center"><sub>Built by <a href="https://github.com/AllStreets">Connor Evans</a></sub></p>

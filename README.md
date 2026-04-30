<p align="center">
  <img src="https://img.shields.io/badge/ONEXUS-v0.2.0-blue?style=for-the-badge" alt="Version"/>&nbsp;<img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>&nbsp;<img src="https://img.shields.io/badge/License-Apache_2.0-green?style=for-the-badge" alt="License"/>
</p>

<p align="center">
  <a href="https://allstreets.github.io/ONEXUS/">
    <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=700&size=64&duration=1&pause=99999&color=00D4FF&center=true&vCenter=true&width=750&height=100&lines=O+N+E+X+U+S" alt="ONEXUS"/>
  </a>
</p>
<p align="center"><strong>Open-Source Neural Executive for Unified Superintelligence</strong></p>
<p align="center"><em>A cognitive operating system that runs on your hardware, answers to no cloud, and compounds intelligence the longer it runs.</em></p>

---

## The Idea

Most AI tools are wrappers around an API. You send text up, you get text back, someone else stores your data.

ONEXUS is the opposite. It is a microkernel -- a small, stable core that loads specialized cognitive modules on demand. Everything runs local. Your conversations, your memory, your audit trail -- all on your machine, in a single SQLite database. The kernel is lightweight and model-agnostic -- connect any LLM provider at runtime, or run fully offline with a local model.

Five kernel components form the nervous system. Nine cognitive modules form the brain. Each module does something fundamentally different -- deliberation, adversarial analysis, pattern detection, self-reflection, behavioral modeling. They communicate through an event bus, earn trust through demonstrated reliability, and are accountable to an immutable audit trail.

The kernel never touches the network. Two modules can optionally connect peer-to-peer -- blocked by default, logged when enabled. There is no central server, no telemetry, no cloud dependency. Every machine owns its own data.

This is not prompt chaining. Not tool use. Not a wrapper around someone else's API. This is an operating system for intelligence -- a digital brain that runs locally and gets smarter the longer you use it.

---

## Architecture

```
                       +---------+
                       |  USER   |
                       +----+----+
                            |
 +==========================|==========================+
 |                    ONEXUS KERNEL                    |
 |                          |                          |
 |                    +-----v-----+                    |
 |                    |  CORTEX   |                    |
 |                    | (router)  |                    |
 |                    +-----+-----+                    |
 |      +--------+----+-----+---+----+-------+         |
 |      |        |    |         |    |       |         |
 |   +--+---+ +--+--+ +---------+ +--+--+ +--+--+      |
 |   |ENGRAM| |PULSE| |CHRONICLE| |AEGIS| | LLM |      |
 |   |(mem) | |(bus)| | (audit) | |(trs)| |(inf)|      |
 |   +------+ +-----+ +---------+ +-----+ +-----+      |
 |                                                     |
 |   Trust: 0.00 -- 0.25 -- 0.50 -- 0.75 -- 1.00       |
 |   +0.12 correct / -0.22 wrong / asymmetric          |
 +=====================================================+
       |            |          |         |        |
 +-----+----+ +-----+----+ +---+---+ +---+--+ +---+--+
 |DELIBERATE| | DEFENSE  | |PATTERN| | SELF | |MODEL |
 |          | |          | |       | |      | |      |
 | Council  | | Specter  | |Oracle | |Consc.| | Echo |
 | Autonomic| |          | |Sentry | |Legacy| |      |
 +-----+----+ +-----+----+ +---+---+ +---+--+ +---+--+
       |            |          |         |        |
       +------+-----+-----+----+------+--+--------+
              |           |           |
         +---------+  +-------+  +---------+
         | ACTION  |  |  MCP  |  | CATALOG |
         | Wraith  |  |bridge |  | reader  |
         +----+----+  +---+---+  +----+----+
                          |           |
      +===================|===========|==========+
      |           ONEXUS-AGENTS CATALOG          |
      |                   |           |          |
      |    +--------------+    +------+------+   |
      |    | adapters/    |    | catalog/    |   |
      |    | mcp.json     |    | <category>/ |   |
      |    | per agent    |    | agent.json  |   |
      |    +--------------+    +-------------+   |
      |                                          |
      |    40 categories -- top 100 per category |
      |    Nightly crawl -- GitHub + Hugging Face|
      +==========================================+
```

### The Kernel

Five components. Each has one job:

| Component | Role | Storage |
|-----------|------|---------|
| **Cortex** | Semantic intent classification -- scores input against 9 intent categories and routes to the right module | -- |
| **Engram** | Three-tier memory -- working (ephemeral), episodic (FTS5), semantic (vector) | SQLite |
| **Pulse** | Async pub/sub event bus with priority queuing and wildcards | In-memory |
| **Chronicle** | Immutable audit trail -- every route, response, denial, trust change | SQLite WAL |
| **Aegis** | Trust engine -- 0.0-1.0 float scoring with +0.12/-0.22 asymmetric adjustment | SQLite |

### The Modules

Nine cognitive modules. Each does something fundamentally different:

| Module | What It Does |
|--------|-------------|
| **Council** | Multi-perspective deliberation with 4 lenses (ethical, verification, lateral, synthesis) and 2 modes (negotiation, simulation) |
| **Specter** | Adversarial analysis -- red-team audits, stress testing, counter-arguments, failure mode detection |
| **Autonomic** | Earned autonomy -- learns routines, proposes actions, acts within earned trust boundaries |
| **Oracle** | Anticipatory pattern detection -- trigger rules, keyword scoring, severity-prioritized threat tracking |
| **Wraith** | Ephemeral sub-agent spawner with death clocks -- auto-terminate on completion or timeout |
| **Legacy** | Knowledge crystallization -- distills experience into frameworks, playbooks, heuristics |
| **Consciousness** | Self-reflection -- journaling, pattern discovery, contradiction detection, reasoning traces |
| **Sentry** | Cognitive regulation -- monitors focus, fatigue, stress, flow state, cognitive load |
| **Echo** | User modeling -- behavioral fingerprinting, social graph, writing style analysis, relationship health |

Modules don't know about each other. They communicate through Pulse. They're constrained by Aegis. They're remembered by Engram. They're accountable to Chronicle.

---

## Trust System

Modules earn autonomy through demonstrated reliability. Every interaction adjusts trust:

| Trust Score | Tier | What It Means |
|-------------|------|---------------|
| 0.00 - 0.24 | OBSERVER | Module only responds when explicitly invoked |
| 0.25 - 0.49 | ADVISOR | Can suggest actions proactively |
| 0.50 - 0.74 | MONITOR | Can watch events and surface findings |
| 0.75 - 0.99 | EXECUTOR | Can act, but substantive work needs user authorization |
| 1.00 | AUTONOMOUS | Full autonomy -- revocable instantly, never decays on its own |

Correct response: **+0.12**. Wrong response: **-0.22**. The asymmetry is intentional -- trust is hard to earn and easy to lose.

---

## Quickstart

```bash
# Clone and install
git clone https://github.com/AllStreets/ONEXUS.git
cd ONEXUS
pip install -e .

# Start the kernel -- no model download required
onexus run

# Connect a model when you're ready:
#   Option A: local open-source model via llama.cpp, Ollama, or vLLM
#   Option B: set NEXUS_OPENAI_KEY or NEXUS_ANTHROPIC_KEY
#   Option C: register a provider at runtime via the API
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `onexus run` | Start an interactive session |
| `onexus tui` | Launch the Rich terminal UI |
| `onexus serve` | Start the REST/WebSocket API server |
| `onexus dashboard` | Launch the live web dashboard |
| `onexus status` | Show system state -- DB, model, port |
| `onexus allow <module>` | Grant a module permission to operate |
| `onexus deny <module>` | Revoke a module's permission |
| `onexus trust <module>` | Show a module's trust score and tier |
| `onexus revoke <module>` | Reset a module's trust to 0.0 immediately |
| `onexus forget --yes` | Erase all data (GDPR Art. 17) |
| `onexus workflow list` | List available built-in workflows |
| `onexus workflow run <name>` | Run a workflow pipeline |
| `onexus replay timeline` | Show Chronicle event timeline |
| `onexus replay snapshot <ts>` | Reconstruct state at a timestamp |
| `onexus replay diff <t1> <t2>` | Compare state between two points |
| `onexus federation status` | Show federation status and peers |
| `onexus federation discover` | Scan local network for peers |
| `onexus mcp` | Start the MCP server (stdio) |

---

## Platform Services

Beyond the kernel, ONEXUS ships with a full platform layer:

### API Server

`onexus serve` starts a FastAPI server exposing the full kernel over REST + WebSocket. Every kernel operation has an endpoint: message routing, module management, memory queries, trust scoring, Chronicle audit, and real-time Pulse event streaming over WebSocket.

### Live Dashboard

A dark-themed real-time web dashboard at `/dashboard`. Trust gauges with animated SVG arcs and glow effects, live Pulse event stream over WebSocket, Chronicle audit timeline, module status panel, and an interactive message console.

### Terminal UI

`onexus tui` launches a Rich-based split-pane terminal interface. Four quadrants: active modules with colored trust bars, conversation history, live Pulse events, and Chronicle entries.

### MCP Server

Every ONEXUS cognitive module exposed as an MCP tool. Connect Claude Desktop, Cursor, VS Code, or any MCP client and ONEXUS becomes the backend brain.

### Workflow Engine

DAG-based pipelines that chain modules into multi-step workflows. Define in YAML or Python. Steps reference outputs of dependencies, support conditional execution, three error policies (stop/skip/continue), and timeout enforcement.

### Time-Travel Replay

Pick any point in ONEXUS history and reconstruct the exact system state: which modules were active, what trust scores were, how messages were routed, what memory was accessed. Snapshot diffs compare two points in time.

### Federation

ONEXUS-to-ONEXUS peer communication. Instances discover each other, exchange capability listings, and route requests across the mesh. HMAC-SHA256 request signing, per-peer rate limiting. All outbound data logged to Chronicle. Disabled by default -- opt-in only.

---

## Multi-Provider Inference

| Component | What it does |
|-----------|-------------|
| **LocalProvider** | llama.cpp HTTP client, ChatML conversion, zero-dependency local inference |
| **OpenAIProvider** | OpenAI SDK wrapper, native messages format, configurable model |
| **AnthropicProvider** | Anthropic SDK wrapper, system message separation per API contract |
| **ProviderRouter** | Named provider registry, per-request routing, automatic fallback on unhealthy |

Set `NEXUS_DEFAULT_PROVIDER`, `NEXUS_OPENAI_KEY`, `NEXUS_ANTHROPIC_KEY` to configure. Local provider is always available as fallback.

Providers can also be registered at runtime via the API — start the kernel bare and connect a model whenever you're ready:

```bash
# Start with no model
onexus serve

# Later, connect OpenAI
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "model": "gpt-4o", "set_default": true}'

# Or connect Anthropic
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514", "set_default": true}'

# Or point to a local model (llama.cpp, Ollama, vLLM)
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "local", "base_url": "http://localhost:11434", "set_default": true}'
```

---

## Project Structure

```
nexus/
+-- __init__.py .......... version
+-- config.py ............ XDG paths, env overrides
+-- cli.py ............... Click entry point
+-- kernel/
|   +-- cortex.py ........ semantic intent router
|   +-- engram.py ........ three-tier memory
|   +-- pulse.py ......... priority event bus
|   +-- chronicle.py ..... immutable audit trail
|   +-- aegis.py ......... trust engine (0.0-1.0)
+-- modules/
|   +-- base.py .......... NexusModule ABC
|   +-- council.py ....... multi-perspective deliberation
|   +-- specter.py ....... adversarial analysis
|   +-- autonomic.py ..... earned autonomy
|   +-- oracle.py ........ anticipatory pattern detection
|   +-- wraith.py ........ ephemeral sub-agent spawner
|   +-- legacy.py ........ knowledge crystallization
|   +-- consciousness.py . self-reflection
|   +-- sentry.py ........ cognitive regulation
|   +-- echo.py .......... behavioral fingerprinting + social graph
+-- agents/
|   +-- catalog.py ....... ONEXUS-Agents catalog reader
+-- inference/
|   +-- provider.py ...... InferenceProvider ABC
|   +-- local.py ......... llama.cpp HTTP client
|   +-- openai_provider.py
|   +-- anthropic_provider.py
|   +-- router.py ........ ProviderRouter with fallback
|   +-- llm.py ........... LLMClient (delegates to router)
+-- messaging/
|   +-- bridge.py ........ MessageBridge ABC
|   +-- telegram.py ...... Telegram two-way bridge
|   +-- discord_bridge.py Discord two-way bridge
|   +-- manager.py ....... BridgeManager lifecycle
+-- api/
|   +-- server.py ........ FastAPI app factory
|   +-- models.py ........ Pydantic request/response types
|   +-- routes/ .......... REST + WebSocket endpoints
+-- dashboard/ ........... dark-themed real-time web UI
+-- tui/ ................. Rich split-pane terminal UI
+-- mcp/ ................. MCP server + tools + resources
+-- workflow/ ............ DAG pipeline engine
+-- replay/ .............. time-travel reconstruction
+-- federation/ .......... peer-to-peer mesh
+-- multimodal/ .......... image, audio, document processing
site/ .................... Astro + Starlight documentation
tests/ ................... test suite
```

---

## Design Principles

**Local-first.** The kernel never touches the network. No telemetry, no central server, no cloud dependency -- architecturally enforced, not just policy. Your data lives on your machine in a single SQLite database.

**Data sovereignty.** Two modules can optionally connect peer-to-peer. They are blocked by default. Enabling them requires explicit consent. Even then, all outbound data is logged to Chronicle. There is no central server collecting anything from anyone.

**Earned autonomy.** Every module starts at trust 0.0. Every action outcome adjusts trust -- correct results earn latitude (+0.12), failures revoke it (-0.22). This is a continuous score per module, enforced on every call by Aegis and logged permanently by Chronicle.

**Microkernel, not monolith.** The kernel is five files. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on.

**Immutable audit.** Chronicle logs every routing decision, every permission check, every module response, every trust adjustment, and every outbound data event. You can always answer: *what happened, when, and why?*

**Model-agnostic.** Qwen, DeepSeek, Phi, Llama, Gemma -- any open-source model served over HTTP works. Cloud providers (OpenAI, Anthropic) available when configured. Providers can be registered and switched at runtime. No vendor lock-in.

**Compounding value.** Through behavioral fingerprinting (Echo), knowledge crystallization (Legacy), and long-term memory (Engram), ONEXUS becomes more valuable over months and years. It does not reset between sessions.

---

## Task Agents

Looking for task-specific agents (code analysis, data pipelines, financial modeling, content generation)? Those live in a separate curated registry:

**[ONEXUS Agents](https://github.com/AllStreets/ONEXUS-Agents)** -- a community hub where developers submit, review, and share task agents that plug into the ONEXUS kernel.

### Deploying Agents into ONEXUS

Clone the catalog and point ONEXUS at it:

```bash
git clone https://github.com/AllStreets/ONEXUS-Agents.git
export NEXUS_AGENTS_CATALOG=/path/to/ONEXUS-Agents
onexus run
```

ONEXUS reads the catalog at startup. When Cortex routes a task that matches a catalogued agent's category, it can dispatch via the agent's MCP adapter. Three MCP tools expose the catalog:

| Tool | What it does |
|------|-------------|
| `nexus_agents_browse` | List agents by category, filter to runnable-only |
| `nexus_agents_search` | Keyword search across names, tags, categories |
| `nexus_agents_info` | Full metadata + MCP adapter descriptor for a specific agent |

Runnable agents declare an `adapter_ref` pointing to an MCP server descriptor under `adapters/<name>/mcp.json`. The descriptor specifies transport, command, env keys, capabilities, and a trust floor -- the minimum Aegis trust score required before dispatch.

### Building an Agent for ONEXUS

1. Write the agent (any language, any framework).
2. Wrap it in an MCP server (stdio or SSE transport).
3. Add a catalog entry to `ONEXUS-Agents/catalog/<category>/<slug>.json`.
4. Add an adapter descriptor to `ONEXUS-Agents/adapters/<slug>/mcp.json`.
5. Open a PR. CI validates the schema. An admin reviews and merges.

The nightly pipeline re-scores every agent. Community submissions become first-class members of the ranking pool the next night after merge.

---

## License

Apache 2.0. Use it, fork it, ship it. The core will always be open.

---

<p align="center"><sub>Built by <a href="https://github.com/AllStreets">Connor Evans</a></sub></p>

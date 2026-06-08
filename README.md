<p align="center">
  <img src="https://img.shields.io/badge/ONEXUS-v1.0-blue?style=for-the-badge" alt="Version"/>&nbsp;
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>&nbsp;
  <img src="https://img.shields.io/badge/Tests-1074_passing-brightgreen?style=for-the-badge" alt="Tests"/>&nbsp;
  <img src="https://img.shields.io/badge/License-Apache_2.0-green?style=for-the-badge" alt="License"/>
</p>

<p align="center">
  <a href="https://allstreets.github.io/ONEXUS/">
    <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=700&size=64&duration=1&pause=99999&color=00D4FF&center=true&vCenter=true&width=750&height=100&lines=O+N+E+X+U+S" alt="ONEXUS"/>
  </a>
</p>

<p align="center"><strong>The operating system for agents.</strong></p>
<p align="center"><em>Local-first. Sovereign. Beautiful. Built so the kernel never touches the network.</em></p>

---

## What it is

NEXUS is an OS that runs **agents** the way iOS runs apps. Built-in cognitive modules (Council, Specter, Wraith, Echo, ...) and third-party catalog agents (aider, cline, browser-use, ...) share one runtime, one manifest format, one trust model, one set of surfaces. Workspaces are rooms with their own roster, memory, grants, and home tone. Every tool call routes through a capability arbiter that gates against the agent's declared permissions, surfaces a first-use prompt when something needs your approval, and logs every byte to an immutable audit ledger.

```
+------------------------------------------------------------------+
|                              YOU                                 |
+------------------------------------------------------------------+
|  Surfaces                                                        |
|  Conversational  ·  Cockpit (Cmd-`)  ·  Spatial  ·  Settings     |
+------------------------------------------------------------------+
|  Workspace layer                                                 |
|  room manager · mood engine · routing pins · templates · grants  |
+------------------------------------------------------------------+
|  Agent runtime  (one process per agent per workspace)            |
|  supervisor · MCP client · capability filter · chronicle bridge  |
+------------------------------------------------------------------+
|  Kernel (5 components, zero network I/O)                         |
|  Cortex · Engram · Pulse · Chronicle · Aegis                     |
+------------------------------------------------------------------+
       Outside world (only via aegis.fs / aegis.network):
       Filesystem · Network · Federation peers
```

## The four surfaces

| Surface | Where | What |
|---|---|---|
| **Workspaces switcher** | ⌘K | Tiles of every workspace with home tone, roster, last-active |
| **Conversational** | default | 3-column primary view — workspaces + roster, conversation, ambient mood |
| **Cockpit** | ⌘\` | Observability overlay — live Pulse waveform, trust gradient, route trace, Chronicle tail |
| **Spatial** | header | Catalog grid — system + installed agents in bespoke identity discs |
| **Settings** | ⌘, | General / Workspaces / Agents / Security / Providers / About |

Each surface lives in one shell at `/aurora`. Eight ambient mood meshes drift behind everything; the body class follows the kernel's current state. Every glyph is custom SVG — zero emojis.

## The safety model

Four permission classes:

| Class | When approved | Auto-grant at Executor tier (≥0.75)? |
|---|---|---|
| **Routine** | At install | Always — silent |
| **Notable** | First-use prompt | Yes, within declared scope |
| **Sensitive** | First-use prompt + 30-day re-confirm | No — always prompts |
| **Privileged** | Settings → Security only | Never automatic |

Trust collapse below 0.50 instantly revokes every grant for that agent across every workspace.

## Local-first, by static invariant

The kernel modules (`cortex`, `engram`, `pulse`, `chronicle`) make **zero** direct network I/O. Aegis is the only kernel module that imports `httpx`; everything else routes through `aegis.network()`, which checks the agent's declared `network.outbound.<domain>` capability, rate-limits per agent, and writes a Chronicle entry for every byte that leaves the machine.

A static test enforces this — see `tests/inference/test_phase_6_smoke.py::test_kernel_never_directly_imports_httpx_in_kernel_modules`.

## Quickstart

```bash
git clone https://github.com/AllStreets/ONEXUS.git
cd ONEXUS
pip install -e ".[llm,api,tui,messaging]"

# Start the API server + Aurora surfaces
onexus serve

# Open the new dashboard
open http://localhost:8000/aurora

# Or use the CLI
onexus workspace new client --name "Client work" --template coding
onexus workspace switch client
onexus run
```

Provider configuration — pick one (or all):

```bash
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_ANTHROPIC_KEY=sk-ant-...
# or point at a local llama.cpp / Ollama / vLLM:
export NEXUS_DEFAULT_PROVIDER=local
```

You can also register a provider at runtime via `POST /api/providers`.

## Workspaces

```bash
onexus workspace list
onexus workspace new <id> --name <name> --template <coding|design|research|writing|personal|blank>
onexus workspace switch <id>
onexus workspace destroy <id> [--yes]
```

Each workspace owns six things, in isolation:
1. Filesystem root(s)
2. Resident agents (warm `InProcessAgent` or `MCPAgent` processes)
3. Memory partition (its own SQLite Engram namespace)
4. Permission grants ("always in this workspace" lives here)
5. Home tone (indigo · magenta · sage · plum · amber) + mood biases
6. Routing pins (`{intent → preferred agent slug}`)

Switching rooms feels like walking through a door — agents pause, mood transitions, pins activate.

## Agents

```bash
onexus agent list                                # installed
onexus agent install <manifest-path> [--dry-run] # preview the install plan
onexus agent uninstall <slug> [--yes]
```

The manifest is the universal contract — see `nexus/schemas/manifest.v1.json` for the JSON Schema. Every agent (built-in or third-party) declares:
- `intents` — patterns + semantic signals that Cortex's classifier consults
- `capabilities.tools` — each tool's permission class + declared capability scope
- `capabilities.declared` — what permissions the agent will ever ask for (4 classes)
- `runtime` — how the kernel launches it (in_process / stdio / sse)
- `identity.mark` — a bespoke geometric SVG glyph + radial-gradient disc

## Built-in agents (ship in the box)

| Slug | What it does | Identity |
|---|---|---|
| **council** | Four-lens deliberation (ethical, verification, lateral, synthesis) | Compass of four |
| **specter** | Adversarial red-team review | Warning triangle |
| **autonomic** | Earned-autonomy routines (Notable: `process.spawn`) | Concentric rings |
| **oracle** | Anticipatory pattern detection | Eye + pupil |
| **wraith** | Ephemeral sub-agents with death clocks | Wisp + trail |
| **legacy** | Knowledge crystallization (playbooks, heuristics) | Open book |
| **consciousness** | Self-reflection, journaling | Spiral |
| **sentry** | Cognitive load / flow detection | Heartbeat |
| **echo** | Behavioural fingerprinting (Privileged: `engram.read.global`) | Nested arcs |
| **agents** | Catalog dispatcher (Notable: `inter_agent.call.*`) | Tile grid |

## Key APIs

```
GET  /aurora                          # The Aurora shell
GET  /api/mood/current                # Current mood snapshot
WS   /api/mood/ws                     # Push mood transitions
GET  /api/workspaces                  # List + active marker
POST /api/workspaces/{id}/switch
POST /api/messages                    # Send a message to Cortex
GET  /api/permissions/pending         # First-use prompt inbox
POST /api/permissions/decide
WS   /api/permissions/ws              # Push pending tickets
POST /api/agents/install              # Dry-run or persist
GET  /api/spatial/agents              # System + installed agents
GET  /api/cockpit/snapshot            # Cockpit panel data
```

The classic `/dashboard` is preserved for backward compatibility.

## Design principles

- **Local-first** — the kernel makes zero network calls. Enforced by a static test, not by policy.
- **Earned autonomy** — every agent starts at trust 0.0. Correct outcomes earn +0.12; failures lose −0.22. Trust ≥ 0.75 unlocks Notable auto-grants in declared scope.
- **Immutable audit** — Chronicle WAL'd SQLite ledger captures every routing decision, permission check, network request, file access, trust adjustment.
- **Microkernel, not monolith** — five components: Cortex, Engram, Pulse, Chronicle, Aegis.
- **Model-agnostic** — OpenAI / Anthropic / local llama.cpp / any HTTP LLM. Switch at runtime.
- **Sovereign data** — federation is opt-in per workspace; all outbound traffic logged.
- **Bespoke iconography** — custom SVG everywhere; never emojis.
- **Accessibility non-negotiable** — `prefers-reduced-motion`, `prefers-contrast`, `prefers-reduced-data`, AAA contrast, color-blind signals via shape + name + drift speed (not color alone).

## Documentation

- Architecture spec: `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` (the design that drove v1)
- Phase docs: `docs/agents/{foundation,workspaces,safety-ux,surfaces,network-gateway}.md`
- Catalog of third-party agents: [ONEXUS-Agents](https://github.com/AllStreets/ONEXUS-Agents)

## License

Apache 2.0. Use it, fork it, ship it. The core will always be open.

---

<p align="center"><sub>Built by <a href="https://github.com/AllStreets">Connor Evans</a></sub></p>

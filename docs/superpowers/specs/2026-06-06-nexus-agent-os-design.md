# NEXUS as an Operating System for Agents — Design

**Date:** 2026-06-06
**Author:** Connor Evans (with brainstorming session)
**Status:** Approved for implementation planning

---

## 1. Overview

NEXUS today is a microkernel with 9 in-process cognitive modules and a sibling catalog of MCP-served agents that can be launched but are never actually wired into routing. This design transforms NEXUS into a true operating system for agents — a layered, sovereign, local-first runtime where built-in cognitive modules and catalog agents share one lifecycle, one manifest format, one trust model, one set of surfaces, and one beautiful Aurora-led interface.

The transformation covers four sub-systems built together:

- **A. Agent runtime** — process model, MCP client plumbing, sandbox, lifecycle, supervision.
- **B. Routing-to-agents** — Cortex learns capabilities from manifests, scores agents, picks one, calls its tools.
- **C. Surface layer** — Workspaces (rooms), Conversational primary surface, Cockpit observability, Spatial catalog, Settings.
- **D. Agent SDK / packaging** — the v1 manifest, the bespoke icon system, the install/first-use experience.

Nothing is sacrificed on either side: the kernel still never touches the network; data sovereignty is preserved; the existing 9 cognitive modules survive their behaviour intact while becoming unified agents.

## 2. Goals and Non-Goals

### 2.1 Goals
- **Unified runtime.** Every "thing that runs intelligence" is an Agent. Built-ins ship in the box; catalog agents install on top. Same manifest, same lifecycle, same trust, same UI affordances.
- **OS-grade safety.** Installing an agent feels as safe as installing an iOS app. Permissions are class-coded, install-reviewed, and first-use-prompted. Trust collapse instantly revokes auto-grants.
- **Workspaces as rooms.** Each workspace owns its filesystem root(s), resident agents, memory partition, permission grants, home tone, and routing pins. Switching workspaces feels like walking through a door.
- **Aurora-led visual identity.** Beautiful, modern, alive, sovereign. Eight psychologically grounded mood states with eight distinct hue families; bespoke per-agent identity marks; never an emoji.
- **Local-first preserved.** Kernel does zero network I/O. All outbound traffic flows through `aegis.network()`, allow-listed per agent, logged to Chronicle.
- **Routing that actually picks agents.** Cortex reads every agent's declared intents and capabilities and routes to the right one — built-in or catalog. Confidence-tiered: silent when sure, chooser when uncertain, ask when lost.
- **Observability one keystroke away.** Cockpit view (⌘\`) reveals Pulse waveform, trust gradients, routing trace with Concierge synthesis, Chronicle tail, network gateway activity.

### 2.2 Non-Goals (v1)
- Multi-user / multi-account on one NEXUS instance. Single-user; future work.
- Cross-machine workspace sync. Workspace structure is exportable as JSON; data does not sync.
- A marketplace with billing. Catalog stays open-source and curated; payments out of scope.
- Mobile clients. Desktop only (macOS / Linux); mobile companion is future work.
- Replacing the existing federation system. Federation is preserved but flows through the new `aegis.network()` gateway.

## 3. The Layered Architecture

```
+------------------------------------------------------------------+
|                              YOU                                 |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|  Surfaces                                                        |
|  Conversational  ·  Cockpit (Cmd-`)  ·  Spatial  ·  Settings     |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|  Workspace layer                                                 |
|  room manager · mood engine · routing pins · templates · grants  |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|  Agent runtime  (one process per agent per workspace)            |
|  supervisor · MCP client · capability filter · chronicle bridge  |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
|  Kernel (5 components, zero network I/O)                         |
|  Cortex · Engram · Pulse · Chronicle · Aegis                     |
+------------------------------------------------------------------+
                                |
       Outside world (only via aegis.fs / aegis.network):
       Filesystem · Network · Federation peers
```

Each layer talks only to its immediate neighbours. The kernel does not know about surfaces. Surfaces do not directly invoke kernel internals — they go through the workspace layer.

## 4. Kernel — five components

The kernel stays at five components. Aegis grows new responsibilities (network gateway, filesystem broker, capability arbiter) but remains a single module to keep the kernel surface area small. The kernel performs zero network I/O.

### 4.1 Cortex (routing)
- Reads every loaded agent's declared `intents` from its manifest.
- Combines existing semantic / pattern / structure / context scoring with the new per-agent intent declarations.
- Produces a confidence score and the top-K candidate agents per message.
- Surfaces the candidate set to the workspace's routing controller, which applies workspace pins and the confidence-tier rules (Section 8).
- The 10 hand-coded `_INTENT_DEFS` in the current `cortex.py` becomes the manifest declaration for the 9 built-in agents plus the `summon` intent for the catalog dispatcher.

### 4.2 Engram (memory)
- Three tiers preserved: working (ephemeral), episodic (FTS5), semantic (vector).
- Adds workspace partitioning. Each workspace gets its own SQLite namespace under `~/.nexus/workspaces/<workspace-id>/engram/`.
- Cross-workspace reads require the Privileged capability `engram.read.global` (currently only Echo declares this, for user-modeling continuity).
- Global tier remains for system-wide facts (config, agent registry, user profile).

### 4.3 Pulse (event bus)
- Async pub/sub with priority queuing — unchanged structurally.
- Adds workspace tagging on every message — events carry `workspace_id` so the Cockpit can filter to "this room only."
- The Cockpit subscribes to the live Pulse and renders the waveform from event rate per topic.

### 4.4 Chronicle (audit)
- Immutable WAL'd SQLite ledger — unchanged structurally.
- Adds new event types: `agent_installed`, `agent_uninstalled`, `permission_granted`, `permission_revoked`, `network_request`, `network_request_denied`, `fs_access`, `fs_access_denied`, `workspace_created`, `workspace_switched`, `trust_collapse`.
- Every Aegis `network()` and `fs()` call writes an entry.

### 4.5 Aegis (trust · permission · gateway)
Aegis grows from a trust scorer into the kernel's permission arbiter. New responsibilities:

- **Trust** — preserved. Float `0.0–1.0`, asymmetric `+0.12 / −0.22` adjustment, five tiers.
- **Capability arbitration** — `aegis.check_capability(agent_slug, capability, scope) → Allow | Prompt | Deny`. Reads the manifest's declared capabilities, the current trust tier, and the workspace's permission grants table. Drives the install review (Section 9.2), the first-use prompt (Section 9.3), and the auto-grant logic at Executor tier and above.
- **Filesystem broker** — `aegis.fs(agent_slug, path, mode) → file_handle | PermissionDenied`. Enforces workspace root containment; logs every access; refuses paths outside declared roots.
- **Network gateway** — `aegis.network(agent_slug, url, method, ...) → response | PermissionDenied`. Checks the agent's declared `network.outbound.<domain>` allow-list, the workspace's grants, rate limits per agent, and writes Chronicle. The **only** network I/O in the whole system flows through this function. Federation reuses it under `network.federation.<peer-id>`.

Aegis stays one module. The new methods are public Python functions called by the Agent Runtime layer; they are not exposed over MCP except as kernel-facing tools.

## 5. Agent Runtime

The Agent Runtime sits above the kernel and below the workspace layer. It owns the per-agent processes.

### 5.1 Process model
- **One process per agent per workspace.** Each room runs its own copy of an agent's MCP server.
- Built-in agents (the migrated 9) run **in-process** via an `InProcessAgent` shim that speaks the same interface as the MCP client but invokes Python directly. Zero subprocess cost for built-ins.
- External agents launch via `subprocess.Popen` and an MCP stdio client.
- Optional OS-level sandbox (Settings → Security): `sandbox-exec` on macOS, `firejail` on Linux. Off by default; per-agent toggle.

### 5.2 Lifecycle
- **install** — fetch manifest from the catalog, validate the schema, show the install review (Section 9.2), persist to `~/.nexus/agents/<slug>/`, register in the catalog index.
- **launch** — when an agent becomes resident in a workspace, the supervisor starts the process (or wakes an `InProcessAgent`), waits for the MCP handshake, registers tools, applies the capability filter.
- **pause / wake** — `SIGSTOP` and `SIGCONT` for external processes; method calls on `InProcessAgent`. Pause cost: zero CPU, memory held. Wake latency: < 200 ms.
- **uninstall** — terminate any resident copies, remove from all workspaces, delete `~/.nexus/agents/<slug>/`, log to Chronicle.
- **update** — replace the manifest and binaries; if capability set changed, prompt the user to re-review.

### 5.3 MCP client
- Use the official `mcp` Python library.
- Per resident agent: one stdio connection, lazy tool discovery, capability filter on every tool call.
- All tool calls route through `aegis.check_capability()` before invocation. Failed checks return a `PermissionDenied` MCP error to the calling code path.

### 5.4 Capability filter
A per-agent allow-list of `tool_name → permission_class`. When Cortex (or another agent) calls `aider.edit_file()`, the runtime:
1. Looks up the declared class for `edit_file` (e.g., Notable / `fs.write.workspace`).
2. Calls `aegis.check_capability("aider", "fs.write.workspace", path=workspace_root)`.
3. If `Allow` → invoke the tool. If `Prompt` → suspend, show first-use prompt, resume on grant. If `Deny` → return error.

### 5.5 Chronicle bridge
Every tool call (success or failure) writes to Chronicle: `{ts, agent, tool, args_preview, result, latency, workspace_id, trust_delta?}`. This is the data source for the Cockpit's routing-trace panel and the "show me who handled that" replay.

## 6. Agent Manifest Schema v1

Every agent — built-in or third-party — has a `manifest.json` matching this schema.

```jsonc
{
  "manifest_version": 1,
  "slug": "aider",
  "name": "aider",
  "tagline": "Pair-programming in your terminal, git-aware.",
  "version": "0.74.0",
  "system": false,                                  // true only for built-ins
  "publisher": {
    "type": "org",                                  // or "individual"
    "handle": "Aider-AI",
    "url": "https://github.com/Aider-AI"
  },
  "category": "coding",                             // catalog category
  "tags": ["coding", "cli", "git"],
  "license": "Apache-2.0",
  "source": {
    "github": "Aider-AI/aider",
    "huggingface": null,
    "homepage": "https://aider.chat/"
  },

  "identity": {
    "mark": {
      "kind": "svg",                                // or "builtin:council" etc.
      "path": "./icon.svg",                          // 14x14 + 22x22 + 44x44 variants
      "gradient": ["#9aa8ff", "#4d5bcf"]            // disc colour
    }
  },

  "intents": [
    { "name": "code",  "patterns": ["edit", "refactor", "fix.*bug"],
      "semantic_signals": ["fix this", "edit this file"], "weight": 1.0 },
    { "name": "git",   "patterns": ["commit", "branch", "stash"],
      "semantic_signals": ["commit this", "git history"], "weight": 0.8 }
  ],

  "capabilities": {
    "tools": [
      { "name": "edit_file",   "class": "Notable",   "scope": "fs.write.workspace" },
      { "name": "create_file", "class": "Notable",   "scope": "fs.write.workspace" },
      { "name": "run_command", "class": "Sensitive", "scope": "process.shell"      },
      { "name": "git_commit",  "class": "Notable",   "scope": "process.spawn"      },
      { "name": "search_repo", "class": "Routine"                                   }
    ],
    "declared": {
      "Routine":    ["fs.read.workspace", "engram.read.workspace"],
      "Notable":    ["fs.write.workspace", "process.spawn",
                     "network.outbound.openai.com",
                     "network.outbound.anthropic.com"],
      "Sensitive":  ["process.shell"],
      "Privileged": []
    }
  },

  "runtime": {
    "transport": "stdio",                           // or "sse" or "in_process"
    "command": "aider-mcp",
    "args": [],
    "env_keys": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AIDER_MODEL"]
  },

  "trust": {
    "floor": 0.55,                                  // minimum trust for routing
    "default_tier": "ADVISOR"                       // starting tier
  },

  "compatibility": {
    "nexus_version": ">=1.0.0"
  }
}
```

### 6.1 Validation rules
- `slug` is unique, kebab-case, max 64 chars.
- `manifest_version` must equal `1`.
- Every capability listed in `capabilities.tools[].scope` must appear in `capabilities.declared[*]` for its class.
- Built-in agents (`system: true`) may declare `Privileged` capabilities; third parties may declare them but they are never auto-granted from a prompt — only via Settings → Security.
- The schema lives at `nexus/schemas/manifest.v1.json` (JSON Schema). Catalog CI rejects invalid manifests.

### 6.2 Built-in identity marks
The 9 built-in agents reference identity marks by name (`"kind": "builtin:council"`) which resolve to bespoke SVGs shipped in `nexus/dashboard/icons/builtins/`. This guarantees the visual signature is part of the OS, not a third-party asset that can rot.

## 7. Workspace System

### 7.1 What a workspace owns
A workspace owns six isolated things:

1. **Filesystem root(s)** — one or more directories that scoped agents may read/write. `aegis.fs()` rejects paths outside.
2. **Resident agents** — the subset of installed agents that are currently warm (process running, MCP connection live) for this workspace.
3. **Memory partition** — its own Engram namespace at `~/.nexus/workspaces/<id>/engram/`. Cross-workspace reads require the Privileged `engram.read.global` capability.
4. **Permission grants** — the "always in this workspace" table. Same agent can have different grants in different rooms.
5. **Home tone & mood overrides** — signature gradient (indigo / magenta / sage / plum / amber / custom) and optional mood biases (e.g., "Writing always trends Reflective").
6. **Routing pins** — `{ intent_or_category → preferred_agent_slug }` mapping. Bypasses the chooser for routine cases.

### 7.2 Storage layout
```
~/.nexus/
├── config.toml                      # global config
├── kernel/
│   ├── engram.sqlite                # global tier of Engram
│   ├── chronicle.sqlite             # the immutable ledger
│   └── aegis.sqlite                 # trust scores + global grants
├── agents/
│   ├── aider/                       # installed third-party agent
│   │   ├── manifest.json
│   │   ├── icon.svg
│   │   └── data/                    # agent's private storage
│   └── council/                     # built-in agent (system: true)
│       └── manifest.json
└── workspaces/
    └── client-work-7b3a/            # one per workspace
        ├── workspace.json           # roots, roster, pins, tone
        ├── engram/                  # workspace memory partition
        │   ├── episodic.sqlite
        │   └── semantic.vec
        └── grants.sqlite            # per-workspace permission grants
```

### 7.3 Switcher
- Trigger: ⌘K (or click the kernel mark in the top-left).
- Grid of workspace tiles, each rendered in its home tone gradient with the resident agent stack and a last-touched timestamp.
- Cmd-1 through Cmd-9 jump to slots 1–9.
- Cmd-N opens the template picker (Coding / Design / Research / Writing / Personal / Blank).

### 7.4 Concurrency
Exactly **one workspace is active at a time.** Switching workspaces:
1. Pauses every resident agent in the current workspace.
   - External agents: `SIGSTOP` on the subprocess.
   - `InProcessAgent` built-ins: set a `paused=True` flag that rejects new `call_tool()` invocations until woken (zero CPU cost — built-ins aren't actively running anyway when not handling a call).
2. Wakes the agents in the target workspace, starting any not yet running.
   - External agents: `SIGCONT` (or `Popen` if first launch).
   - `InProcessAgent` built-ins: clear the `paused` flag.
3. Loads the workspace's mood, routing pins, permission grants into the active session.
4. Animates the Aurora atmosphere to the new home tone (1.2s ease).

### 7.5 Templates
Six templates ship in the box (`nexus/templates/`):

| Template | Tone | Roster (initial residents) | Routing pins | Mood bias |
|---|---|---|---|---|
| Coding | Indigo | aider, cline, council | CODE → aider | (none) |
| Design / Generative | Magenta | comfyui, echo, sd-webui | (none) | favors Creative |
| Research | Sage | council, specter, browser-use | DELIBERATE → council | favors Watchful |
| Writing | Plum | echo, council, consciousness | (none) | favors Reflective |
| Personal | Amber | echo, sentry | (none) | (none) |
| Blank | (user picks) | (empty) | (none) | (none) |

### 7.6 Export
`workspace.json` and `pins.json` are exportable as a single `template.json` (the user clicks "Export as template" in workspace settings). The export contains *structure only* — never memory, conversation, or grants. Templates can be shared, imported on another machine, or submitted to the catalog as community templates (post-v1).

## 8. Routing

### 8.1 Confidence tiers
After Cortex scores every loaded agent, the top candidate's score determines the path:

- **≥ 0.85** — silent routing. The agent runs. Response leads with a small "picked by cortex · 0.78 match · 0.67 trust" line.
- **0.55–0.84** — surface chooser. Top candidate pre-selected; Enter accepts; ⌥ dismisses; up to two alternates shown with one-line "why this one" reasons.
- **< 0.55** — Cortex asks plainly: "what kind of help do you need?" with the top 3 candidates as buttons and an "@-mention an agent" affordance.

The chooser is a calm panel inside the conversational surface — never a blocking modal. The mood of the workspace stays visible behind it.

### 8.2 Workspace pinning
A pin maps an intent or category to a specific agent slug:

```jsonc
{
  "pins": [
    { "intent": "CODE", "agent": "aider" },
    { "category": "deliberation", "agent": "council" }
  ]
}
```

A matching pin bypasses the chooser even at medium confidence. Pins are per-workspace, so the same intent can go to different agents in different rooms.

### 8.3 @-mention override
Typing `@aider …` directly addresses an agent regardless of Cortex's score, regardless of pins. Bypasses everything. Power-user escape hatch.

### 8.4 Concierge synthesis (Cockpit feature)
When the user invokes "show me how that was handled" (a Cockpit affordance or `/trace` slash command), the routing trace shows the synthesis of what actually happened: which agents Cortex considered, what each one scored, which one was called (or which alternates were also called — e.g., Specter audited Aider's draft), what each returned, and how the final answer was composed. **This is a retrospective view of normal Hybrid routing**, not a live parallel-execution mode — the per-turn latency cost is zero. The Cockpit reads the routing trace from Chronicle and renders it.

### 8.5 No LLM fallback classifier
The current `Cortex._llm_classify()` path — which calls the LLM directly for ambiguous queries — is **removed**. Under the new model, classification is manifest-driven; if no agent scores above 0.55, Cortex asks the user (the `<0.55 → ask` branch in Section 8.1). This removes the only kernel-side network call in the current code, preserving the "kernel does zero network I/O" promise.

## 9. Safety Model

### 9.1 Permission classes
| Class | Approval moment | Behaviour after approval | Trust collapse |
|---|---|---|---|
| **Routine** | Approved at install | Silent forever | Unaffected |
| **Notable** | First-use prompt | Auto-grant within declared scope at Executor (≥ 0.75) trust | Revoked at < 0.50 |
| **Sensitive** | First-use prompt | Stronger tone; re-confirmed every 30 days | Revoked at < 0.50 |
| **Privileged** | Settings → Security only | Never grantable from a prompt | Revoked, period |

Class is the UI accent colour (Routine green / Notable blue / Sensitive amber / Privileged coral). The colour language matches the trust-event temperature trio (Section 11.2).

### 9.2 Install manifest review
When the user clicks "Install" on an agent in the Spatial grid, a panel surfaces:
- The agent's identity mark, name, tagline, license, publisher.
- A categorized list of what the agent will be able to do, grouped by class with plain-language descriptions.
- A small footer: *"Sensitive permissions ask first. You can change permissions any time in Settings → Security."*
- Three buttons: **Cancel** / **Install with restrictions** / **Install**.
- "Install with restrictions" opens a per-capability editor — the user can deny any Notable or Sensitive capability before install. The agent will then have to do without (and may not function — Cortex will deprioritize it if its core capabilities are denied).

### 9.3 First-use prompt
When an agent reaches for a Notable or Sensitive capability for the first time, a panel slides up *inside* the current conversational surface. It is never a modal; the Aurora mood behind it remains visible.

The panel shows:
- The agent's identity mark, name, and what it's asking ("aider wants to write to a file").
- The exact target (path, command, URL).
- A preview of the proposed change (file diff, command text, URL).
- Four choices in order of safety:
  1. **Allow once**
  2. **Always in `<current workspace>`**
  3. **Always for `<agent>`, everywhere**
  4. **Don't allow** (warn-coloured)
- A small footer with the agent's trust score and tier, plus the threshold at which auto-grants unlock.

The user's choice writes to the workspace's grants table (for "Always in workspace") or the global grants table (for "Always everywhere"). Trust collapse at any point invalidates these.

### 9.4 Trust-gated automation
At Executor tier (trust ≥ 0.75), Notable capabilities **inside their declared scope** auto-grant without prompting. Out-of-scope requests still prompt. At Autonomous tier (trust = 1.00), previously-approved Sensitive capabilities also auto-grant. Privileged stays manual forever.

Trust collapse below 0.50:
- Revokes every auto-grant for that agent across all workspaces.
- Writes a Chronicle entry `trust_collapse: {agent, prior_trust, current_trust, revoked_grants: [...]}`
- Triggers the **Alert** mood (crimson) on the active workspace for ~30 seconds.
- Sends a Pulse event subscribable by Specter, Oracle, and the dashboard.

### 9.5 Network gateway
Every outbound HTTP / WebSocket request agents make flows through `aegis.network()`. The function:
1. Reads the requesting agent's declared `network.outbound.<domain>` allow-list from manifest + workspace grants.
2. Resolves the request URL's domain.
3. Rejects if not allow-listed, returning `PermissionDenied` to the calling code.
4. Applies per-agent rate limit (default 60 rpm, configurable).
5. Performs the actual HTTP via `httpx` (or the configured library).
6. Writes Chronicle: `network_request: {agent, url, method, status, bytes_in, bytes_out, ts}`.
7. Returns the response.

The kernel modules themselves never call `aegis.network()` — only the agent runtime does, on behalf of agents.

Federation (existing peer-ONEXUS feature) uses a special capability `network.federation.<peer-id>` and flows through the same gateway.

### 9.6 OS-level sandbox (opt-in)
Settings → Security exposes a per-agent toggle: "Run in OS sandbox." When on:
- macOS: launch the agent inside `sandbox-exec` with a profile generated from the manifest's declared capabilities.
- Linux: launch inside `firejail` with an analogous profile.

Defaults to off because most agents need broader filesystem and process access than a profile generator can perfectly predict. Off-by-default preserves the v1 simplicity; the toggle is advertised for users who want hardware-level isolation.

## 10. Visual Identity and Design System

### 10.1 Core principles
- **Bespoke icons only. Never emojis.** Custom-drawn SVG at three sizes (14, 22, 44 px) for every glyph.
- **Aurora-led atmosphere.** Each workspace renders a gradient mesh that shifts with system state (Section 11). Mesh is blurred 55–70 px; opacity capped to keep text contrast AAA.
- **Film grain underlay.** A 12-bit fractal-noise SVG overlay (10% alpha, overlay blend) prevents the CSS-perfect "AI dashboard" look.
- **The kernel mark.** A small breathing orb — a radial gradient `#fbf7ff → #c9b8ff → #5a4ac4` with a 4.5s pulse animation — appears anywhere NEXUS is "alive": top-left of workspaces, inside the conversational input, at the start of system messages. This is the OS's signature element.

### 10.2 Typography
- **Display & UI body:** Inter Display + Inter (with `letter-spacing: -0.005em` for body, `-0.02em` for display).
- **Monospace (data, IDs, timestamps, paths, code):** IBM Plex Mono with `ss01`, `ss02` enabled for the curved zero and dotted lowercase l.
- Headings range 17–30 px; body 13–14.5 px; eyebrows (uppercase labels) 9–10.5 px with `0.22em` letter-spacing.

### 10.3 Surface tokens
- **Glass card:** `background: rgba(255,255,255,0.05); backdrop-filter: blur(20px) saturate(140%); border: 1px solid rgba(255,255,255,0.08); border-radius: 12–14px;`
- **Hairline:** `border-top: 1px solid rgba(255,255,255,0.07);`
- **Pill:** `background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 99px;`

### 10.4 Per-agent identity marks
Each agent gets:
- A unique bespoke SVG glyph (geometric, line-based, white-on-gradient).
- A radial-gradient identity disc as background, using the agent's declared `gradient` colours (manifest field).
- A trust ring drawn around the disc — circumference proportional to current trust, stroke `rgba(255,255,255,0.55)`, stroke-linecap round.

Examples of bespoke glyphs already designed in the brainstorming session:
- **aider** — chevron-flow (path: `M3 10l4-6 4 6` + `M5 10h4`)
- **council** — 4 dots arranged as compass points with a centre dot
- **cline** — three offset horizontal bars
- **echo** — nested arcs with a centre dot
- **specter** — warning triangle with vertical mark + dot
- **comfyui** — node-graph with 4 connected dots
- **browser-use** — rounded window with horizon line
- **wraith** (built-in) — to be designed
- **oracle** (built-in) — to be designed
- **autonomic** (built-in) — to be designed
- **legacy** (built-in) — to be designed
- **consciousness** (built-in) — to be designed
- **sentry** (built-in) — to be designed

All six remaining built-in glyphs will be designed during implementation, all rendered as bespoke geometric SVG; no emoji and no third-party icon set.

### 10.5 Colour palette (system tokens)
- **Base midnight:** `#0c0a14` (page background under the mood mesh).
- **Text high:** `#f0e9ff` · **Text mid:** `#e8e4f0` · **Text dim:** opacity 0.62 · **Text softer:** opacity 0.42.
- **Trust ring active:** `rgba(255,255,255,0.55)` · **inactive:** `rgba(255,255,255,0.08)`.
- **Permission class accents:**
  - Routine: `#9affb6` (jewel green) — confirms.
  - Notable: `#a8b4ff` (calm violet-blue) — first-use blue.
  - Sensitive: `#f8c460` (warm amber) — caution.
  - Privileged: `#f86078` (coral) — gate.

## 11. Mood Atlas

Eight ambient states, each tied to a kernel condition. Each mood is a gradient mesh with a tuned drift speed. Drift speed encodes pace independent of colour.

### 11.1 The eight moods
| Mood | Hue family | Trigger | Drift |
|---|---|---|---|
| **Calm Focus** | Indigo · violet · warm amber · undertone cyan | Default; nothing else takes priority | 24 s |
| **Deep Flow** | Pine · jade · oceanic deep blue · gold ember | Sentry detects sustained focus (≥ 15 min high engagement, low context-switching) | 38 s |
| **Routing** | Electric magenta · bright cyan · indigo | Pulse rate above baseline AND multiple agents active simultaneously | 14 s |
| **Deliberating** | Amber · bronze · burgundy · cream | Council, Specter, or Legacy is the active agent and is deliberating | 30 s |
| **Creative** | Hot coral · tangerine · magenta · teal edge | Generative agents resident (image, audio, writing) OR workspace category = creative | 20 s |
| **Reflective** | Near-monochrome plum · single rose ember | Consciousness active, low pulse, late hour | 42 s |
| **Watchful** | Brass · olive · slate · ember | Oracle flagged a pattern OR Specter auditing OR an agent's trust is sliding (not collapsed) | 12 s |
| **Alert** | Crimson · coral glow · deep ember | Trust collapse · security breach · federation peer rejected · permission denied after grant | 7 s |

### 11.2 Trust event overlays (1.5 s transient washes)
Layered over the current mood; do **not** replace it.

- **Rising — warm gold wash.** Agent earned trust (`+0.012` or larger). Brief golden sweep.
- **Falling — cool steel wash.** Agent lost trust (`-0.022` or larger). Pale steel-blue cooling. **Distinct from violet calm AND from red.** Says "warmth is draining; pay attention."
- **Collapse — hot crimson flash.** Trust dropped below 0.50. Aegis revoked the agent. Single crimson pulse + permanent Chronicle entry. The room remembers (Alert mood persists 30 s).

### 11.3 Workspace home tones
Default tones per template:
- **Indigo** — Coding workspaces · `#5a6cd0 → #2c3a78`.
- **Magenta** — Design / Generative · `#c060a0 → #5e2050`.
- **Sage** — Research · `#88a888 → #3e5840`.
- **Plum** — Writing · `#7e5ea0 → #2c1c44`.
- **Amber** — Personal · `#e8a06c → #844820`.

A workspace's tone shows through in Calm Focus and biases the colour of state moods (e.g., Deep Flow in a Magenta workspace leans slightly warmer green).

### 11.4 Time-of-day modulation
A quiet 5–10% bias on whatever mood is active:
- 06:00–10:00 — +5% gold.
- 10:00–17:00 — neutral.
- 17:00–22:00 — +5% violet.
- 22:00–06:00 — −10% saturation overall.

Modulation never overrides the active state; it shifts hue subtly.

### 11.5 Accessibility (non-negotiable)
- **Reduce Motion** (matches the OS-level preference automatically) freezes the mesh drift; transitions become instant.
- **Reduce Color** collapses every mood to deep-midnight monochrome; state is signalled only by typography and small accent dots (never colour alone).
- **Colour-blind safe** — every state has a non-colour signal (drift speed + named label + icon shape).
- **AAA text contrast** at full mesh saturation. Verified per mood.

## 12. The Four Surfaces

### 12.1 Conversational (primary, in-workspace)
Three columns: workspaces + agent roster on the left, the conversation in the center, ambient mood + kernel status on the right. The conversation shows messages with the responding agent's identity disc, name, and a small "picked by cortex · 0.78 match" line. The input at the bottom shows the kernel mark, a placeholder `Ask anything, or @ to call a specific agent…`, and a ⌘K hint.

When Cortex confidence is medium (0.55–0.84), the chooser panel surfaces inline above the input — never as a modal.

### 12.2 Cockpit (observability, ⌘\`)
Slides up over the conversational surface. Signal aesthetic (faint grid, gentle scanline, oscilloscope traces) layered over the workspace's current Aurora mood. Six panels:
1. **Pulse waveform** — live, three traces (cortex.route / aegis.check / chronicle), 60-second rolling window.
2. **Resident agents** — name, identity disc, memory cost, current trust.
3. **Trust gradient · 24h** — per-agent sparklines.
4. **Last route · concierge synthesis** — the full routing trace for the most recent message; expandable.
5. **Chronicle live tail** — colour-coded by source module; ⌘L pins it to live-tail mode.
6. **Network gateway** + **Engram partition stats**.

Tapping anywhere outside dismisses. The Aurora atmosphere underneath was always there.

### 12.3 Spatial (catalog browse)
The full Catalog grid. Each card: bespoke identity mark inside an identity disc, name, one-line tagline, status (resident · sleeping · installed · installable), trust score, install button when not yet installed. Filter strip at the top by category. Search opens a Spotlight-style overlay. System agents (the migrated 9) appear alongside third-party agents — both have an identity mark, a trust ring, an action button. System agents carry a small "system · ships with NEXUS" badge.

### 12.4 Settings
Tabbed panels:
- **General** — language, model defaults, time-of-day modulation, accessibility toggles.
- **Workspaces** — list, edit, export, delete.
- **Agents** — installed list, per-agent permissions, OS-sandbox toggle, uninstall.
- **Security** — global permission table, trust history, Chronicle export, federation peers.
- **Providers** — LLM provider configuration (preserved from current implementation).
- **About** — version, license, contributors.

## 13. Migration of the Existing 9 Modules

The 9 in-process cognitive modules (Council, Specter, Wraith, Echo, Oracle, Autonomic, Legacy, Consciousness, Sentry) become unified agents while keeping their behaviour and zero-latency in-process execution.

### 13.1 InProcessAgent shim
A new base class `nexus.agents.InProcessAgent` wraps a Python module instance and exposes the same MCP-shaped interface external agents expose:

```python
class InProcessAgent:
    """Adapter: presents an in-process Python module as an MCP-shaped agent."""
    def __init__(self, manifest: dict, module: NexusModule, kernel: Kernel): ...
    async def call_tool(self, tool_name: str, args: dict) -> Any:
        # Bypasses subprocess; calls module method directly.
        # Still routes through aegis.check_capability() first.
        ...
```

Externally, Cortex and the runtime treat an `InProcessAgent` and an `MCPAgent` identically.

### 13.2 Manifests for built-ins
Each of the 9 modules ships a `manifest.json` under `nexus/agents/builtins/<slug>/`:

- `council` — intents DELIBERATE; capabilities mostly Routine; identity mark = compass-of-four.
- `specter` — intents CHALLENGE; capabilities Routine; identity mark = warning triangle.
- `wraith` — intents SPAWN; capabilities include `process.spawn` (Notable, declared) for phantom sub-agents.
- `echo` — intents PROFILE; capabilities include the only Privileged grant in the built-in set: `engram.read.global`, because behavioural fingerprinting needs cross-workspace visibility.
- `oracle` — intents ANTICIPATE; capabilities Routine.
- `autonomic` — intents AUTOMATE; capabilities include `process.spawn` (Notable) for routine execution.
- `legacy` — intents CRYSTALLIZE; capabilities Routine.
- `consciousness` — intents REFLECT; capabilities Routine.
- `sentry` — intents REGULATE; capabilities Routine.

Each manifest declares `"system": true` and references the built-in identity mark by name (`"kind": "builtin:<slug>"`).

### 13.3 What changes in the existing code
- `nexus/modules/base.py` — `NexusModule` ABC gains a `manifest()` classmethod and a `tools()` method that returns the MCP tool descriptors derived from `handle()` and any new explicit tool methods.
- `nexus/kernel/cortex.py` — the hard-coded `_INTENT_DEFS` list is removed; intents come from agent manifests at load time. The classification engine becomes manifest-driven.
- `nexus/agents/catalog.py` — keeps its catalog reader role; gains a `builtins` source that scans `nexus/agents/builtins/`.
- `nexus/agents/launcher.py` — extended to launch `InProcessAgent` (synchronous) alongside `MCPAgent` (subprocess).
- `nexus/modules/agent_dispatcher.py` — the current "SUMMON" intent module is replaced by the unified runtime's lifecycle commands; explicit-summon syntax still works via `@<slug>`.

### 13.4 Backward compatibility
Existing CLI commands (`onexus run`, `onexus tui`, `onexus serve`, `onexus dashboard`) keep working. The TUI and the existing dashboard remain as the v0 surfaces alongside the new Aurora-led dashboard during a transition window. After v1 launch, the old dashboard becomes a "Classic" toggle inside the new Settings.

## 14. SDK, API, and MCP

### 14.1 REST API additions
Preserve existing endpoints; add:
- `GET /api/workspaces` — list.
- `POST /api/workspaces` — create from template.
- `POST /api/workspaces/{id}/switch` — set active.
- `POST /api/workspaces/{id}/agents` — make an agent resident in a workspace.
- `DELETE /api/workspaces/{id}/agents/{slug}` — remove from roster.
- `GET /api/permissions/grants?agent=&workspace=` — list grants.
- `POST /api/permissions/grants` — grant.
- `POST /api/permissions/revoke` — revoke (or trust-collapse triggered).
- `GET /api/mood/current` — current mood + drift + workspace tone.
- WebSocket `/ws/mood` — mood transitions for the surface to animate.

### 14.2 MCP server (the existing one)
NEXUS exposes itself as an MCP server (`onexus mcp`) so Claude Desktop / Cursor / VS Code can use the kernel as their backend brain. The existing tools (`nexus_route`, `nexus_modules_*`, `nexus_agents_*`, `nexus_chronicle_*`, etc.) are preserved. New tools added:
- `nexus_workspace_list`, `nexus_workspace_switch`, `nexus_workspace_create`.
- `nexus_permission_grant`, `nexus_permission_revoke`.
- `nexus_mood_current`.

### 14.3 Third-party agent SDK
A small Python package `nexus-agent-sdk` (publish later) gives third-party authors:
- `Agent` base class for writing an MCP-served agent.
- Manifest schema + validator.
- Helpers for capability checks (the SDK doesn't enforce — the kernel does — but it gives authors typed access to the contract).
- A template generator: `nexus-agent-sdk new my-agent`.

This is documentation + plumbing, not a new runtime; the runtime is the host NEXUS instance.

## 15. Federation and Local-First Boundary

The local-first promise — "the kernel never touches the network" — is preserved literally. The kernel modules (`cortex.py`, `engram.py`, `pulse.py`, `chronicle.py`, `aegis.py`) make zero `import requests`, `import httpx`, `urllib` calls. Code review enforces this.

All network I/O lives in:
- The agent runtime, calling `aegis.network()`.
- LLM provider clients (`nexus/inference/openai_provider.py` etc.), which are invoked by agents and *also* route through `aegis.network()` (this is a change from the current code, where providers call out directly).

Federation:
- Existing federation code (`nexus/federation/`) keeps its discovery + peering API.
- Outbound traffic to peer ONEXUS instances flows through `aegis.network()` with the capability `network.federation.<peer-id>`.
- Federation is a per-workspace toggle; disabled by default in every workspace.

## 16. Lifecycle and Commands

### 16.1 CLI
Preserved + new:
```
onexus run                          # interactive session (current default workspace)
onexus serve                        # API + dashboard
onexus tui                          # Rich TUI (v0)
onexus dashboard                    # new Aurora dashboard (default)
onexus mcp                          # MCP server

onexus workspace list
onexus workspace new <name> [--template coding|design|...]
onexus workspace switch <name>
onexus workspace export <name> > template.json

onexus agent install <slug>
onexus agent uninstall <slug>
onexus agent list                   # all installed
onexus agent permissions <slug>
onexus agent sandbox <slug> --on|--off

onexus trust <slug>                 # current trust + tier
onexus permissions list [--workspace <name>] [--agent <slug>]
onexus permissions revoke <slug> <capability> [--workspace <name>]
onexus forget --yes                 # GDPR full erase
```

### 16.2 Pulse topics
New topics emitted on the bus:
- `workspace.created`, `workspace.switched`, `workspace.destroyed`.
- `agent.installed`, `agent.launched`, `agent.paused`, `agent.woken`, `agent.uninstalled`.
- `permission.requested`, `permission.granted`, `permission.revoked`.
- `network.outbound`, `network.outbound_denied`.
- `mood.changed` — payload `{from: "calm", to: "deliberating", drift_ms: 1200}`.
- `trust.event` — payload `{agent, prior, current, delta, reason}`.

## 17. Implementation Sequencing

All four sub-systems are in scope. The build order minimizes blockers:

1. **Foundation (no behaviour change yet)**
   - Define manifest schema v1 (`nexus/schemas/manifest.v1.json`).
   - Refactor `NexusModule` ABC to support `manifest()` + `tools()`.
   - Write `InProcessAgent` and `MCPAgent` adapters.
   - Extend `Aegis` with `check_capability()`, `fs()`, `network()`.

2. **Migration of the 9 built-ins**
   - Author manifests for each of the 9 modules.
   - Wrap each in `InProcessAgent`.
   - Replace `cortex._INTENT_DEFS` with manifest-driven intent loading.
   - Ensure every existing test still passes.

3. **Workspace layer**
   - Workspace storage layout, the workspace.json schema, the room manager.
   - Engram partitioning + per-workspace grants store.
   - Process supervisor with SIGSTOP/SIGCONT.
   - Workspace-aware Cortex (pins + per-workspace candidate pool).
   - Six built-in templates.

4. **Safety model**
   - Capability classes (Routine/Notable/Sensitive/Privileged).
   - Install review panel (frontend) and the install validator (backend).
   - First-use prompt UI + suspend/resume flow.
   - Trust-gated auto-grant logic in Aegis.

5. **New surfaces**
   - Aurora design system tokens, kernel mark, identity disc + bespoke icon library (build 6 remaining built-in glyphs).
   - Conversational primary surface.
   - Cockpit overlay (⌘\`).
   - Spatial catalog grid.
   - Settings panels.
   - Mood engine (state → CSS variables → animated mesh) + Pulse → mood mapping.

6. **Network gateway + federation rewire**
   - Route every existing outbound call through `aegis.network()`.
   - Per-workspace federation toggle.
   - Cockpit network panel.

7. **Polish**
   - Accessibility audit (Reduce Motion / Reduce Color / colour-blind / contrast).
   - All trust event overlays with the temperature trio.
   - Time-of-day modulation.
   - Export-as-template flow.

The implementation plan (separate document) will turn this sequence into atomic, reviewable tasks.

## 18. Out of Scope for v1

Explicitly *not* built in this design:
- Mobile clients.
- Multi-user accounts on a single NEXUS instance.
- Cross-machine memory sync (workspace structure exports as JSON; memory does not sync).
- A paid marketplace.
- Voice input as a primary surface (text-first; voice can be a wrapping agent later).
- Auto-update for installed agents (manual `onexus agent update <slug>` only).
- Community templates in the catalog (post-v1).

## 19. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Per-workspace processes burn RAM on machines with many rooms × many agents | SIGSTOP'd processes hold but do not run; configurable per-machine cap on simultaneous resident agents; user sees memory cost in Spatial grid before making an agent resident |
| Mood engine is too distracting | Accessibility "Reduce Motion" + "Reduce Color"; drift opacity capped; user can pick a single static tone per workspace |
| First-use prompts feel like permission fatigue | Two mitigations: workspace-scoped grants ("Always in Client work") and trust-gated auto-grant at Executor; users on a productive path will see prompts only when something unusual happens |
| Trust collapse cascade across workspaces feels too punishing | Only auto-grants are revoked, not user-pinned "Always in workspace" grants the user explicitly chose; the user can re-grant from Settings; Chronicle shows exactly what was revoked |
| Existing tests break during migration | Migration phase (sub-system 2) gates on "every existing test passes." Manifest-driven intents must produce identical routing decisions for all current test fixtures |
| Aurora animations harm performance on low-end machines | CSS-only meshes (no GPU canvas); blur is hardware-accelerated; mood transitions throttled to one per 800 ms; auto-reduce on `prefers-reduced-motion` |

## 20. Glossary

- **Agent** — any cognitive unit that runs under the NEXUS runtime. Built-in (e.g., Council) or catalog (e.g., aider). Has a manifest, intents, capabilities, an identity mark, a trust score.
- **Workspace** — a room. Owns its filesystem root(s), resident agents, memory partition, permission grants, home tone, and routing pins.
- **Resident** — an agent that is loaded and ready in the current workspace (warm process, MCP connection live). Becomes "sleeping" (SIGSTOP'd) when the workspace is left.
- **Routing pin** — a per-workspace mapping `{ intent → preferred agent slug }` that bypasses the chooser.
- **Permission class** — Routine / Notable / Sensitive / Privileged. Decides who asks, how often, and what happens on trust collapse.
- **Trust** — float 0.0–1.0, per agent, asymmetric ±0.12/−0.22 adjustment. Now also gates Notable auto-grants at Executor tier (≥ 0.75).
- **Mood** — one of eight ambient OS states tied to kernel conditions; rendered as a gradient mesh with a tuned drift speed.
- **Home tone** — a workspace's signature gradient (indigo / magenta / sage / plum / amber / custom). Bias applied to the active mood when Calm Focus is the active state.
- **Concierge synthesis** — the on-demand parallel-agent trace shown in the Cockpit ("show me who handled that and why").
- **Kernel mark** — the small breathing orb that signals "NEXUS is alive"; appears wherever the OS is present.

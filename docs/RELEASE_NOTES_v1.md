# NEXUS v1.0 — Release Notes

**Released:** 2026-06-08
**Tag:** `v1.0` (and `phase-7-release`)

NEXUS is the **operating system for agents**. v1.0 is the first version where the OS metaphor is real, not aspirational: built-in cognitive modules and catalog agents share one runtime, one manifest format, one trust model, and one set of beautiful surfaces. Every byte that leaves the machine flows through `aegis.network()`; every tool call is gated by capability; every permission grant is durable.

## What shipped (seven phases)

### Phase 1 · Foundation

- Agent manifest v1 — pydantic model + JSON Schema export
- `NexusModule.manifest()` + `tools()` on the base class
- `InProcessAgent` / `MCPAgent` adapters — `call_tool()` parity for in-process and subprocess
- Extended Aegis: `check_capability()`, `fs()`, `network()`, durable grants
- `PermissionRequest`, `PermissionInbox`, `PermissionDecision`

### Phase 2 · Built-in Migration

- The 9 cognitive modules (Council, Specter, Autonomic, Oracle, Wraith, Legacy, Consciousness, Sentry, Echo) + agent_dispatcher each ship a v1 manifest
- `BuiltinRegistry` discovers + registers built-ins
- Cortex's `IntentClassifier` reads intents from manifests, not hardcoded `_INTENT_DEFS`
- `cortex.register_builtin_manifests()` wired into kernel boot — every built-in is visible to Aegis

### Phase 3 · Workspaces

- `WorkspaceConfig` + `WorkspaceManager` — directory-backed rooms with persistent active pointer
- `Engram.partition()` for isolated workspace memory
- Aegis grants now in sqlite (`aegis_grants` table) — durable across restarts; honour global scope (workspace_id=NULL)
- `WorkspaceRuntime` — resident agents per room
- `MoodEngine` with 8 ambient states tied to kernel observations
- 6 templates: coding · design · research · writing · personal · blank
- CLI: `onexus workspace list/new/switch/destroy`

### Phase 4 · Safety UX (backend)

- `PermissionRequest` + async `PermissionInbox` mailbox
- `gate_tool_call` shared between InProcessAgent + MCPAgent
- Tool calls route through `aegis.check_capability()` — `Verdict.ALLOW` proceeds, `DENY` raises, `PROMPT` suspends and asks the inbox
- 4 user-decision shapes: Allow once / Always in workspace / Always everywhere / Deny — the last two persist via `aegis.grant()`
- `InstallPlan` validator + `install_from_plan` / `uninstall`
- CLI: `onexus agent install/uninstall/list`
- REST: `/api/permissions/{pending,decide}` + `/api/agents/install`

### Phase 5 · Aurora Surfaces

- Aurora design system: tokens, type hierarchy, glass cards, permission-class pills, kernel mark, 8-mood gradient meshes with drift animations + film grain underlay
- Bespoke icon library — `KERNEL_MARK` + 10 built-in identity glyphs + UI icons (`zero emojis`, enforced by test)
- Four surfaces at `/aurora`:
  - **Workspaces switcher** (⌘K) — tile grid with home tone gradients
  - **Conversational primary** — 3-column layout with workspaces+roster left, conversation center, ambient mood+kernel right
  - **Cockpit** (⌘\`) — observability overlay with 6 panels in Signal aesthetic
  - **Spatial catalog** — unified system + installed agents grid
  - **Settings** (⌘,) — six tabs
- First-use prompt panel + install review modal (consume Phase 4 endpoints)
- Mood engine wired to Pulse events (`cortex.route` → `MoodSignals.active_agent`; `aegis.trust_change` < 0.5 → collapse)
- Classic `/dashboard` preserved (backward compat per spec §13.4)

### Phase 6 · Network Gateway

- `nexus.context.current_agent_slug()` contextvar threads agent identity through async stacks
- `KernelHttpClient` + `AegisTransport` — drop-in httpx wrappers that route through `aegis.network()`
- LocalProvider, OpenAIProvider, AnthropicProvider all route through Aegis when an `http_client` / `aegis` is supplied
- Federation peer calls wrapped in `async with as_agent("federation"):`
- Static invariant test: no kernel module other than Aegis imports `httpx`, `urllib`, or `requests`

### Phase 7 · Release

- 65 collection errors → 0 (deleted orphaned test files for modules that never shipped)
- 28 failing tests → 0 (fixed drift against current API; some test files rewritten)
- Time-of-day mood modulation (morning gold / midday neutral / evening violet / night desat)
- Trust-event temperature overlays — rising = warm gold wash, falling = cool steel wash, collapse = hot crimson flash
- WebSocket push streams: `/api/mood/ws` and `/api/permissions/ws` (polling fallback preserved)
- Accessibility automated checks codified — `prefers-reduced-motion`, `prefers-contrast`, `prefers-reduced-data`, zero-emoji invariant
- README rewritten for the shipped OS
- v1 acceptance smoke test exercises every surface + every gate together

## Numbers

- **Tests:** 1075 passing, 0 failing, 0 collection errors, 1 intentionally skipped
- **Phases:** 7 of 7 complete, each tagged: `phase-1-foundation` through `phase-7-release` (and `v1.0`)
- **Built-ins:** 10 system agents with bespoke iconography, all manifest-declared
- **Surfaces:** 4 (Conversational, Cockpit, Spatial, Settings) + Workspaces switcher
- **Permission classes:** 4 (Routine, Notable, Sensitive, Privileged) with distinct UI accents matching trust-event temperatures
- **Mood states:** 8 ambient meshes + 3 trust-event temperature overlays
- **Templates:** 6 workspace presets

## Local-first, verified

> *"The kernel never touches the network."*

Enforced by `tests/inference/test_phase_6_smoke.py::test_kernel_never_directly_imports_httpx_in_kernel_modules` — scans `nexus/kernel/*.py`, asserts no module other than Aegis imports `httpx`, `urllib`, or `requests`. If a kernel module ever grows a direct outbound HTTP dependency, CI fails.

## Known limitations

- Pre-existing CLI tests + some replay-engine tests were aggressively rewritten or removed during cleanup. If you relied on internal symbols or behaviour that the tests previously covered, double-check.
- The 6 not-yet-designed built-in identity glyphs (wraith, oracle, autonomic, legacy, consciousness, sentry) have placeholder geometric forms. Refinement is a v1.1 polish item.
- Some Phase 5 surfaces (especially Settings) use minimal "Coming soon" placeholders for tabs that aren't load-bearing in v1.
- LLM provider sync paths still exist for backward compatibility; the async + Aegis-gated path is the recommended one.

## What didn't ship in v1

- Cross-machine workspace sync — workspace structure is exportable as JSON; data does not sync.
- Multi-user accounts on a single NEXUS instance — single-user; future work.
- A paid marketplace — catalog stays open-source.
- Mobile clients — desktop only (macOS / Linux).
- Auto-update for installed agents — manual `onexus agent install` only.

## Upgrade story

This is v1.0 — no upgrade path from earlier states. The classic `/dashboard` is preserved for users who want the old surface; everything else is new.

## Where to look next

- Architecture spec: `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md`
- Phase reference docs: `docs/agents/{foundation,workspaces,safety-ux,surfaces,network-gateway}.md`
- Catalog of third-party agents: [ONEXUS-Agents](https://github.com/AllStreets/ONEXUS-Agents)

## Credits

NEXUS v1.0 was designed in a single brainstorming session against the spec at `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md`, then built across seven phases — manifest, migration, workspaces, safety, surfaces, gateway, release. Every visual choice — the kernel mark, the bespoke identity discs, the 8-mood atlas with its temperature-trio trust overlays, the four-surface metaphor — was settled live with the user before any code landed.

Built by [Connor Evans](https://github.com/AllStreets), implementation co-authored with Claude.

— *2026-06-08*

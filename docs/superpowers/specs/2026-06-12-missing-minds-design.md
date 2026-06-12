# NEXUS v2 — The Missing Minds

**Date:** 2026-06-12
**Branch:** `feat/missing-minds`
**Status:** Approved (direction approved by operator 2026-06-12; all three layers selected)

## Mission

NEXUS v1 shipped the kernel (Cortex, Aegis, Engram, Chronicle, Pulse), 10 of the 19
modules in `docs/specs/design.md`, and Aurora. v2 ships the missing minds — the modules
that turn an agent OS into something with genuine cognition — and makes Aurora visualize
the kernel live. Three layers, shipped in order; each lands on the existing manifest v1 /
Aegis trust / Chronicle audit contracts without modifying them.

Non-goals: changing kernel contracts, reworking shipped modules, multimodal (stays
phase-2-TBD), bundling Python in the standalone app.

---

## Layer N1 — Perception

### N1.1 Sigil — threat radar

- New module `nexus/modules/sigil.py` (manifest v1, in_process, base trust 0.30 like all
  modules; its *detections* carry weight through Pulse priority, not through elevated
  trust).
- Watches: Chronicle event stream + Pulse traffic + Aegis trust deltas. Detection rules
  v1 (deterministic, table-driven):
  - trust collapse (module trust falls a full tier within a session),
  - denied-call bursts (N denials in M minutes from one module),
  - runaway loops (Sentry already detects; Sigil consumes Sentry signals and correlates
    across modules),
  - anomalous egress cadence (Aegis network log rate spikes vs. workspace baseline),
  - permission-escalation patterns (repeated requests for the same privileged
    capability after denial).
- On detection: emit a Pulse message with `priority: emergency` and provenance hash;
  Cortex gives emergency-priority Pulse messages a routing bypass (small, contained
  change in `cortex.py` routing preamble); Chronicle records the broadcast. High-stakes
  detections auto-activate Specter for an adversarial read of the triggering context.
- Every detection is observable in Aurora (N1.3) and queryable via a new
  `/api/sigil/detections` route.

### N1.2 Atlas — temporal knowledge graph with confidence decay

- New module `nexus/modules/atlas.py` + storage extension in Engram's semantic tier:
  facts become nodes with `(subject, relation, object, confidence, observed_at,
  last_confirmed_at, source_ref)`; edges link related facts.
- Confidence decay: a deterministic decay function (half-life per fact class; config
  default, overridable) applied at read time — old unconfirmed facts fade rather than
  lie. Re-confirmation (the same fact observed again) restores confidence and bumps
  `last_confirmed_at`.
- Atlas answers: "what do we believe about X, with what confidence, learned when, from
  where" — with citations to Chronicle/Engram sources. Contradictory facts coexist with
  competing confidences instead of overwriting.
- Sqlite remains the store (same as the rest of Engram); no new external dependencies.

### N1.3 Aurora — live kernel visualization

- New cockpit panel (and ⌘-shortcut overlay) rendering the kernel as a living system:
  Cortex routing decisions appearing as they happen (which signals fired, which module
  won), Aegis gates resolving (allow/prompt/deny with capability class colors), trust
  sparklines per module, Sigil detections as radar pings, Pulse emergency broadcasts as
  full-surface alerts consistent with the existing mood-engine alert palette.
- Transport: the existing SSE/WebSocket event infrastructure (`routes/events.py`);
  new event topics `kernel.route`, `kernel.gate`, `sigil.detection`. No polling.
- Visual language: existing tokens.css / mood.css palettes, line-stroke SVG glyphs from
  `icons.js` (Sigil gets a real identity glyph — concentric radar arcs). No emoji,
  enforced by the existing accessibility tests.

## Layer N2 — Cognition

### N2.1 Prism — cross-domain synthesis

- Module that reads across Engram partitions (with Aegis-gated cross-workspace access —
  cross-partition reads are a `sensitive` capability, always prompted) and surfaces
  connections: recurring entities, contradictions between workspaces, patterns the
  per-workspace view can't see. Outputs cite Engram/Atlas sources.

### N2.2 Chronos/Dreamweaver — overnight synthesis + counterfactuals

- Dreamweaver: a scheduled batch run (local scheduler, kill-switch file consistent with
  ecosystem conventions) over the day's episodic memory → distilled semantic/Atlas
  facts, surfaced as a morning brief in Aurora.
- Chronos: counterfactual queries over Chronicle's decision history — "what would have
  happened if that grant had been denied" — replaying the decision DAG with one node
  flipped, reporting which downstream actions had that decision as a dependency.
  Deterministic dependency tracing first; LLM narration optional on top.

### N2.3 Aurora surfaces

- Atlas graph view (force layout over the knowledge graph, confidence as opacity,
  decay visible as fading), Chronos timeline (decision history with counterfactual
  branch points), morning-brief card.

## Layer N3 — Society

### N3.1 Herald/Forge — agent-to-agent negotiation

- Structured negotiation protocol between agents inside Aegis boundaries: proposals,
  counters, and commitments are typed Pulse messages; Aegis gates each commitment by
  capability class; Chronicle records the full negotiation transcript.

### N3.2 Federation peer operations

- Wire the existing federation config to real peer discovery + scoped sync between
  NEXUS instances (workspace-scoped, allowlist-only peers, Aegis-gated). 

### N3.3 Serendipity + Aurora v3

- Serendipity: anti-optimization discovery (deliberately surfaces low-relevance-score
  but high-novelty items from Engram/Atlas on a budget).
- Aurora v3 responsive layout per `docs/superpowers/plans/2026-06-09-aurora-v3-layout.md`
  + finished identity glyphs for the six placeholder modules.

---

## Invariants (all layers)

- Kernel contracts unchanged: every new module is a manifest-v1 NexusModule starting at
  ADVISOR trust; every tool call passes `aegis.check_capability()`; every action lands
  in Chronicle; the only kernel module touching the network remains Aegis (the static
  import invariant test must keep passing).
- All new automated behavior (Dreamweaver schedule, Sigil auto-activation of Specter,
  federation sync) ships with a kill switch and is observable in Aurora.
- Zero emoji anywhere; existing accessibility tests extended to new surfaces.

## Testing strategy

- TDD against the worktree venv. N1: table-driven Sigil detection tests; Cortex
  emergency-bypass routing tests; Atlas decay/confirmation/contradiction golden tests;
  event-topic contract tests for the new SSE streams; Aurora asset tests extended
  (no-emoji, reduced-motion).
- N2/N3 get their own plan-level test design when their build starts.

## Build order

N1.1 → N1.2 → N1.3 → N2.1 → N2.2 → N2.3 → N3.1 → N3.2 → N3.3. Aurora work ships with
the layer that produces its data.

# N2 — Prism cross-domain synthesis · Chronos/Dreamweaver temporal reasoning · Aurora surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Layer N2 of the missing-minds spec on top of N1. Prism (`nexus/modules/prism.py`) reads across Engram partitions behind an Aegis-gated `Sensitive` cross-partition capability (always prompted) and surfaces recurring entities, cross-workspace contradictions, and patterns the per-workspace view can't see — every output citing its Engram/Atlas source. Chronos answers counterfactual queries over Chronicle's decision history by replaying a deterministically-reconstructed decision DAG with one node flipped and reporting which downstream actions depended on it. Dreamweaver runs an overnight batch (local asyncio scheduler, env + kill-switch file) over the day's episodic memory, distilling semantic/Atlas facts into a morning brief. Aurora gains an Atlas force-layout graph view, a Chronos counterfactual timeline, a morning-brief card, and identity glyphs for Prism and Chronos.

**Architecture:** Prism and Chronos are manifest-v1 `NexusModule`s (in_process, base trust 0.30 / ADVISOR) landing on the existing Cortex/Aegis/Chronicle/Pulse/Engram contracts without modifying kernel contracts. Cross-partition synthesis is enabled by declaring `engram.read.global` as a **Sensitive** capability in Prism's manifest — `Aegis._decide_capability` already returns **PROMPT** for any Sensitive capability without an explicit grant, which is exactly the spec's "always prompted" requirement (no kernel change needed). Prism enumerates workspaces via the existing `WorkspaceManager.list()` and reads each partition's Engram (`Engram.partition()` → `.atlas` / `.episodic`), reusing the N1 `AtlasFacts` store. Chronos reconstructs the decision DAG purely from existing Chronicle rows (`cortex` route/response, `aegis` permission_granted / aegis.trust_change) — no new logging, deterministic tracing first, LLM narration optional and off by default. Dreamweaver is a background `asyncio.create_task` loop attached in the app lifespan (mirroring the existing `_catalog_refresher`), guarded by `dreamweaver_enabled(config)` (env `NEXUS_DREAMWEAVER=0` or `<data_dir>/dreamweaver.kill`, mirroring N1's `specter_autoactivation_enabled`); each run writes distilled facts to Engram semantic/Atlas and a `dreamweaver`/`morning_brief` record to Chronicle, observable in Aurora. Aurora surfaces consume new REST routes (`/api/prism`, `/api/chronos`, `/api/atlas`, `/api/dreamweaver`) and the existing `/api/events/ws` Pulse relay — no polling.

**Tech Stack:** Python 3.14 / FastAPI / SQLite / Pulse async pub-sub (existing kernel), pytest + pytest-asyncio (`asyncio_mode = "auto"`), vanilla ES-module JS + hand-drawn SVG (Aurora, no build step). Tests run with `.venv/bin/python -m pytest` from the worktree root. Baseline green at 1159 passed.

## Spec deviations (approved adaptations)

1. **"Aegis-gated cross-workspace access — `sensitive` capability, always prompted":** Implemented declaratively. Prism declares `engram.read.global` under **Sensitive** in its manifest; `Aegis._decide_capability` (aegis.py ~line 639) already returns `PROMPT` for Sensitive capabilities with no explicit grant. Prism treats any non-`ALLOW` verdict as "blocked unless approved" and degrades to single-partition (active workspace) synthesis with a banner, rather than silently reading every partition. No kernel change.
2. **"Replay the decision DAG":** Chronicle stores a flat, append-only event log, not a materialized DAG. Chronos reconstructs a deterministic dependency graph in memory from existing Chronicle rows within a session/time window: a `permission_granted` / `aegis.trust_change` / `cortex.route` node is an *upstream dependency* of every later `cortex.response` / module action that names the same module (and, for grants, the same capability) before the next contradicting event. Flipping a node prunes its dependents. This is the "deterministic dependency tracing first" the spec calls for; the heuristic edges are explicit and tested.
3. **"What would have happened if that grant had been denied":** A counterfactual is keyed by a Chronicle `event_id` (or a `(module, action)` selector). Flipping a `permission_granted` to denied removes that grant node and every downstream node whose module depended on it within the window; Chronos reports the pruned (would-not-have-happened) actions. There is no live re-execution — the kernel is never re-run — only dependency-graph pruning over recorded history, which keeps it deterministic and side-effect-free.
4. **"Overnight batch / local scheduler":** Implemented as an in-process `asyncio` interval loop in the FastAPI lifespan (same mechanism as the existing `_catalog_refresher` background task), not an OS cron. Interval defaults to 24h and is overridable via `NEXUS_DREAMWEAVER_INTERVAL_S` for tests. A single immediate `Dreamweaver.run_once()` is also exposed for the CLI/`/api/dreamweaver/run` and for deterministic testing. Kill switch: env `NEXUS_DREAMWEAVER=0/false/no` or `<data_dir>/dreamweaver.kill`.
5. **"Distilled semantic/Atlas facts":** Dreamweaver distillation v1 is deterministic and table-driven (no LLM dependency): it scans the day's `episodic` rows + `cortex.route` Chronicle rows for recurring `(source, token)` frequencies above a threshold and writes them as Atlas facts (`day --observed--> <topic>`) plus a semantic-memory summary. LLM narration of the brief is optional, off by default, and never required for the brief to render.
6. **Aurora `/api/atlas/graph`:** N1 shipped the `AtlasFacts` store and `AtlasModule` but no graph REST surface. N2.3 adds `GET /api/atlas/graph` (nodes = facts with effective confidence, edges = `atlas_edges`) so the Aurora force-layout view has a data source. This reads the active-workspace Engram only by default; the global view requires the same Prism Sensitive gate.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `nexus/modules/prism.py` | Create | `PrismModule` (manifest v1, `engram.read.global` Sensitive), `CrossDomainSynthesizer` (recurring entities, contradictions, patterns across partitions, citations) |
| `nexus/synthesis/__init__.py` | Create | package marker |
| `nexus/synthesis/dreamweaver.py` | Create | `dreamweaver_enabled()`, `Dreamweaver` (deterministic distillation, `run_once()`, kill switch), morning-brief builder |
| `nexus/synthesis/chronos.py` | Create | `DecisionGraph` (reconstruct DAG from Chronicle), `Chronos` (counterfactual flip + downstream prune), optional narration hook |
| `nexus/modules/chronos.py` | Create | `ChronosModule` (manifest v1, `chronicle.read.workspace` Routine) wrapping `synthesis.chronos` |
| `nexus/kernel/cortex.py` | Modify | register Prism + Chronos in `default_builtin_registry()` |
| `nexus/api/server.py` | Modify | register Prism/Chronos modules; wire Dreamweaver background task in lifespan with kill switch; mount new routers |
| `nexus/api/routes/prism.py` | Create | `GET /api/prism/synthesis` (gated cross-partition) |
| `nexus/api/routes/chronos.py` | Create | `GET /api/chronos/timeline`, `POST /api/chronos/counterfactual` |
| `nexus/api/routes/atlas.py` | Create | `GET /api/atlas/graph` (force-layout data) |
| `nexus/api/routes/dreamweaver.py` | Create | `GET /api/dreamweaver/brief`, `POST /api/dreamweaver/run` |
| `nexus/aurora/icons.js` | Modify | `GLYPHS.prism`, `GLYPHS.chronos`, `GRADIENTS`, `BUILTIN_CAPABILITIES` entries; add to BUILTINS roster |
| `nexus/aurora/index.html` | Modify | cockpit-rail morning-brief card mount (`#nx-morning-brief`) |
| `nexus/aurora/app.js` | Modify | `state.n2`, brief fetch + render, Atlas graph force-layout view, Chronos timeline view, hash routes `#/atlas` and `#/chronos`, `dreamweaver.brief` WS handling |
| `nexus/aurora/app.css` | Modify | atlas-graph node/edge styles (confidence opacity, decay fade), chronos timeline + branch-point styles, morning-brief card; reduced-motion guards |
| `tests/synthesis/test_dreamweaver.py` | Create | distillation, kill switch, brief shape, Chronicle/Atlas writes |
| `tests/synthesis/test_chronos.py` | Create | DAG reconstruction, counterfactual prune golden tests |
| `tests/modules/test_prism_manifest.py` / `test_prism.py` | Create | manifest + behavior pair |
| `tests/modules/test_chronos_manifest.py` / `test_chronos.py` | Create | manifest + behavior pair |
| `tests/aurora/test_prism_routes.py` | Create | `/api/prism/synthesis` gated route |
| `tests/aurora/test_chronos_routes.py` | Create | timeline + counterfactual routes |
| `tests/aurora/test_atlas_graph_route.py` | Create | `/api/atlas/graph` route |
| `tests/aurora/test_dreamweaver_routes.py` | Create | brief + run routes |
| `tests/aurora/test_n2_surfaces.py` | Create | glyphs, topics, views, no-emoji, reduced-motion asset contracts |

---

## Task 1 — Chronos decision graph + counterfactual engine (deterministic)

**Files:** Create `nexus/synthesis/__init__.py`, `nexus/synthesis/chronos.py`. Create `tests/synthesis/test_chronos.py`.

- [ ] **1.1 Failing test.** Create `tests/synthesis/test_chronos.py`:

```python
"""N2.2 — Chronos deterministic decision-graph reconstruction + counterfactuals."""
from __future__ import annotations

from nexus.kernel.chronicle import Chronicle
from nexus.synthesis.chronos import Chronos, DecisionGraph


def _chronicle(tmp_path):
    c = Chronicle(str(tmp_path / "c.sqlite"))
    c.init_db()
    return c


def _seed_grant_then_actions(c):
    c.log("aegis", "permission_granted",
          {"agent_slug": "wraith", "capability": "fs.write.workspace"})
    c.log("cortex", "route", {"target": "wraith", "message_preview": "write report"})
    c.log("cortex", "response", {"module": "wraith", "response_preview": "wrote report.md"})
    c.log("cortex", "route", {"target": "council", "message_preview": "decide offers"})
    c.log("cortex", "response", {"module": "council", "response_preview": "chose A"})


def test_graph_reconstructs_nodes_from_chronicle(tmp_path):
    c = _chronicle(tmp_path)
    _seed_grant_then_actions(c)
    graph = DecisionGraph.from_chronicle(c)
    kinds = {n.kind for n in graph.nodes}
    assert "grant" in kinds and "route" in kinds and "response" in kinds
    assert len(graph.nodes) == 5


def test_grant_is_upstream_dependency_of_same_module_actions(tmp_path):
    c = _chronicle(tmp_path)
    _seed_grant_then_actions(c)
    graph = DecisionGraph.from_chronicle(c)
    grant = next(n for n in graph.nodes if n.kind == "grant")
    dependents = graph.downstream(grant.id)
    modules = {graph.node(nid).module for nid in dependents}
    assert modules == {"wraith"}
    assert len(dependents) == 2


def test_counterfactual_deny_grant_prunes_downstream(tmp_path):
    c = _chronicle(tmp_path)
    _seed_grant_then_actions(c)
    chronos = Chronos(c)
    grant = next(n for n in DecisionGraph.from_chronicle(c).nodes if n.kind == "grant")
    result = chronos.counterfactual(grant.id)
    assert result["flipped"]["kind"] == "grant"
    assert result["flipped"]["module"] == "wraith"
    pruned_modules = {a["module"] for a in result["would_not_have_happened"]}
    assert pruned_modules == {"wraith"}
    assert any(a["module"] == "council" for a in result["unaffected"])


def test_counterfactual_by_selector_matches_first_grant(tmp_path):
    c = _chronicle(tmp_path)
    _seed_grant_then_actions(c)
    chronos = Chronos(c)
    result = chronos.counterfactual_by(module="wraith", action="permission_granted")
    assert result["flipped"]["module"] == "wraith"
    assert len(result["would_not_have_happened"]) == 2


def test_unknown_event_id_returns_empty_counterfactual(tmp_path):
    c = _chronicle(tmp_path)
    _seed_grant_then_actions(c)
    chronos = Chronos(c)
    result = chronos.counterfactual("does-not-exist")
    assert result["flipped"] is None
    assert result["would_not_have_happened"] == []
```

- [ ] **1.2 Run, expect failure:** `.venv/bin/python -m pytest tests/synthesis/test_chronos.py -q` → `ModuleNotFoundError: No module named 'nexus.synthesis'`.
- [ ] **1.3 Implement.** Create `nexus/synthesis/__init__.py`:

```python
"""N2 synthesis package — Chronos counterfactuals, Dreamweaver overnight distillation."""
```

Create `nexus/synthesis/chronos.py`:

```python
# nexus/synthesis/chronos.py
"""
Chronos -- counterfactual reasoning over Chronicle's decision history (N2.2).

Chronicle is a flat, append-only audit log. Chronos reconstructs a
deterministic in-memory dependency graph from recorded events, then answers
counterfactuals ("what would have happened if that grant had been denied")
by flipping one node and pruning everything that depended on it. The kernel
is never re-run -- this is pure history analysis, side-effect free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nexus.kernel.chronicle import Chronicle


_MODULE_KEYS = ("module", "target", "agent_slug", "agent")


def _module_of(payload: dict[str, Any]) -> str | None:
    for k in _MODULE_KEYS:
        v = payload.get(k)
        if v:
            return str(v)
    return None


@dataclass
class DecisionNode:
    id: str
    kind: str          # "grant" | "route" | "response" | "trust_change" | "error"
    module: str | None
    action: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionGraph:
    nodes: list[DecisionNode]
    _edges: dict[str, set[str]] = field(default_factory=dict)
    _by_id: dict[str, DecisionNode] = field(default_factory=dict)

    _KIND = {
        ("aegis", "permission_granted"): "grant",
        ("cortex", "route"): "route",
        ("cortex", "response"): "response",
        ("cortex", "module_error"): "error",
        ("aegis", "aegis.trust_change"): "trust_change",
    }

    @classmethod
    def from_chronicle(cls, chronicle: Chronicle, *, limit: int = 5000) -> "DecisionGraph":
        rows = chronicle.query(limit=limit)
        rows = sorted(rows, key=lambda r: r["timestamp"])
        nodes: list[DecisionNode] = []
        for r in rows:
            kind = cls._KIND.get((r["source"], r["action"]))
            if kind is None:
                continue
            payload = r["payload"] or {}
            nodes.append(DecisionNode(
                id=r["event_id"], kind=kind, module=_module_of(payload),
                action=r["action"], timestamp=r["timestamp"], payload=payload,
            ))
        graph = cls(nodes=nodes)
        graph._by_id = {n.id: n for n in nodes}
        graph._build_edges()
        return graph

    def _build_edges(self) -> None:
        self._edges = {n.id: set() for n in self.nodes}
        for i, src in enumerate(self.nodes):
            if src.kind != "grant" or not src.module:
                continue
            for later in self.nodes[i + 1:]:
                if later.kind == "trust_change" and later.module == src.module:
                    new = later.payload.get("new_score")
                    if isinstance(new, (int, float)) and new < 0.5:
                        break
                    continue
                if later.module == src.module and later.kind in ("route", "response", "error"):
                    self._edges[src.id].add(later.id)
        for i, src in enumerate(self.nodes):
            if src.kind != "route" or not src.module:
                continue
            for later in self.nodes[i + 1:]:
                if later.module == src.module and later.kind == "response":
                    self._edges[src.id].add(later.id)
                    break

    def node(self, node_id: str) -> DecisionNode:
        return self._by_id[node_id]

    def downstream(self, node_id: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self._edges.get(node_id, set()))
        while stack:
            nid = stack.pop()
            if nid in seen:
                continue
            seen.add(nid)
            stack.extend(self._edges.get(nid, set()))
        return seen


class Chronos:
    """Counterfactual queries over the reconstructed decision graph."""

    def __init__(self, chronicle: Chronicle,
                 narrator: Callable[[dict[str, Any]], str] | None = None) -> None:
        self._chronicle = chronicle
        self._narrator = narrator

    def _serialize(self, n: DecisionNode) -> dict[str, Any]:
        return {"id": n.id, "kind": n.kind, "module": n.module,
                "action": n.action, "timestamp": n.timestamp,
                "preview": n.payload.get("response_preview")
                          or n.payload.get("message_preview")
                          or n.payload.get("capability") or ""}

    def timeline(self, limit: int = 200) -> list[dict[str, Any]]:
        graph = DecisionGraph.from_chronicle(self._chronicle, limit=limit)
        branchable = {n.id for n in graph.nodes if n.kind in ("grant", "route")}
        out = []
        for n in graph.nodes:
            d = self._serialize(n)
            d["branch_point"] = n.id in branchable
            out.append(d)
        return out

    def counterfactual(self, event_id: str) -> dict[str, Any]:
        graph = DecisionGraph.from_chronicle(self._chronicle)
        if event_id not in graph._by_id:
            return {"flipped": None, "would_not_have_happened": [], "unaffected": []}
        pruned = graph.downstream(event_id)
        flipped = graph.node(event_id)
        result = {
            "flipped": self._serialize(flipped),
            "would_not_have_happened": [self._serialize(graph.node(nid)) for nid in
                                        sorted(pruned, key=lambda i: graph.node(i).timestamp)],
            "unaffected": [self._serialize(n) for n in graph.nodes
                           if n.id != event_id and n.id not in pruned],
        }
        if self._narrator is not None:
            result["narration"] = self._narrator(result)
        return result

    def counterfactual_by(self, *, module: str, action: str) -> dict[str, Any]:
        graph = DecisionGraph.from_chronicle(self._chronicle)
        for n in graph.nodes:
            if n.module == module and n.action == action:
                return self.counterfactual(n.id)
        return {"flipped": None, "would_not_have_happened": [], "unaffected": []}
```

- [ ] **1.4 Run to pass:** `.venv/bin/python -m pytest tests/synthesis/test_chronos.py -q` → all pass. (Confirm `Chronicle.query` and `Chronicle.log` signatures match — adapt the row-key access if `query` returns objects vs dicts.)
- [ ] **1.5 Commit:** `git add -A && git commit -m "feat(chronos): deterministic decision-graph counterfactual engine over Chronicle"`

## Task 2 — ChronosModule: manifest, behavior, registration

**Files:** Create `nexus/modules/chronos.py`. Modify `nexus/kernel/cortex.py` (`default_builtin_registry`). Modify `nexus/api/server.py` (import + module list). Create `tests/modules/test_chronos_manifest.py`, `tests/modules/test_chronos.py`.

- [ ] **2.1 Failing tests.** Create the manifest test (slug `chronos`, system True, in_process, trust floor 0.30/ADVISOR, intent `COUNTERFACTUAL`, only `chronicle.read.workspace` Routine, in `default_builtin_registry().slugs()`) and the behavior test (timeline reports branch points; a "what if wraith permission_granted denied" counterfactual reports pruned actions; reads gated by `check_capability` — a bare Aegis with no manifest returns DENY and `handle` returns "blocked by Aegis"; a query lands in Chronicle source `chronos` action `query`). Mirror the N1 `tests/modules/test_atlas*.py` structure exactly.
- [ ] **2.2 Run, expect failure:** `ModuleNotFoundError: No module named 'nexus.modules.chronos'`.
- [ ] **2.3 Implement.** Create `nexus/modules/chronos.py`:

```python
# nexus/modules/chronos.py
"""Chronos -- temporal counterfactual reasoning (N2.2). Wraps synthesis.chronos."""
from __future__ import annotations

import re
from typing import Any

from nexus.modules.base import NexusModule
from nexus.synthesis.chronos import Chronos


_CF_RE = re.compile(
    r"(?:what\s+if|counterfactual[:,]?)\s+(?P<module>[\w-]+)\s+(?P<action>[\w.]+)?",
    re.IGNORECASE,
)


class ChronosModule(NexusModule):
    name = "chronos"
    description = (
        "Temporal counterfactual reasoning -- replay the decision history with "
        "one node flipped and report which downstream actions depended on it"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "chronos",
            "name": "chronos",
            "tagline": "Counterfactuals: replay the decision DAG with one node flipped.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reasoning",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:chronos",
                                  "gradient": ["#b8c4ff", "#3a4a9c"]}},
            "intents": [{
                "name": "COUNTERFACTUAL",
                "patterns": [
                    r"\bchronos\b", r"\bcounterfactual\b", r"\bwhat\s+if\b",
                    r"\bwould\s+have\s+happened\b", r"\bdecision\s+history\b",
                    r"\bdecision\s+timeline\b", r"\bif\s+.*\s+had\s+been\s+denied\b",
                ],
                "semantic_signals": [
                    "chronos", "counterfactual", "what would have happened",
                    "what if", "decision history", "decision timeline",
                    "if that grant had been denied", "replay decisions",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["chronicle.read.workspace"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        chronicle = context.get("chronicle")
        if aegis is not None:
            decision = aegis.check_capability("chronos", "chronicle.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Chronos] Read blocked by Aegis: " + decision.reason
        if chronicle is None:
            return "[Chronos] Chronicle unavailable."
        chronos = Chronos(chronicle)

        m = _CF_RE.search(message)
        if m and ("what if" in message.lower() or "counterfactual" in message.lower()):
            module = m.group("module").lower()
            action = (m.group("action") or "permission_granted").lower()
            result = chronos.counterfactual_by(module=module, action=action)
            chronicle.log("chronos", "query",
                          {"mode": "counterfactual", "module": module, "action": action})
            if result["flipped"] is None:
                return f"[Chronos] No recorded '{action}' decision for '{module}' to flip."
            lines = [
                f"[Chronos] Counterfactual: if {module}'s {action} had been denied —",
                f"  flipped: {result['flipped']['action']} @ {result['flipped']['timestamp'][:19]} "
                f"(event {result['flipped']['id']})",
                "  Would NOT have happened:",
            ]
            for a in result["would_not_have_happened"]:
                lines.append(f"    - {a['module']} · {a['action']} · {a['preview'][:48]}")
            if not result["would_not_have_happened"]:
                lines.append("    (nothing downstream depended on it)")
            return "\n".join(lines)

        timeline = chronos.timeline(limit=40)
        chronicle.log("chronos", "query", {"mode": "timeline", "results": len(timeline)})
        if not timeline:
            return "[Chronos] No decisions recorded yet."
        lines = ["[Chronos] Decision timeline (branch points marked *):"]
        for d in timeline[-15:]:
            mark = "*" if d["branch_point"] else " "
            lines.append(f"  {mark} {d['timestamp'][:19]} {d['kind']:<8} "
                         f"{(d['module'] or '-'):<10} {d['preview'][:40]}")
        return "\n".join(lines)
```

- [ ] **2.4 Register.** Add `ChronosModule` to `default_builtin_registry()` in `cortex.py` and to the module-registration loop in `server.py` (after the N1 `AtlasModule` import/registration). Match the exact pattern N1 used for Sigil/Atlas.
- [ ] **2.5 Run to pass:** `.venv/bin/python -m pytest tests/modules/test_chronos_manifest.py tests/modules/test_chronos.py tests/kernel/test_cortex_manifest_loading.py tests/release -q` → all pass.
- [ ] **2.6 Commit:** `git add -A && git commit -m "feat(chronos): counterfactual reasoning module with kernel + server registration"`

## Task 3 — Prism cross-domain synthesizer

**Files:** Create `nexus/modules/prism.py`. Modify `cortex.py` + `server.py` registration. Create `tests/modules/test_prism_manifest.py`, `tests/modules/test_prism.py`.

- [ ] **3.1 Failing tests.** Manifest test (slug `prism`, system True, in_process, 0.30/ADVISOR, intent `CROSS_DOMAIN_SYNTHESIS`, `engram.read.global` declared **Sensitive** + `engram.read.workspace` Routine, in registry). Behavior test using `WorkspaceManager` (create alpha+beta workspaces, seed each partition's `Engram(...).atlas` with facts): cross-partition read is blocked without a grant (output mentions approval/prompt/sensitive); after `aegis.grant("prism", "engram.read.global", workspace_id=None)`, a recurring entity ("acme" in both) is surfaced with citations to both partitions; a contradiction (alpha hq=berlin vs beta hq=munich) is surfaced; synthesis lands in Chronicle source `prism` action `synthesis`. Mirror the exact WorkspaceManager/Engram-partition seeding the N1 tests used.
- [ ] **3.2 Run, expect failure:** `ModuleNotFoundError`.
- [ ] **3.3 Implement.** Create `nexus/modules/prism.py` with `CrossDomainSynthesizer` (pure `recurring_entities(partitions, min_workspaces=2)` and `contradictions(partitions)` over `[(ws_id, [fact dicts])]`, citations `ws_id:source_ref`) and `PrismModule` (manifest with `engram.read.global` Sensitive; `_load_partitions(mgr)` reading each workspace's `atlas_facts`; `handle` checks `aegis.check_capability("prism", "engram.read.global")` — non-ALLOW returns the "needs approval / Sensitive / no partitions read" banner; else synthesizes recurring entities or contradictions per the message, chronicles, returns cited findings):

```python
# nexus/modules/prism.py
"""Prism -- cross-domain synthesis (N2.1). Aegis-gated cross-partition reads."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from nexus.modules.base import NexusModule


class CrossDomainSynthesizer:
    def recurring_entities(self, partitions, min_workspaces=2):
        by_subject = defaultdict(set)
        cites = defaultdict(list)
        for ws_id, facts in partitions:
            for f in facts:
                by_subject[f["subject"]].add(ws_id)
                cites[f["subject"]].append(f"{ws_id}:{f.get('source_ref') or f.get('id', '')}")
        out = []
        for subject, workspaces in by_subject.items():
            if len(workspaces) >= min_workspaces:
                out.append({"subject": subject, "workspaces": sorted(workspaces),
                            "citations": cites[subject]})
        out.sort(key=lambda e: (-len(e["workspaces"]), e["subject"]))
        return out

    def contradictions(self, partitions):
        index = defaultdict(lambda: defaultdict(list))
        for ws_id, facts in partitions:
            for f in facts:
                index[(f["subject"], f["relation"])][f["object"]].append(
                    (ws_id, f.get("confidence", 0.0), f.get("source_ref") or ""))
        out = []
        for (subject, relation), objects in index.items():
            if len(objects) < 2:
                continue
            claims = []
            for obj, refs in objects.items():
                for ws_id, conf, cite in refs:
                    claims.append({"object": obj, "workspace": ws_id,
                                   "confidence": round(float(conf), 3),
                                   "citation": f"{ws_id}:{cite}"})
            claims.sort(key=lambda c: -c["confidence"])
            out.append({"subject": subject, "relation": relation, "claims": claims})
        out.sort(key=lambda c: c["subject"])
        return out


class PrismModule(NexusModule):
    name = "prism"
    description = (
        "Cross-domain synthesis -- reads across Engram partitions (Aegis-gated, "
        "always prompted) to surface recurring entities, contradictions, and "
        "patterns the per-workspace view can't see, with source citations"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "prism", "name": "prism",
            "tagline": "Cross-domain synthesis: recurring entities, contradictions, patterns.",
            "version": cls.version, "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reasoning", "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:prism", "gradient": ["#d8b4ff", "#5a2a9c"]}},
            "intents": [{
                "name": "CROSS_DOMAIN_SYNTHESIS",
                "patterns": [
                    r"\bprism\b", r"\bcross-?domain\b", r"\bcross-?workspace\b",
                    r"\bsynthesi[sz]e?\b", r"\bconnections?\s+across\b",
                    r"\brecurring\s+entit\w+\b", r"\bcontradictions?\s+across\b",
                ],
                "semantic_signals": [
                    "prism", "cross-domain synthesis", "across workspaces",
                    "recurring entities", "contradictions between workspaces",
                    "connections across", "synthesize across", "patterns across",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": ["engram.read.global"], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self):
        self._synth = CrossDomainSynthesizer()

    def _load_partitions(self, mgr):
        from nexus.kernel.engram import Engram
        partitions = []
        for ws in mgr.list():
            db = mgr.workspace_dir(ws.workspace_id) / "engram" / "episodic.sqlite"
            if not db.exists():
                continue
            eng = Engram(db)
            conn = eng.atlas._conn()
            try:
                rows = conn.execute(
                    "SELECT id, subject, relation, object, confidence, source_ref "
                    "FROM atlas_facts").fetchall()
            except Exception:
                rows = []
            finally:
                conn.close()
            partitions.append((ws.workspace_id, [
                {"id": r["id"], "subject": r["subject"], "relation": r["relation"],
                 "object": r["object"], "confidence": float(r["confidence"]),
                 "source_ref": r["source_ref"]} for r in rows]))
        return partitions

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        chronicle = context.get("chronicle")
        mgr = context.get("workspace_manager")
        if mgr is None:
            return "[Prism] Workspace manager unavailable."
        granted = True
        if aegis is not None:
            decision = aegis.check_capability("prism", "engram.read.global")
            granted = decision.verdict.value == "ALLOW"
        if not granted:
            return ("[Prism] Cross-workspace synthesis needs approval — "
                    "`engram.read.global` is a Sensitive capability and is always "
                    "prompted. Grant it (Settings -> Security) to let Prism read "
                    "across partitions. No partitions were read.")
        partitions = self._load_partitions(mgr)
        want_contradictions = "contradiction" in message.lower()
        findings = (self._synth.contradictions(partitions) if want_contradictions
                    else self._synth.recurring_entities(partitions))
        mode = "contradictions" if want_contradictions else "recurring_entities"
        if chronicle is not None:
            chronicle.log("prism", "synthesis",
                          {"mode": mode, "partitions": [w for w, _ in partitions],
                           "findings": len(findings)})
        if not findings:
            return f"[Prism] No cross-workspace {mode.replace('_', ' ')} found."
        lines = [f"[Prism] Cross-workspace {mode.replace('_', ' ')} "
                 f"(read {len(partitions)} partitions):"]
        if mode == "recurring_entities":
            for e in findings[:10]:
                lines.append(f"  - '{e['subject']}' appears in {', '.join(e['workspaces'])} "
                             f"(sources: {', '.join(e['citations'][:4])})")
        else:
            for c in findings[:10]:
                lines.append(f"  - CONTRADICTION on {c['subject']} · {c['relation']}:")
                for claim in c["claims"][:4]:
                    lines.append(f"      {claim['object']} (conf {claim['confidence']:.2f}, "
                                 f"from {claim['workspace']}, cite {claim['citation']})")
        return "\n".join(lines)
```

- [ ] **3.4 Register** Prism in `cortex.py` + `server.py` (after Chronos). Confirm `Cortex._build_context()` provides `workspace_manager`; if not, the API route (Task 7) passes it and CLI synthesis stays single-partition by design.
- [ ] **3.5 Run to pass:** `.venv/bin/python -m pytest tests/modules/test_prism_manifest.py tests/modules/test_prism.py tests/kernel/test_cortex_manifest_loading.py tests/release -q` → all pass.
- [ ] **3.6 Commit:** `git add -A && git commit -m "feat(prism): cross-domain synthesis module with Aegis-gated cross-partition reads"`

## Task 4 — Dreamweaver overnight distillation + kill switch

**Files:** Create `nexus/synthesis/dreamweaver.py`. Create `tests/synthesis/test_dreamweaver.py`.

- [ ] **4.1 Failing test.** Kill switch: env `NEXUS_DREAMWEAVER=0` ⇒ `dreamweaver_enabled` False; `<data_dir>/dreamweaver.kill` ⇒ False; default True. `run_once` distills recurring topics (store several episodic rows mentioning "acme") into Atlas (`engram.atlas.beliefs("day")` contains an acme topic) and writes a `dreamweaver`/`morning_brief` Chronicle record with a `headline`; killed ⇒ `brief["skipped"] == "kill_switch"` and no brief in Chronicle. Use `NexusConfig(data_dir=tmp_path)` + `Engram`/`Chronicle` as N1 tests do. (Confirm `engram.episodic.store(...)`/`recall_recent(...)` and `engram.semantic.store(...)` signatures against the real Engram; adapt method names if they differ.)
- [ ] **4.2 Run, expect failure:** `ImportError: cannot import name 'Dreamweaver'`.
- [ ] **4.3 Implement.** Create `nexus/synthesis/dreamweaver.py`:

```python
# nexus/synthesis/dreamweaver.py
"""Dreamweaver -- overnight synthesis (N2.2). Deterministic, kill-switched."""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.config import NexusConfig
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram

_STOPWORDS = {"user", "nexus", "the", "a", "an", "for", "and", "or", "to", "of",
              "in", "on", "is", "it", "that", "this", "with", "review", "about",
              "what", "how"}
_TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{2,}")
_MIN_FREQ = 3


def dreamweaver_enabled(config: NexusConfig) -> bool:
    if os.environ.get("NEXUS_DREAMWEAVER", "1").lower() in ("0", "false", "no"):
        return False
    return not (Path(config.data_dir) / "dreamweaver.kill").exists()


class Dreamweaver:
    def __init__(self, config: NexusConfig, engram: Engram, chronicle: Chronicle) -> None:
        self._config = config
        self._engram = engram
        self._chronicle = chronicle

    def _recurring_topics(self, limit: int = 500):
        rows = self._engram.episodic.recall_recent(limit=limit)
        counts: Counter[str] = Counter()
        for r in rows:
            for tok in _TOKEN_RE.findall(r["content"].lower()):
                if tok in _STOPWORDS:
                    continue
                counts[tok] += 1
        return [(tok, n) for tok, n in counts.most_common(20) if n >= _MIN_FREQ]

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        if not dreamweaver_enabled(self._config):
            self._chronicle.log("dreamweaver", "skipped", {"reason": "kill_switch"})
            return {"skipped": "kill_switch", "distilled_facts": 0}
        moment = now or datetime.now(timezone.utc)
        topics = self._recurring_topics()
        source_ref = f"dreamweaver:{moment.date().isoformat()}"
        distilled = 0
        for tok, freq in topics:
            self._engram.atlas.observe("day", "observed", tok,
                                       confidence=min(0.6 + 0.05 * freq, 0.95),
                                       fact_class="volatile", source_ref=source_ref, now=moment)
            distilled += 1
        if topics:
            summary = "Recurring today: " + ", ".join(f"{t} (x{n})" for t, n in topics[:8])
            self._engram.semantic.store(summary, category="dreamweaver_brief")
        headline = (f"{distilled} recurring topic(s) distilled" if distilled
                    else "Quiet day - nothing recurred above threshold")
        brief = {"headline": headline, "date": moment.date().isoformat(),
                 "topics": [{"topic": t, "count": n} for t, n in topics],
                 "distilled_facts": distilled, "generated_at": moment.isoformat(),
                 "skipped": None}
        self._chronicle.log("dreamweaver", "morning_brief", brief)
        return brief

    def latest_brief(self) -> dict[str, Any] | None:
        rows = self._chronicle.query(source="dreamweaver", action="morning_brief", limit=1)
        return rows[0]["payload"] if rows else None
```

- [ ] **4.4 Run to pass:** `.venv/bin/python -m pytest tests/synthesis/test_dreamweaver.py -q` → all pass.
- [ ] **4.5 Commit:** `git add -A && git commit -m "feat(dreamweaver): deterministic overnight distillation with kill switch and morning brief"`

## Task 5 — Wire Dreamweaver scheduler into the server lifespan

**Files:** Modify `nexus/api/server.py` (lifespan, near the existing `_catalog_refresher` task). Create `tests/aurora/test_dreamweaver_routes.py` (route impl in Task 8; scheduler here).

- [ ] **5.1 Failing test.** `tests/aurora/test_dreamweaver_routes.py`: `POST /api/dreamweaver/run` → 200 with `headline`, and a `dreamweaver`/`morning_brief` Chronicle row; `GET /api/dreamweaver/brief` reflects it; with `NEXUS_DREAMWEAVER=0`, `POST /run` returns `skipped == "kill_switch"`.
- [ ] **5.2 Run, expect failure:** 404 (route not mounted yet).
- [ ] **5.3 Implement scheduler.** In the lifespan, after the catalog-refresher task is created, build a `Dreamweaver`, store it on `app.state.dreamweaver`, and start an `asyncio` interval loop (`NEXUS_DREAMWEAVER_INTERVAL_S` default 86400) that, when `dreamweaver_enabled`, runs `run_once` via `asyncio.to_thread` and publishes a `dreamweaver.brief` Pulse message. Cancel the task in shutdown. Ensure `import os` and `from nexus.kernel.pulse import Message` are in scope. Match how N1 wired its lifespan additions.
- [ ] **5.4 Run to pass (partial — routes land in Task 8):** `.venv/bin/python -m pytest tests/api tests/release -q` → server still boots, no regressions. (`tests/aurora/test_dreamweaver_routes.py` stays red until Task 8; implement Task 8 before committing if you prefer green-per-commit.)
- [ ] **5.5 Commit:** `git add -A && git commit -m "feat(server): wire Dreamweaver overnight scheduler into lifespan with kill switch"`

## Task 6 — `/api/chronos` timeline + counterfactual routes

**Files:** Create `nexus/api/routes/chronos.py`. Modify `server.py` (import + mount near `sigil_router`). Create `tests/aurora/test_chronos_routes.py`.

- [ ] **6.1 Failing test.** Seed Chronicle (grant + route + response for wraith); `GET /api/chronos/timeline` → `count >= 3` with at least one `branch_point`; `POST /api/chronos/counterfactual {module:"wraith", action:"permission_granted"}` → `flipped.module == "wraith"` and pruned modules `{"wraith"}`; unknown `event_id` → `flipped is None`.
- [ ] **6.2 Run, expect failure:** 404.
- [ ] **6.3 Implement.** Create `nexus/api/routes/chronos.py` (APIRouter prefix `/api/chronos`; `GET /timeline` → `Chronos(kernel.chronicle).timeline(limit)`; `POST /counterfactual` with a `CounterfactualBody(event_id?, module?, action?)` dispatching to `counterfactual`/`counterfactual_by`). Mount in `server.py` after `sigil_router`.
- [ ] **6.4 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_chronos_routes.py -q` → all pass.
- [ ] **6.5 Commit:** `git add -A && git commit -m "feat(api): /api/chronos timeline and counterfactual routes"`

## Task 7 — `/api/prism/synthesis` (gated) + `/api/atlas/graph` routes

**Files:** Create `nexus/api/routes/prism.py`, `nexus/api/routes/atlas.py`. Modify `server.py`. Create `tests/aurora/test_prism_routes.py`, `tests/aurora/test_atlas_graph_route.py`.

- [ ] **7.1 Failing tests.** Prism: `GET /api/prism/synthesis` without a grant → 200 `{gated: True, findings: []}`; after `kernel.aegis.grant("prism", "engram.read.global", workspace_id=None)` → `gated: False`. Atlas: seed two linked facts via `kernel.engram.atlas.observe(...)` + `.link(...)`; `GET /api/atlas/graph` → nodes include both ids, every node has `confidence`, edges include the link.
- [ ] **7.2 Run, expect failure:** 404.
- [ ] **7.3 Implement.** `nexus/api/routes/prism.py` (gate on `kernel.aegis.check_capability("prism","engram.read.global")`; if not ALLOW return `{gated:True,...}`; else enumerate workspaces via a `WorkspaceManager` resolved from `app.state` or `<data_dir>/workspaces`, read each partition's `atlas_facts`, run `CrossDomainSynthesizer`, chronicle, return `{gated:False, findings, partitions}`). `nexus/api/routes/atlas.py` (`GET /graph` reads `kernel.engram.atlas` tables, computes `effective_confidence` per fact for the opacity/`decayed` flag, returns `{nodes, edges}`). Mount both after `chronos_router`.
- [ ] **7.4 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_prism_routes.py tests/aurora/test_atlas_graph_route.py -q` → all pass.
- [ ] **7.5 Commit:** `git add -A && git commit -m "feat(api): /api/prism/synthesis (gated) and /api/atlas/graph routes"`

## Task 8 — `/api/dreamweaver` brief + run routes

**Files:** Create `nexus/api/routes/dreamweaver.py`. Modify `server.py` (import + mount). (Tests from Task 5.1.)

- [ ] **8.1 Confirm red:** `tests/aurora/test_dreamweaver_routes.py` → 404.
- [ ] **8.2 Implement.** `nexus/api/routes/dreamweaver.py` (`_dreamweaver(request)` resolves/creates `app.state.dreamweaver`; `GET /brief` → `latest_brief()` or an empty-brief default; `POST /run` → `await asyncio.to_thread(dw.run_once)` and, unless skipped, publish a `dreamweaver.brief` Pulse message). Mount after `atlas_router`.
- [ ] **8.3 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_dreamweaver_routes.py tests/api tests/release -q` → all pass.
- [ ] **8.4 Commit:** `git add -A && git commit -m "feat(api): /api/dreamweaver brief and run routes with Pulse broadcast"`

## Task 9 — Aurora identity glyphs: Prism + Chronos

**Files:** Modify `nexus/aurora/icons.js` (`GLYPHS`, `GRADIENTS`, `BUILTIN_CAPABILITIES`), `nexus/aurora/app.js` (BUILTINS roster). Create `tests/aurora/test_n2_surfaces.py` (glyph tests).

- [ ] **9.1 Failing test.** `tests/aurora/test_n2_surfaces.py`: icons.js contains `prism:` + `"#d8b4ff"`, `chronos:` + `"#b8c4ff"`, the capability sheet has "Cross-domain synthesis" and "Counterfactual"/"counterfactual", and no emoji (regex `[\U0001F300-\U0001FAFF\U00002600-\U000027BF]`).
- [ ] **9.2 Run, expect failure:** `assert "prism:" in r.text` fails.
- [ ] **9.3 Implement.** In `icons.js`, add `GLYPHS.prism` (refracting triangular prism — line-stroke SVG) and `GLYPHS.chronos` (clock face with a forking branch), the two `GRADIENTS` entries (`prism: ["#d8b4ff","#5a2a9c"]`, `chronos: ["#b8c4ff","#3a4a9c"]`), and `BUILTIN_CAPABILITIES` entries for both (Prism: tagline "Cross-domain synthesis — connections the per-workspace view can't see", tools `engram.read.workspace` Routine + `engram.read.global` Sensitive; Chronos: tagline "Counterfactual reasoning — replay the decision DAG with one node flipped", tool `chronicle.read.workspace` Routine). Add `"prism"` and `"chronos"` to the `BUILTINS` roster array in `app.js`. No emoji; follow the N1 Sigil/Atlas glyph format exactly.
- [ ] **9.4 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_n2_surfaces.py tests/aurora/test_accessibility.py -q` → all pass.
- [ ] **9.5 Commit:** `git add -A && git commit -m "feat(aurora): prism and chronos identity glyphs + capability sheets"`

## Task 10 — Aurora morning-brief card + Atlas graph view + Chronos timeline view

**Files:** Modify `nexus/aurora/index.html` (brief card mount after the N1 KERNEL·LIVE section), `nexus/aurora/app.js` (state.n2 + renderers + hash routes + WS handling), `nexus/aurora/app.css` (append), `nexus/aurora/tokens.css` (`--nx-chronos-branch` token). Extend `tests/aurora/test_n2_surfaces.py`.

- [ ] **10.1 Failing tests.** index has `id="nx-morning-brief"` + "MORNING BRIEF"/"BRIEF"; app.js references `/api/dreamweaver/brief`, `/api/atlas/graph`, `renderAtlasGraph`, `renderMorningBrief`, `/api/chronos/timeline`, `/api/chronos/counterfactual`, `renderChronosTimeline`, `#/chronos`, `#/atlas`, `dreamweaver.brief`, `/api/events/ws`; app.css has `.nx-atlas-node`, `.nx-atlas-edge`, `.nx-atlas-node.decayed`, `.nx-chronos-branch`, and a `prefers-reduced-motion` block referencing the atlas/chronos classes; no emoji in `/aurora`, app.js, app.css.
- [ ] **10.2 Run, expect failure:** `assert 'id="nx-morning-brief"' in r.text` fails.
- [ ] **10.3 Implement index.html.** After the N1 `#nx-kernel-viz` cockpit section, add a `MORNING BRIEF` `nx-cp-section` mounting `#nx-morning-brief`.
- [ ] **10.4 Implement app.js.** Add `state.n2 = {brief, atlasGraph, chronos}`; `loadMorningBrief()`/`renderMorningBrief()` (fetch `/api/dreamweaver/brief`, render headline + topic chips); `renderAtlasGraph()` (fetch `/api/atlas/graph`, deterministic radial layout where low confidence drifts outward, node opacity = confidence, `.decayed` class for faded facts, edges as lines); `renderChronosTimeline()` + `runCounterfactual(module, action, eventId)` (fetch timeline, render rows with branch-point buttons that POST to `/api/chronos/counterfactual` and render the pruned "would NOT have happened" list); hash routes `#/atlas` and `#/chronos` in the router; a `dreamweaver.brief` branch in `handleKernelEvent` that refreshes the brief; call `loadMorningBrief()` once in `renderCockpitRail()`. Use `escapeHtml` for all interpolated text. Full renderer code is in the spec reference — keep it vanilla, no animation loop (the layout is static/deterministic).
- [ ] **10.5 Implement app.css + tokens.css.** Append atlas-graph styles (node fill `--nx-routine`, `.decayed` → `--nx-sensitive` + italic, edges `--nx-hairline`), chronos timeline + `.nx-chronos-branch` (left-border `--nx-chronos-branch`, hover), morning-brief card + chips, and a `@media (prefers-reduced-motion: reduce)` block touching the atlas/chronos classes. Add `--nx-chronos-branch: #b8c4ff;` to tokens.css near the N1 `--nx-trust-collapse` token; reuse existing `--nx-routine`/`--nx-sensitive` from N1.
- [ ] **10.6 Run to pass:** `.venv/bin/python -m pytest tests/aurora -q` → all pass (including N1 `test_kernel_viz.py`, `test_accessibility.py`).
- [ ] **10.7 Commit:** `git add -A && git commit -m "feat(aurora): morning-brief card, Atlas graph view, Chronos counterfactual timeline"`

## Task 11 — Invariants sweep + full suite

**Files:** none new (verification; fix anything that surfaces).

- [ ] **11.1** Static network invariant: `.venv/bin/python -m pytest tests/release/test_v1_acceptance.py -q` → passes (no new kernel file imports the network stack; `prism.py`/`chronos.py` under `nexus/modules/`, `synthesis/*` import only stdlib + kernel; routes use FastAPI only). If acceptance asserts an exact built-in count, bump it from the N1 count to include `prism` + `chronos`.
- [ ] **11.2** Gating invariants spot-check: Prism Sensitive prompt gate, Chronos Routine read gate, Dreamweaver kill switch — run the three named tests.
- [ ] **11.3** Full suite: `.venv/bin/python -m pytest -q` → green (≥ 1159 + new). Prefer fixing registration over weakening membership-style assertions.
- [ ] **11.4** Commit any stragglers: `git add -A && git commit -m "test: N2 invariants sweep green"`

---

## Self-Review — spec requirement → task mapping

| N2 requirement | Where |
|---|---|
| N2.1 Prism manifest v1, in_process, base trust 0.30 | Task 3 |
| N2.1 reads across Engram partitions | Task 3 `_load_partitions`; Task 7 route |
| N2.1 cross-workspace read = Sensitive, always prompted | Task 3 (`engram.read.global` Sensitive → Aegis PROMPT; deviation 1); Task 7 enforces |
| N2.1 recurring entities / contradictions / patterns | Task 3 `CrossDomainSynthesizer` |
| N2.1 outputs cite Engram/Atlas sources | Task 3 / Task 7 (citations = `ws_id:source_ref`) |
| N2.1 reuse N1 Atlas store | Tasks 3/7 read each partition's `atlas_facts` |
| N2.2 Dreamweaver scheduled batch + kill switch | Tasks 4–5 (deviation 4) |
| N2.2 distill episodic → semantic/Atlas facts | Task 4 (deviation 5) |
| N2.2 morning brief in Aurora | Task 4 (Chronicle record), Task 8 routes, Task 10 card + `dreamweaver.brief` |
| N2.2 Chronos counterfactual over decision history | Tasks 1–2, 6 (deviations 2–3) |
| N2.2 replay DAG with one node flipped; report dependents | Task 1 (`downstream` + `counterfactual`) |
| N2.2 deterministic first, optional LLM narration | Task 1 (`narrator` hook, off by default) |
| N2.3 Atlas graph view (force layout, confidence opacity, decay fade) | Task 7 + Task 10 |
| N2.3 Chronos timeline with branch points | Task 6 + Task 10 |
| N2.3 morning-brief card | Task 10 |
| N2.3 Prism + Chronos glyphs (line-stroke, no emoji) | Task 9 |
| N2.3 existing SSE/WS, no polling | Tasks 6–8 push `dreamweaver.brief`; Task 10 subscribes `/api/events/ws`, fetch-on-navigate |
| Invariant: manifest-v1 at ADVISOR trust | Tasks 2–3 |
| Invariant: every tool call passes `aegis.check_capability()` | Tasks 2/3/7 |
| Invariant: every action lands in Chronicle | Tasks 2/3/4 |
| Invariant: only Aegis touches the network | Task 11.1 |
| Invariant: new automated behavior kill-switched + observable | Tasks 4/5 |
| Invariant: zero emoji | Tasks 9–10 |
| Invariant: kernel contracts unchanged | All additive; deviation 1 avoids any Aegis change |

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

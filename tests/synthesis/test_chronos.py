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

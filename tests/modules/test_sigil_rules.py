"""N1.1 — table-driven Sigil detection rules (pure, deterministic)."""
from __future__ import annotations

from nexus.modules.sigil import DETECTION_RULES, SigilRuleEngine


def test_rule_table_covers_spec_rules():
    # The five security detections, plus the informational swarm_burst radar ping.
    assert {
        "trust_collapse", "denied_burst", "runaway_loop",
        "egress_anomaly", "permission_escalation",
    } <= set(DETECTION_RULES)
    # swarm_burst is informational — never high-stakes, so it never trips the veil.
    assert DETECTION_RULES["swarm_burst"].high_stakes is False


def test_swarm_burst_fires_on_route_fanout():
    eng = SigilRuleEngine()
    dets = []
    for i in range(4):
        dets += eng.observe({"kind": "route", "module": f"agent{i}",
                             "preview": f"task {i}", "ts": 1000.0 + i})
    assert any(d.rule == "swarm_burst" for d in dets)
    burst = next(d for d in dets if d.rule == "swarm_burst")
    assert burst.high_stakes is False


def test_trust_collapse_fires_on_full_tier_drop():
    eng = SigilRuleEngine()
    dets = eng.observe({"kind": "trust_change", "module": "echo",
                        "old_score": 0.30, "new_score": 0.08, "ts": 1000.0})
    assert len(dets) == 1
    assert dets[0].rule == "trust_collapse"
    assert dets[0].severity == "critical"
    assert dets[0].high_stakes is True
    assert dets[0].module == "echo"


def test_trust_collapse_does_not_fire_within_a_tier():
    eng = SigilRuleEngine()
    assert eng.observe({"kind": "trust_change", "module": "echo",
                        "old_score": 0.30, "new_score": 0.27, "ts": 1000.0}) == []


def test_trust_collapse_dedupes_identical_drop():
    eng = SigilRuleEngine()
    ev = {"kind": "trust_change", "module": "echo",
          "old_score": 0.30, "new_score": 0.08, "ts": 1000.0}
    assert len(eng.observe(ev)) == 1
    assert eng.observe(dict(ev, ts=1010.0)) == []


def test_denied_burst_fires_at_threshold_within_window():
    eng = SigilRuleEngine()
    out = []
    for i in range(5):
        out = eng.observe({"kind": "gate", "module": "wraith",
                           "capability": "fs.write.workspace", "verdict": "DENY",
                           "permission_class": "Sensitive", "ts": 1000.0 + i * 10})
    assert len(out) == 1 and out[0].rule == "denied_burst"


def test_denied_burst_respects_window():
    eng = SigilRuleEngine()
    out = []
    for i in range(5):
        out = eng.observe({"kind": "gate", "module": "wraith",
                           "capability": "fs.write.workspace", "verdict": "DENY",
                           "permission_class": "Sensitive", "ts": 1000.0 + i * 400})
    assert out == []


def test_runaway_loop_fires_on_identical_route_cadence():
    eng = SigilRuleEngine()
    out = []
    for i in range(8):
        out = eng.observe({"kind": "route", "module": "oracle",
                           "preview": "scan for patterns", "ts": 1000.0 + i * 5})
    assert len(out) == 1 and out[0].rule == "runaway_loop"
    assert out[0].high_stakes is True


def test_permission_escalation_on_repeated_privileged_asks():
    eng = SigilRuleEngine()
    out = []
    for i in range(3):
        out = eng.observe({"kind": "gate", "module": "wraith",
                           "capability": "chronicle.redact", "verdict": "PROMPT",
                           "permission_class": "Privileged", "ts": 1000.0 + i * 60})
    assert len(out) == 1 and out[0].rule == "permission_escalation"
    assert out[0].severity == "critical"


def test_egress_anomaly_vs_baseline():
    eng = SigilRuleEngine()
    now = 100000.0
    baseline = [now - 3600 + i * 60 for i in range(59)]       # ~1/min for an hour
    spike = [now - j for j in range(12)]                       # 12 in last minute
    dets = eng.check_egress(baseline + spike, now=now)
    assert len(dets) == 1 and dets[0].rule == "egress_anomaly"


def test_egress_quiet_traffic_is_clean():
    eng = SigilRuleEngine()
    now = 100000.0
    assert eng.check_egress([now - j * 30 for j in range(6)], now=now) == []

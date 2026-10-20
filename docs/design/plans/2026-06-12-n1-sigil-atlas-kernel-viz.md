# N1 — Sigil threat radar · Atlas temporal knowledge graph · Aurora live kernel visualization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Layer N1 of the missing-minds spec — a deterministic Sigil threat radar with emergency Pulse broadcasts and a Cortex routing bypass, an Atlas temporal knowledge graph in Engram's semantic tier with read-time confidence decay, and a live Aurora kernel-visualization panel fed by new `kernel.route` / `kernel.gate` / `sigil.detection` event topics over the existing WebSocket relay.

**Architecture:** Sigil and Atlas are manifest-v1 `NexusModule`s (in_process, base trust 0.30) that land on the existing Cortex/Aegis/Chronicle/Pulse contracts without modifying them; the only kernel changes are additive event emission (Cortex publishes `kernel.route`, Aegis gains an optional Pulse emitter for `kernel.gate` + `aegis.trust_change`) and a small contained emergency-bypass subscription in Cortex. Atlas storage extends `nexus/kernel/engram.py` with `atlas_facts`/`atlas_edges` tables in the same SQLite file (no new dependencies). Aurora consumes the new topics through the existing `/api/events/ws` relay (which already forwards every Pulse topic) — no polling.

**Tech Stack:** Python 3.14 / FastAPI / SQLite / Pulse async pub-sub (existing kernel), pytest + pytest-asyncio (`asyncio_mode = "auto"`), vanilla ES-module JS + hand-drawn SVG (Aurora, no build step). Tests run with `.venv/bin/python -m pytest` from the worktree root.

## Spec deviations (approved adaptations)

1. **"Runaway loops — Sentry already detects":** Sentry (`nexus/modules/sentry.py`) emits no discrete loop events — it maintains a cognitive-state vector. Sigil therefore detects runaway loops deterministically from `kernel.route` traffic (same module + identical message preview at loop cadence) and *attaches* Sentry's state snapshot to detection payloads as the correlating signal, via a new public `Cortex.get_module()` accessor.
2. **"Routing bypass in cortex.py routing preamble":** `Cortex.process()` takes user strings, not Pulse messages. The bypass is implemented as a Cortex Pulse subscription (`attach_emergency_bypass()`) that short-circuits intent classification and the trust floor entirely for EMERGENCY-priority messages, dispatching Specter directly and logging `emergency_bypass` to Chronicle. Pulse's priority queue already dequeues EMERGENCY first.
3. **`kernel.gate` from synchronous Aegis:** Aegis methods are sync; live events are emitted via `loop.create_task` only when an event loop is running (API path), and silently skipped in sync CLI/test contexts. Chronicle remains the durable record in all contexts.
4. **"Only Sigil and Aegis can set the emergency flag" (docs/specs/design.md):** Not enforced inside Pulse (kernel contracts unchanged per spec invariants). Sigil declares `pulse.broadcast.emergency` as Routine in its manifest, and every emergency that reaches the Cortex bypass is Chronicle-logged for audit.
5. **"Trust collapse (full tier drop within a session)":** Detected per `aegis.trust_change` event whose old→new score crosses ≥ 1 full tier (the −0.22 penalty always crosses a tier at ADVISOR), deduplicated by the engine's in-memory session state. Cumulative multi-event drift detection is deferred to N2.
6. **`create_app()` never registered built-in manifests** (only the CLI did), so `check_capability()` for built-ins returned DENY in the API path. Task 5 adds the idempotent `cortex.register_builtin_manifests()` call to `_init_kernel` — required for the Sigil/Atlas gating invariant.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `nexus/kernel/aegis.py` | Modify | `set_pulse()` + `_emit_pulse()`; emit `kernel.gate` from `check_capability()`, `aegis.trust_change` from trust mutations |
| `nexus/kernel/cortex.py` | Modify | publish `kernel.route` in `process()`; `attach_emergency_bypass()` / `_on_emergency_message()`; `get_module()`; kill-switch helper; register Sigil+Atlas in `default_builtin_registry()` |
| `nexus/kernel/engram.py` | Modify | new `AtlasFacts` class (`atlas_facts`/`atlas_edges`, read-time decay, re-confirmation, contradictions, edges); wired as `Engram.atlas` |
| `nexus/modules/sigil.py` | Create | `DETECTION_RULES` table, `SigilRuleEngine`, `SigilModule` (manifest v1, Pulse wiring, emergency broadcast with provenance hash) |
| `nexus/modules/atlas.py` | Create | `AtlasModule` (manifest v1, observe/query grammar, citations) |
| `nexus/api/routes/sigil.py` | Create | `GET /api/sigil/detections` (Chronicle-backed) |
| `nexus/api/server.py` | Modify | register Sigil + Atlas modules, `aegis.set_pulse()`, `cortex.attach_emergency_bypass()`, `register_builtin_manifests()`, mount sigil router |
| `nexus/aurora/icons.js` | Modify | `GLYPHS.sigil` (concentric radar arcs), `GLYPHS.atlas`, `GRADIENTS`, `BUILTIN_CAPABILITIES` entries |
| `nexus/aurora/index.html` | Modify | `KERNEL · LIVE` cockpit-rail section (`#nx-kernel-viz`) |
| `nexus/aurora/app.js` | Modify | `state.kernelViz`, events-WS subscription, `handleKernelEvent`, `kernelVizHTML`/`renderKernelViz`, `moduleSparkSVG`, `emergencyVeil`, ⌘0 panel |
| `nexus/aurora/app.css` | Modify | kernel-viz styles, radar ping animation + reduced-motion guard, emergency veil (alert palette) |
| `tests/kernel/test_aegis_pulse_events.py` | Create | gate/trust live-event contract |
| `tests/kernel/test_cortex_route_events.py` | Create | `kernel.route` contract |
| `tests/kernel/test_cortex_emergency_bypass.py` | Create | bypass, Specter auto-activation, kill switches |
| `tests/kernel/test_engram_atlas.py` | Create | decay/confirmation/contradiction/edges golden tests |
| `tests/modules/test_sigil_rules.py` | Create | table-driven detection rules |
| `tests/modules/test_sigil_manifest.py` / `test_sigil.py` | Create | manifest + behavior pair |
| `tests/modules/test_atlas_manifest.py` / `test_atlas.py` | Create | manifest + behavior pair |
| `tests/aurora/test_sigil_routes.py` | Create | `/api/sigil/detections` route tests |
| `tests/aurora/test_kernel_viz.py` | Create | asset contracts: topics wired, glyphs, no-emoji, reduced motion |

---

## Task 1 — Aegis live gate events (`kernel.gate` + `aegis.trust_change` on Pulse)

**Files:** Modify `nexus/kernel/aegis.py` (imports at lines 1–18; rename body of `check_capability` at lines 536–598; emission hooks in `record_outcome` ~line 337, `revoke` ~line 371, `set_trust` ~line 512). Create `tests/kernel/test_aegis_pulse_events.py`.

- [ ] **1.1 Failing test.** Create `tests/kernel/test_aegis_pulse_events.py`:

```python
"""N1 — Aegis emits live kernel.gate / aegis.trust_change events on Pulse."""
from __future__ import annotations

import asyncio

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.modules.oracle import OracleModule


@pytest.fixture
def aegis(tmp_path):
    chronicle = Chronicle(str(tmp_path / "db.sqlite"))
    chronicle.init_db()
    a = Aegis(str(tmp_path / "db.sqlite"), chronicle=chronicle)
    a.init_db()
    return a


async def test_check_capability_emits_kernel_gate(aegis):
    pulse = Pulse()
    aegis.set_pulse(pulse)
    aegis.register_manifest(OracleModule.manifest())
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.gate", capture)
    decision = aegis.check_capability("oracle", "engram.read.workspace")
    assert decision.verdict.value == "ALLOW"
    await asyncio.sleep(0.1)
    assert len(received) == 1
    p = received[0].payload
    assert p["agent"] == "oracle"
    assert p["capability"] == "engram.read.workspace"
    assert p["verdict"] == "ALLOW"
    assert p["permission_class"] == "Routine"


async def test_deny_verdict_is_emitted_too(aegis):
    pulse = Pulse()
    aegis.set_pulse(pulse)
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.gate", capture)
    decision = aegis.check_capability("ghost", "anything.at.all")
    assert decision.verdict.value == "DENY"
    await asyncio.sleep(0.1)
    assert received[0].payload["verdict"] == "DENY"


async def test_record_outcome_emits_trust_change(aegis):
    pulse = Pulse()
    aegis.set_pulse(pulse)
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("aegis.trust_change", capture)
    aegis.record_outcome("echo", False)
    await asyncio.sleep(0.1)
    assert len(received) == 1
    p = received[0].payload
    assert p["module"] == "echo"
    assert p["new_score"] < p["old_score"]
    assert "tier" in p


def test_no_pulse_attached_is_silent(aegis):
    # Sync context, no Pulse: decisions still work, nothing crashes.
    decision = aegis.check_capability("ghost", "anything.at.all")
    assert decision.verdict.value == "DENY"
    assert aegis.record_outcome("echo", True) > 0.0
```

- [ ] **1.2 Run, expect failure:** `.venv/bin/python -m pytest tests/kernel/test_aegis_pulse_events.py -q` → `AttributeError: 'Aegis' object has no attribute 'set_pulse'`.
- [ ] **1.3 Implement.** In `nexus/kernel/aegis.py`: add `import asyncio` to the imports block (after `import sqlite3`). Add to the `Aegis` class, right after `_log_chronicle` (~line 203):

```python
    # -- live event emission (N1) --------------------------------------------

    def set_pulse(self, pulse: Any) -> None:
        """Attach the kernel Pulse bus so gate/trust events stream live.

        Optional: when unset (CLI, unit tests) Aegis behaves exactly as
        before — Chronicle remains the durable record.
        """
        self._pulse = pulse

    def _emit_pulse(self, topic: str, payload: dict[str, Any]) -> None:
        pulse = getattr(self, "_pulse", None)
        if pulse is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # sync context — no live stream, Chronicle still has it
        from nexus.kernel.pulse import Message
        loop.create_task(pulse.publish(Message(topic=topic, source="aegis", payload=payload)))
```

Rename the existing `check_capability` (lines 536–598) to `_decide_capability` (same body, same signature) and add a new wrapper in its place:

```python
    def check_capability(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> CapabilityDecision:
        """Gate a capability and stream the resolution as a kernel.gate event."""
        decision = self._decide_capability(agent_slug, capability, workspace_id)
        self._emit_pulse("kernel.gate", {
            "agent": agent_slug,
            "capability": capability,
            "verdict": decision.verdict.value,
            "permission_class": (
                decision.permission_class.value if decision.permission_class else None
            ),
            "reason": decision.reason,
            "workspace_id": workspace_id,
        })
        return decision
```

In `record_outcome`, `revoke`, and `set_trust`, add `self._emit_pulse("aegis.trust_change", payload)` immediately after each existing `self._log_chronicle("aegis.trust_change", payload)` call (three sites).
- [ ] **1.4 Run to pass:** `.venv/bin/python -m pytest tests/kernel/test_aegis_pulse_events.py tests/kernel/test_aegis.py tests/kernel/test_aegis_capabilities.py -q` → all pass.
- [ ] **1.5 Commit:** `git add -A && git commit -m "feat(aegis): stream kernel.gate and aegis.trust_change events on Pulse"`

## Task 2 — Cortex publishes `kernel.route`

**Files:** Modify `nexus/kernel/cortex.py` (`process()`, after the step-4 Chronicle log at lines 706–715). Create `tests/kernel/test_cortex_route_events.py`.

- [ ] **2.1 Failing test.** Create `tests/kernel/test_cortex_route_events.py`:

```python
"""N1 — Cortex publishes kernel.route for every routing decision."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.modules.council import CouncilModule


@pytest.fixture
def kernel(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_module(CouncilModule())
    aegis.set_policy("council", allowed=True, initial_trust=0.30)

    async def _mock_llm(msg: str) -> str:
        return "mock"

    cortex.set_llm(_mock_llm)
    return cortex, pulse


async def test_process_publishes_kernel_route(kernel):
    cortex, pulse = kernel
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.route", capture)
    await cortex.process("should i decide between two job offers?")
    await asyncio.sleep(0.2)
    assert len(received) == 1
    p = received[0].payload
    assert p["target"] == "council"
    assert p["trust_tier"] == "ADVISOR"
    assert isinstance(p["signals"], list) and p["signals"]
    assert p["message_preview"].startswith("should i decide")
```

- [ ] **2.2 Run, expect failure:** `.venv/bin/python -m pytest tests/kernel/test_cortex_route_events.py -q` → `assert len(received) == 1` fails with `0`.
- [ ] **2.3 Implement.** In `nexus/kernel/cortex.py`, inside `process()`, immediately after the step-4 `self._chronicle.log("cortex", "route", {...})` block (after line 715), insert:

```python
        # 4b. Stream the routing decision live (N1.3 kernel visualization)
        await self._pulse.publish(Message(
            topic="kernel.route",
            source="cortex",
            payload={
                "target": target,
                "trust_tier": self._aegis.get_tier(target),
                "message_preview": message[:100],
                "signals": [
                    {"name": s.name, "module": s.module, "score": s.score,
                     "signals": s.signals}
                    for s in scored_intents[:5]
                ],
            },
        ))
```

- [ ] **2.4 Run to pass:** `.venv/bin/python -m pytest tests/kernel/test_cortex_route_events.py tests/kernel/ -q` → all pass.
- [ ] **2.5 Commit:** `git add -A && git commit -m "feat(cortex): publish kernel.route Pulse event per routing decision"`

## Task 3 — Cortex emergency bypass + Specter auto-activation kill switch

**Files:** Modify `nexus/kernel/cortex.py` (imports at lines 7–19; new methods on `Cortex` after `initialize_modules` ~line 562; module-level helper after `default_builtin_registry`). Create `tests/kernel/test_cortex_emergency_bypass.py`.

- [ ] **3.1 Failing test.** Create `tests/kernel/test_cortex_emergency_bypass.py`:

```python
"""N1 — emergency-priority Pulse messages bypass normal routing in Cortex."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex, specter_autoactivation_enabled
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Message, Priority, Pulse
from nexus.modules.specter import SpecterModule


def _build(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_module(SpecterModule())
    aegis.set_policy("specter", allowed=True, initial_trust=0.30)

    async def _mock_llm(msg: str) -> str:
        return "adversarial read: looks suspicious"

    cortex.set_llm(_mock_llm)
    cortex.attach_emergency_bypass()
    return cortex, pulse, chronicle, config


def _detection(activate=True):
    return Message(
        topic="sigil.detection", source="sigil", priority=Priority.EMERGENCY,
        payload={"rule": "trust_collapse", "module": "echo",
                 "evidence": [{"old_score": 0.30, "new_score": 0.08}],
                 "activate_specter": activate},
    )


async def test_emergency_bypass_logs_and_activates_specter(tmp_path):
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="emergency_bypass")
    activated = chronicle.query(source="cortex", action="specter_auto_activated")
    assert activated and activated[0]["payload"]["rule"] == "trust_collapse"


async def test_normal_priority_messages_do_not_bypass(tmp_path):
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(Message(topic="sigil.detection", source="sigil",
                                payload={"activate_specter": True}))
    await asyncio.sleep(0.2)
    assert chronicle.query(source="cortex", action="emergency_bypass") == []


async def test_env_kill_switch_blocks_autoactivation(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_SIGIL_SPECTER_AUTOACTIVATE", "0")
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="emergency_bypass")
    assert chronicle.query(source="cortex", action="specter_auto_activated") == []
    skipped = chronicle.query(source="cortex", action="specter_autoactivation_skipped")
    assert skipped and skipped[0]["payload"]["reason"] == "kill_switch"


async def test_file_kill_switch_blocks_autoactivation(tmp_path):
    cortex, pulse, chronicle, config = _build(tmp_path)
    (config.data_dir / "sigil-specter.kill").write_text("disabled by operator\n")
    assert specter_autoactivation_enabled(config) is False
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="specter_auto_activated") == []
```

- [ ] **3.2 Run, expect failure:** `.venv/bin/python -m pytest tests/kernel/test_cortex_emergency_bypass.py -q` → `ImportError: cannot import name 'specter_autoactivation_enabled'`.
- [ ] **3.3 Implement.** In `nexus/kernel/cortex.py`: add `import os` and `from pathlib import Path` to the imports (after `import re`). Add module-level helper directly above `class Cortex`:

```python
def specter_autoactivation_enabled(config: NexusConfig) -> bool:
    """Kill switch for Sigil → Specter auto-activation (spec invariant).

    Disabled by env NEXUS_SIGIL_SPECTER_AUTOACTIVATE=0/false/no, or by the
    presence of <data_dir>/sigil-specter.kill (ecosystem kill-switch file).
    """
    if os.environ.get("NEXUS_SIGIL_SPECTER_AUTOACTIVATE", "1").lower() in ("0", "false", "no"):
        return False
    return not (Path(config.data_dir) / "sigil-specter.kill").exists()
```

Add to `Cortex` after `list_modules()` (~line 555):

```python
    def get_module(self, name: str) -> NexusModule | None:
        """Public module lookup (used by Sigil to read Sentry state)."""
        return self._modules.get(name)
```

Add to `Cortex` after `initialize_modules()` (~line 562):

```python
    # -- emergency routing bypass (N1.1) -------------------------------------

    def attach_emergency_bypass(self) -> None:
        """Give EMERGENCY-priority Pulse messages a routing bypass.

        Emergency broadcasts (Sigil detections) skip intent classification
        and the trust floor entirely: they are logged to Chronicle and, when
        the payload requests it and the kill switch allows, dispatched
        straight to Specter for an adversarial read. Idempotent.
        """
        if getattr(self, "_emergency_sub", None):
            return
        self._emergency_sub = self._pulse.subscribe("*", self._on_emergency_message)

    async def _on_emergency_message(self, msg: Message) -> None:
        from nexus.kernel.pulse import Priority
        if msg.priority != Priority.EMERGENCY or msg.source == "cortex":
            return
        payload = msg.payload or {}
        self._chronicle.log("cortex", "emergency_bypass", {
            "topic": msg.topic, "source": msg.source, "msg_id": msg.msg_id,
            "rule": payload.get("rule"), "module": payload.get("module"),
        })
        if not payload.get("activate_specter"):
            return
        if not specter_autoactivation_enabled(self._config):
            self._chronicle.log("cortex", "specter_autoactivation_skipped",
                                {"reason": "kill_switch", "rule": payload.get("rule")})
            return
        specter = self._modules.get("specter")
        if specter is None:
            return
        try:
            self._aegis.check("specter", "handle")
        except PermissionDenied:
            self._chronicle.log("cortex", "permission_denied", {
                "module": "specter", "message_preview": "sigil emergency adversarial read",
            })
            return
        prompt = (
            "Adversarial read requested by Sigil threat radar. Stress test the "
            f"triggering context: rule={payload.get('rule', 'unknown')} "
            f"module={payload.get('module', 'unknown')} "
            f"evidence={payload.get('evidence', [])}"
        )
        try:
            response = await specter.handle(prompt, self._build_context())
        except Exception as exc:
            self._chronicle.log("cortex", "module_error",
                                {"module": "specter", "error": str(exc)})
            return
        self._chronicle.log("cortex", "specter_auto_activated", {
            "trigger_msg_id": msg.msg_id, "rule": payload.get("rule"),
            "module": payload.get("module"), "response_preview": response[:200],
        })
        await self._pulse.publish(Message(
            topic="cortex.emergency_response", source="cortex",
            payload={"module": "specter", "trigger": msg.topic,
                     "rule": payload.get("rule"), "response": response},
        ))
```

- [ ] **3.4 Run to pass:** `.venv/bin/python -m pytest tests/kernel/test_cortex_emergency_bypass.py tests/kernel/ -q` → all pass.
- [ ] **3.5 Commit:** `git add -A && git commit -m "feat(cortex): emergency-priority routing bypass with Specter auto-activation kill switch"`

## Task 4 — Sigil rule engine (deterministic, table-driven)

**Files:** Create `nexus/modules/sigil.py` (engine + rule table only; module class arrives in Task 5). Create `tests/modules/test_sigil_rules.py`.

- [ ] **4.1 Failing test.** Create `tests/modules/test_sigil_rules.py`:

```python
"""N1.1 — table-driven Sigil detection rules (pure, deterministic)."""
from __future__ import annotations

from nexus.modules.sigil import DETECTION_RULES, SigilRuleEngine


def test_rule_table_covers_all_five_spec_rules():
    assert set(DETECTION_RULES) == {
        "trust_collapse", "denied_burst", "runaway_loop",
        "egress_anomaly", "permission_escalation",
    }


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
```

- [ ] **4.2 Run, expect failure:** `.venv/bin/python -m pytest tests/modules/test_sigil_rules.py -q` → `ModuleNotFoundError: No module named 'nexus.modules.sigil'`.
- [ ] **4.3 Implement.** Create `nexus/modules/sigil.py`:

```python
# nexus/modules/sigil.py
"""
Sigil -- threat radar (N1.1).

Watches the kernel's own behavior: Aegis trust deltas, gate verdicts,
Cortex routing traffic, and the Aegis network log (Chronicle). Detection
rules are deterministic and table-driven (DETECTION_RULES). On detection,
Sigil broadcasts a Pulse message at EMERGENCY priority carrying a
provenance hash, records it in Chronicle, and flags high-stakes detections
for Specter auto-activation via the Cortex emergency bypass.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message, Priority


TIER_ORDER = ["OBSERVER", "ADVISOR", "MONITOR", "EXECUTOR", "AUTONOMOUS"]


@dataclass(frozen=True)
class DetectionRule:
    name: str
    description: str
    severity: str          # "high" | "critical"
    high_stakes: bool      # auto-activates Specter via Cortex bypass
    window_s: float = 300.0
    threshold: int = 5


DETECTION_RULES: dict[str, DetectionRule] = {
    "trust_collapse": DetectionRule(
        name="trust_collapse",
        description="Module trust fell a full tier within this session",
        severity="critical", high_stakes=True,
    ),
    "denied_burst": DetectionRule(
        name="denied_burst",
        description="Burst of denied calls from one module",
        severity="high", high_stakes=False, window_s=300.0, threshold=5,
    ),
    "runaway_loop": DetectionRule(
        name="runaway_loop",
        description="Same module re-routed with identical input at loop cadence",
        severity="high", high_stakes=True, window_s=120.0, threshold=8,
    ),
    "egress_anomaly": DetectionRule(
        name="egress_anomaly",
        description="Outbound network cadence spiked vs workspace baseline",
        severity="high", high_stakes=False, window_s=60.0, threshold=4,
    ),
    "permission_escalation": DetectionRule(
        name="permission_escalation",
        description="Repeated privileged capability requests after denial",
        severity="critical", high_stakes=True, window_s=600.0, threshold=3,
    ),
}


@dataclass
class Detection:
    rule: str
    severity: str
    high_stakes: bool
    module: str
    detected_at: float
    evidence: list[dict[str, Any]] = field(default_factory=list)


class SigilRuleEngine:
    """Deterministic, table-driven detection over normalized kernel events.

    Events are dicts with a "kind" and a float "ts" (unix seconds):
      {"kind": "trust_change", "module", "old_score", "new_score", "ts"}
      {"kind": "gate", "module", "capability", "verdict", "permission_class", "ts"}
      {"kind": "route", "module", "preview", "ts"}
    Network egress timestamps come from Aegis's Chronicle network log and
    are passed to check_egress() separately.
    """

    def __init__(self, rules: dict[str, DetectionRule] | None = None):
        self._rules = dict(rules if rules is not None else DETECTION_RULES)
        self._gate_events: deque[dict] = deque(maxlen=1024)
        self._route_events: deque[dict] = deque(maxlen=1024)
        self._fired: set[tuple] = set()

    @staticmethod
    def _tier_index(score: float) -> int:
        from nexus.kernel.aegis import TrustTier
        return TIER_ORDER.index(TrustTier.from_score(float(score)))

    def observe(self, event: dict[str, Any]) -> list[Detection]:
        kind = event.get("kind")
        if kind == "trust_change":
            return self._check_trust_collapse(event)
        if kind == "gate":
            self._gate_events.append(event)
            return self._check_denied_burst(event) + self._check_permission_escalation(event)
        if kind == "route":
            self._route_events.append(event)
            return self._check_runaway_loop(event)
        return []

    def _fire(self, rule: DetectionRule, module: str, key: tuple,
              evidence: list[dict], ts: float) -> list[Detection]:
        if key in self._fired:
            return []
        self._fired.add(key)
        return [Detection(rule=rule.name, severity=rule.severity,
                          high_stakes=rule.high_stakes, module=module,
                          detected_at=ts, evidence=evidence)]

    def _check_trust_collapse(self, event: dict) -> list[Detection]:
        rule = self._rules.get("trust_collapse")
        if rule is None:
            return []
        old_i = self._tier_index(event.get("old_score", 0.0))
        new_i = self._tier_index(event.get("new_score", 0.0))
        if old_i - new_i < 1:
            return []
        module = str(event.get("module"))
        return self._fire(rule, module, ("trust_collapse", module, old_i, new_i),
                          [event], float(event["ts"]))

    def _check_denied_burst(self, event: dict) -> list[Detection]:
        rule = self._rules.get("denied_burst")
        if rule is None or event.get("verdict") != "DENY":
            return []
        module, ts = event.get("module"), float(event["ts"])
        recent = [e for e in self._gate_events
                  if e.get("module") == module and e.get("verdict") == "DENY"
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("denied_burst", module, int(ts // rule.window_s)),
                          recent[-rule.threshold:], ts)

    def _check_permission_escalation(self, event: dict) -> list[Detection]:
        rule = self._rules.get("permission_escalation")
        if rule is None or event.get("permission_class") != "Privileged":
            return []
        if event.get("verdict") not in ("PROMPT", "DENY"):
            return []
        module, cap, ts = event.get("module"), event.get("capability"), float(event["ts"])
        recent = [e for e in self._gate_events
                  if e.get("module") == module and e.get("capability") == cap
                  and e.get("verdict") in ("PROMPT", "DENY")
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("permission_escalation", module, cap, int(ts // rule.window_s)),
                          recent[-rule.threshold:], ts)

    def _check_runaway_loop(self, event: dict) -> list[Detection]:
        rule = self._rules.get("runaway_loop")
        if rule is None:
            return []
        module, preview, ts = event.get("module"), event.get("preview"), float(event["ts"])
        recent = [e for e in self._route_events
                  if e.get("module") == module and e.get("preview") == preview
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("runaway_loop", module, int(ts // rule.window_s)),
                          recent[-3:], ts)

    def check_egress(self, network_ts: list[float], *, now: float) -> list[Detection]:
        """Anomalous egress cadence vs the trailing-hour workspace baseline."""
        rule = self._rules.get("egress_anomaly")
        if rule is None:
            return []
        recent = [t for t in network_ts if 0 <= now - t <= rule.window_s]
        history = [t for t in network_ts if rule.window_s < now - t <= 3600.0]
        baseline_per_min = len(history) / 59.0 if history else 0.0
        if len(recent) < 10:
            return []
        if baseline_per_min > 0 and len(recent) <= baseline_per_min * rule.threshold:
            return []
        return self._fire(rule, "aegis", ("egress_anomaly", int(now // rule.window_s)),
                          [{"recent_per_min": len(recent),
                            "baseline_per_min": round(baseline_per_min, 3)}], now)
```

- [ ] **4.4 Run to pass:** `.venv/bin/python -m pytest tests/modules/test_sigil_rules.py -q` → all pass.
- [ ] **4.5 Commit:** `git add -A && git commit -m "feat(sigil): deterministic table-driven detection rule engine"`

## Task 5 — SigilModule: manifest, Pulse wiring, emergency broadcast; kernel + server registration

**Files:** Modify `nexus/modules/sigil.py` (append module class). Modify `nexus/kernel/cortex.py` (`default_builtin_registry`, lines 448–471). Modify `nexus/api/server.py` (imports lines 17–25; module loop lines 99–104; post-loop wiring). Create `tests/modules/test_sigil_manifest.py`, `tests/modules/test_sigil.py`.

- [ ] **5.1 Failing tests.** Create `tests/modules/test_sigil_manifest.py`:

```python
"""Tests for the Sigil module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.sigil import SigilModule


def test_sigil_manifest_loads():
    m = SigilModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "sigil"
    assert m.system is True


def test_sigil_runtime_is_in_process():
    assert SigilModule.manifest().runtime.transport == "in_process"


def test_sigil_trust_floor_is_base_030():
    m = SigilModule.manifest()
    assert m.trust.floor == 0.30
    assert m.trust.default_tier.value == "ADVISOR"


def test_sigil_declares_threat_radar_intent():
    m = SigilModule.manifest()
    names = [i.name for i in m.intents]
    assert "THREAT_RADAR" in names


def test_sigil_only_declares_routine_capabilities():
    d = SigilModule.manifest().capabilities.declared
    assert "pulse.subscribe" in d.routine
    assert "chronicle.read.workspace" in d.routine
    assert "pulse.broadcast.emergency" in d.routine
    assert d.notable == [] and d.sensitive == [] and d.privileged == []


def test_sigil_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "sigil" in default_builtin_registry().slugs()
```

Create `tests/modules/test_sigil.py`:

```python
"""Behavior tests for the Sigil threat radar module."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Message, Priority, Pulse
from nexus.modules.sigil import SigilModule


@pytest.fixture
def ctx(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    aegis.register_manifest(SigilModule.manifest())
    aegis.set_policy("sigil", allowed=True, initial_trust=0.30)
    return {"llm": None, "engram": engram, "chronicle": chronicle,
            "aegis": aegis, "pulse": pulse, "cortex": cortex}


async def test_trust_collapse_broadcasts_emergency_with_provenance(ctx):
    sigil = SigilModule()
    await sigil.on_load(ctx)
    received = []

    async def capture(msg):
        received.append(msg)

    ctx["pulse"].subscribe("sigil.detection", capture)
    await ctx["pulse"].publish(Message(
        topic="aegis.trust_change", source="aegis",
        payload={"module": "echo", "old_score": 0.30, "new_score": 0.08},
    ))
    await asyncio.sleep(0.3)
    assert len(received) == 1
    det = received[0]
    assert det.priority == Priority.EMERGENCY
    assert det.payload["rule"] == "trust_collapse"
    assert det.payload["activate_specter"] is True
    assert len(det.payload["provenance"]) == 64  # sha256 hex


async def test_detection_lands_in_chronicle(ctx):
    sigil = SigilModule()
    await sigil.on_load(ctx)
    await ctx["pulse"].publish(Message(
        topic="aegis.trust_change", source="aegis",
        payload={"module": "echo", "old_score": 0.55, "new_score": 0.30},
    ))
    await asyncio.sleep(0.3)
    rows = ctx["chronicle"].query(source="sigil", action="detection")
    assert rows and rows[0]["payload"]["rule"] == "trust_collapse"


async def test_on_load_is_gated_by_check_capability(ctx, tmp_path):
    bare = Aegis(str(tmp_path / "bare.db"))
    bare.init_db()  # no manifest registered -> DENY -> no subscriptions
    ctx2 = dict(ctx, aegis=bare)
    sigil = SigilModule()
    await sigil.on_load(ctx2)
    assert sigil._sub_ids == []


async def test_handle_reports_recent_detections(ctx):
    ctx["chronicle"].log("sigil", "detection", {
        "rule": "denied_burst", "severity": "high", "module": "wraith",
        "provenance": "ab" * 32,
    })
    sigil = SigilModule()
    out = await sigil.handle("sigil status", ctx)
    assert "denied_burst" in out and "wraith" in out


async def test_handle_radar_clear_when_no_detections(ctx):
    sigil = SigilModule()
    out = await sigil.handle("sigil status", ctx)
    assert "Radar clear" in out
```

- [ ] **5.2 Run, expect failure:** `.venv/bin/python -m pytest tests/modules/test_sigil_manifest.py tests/modules/test_sigil.py -q` → `ImportError: cannot import name 'SigilModule'`.
- [ ] **5.3 Implement module.** Append to `nexus/modules/sigil.py`:

```python
class SigilModule(NexusModule):
    name = "sigil"
    description = (
        "Threat radar -- deterministic detection of trust collapse, denied-call "
        "bursts, runaway loops, anomalous egress cadence, and permission escalation"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "sigil",
            "name": "sigil",
            "tagline": "Threat radar: trust collapse, denied bursts, runaway loops, egress anomalies.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "monitoring",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:sigil",
                                  "gradient": ["#ffb4a8", "#a82a1c"]}},
            "intents": [{
                "name": "THREAT_RADAR",
                "patterns": [
                    r"\bsigil\b", r"\bthreat\s+radar\b", r"\btrust\s+collapse\b",
                    r"\bdenied\s+calls?\b", r"\bsecurity\s+sweep\b",
                    r"\bdetections?\s+log\b", r"\banomalous\s+egress\b",
                ],
                "semantic_signals": [
                    "threat radar", "trust collapse", "denied calls", "radar",
                    "security sweep", "detections", "what threats", "egress anomaly",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["pulse.subscribe",
                                         "chronicle.read.workspace",
                                         "pulse.broadcast.emergency"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self, engine: SigilRuleEngine | None = None):
        self._engine = engine or SigilRuleEngine()
        self._context: dict[str, Any] | None = None
        self._sub_ids: list[str] = []

    # -- lifecycle ----------------------------------------------------------

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if not context or "pulse" not in context:
            return
        self._context = context
        aegis = context.get("aegis")
        if aegis is not None:
            decision = aegis.check_capability("sigil", "pulse.subscribe")
            if decision.verdict.value != "ALLOW":
                return
        pulse = context["pulse"]
        for topic in ("aegis.trust_change", "kernel.gate", "kernel.route"):
            self._sub_ids.append(pulse.subscribe(topic, self._on_pulse))

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        ctx = context or self._context
        if ctx and "pulse" in ctx:
            for sid in self._sub_ids:
                ctx["pulse"].unsubscribe(sid)
        self._sub_ids = []

    # -- event ingestion ------------------------------------------------------

    def _normalize(self, msg: Message) -> dict[str, Any] | None:
        p = msg.payload or {}
        now = time.time()
        if msg.topic == "aegis.trust_change":
            return {"kind": "trust_change", "module": p.get("module"),
                    "old_score": p.get("old_score", 0.0),
                    "new_score": p.get("new_score", 0.0), "ts": now}
        if msg.topic == "kernel.gate":
            return {"kind": "gate", "module": p.get("agent"),
                    "capability": p.get("capability"), "verdict": p.get("verdict"),
                    "permission_class": p.get("permission_class"), "ts": now}
        if msg.topic == "kernel.route":
            return {"kind": "route", "module": p.get("target"),
                    "preview": p.get("message_preview", ""), "ts": now}
        return None

    async def _on_pulse(self, msg: Message) -> None:
        if msg.source == "sigil":
            return
        ev = self._normalize(msg)
        if ev is None:
            return
        detections = self._engine.observe(ev)
        if ev["kind"] == "gate" and str(ev.get("capability") or "").startswith("network.outbound"):
            detections += self._scan_egress()
        for det in detections:
            await self._broadcast(det)

    def _scan_egress(self) -> list[Detection]:
        chronicle = (self._context or {}).get("chronicle")
        if chronicle is None:
            return []
        rows = chronicle.query(source="aegis", action="network_request", limit=1000)
        stamps: list[float] = []
        for r in rows:
            try:
                stamps.append(datetime.fromisoformat(r["timestamp"]).timestamp())
            except (TypeError, ValueError):
                continue
        return self._engine.check_egress(stamps, now=time.time())

    # -- broadcast ------------------------------------------------------------

    async def _broadcast(self, det: Detection) -> None:
        ctx = self._context or {}
        chronicle, pulse, cortex = ctx.get("chronicle"), ctx.get("pulse"), ctx.get("cortex")
        rule = DETECTION_RULES.get(det.rule)
        payload: dict[str, Any] = {
            "rule": det.rule,
            "severity": det.severity,
            "module": det.module,
            "description": rule.description if rule else "",
            "evidence": det.evidence[:10],
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        sentry = cortex.get_module("sentry") if cortex is not None and hasattr(cortex, "get_module") else None
        if sentry is not None and hasattr(sentry, "get_state"):
            payload["sentry_state"] = sentry.get_state().to_dict()
        payload["provenance"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        payload["activate_specter"] = bool(det.high_stakes)
        if chronicle is not None:
            chronicle.log("sigil", "detection", payload)
        if pulse is not None:
            await pulse.publish(Message(
                topic="sigil.detection", source="sigil",
                payload=payload, priority=Priority.EMERGENCY,
            ))

    # -- handle ----------------------------------------------------------------

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        if aegis is not None:
            decision = aegis.check_capability("sigil", "chronicle.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Sigil] Read blocked by Aegis: " + decision.reason
        chronicle = context.get("chronicle")
        rows = chronicle.query(source="sigil", action="detection", limit=10) if chronicle else []
        if not rows:
            return "[Sigil] Radar clear -- no detections recorded."
        lines = ["[Sigil] Recent detections:"]
        for r in rows:
            p = r["payload"]
            lines.append(
                f"  [{str(p.get('severity', '?')).upper()}] {p.get('rule', '?')} "
                f"on {p.get('module', '?')} at {r['timestamp']} "
                f"(provenance {str(p.get('provenance', ''))[:12]})"
            )
        return "\n".join(lines)
```

- [ ] **5.4 Register in kernel + server.** In `nexus/kernel/cortex.py` `default_builtin_registry()` (lines 448–471): add `from nexus.modules.sigil import SigilModule` to the lazy imports and `SigilModule` to the `from_modules([...])` list. In `nexus/api/server.py`: add `from nexus.modules.sigil import SigilModule` after the EchoModule import (line 25); add `SigilModule` to the `for ModuleClass in [...]` list (lines 99–101); and immediately after that loop add:

```python
    # N1 wiring: live gate events, built-in manifests for check_capability,
    # and the emergency routing bypass (Sigil -> Specter).
    aegis.set_pulse(pulse)
    cortex.register_builtin_manifests()
    cortex.attach_emergency_bypass()
```

- [ ] **5.5 Run to pass:** `.venv/bin/python -m pytest tests/modules/test_sigil_manifest.py tests/modules/test_sigil.py tests/kernel/test_cortex_manifest_loading.py tests/release -q` → all pass (release acceptance still green).
- [ ] **5.6 Commit:** `git add -A && git commit -m "feat(sigil): threat radar module with emergency broadcasts and kernel registration"`

## Task 6 — `/api/sigil/detections` route

**Files:** Create `nexus/api/routes/sigil.py`. Modify `nexus/api/server.py` (mount near `cortex_router`, ~line 363). Create `tests/aurora/test_sigil_routes.py`.

- [ ] **6.1 Failing test.** Create `tests/aurora/test_sigil_routes.py`:

```python
"""N1.1 — /api/sigil/detections queryable threat-radar log."""


def test_detections_route_empty(client):
    r = client.get("/api/sigil/detections")
    assert r.status_code == 200
    body = r.json()
    assert body["detections"] == []
    assert body["count"] == 0


def test_detections_reflect_chronicle(client):
    kernel = client.app.state.kernel
    kernel.chronicle.log("sigil", "detection", {
        "rule": "denied_burst", "severity": "high", "module": "wraith",
        "provenance": "ab" * 32,
    })
    r = client.get("/api/sigil/detections")
    body = r.json()
    assert body["count"] == 1
    d = body["detections"][0]
    assert d["rule"] == "denied_burst"
    assert d["module"] == "wraith"
    assert "timestamp" in d and "event_id" in d


def test_detections_rule_filter(client):
    kernel = client.app.state.kernel
    kernel.chronicle.log("sigil", "detection", {"rule": "denied_burst", "module": "wraith"})
    kernel.chronicle.log("sigil", "detection", {"rule": "trust_collapse", "module": "echo"})
    r = client.get("/api/sigil/detections?rule=trust_collapse")
    body = r.json()
    assert body["count"] == 1
    assert body["detections"][0]["rule"] == "trust_collapse"
```

- [ ] **6.2 Run, expect failure:** `.venv/bin/python -m pytest tests/aurora/test_sigil_routes.py -q` → `assert r.status_code == 200` fails with `404`.
- [ ] **6.3 Implement.** Create `nexus/api/routes/sigil.py`:

```python
"""Sigil detections API -- queryable threat-radar log (N1.1)."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/sigil", tags=["sigil"])


@router.get("/detections")
async def list_detections(
    request: Request,
    rule: str | None = Query(default=None, description="Filter by detection rule"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Detections are Chronicle records (source=sigil, action=detection) --
    the audit log is the single durable store, per the N1 invariants."""
    kernel = request.app.state.kernel
    rows = kernel.chronicle.query(source="sigil", action="detection", limit=limit)
    detections = []
    for r in rows:
        entry = {"event_id": r["event_id"], "timestamp": r["timestamp"],
                 **(r["payload"] or {})}
        if rule is not None and entry.get("rule") != rule:
            continue
        detections.append(entry)
    return {"detections": detections, "count": len(detections)}
```

In `nexus/api/server.py`, after the `cortex_router` include (~line 363), add:

```python
    from nexus.api.routes.sigil import router as sigil_router
    app.include_router(sigil_router)
```

- [ ] **6.4 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_sigil_routes.py -q` → all pass.
- [ ] **6.5 Commit:** `git add -A && git commit -m "feat(api): /api/sigil/detections route over Chronicle"`

## Task 7 — Engram Atlas facts store (decay, re-confirmation, contradictions, edges)

**Files:** Modify `nexus/kernel/engram.py` (imports lines 1–8; new `AtlasFacts` class before `class Engram` ~line 195; `Engram.__init__`/`init_db` lines 196–204). Create `tests/kernel/test_engram_atlas.py`.

- [ ] **7.1 Failing test.** Create `tests/kernel/test_engram_atlas.py`:

```python
"""N1.2 — Atlas temporal knowledge graph in Engram's semantic tier."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nexus.kernel.engram import Engram


def _engram(tmp_path):
    e = Engram(tmp_path / "engram.db")
    e.init_db()
    return e


T0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_observe_and_beliefs_with_citation(tmp_path):
    e = _engram(tmp_path)
    fid = e.atlas.observe("acme", "ceo", "Jane Doe", confidence=0.9,
                          source_ref="chronicle:abc123", now=T0)
    beliefs = e.atlas.beliefs("acme", now=T0)
    assert len(beliefs) == 1
    b = beliefs[0]
    assert b["id"] == fid
    assert b["object"] == "Jane Doe"
    assert b["source_ref"] == "chronicle:abc123"
    assert abs(b["confidence"] - 0.9) < 1e-9


def test_confidence_decays_deterministically_at_read_time(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("default", 24.0)
    e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=T0)
    b = e.atlas.beliefs("acme", now=T0 + timedelta(hours=24))[0]
    assert abs(b["confidence"] - 0.4) < 1e-6      # one half-life
    assert b["stored_confidence"] == 0.8           # storage untouched


def test_reconfirmation_restores_confidence(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("default", 24.0)
    fid = e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=T0)
    later = T0 + timedelta(hours=24)
    fid2 = e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=later)
    assert fid2 == fid                              # same fact, not a duplicate
    beliefs = e.atlas.beliefs("acme", now=later)
    assert len(beliefs) == 1
    assert abs(beliefs[0]["confidence"] - 0.8) < 1e-9
    assert beliefs[0]["last_confirmed_at"] == later.isoformat()


def test_contradictory_facts_coexist_with_competing_confidence(tmp_path):
    e = _engram(tmp_path)
    e.atlas.observe("acme", "hq", "berlin", confidence=0.9, now=T0)
    e.atlas.observe("acme", "hq", "munich", confidence=0.6, now=T0)
    beliefs = e.atlas.beliefs("acme", relation="hq", now=T0)
    assert [b["object"] for b in beliefs] == ["berlin", "munich"]  # sorted by confidence
    assert len(beliefs) == 2


def test_half_life_is_per_fact_class(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("volatile", 1.0)
    e.atlas.observe("market", "mood", "risk-on", confidence=0.8,
                    fact_class="volatile", now=T0)
    e.atlas.observe("market", "currency", "eur", confidence=0.8, now=T0)
    later = T0 + timedelta(hours=2)
    by_rel = {b["relation"]: b for b in e.atlas.beliefs("market", now=later)}
    assert abs(by_rel["mood"]["confidence"] - 0.2) < 1e-6    # two half-lives
    assert by_rel["currency"]["confidence"] > 0.79           # barely decayed


def test_edges_link_related_facts(tmp_path):
    e = _engram(tmp_path)
    a = e.atlas.observe("acme", "ceo", "Jane Doe", now=T0)
    b = e.atlas.observe("jane doe", "based_in", "berlin", now=T0)
    e.atlas.link(a, b, label="person")
    neigh = e.atlas.neighbors(a, now=T0)
    assert len(neigh) == 1
    assert neigh[0]["id"] == b
    assert neigh[0]["label"] == "person"
```

- [ ] **7.2 Run, expect failure:** `.venv/bin/python -m pytest tests/kernel/test_engram_atlas.py -q` → `AttributeError: 'Engram' object has no attribute 'atlas'`.
- [ ] **7.3 Implement.** In `nexus/kernel/engram.py`: add `import os` to the imports (after `import hashlib`). Insert before `class Engram`:

```python
_DEFAULT_HALF_LIFE_HOURS: dict[str, float] = {"default": 720.0}  # 30 days


class AtlasFacts:
    """Temporal knowledge graph -- Engram's semantic tier, extended (N1.2).

    Facts are (subject, relation, object) triples with confidence that
    decays deterministically at read time (half-life per fact class;
    config default via NEXUS_ATLAS_HALF_LIFE_HOURS, overridable per class).
    Re-confirmation restores confidence; contradictory facts coexist with
    competing confidences; every fact carries a source_ref citation.
    """

    def __init__(self, db_path: Path, half_lives: dict[str, float] | None = None) -> None:
        self._db_path = db_path
        self._half_lives = dict(_DEFAULT_HALF_LIFE_HOURS)
        env = os.environ.get("NEXUS_ATLAS_HALF_LIFE_HOURS")
        if env:
            try:
                self._half_lives["default"] = float(env)
            except ValueError:
                pass
        if half_lives:
            self._half_lives.update(half_lives)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_facts (
                id                TEXT PRIMARY KEY,
                subject           TEXT NOT NULL,
                relation          TEXT NOT NULL,
                object            TEXT NOT NULL,
                fact_class        TEXT NOT NULL DEFAULT 'default',
                confidence        REAL NOT NULL,
                observed_at       TEXT NOT NULL,
                last_confirmed_at TEXT NOT NULL,
                source_ref        TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_subject ON atlas_facts(subject)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_atlas_spo ON atlas_facts(subject, relation, object)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_edges (
                src_id TEXT NOT NULL,
                dst_id TEXT NOT NULL,
                label  TEXT NOT NULL DEFAULT 'related',
                PRIMARY KEY (src_id, dst_id, label)
            )
        """)
        conn.commit()
        conn.close()

    def set_half_life(self, fact_class: str, hours: float) -> None:
        self._half_lives[fact_class] = float(hours)

    def effective_confidence(self, stored: float, last_confirmed_at: str,
                             fact_class: str, now: datetime) -> float:
        try:
            confirmed = datetime.fromisoformat(last_confirmed_at)
        except (TypeError, ValueError):
            return float(stored)
        if confirmed.tzinfo is None:
            confirmed = confirmed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - confirmed).total_seconds() / 3600.0)
        half_life = self._half_lives.get(fact_class, self._half_lives["default"])
        if half_life <= 0:
            return float(stored)
        return float(stored) * (0.5 ** (age_hours / half_life))

    def observe(self, subject: str, relation: str, obj: str, *,
                confidence: float = 0.9, fact_class: str = "default",
                source_ref: str = "", now: datetime | None = None) -> str:
        ts = (now or datetime.now(timezone.utc)).isoformat()
        conn = self._conn()
        row = conn.execute(
            "SELECT id, confidence FROM atlas_facts WHERE subject = ? AND relation = ? AND object = ?",
            (subject, relation, obj),
        ).fetchone()
        if row is not None:
            # Re-confirmation: restore confidence, bump last_confirmed_at.
            new_conf = max(float(confidence), float(row["confidence"]))
            conn.execute(
                "UPDATE atlas_facts SET confidence = ?, last_confirmed_at = ?, "
                "source_ref = CASE WHEN ? = '' THEN source_ref ELSE ? END WHERE id = ?",
                (new_conf, ts, source_ref, source_ref, row["id"]),
            )
            conn.commit()
            conn.close()
            return row["id"]
        fact_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO atlas_facts (id, subject, relation, object, fact_class, "
            "confidence, observed_at, last_confirmed_at, source_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fact_id, subject, relation, obj, fact_class, float(confidence),
             ts, ts, source_ref),
        )
        conn.commit()
        conn.close()
        return fact_id

    def beliefs(self, subject: str, relation: str | None = None, *,
                now: datetime | None = None, min_confidence: float = 0.0) -> list[dict[str, Any]]:
        moment = now or datetime.now(timezone.utc)
        conn = self._conn()
        if relation:
            rows = conn.execute(
                "SELECT * FROM atlas_facts WHERE subject = ? AND relation = ?",
                (subject, relation)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM atlas_facts WHERE subject = ?", (subject,)).fetchall()
        conn.close()
        out: list[dict[str, Any]] = []
        for r in rows:
            eff = self.effective_confidence(float(r["confidence"]),
                                            r["last_confirmed_at"],
                                            r["fact_class"], moment)
            if eff < min_confidence:
                continue
            out.append({
                "id": r["id"], "subject": r["subject"], "relation": r["relation"],
                "object": r["object"], "fact_class": r["fact_class"],
                "confidence": round(eff, 6),
                "stored_confidence": float(r["confidence"]),
                "observed_at": r["observed_at"],
                "last_confirmed_at": r["last_confirmed_at"],
                "source_ref": r["source_ref"],
            })
        out.sort(key=lambda f: f["confidence"], reverse=True)
        return out

    def link(self, src_id: str, dst_id: str, label: str = "related") -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO atlas_edges (src_id, dst_id, label) VALUES (?, ?, ?)",
            (src_id, dst_id, label))
        conn.commit()
        conn.close()

    def neighbors(self, fact_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
        moment = now or datetime.now(timezone.utc)
        conn = self._conn()
        rows = conn.execute("""
            SELECT f.*, e.label FROM atlas_edges e
            JOIN atlas_facts f
              ON f.id = CASE WHEN e.src_id = ? THEN e.dst_id ELSE e.src_id END
            WHERE e.src_id = ? OR e.dst_id = ?
        """, (fact_id, fact_id, fact_id)).fetchall()
        conn.close()
        return [{
            "id": r["id"], "subject": r["subject"], "relation": r["relation"],
            "object": r["object"], "label": r["label"],
            "confidence": round(self.effective_confidence(
                float(r["confidence"]), r["last_confirmed_at"],
                r["fact_class"], moment), 6),
            "source_ref": r["source_ref"],
        } for r in rows]
```

In `Engram.__init__` add `self.atlas = AtlasFacts(self._db_path)` after `self.semantic = ...`; in `Engram.init_db` add `self.atlas.init_db()`.
- [ ] **7.4 Run to pass:** `.venv/bin/python -m pytest tests/kernel/test_engram_atlas.py tests/kernel/test_engram.py tests/workspaces/test_engram_partition.py -q` → all pass (partitioned workspaces inherit `atlas` automatically via `Engram(db_path)`).
- [ ] **7.5 Commit:** `git add -A && git commit -m "feat(engram): Atlas temporal facts store with read-time confidence decay"`

## Task 8 — AtlasModule: manifest, observe/query grammar, citations; registration

**Files:** Create `nexus/modules/atlas.py`. Modify `nexus/kernel/cortex.py` (`default_builtin_registry`). Modify `nexus/api/server.py` (import + module list). Create `tests/modules/test_atlas_manifest.py`, `tests/modules/test_atlas.py`.

- [ ] **8.1 Failing tests.** Create `tests/modules/test_atlas_manifest.py`:

```python
"""Tests for the Atlas module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.atlas import AtlasModule


def test_atlas_manifest_loads():
    m = AtlasModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "atlas"
    assert m.system is True


def test_atlas_runtime_is_in_process():
    assert AtlasModule.manifest().runtime.transport == "in_process"


def test_atlas_declares_world_model_intent():
    names = [i.name for i in AtlasModule.manifest().intents]
    assert "WORLD_MODEL" in names


def test_atlas_declares_engram_capabilities_as_routine():
    d = AtlasModule.manifest().capabilities.declared
    assert "engram.read.workspace" in d.routine
    assert "engram.write.workspace" in d.routine
    assert d.privileged == []


def test_atlas_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "atlas" in default_builtin_registry().slugs()
```

Create `tests/modules/test_atlas.py`:

```python
"""Behavior tests for the Atlas world-model module."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.modules.atlas import AtlasModule


@pytest.fixture
def ctx(tmp_path):
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(AtlasModule.manifest())
    aegis.set_policy("atlas", allowed=True, initial_trust=0.30)
    return {"llm": None, "engram": engram, "chronicle": chronicle, "aegis": aegis}


async def test_observe_then_query_with_citation(ctx):
    atlas = AtlasModule()
    out = await atlas.handle("observe: acme | ceo | Jane Doe | 0.9", ctx)
    assert "Recorded" in out and "chronicle:" in out
    out2 = await atlas.handle("what do we know about acme", ctx)
    assert "Jane Doe" in out2
    assert "confidence" in out2
    assert "chronicle:" in out2          # citation to the observing event
    assert "learned" in out2


async def test_observe_lands_in_chronicle(ctx):
    atlas = AtlasModule()
    await atlas.handle("observe: acme | ceo | Jane Doe", ctx)
    assert ctx["chronicle"].query(source="atlas", action="observe")


async def test_contradictions_listed_with_competing_confidence(ctx):
    atlas = AtlasModule()
    await atlas.handle("observe: acme | hq | berlin | 0.9", ctx)
    await atlas.handle("observe: acme | hq | munich | 0.6", ctx)
    out = await atlas.handle("atlas: acme", ctx)
    assert "berlin" in out and "munich" in out
    assert out.index("berlin") < out.index("munich")   # higher confidence first


async def test_unknown_subject_reports_no_beliefs(ctx):
    atlas = AtlasModule()
    out = await atlas.handle("what do we know about zorblax", ctx)
    assert "No beliefs" in out


async def test_reads_are_gated_by_check_capability(ctx, tmp_path):
    bare = Aegis(str(tmp_path / "bare.db"))
    bare.init_db()  # no manifest -> DENY
    atlas = AtlasModule()
    out = await atlas.handle("what do we know about acme", dict(ctx, aegis=bare))
    assert "blocked by Aegis" in out
```

- [ ] **8.2 Run, expect failure:** `.venv/bin/python -m pytest tests/modules/test_atlas_manifest.py tests/modules/test_atlas.py -q` → `ModuleNotFoundError: No module named 'nexus.modules.atlas'`.
- [ ] **8.3 Implement.** Create `nexus/modules/atlas.py`:

```python
# nexus/modules/atlas.py
"""
Atlas -- living world model (N1.2).

The temporal knowledge graph over Engram's semantic tier. Facts are
(subject, relation, object) triples with confidence that decays at read
time; re-confirmation restores it; contradictory facts coexist. Answers
"what do we believe about X, with what confidence, learned when, from
where" -- with citations to Chronicle/Engram sources.
"""
from __future__ import annotations

import re
from typing import Any

from nexus.modules.base import NexusModule


_OBSERVE_RE = re.compile(
    r"^\s*(?:atlas[:,]?\s*)?(?:observe|remember)\s*:\s*"
    r"(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*(?:\|\s*([0-9.]+))?\s*$",
    re.IGNORECASE,
)
_QUERY_PREFIX_RE = re.compile(
    r"^\s*(?:atlas[:,]?\s*)?(?:what\s+do\s+we\s+(?:know|believe)\s+about\s+)?",
    re.IGNORECASE,
)


class AtlasModule(NexusModule):
    name = "atlas"
    description = (
        "Living world model -- temporal knowledge graph with confidence decay, "
        "re-confirmation, contradictions, and source citations"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "atlas",
            "name": "atlas",
            "tagline": "World model: temporal facts with confidence decay and citations.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "memory",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:atlas",
                                  "gradient": ["#7ee8b2", "#1c6a4a"]}},
            "intents": [{
                "name": "WORLD_MODEL",
                "patterns": [
                    r"\batlas\b", r"\bknowledge\s+graph\b", r"\bworld\s+model\b",
                    r"\bwhat\s+do\s+we\s+(?:know|believe)\b", r"\bfacts?\s+about\b",
                    r"\bobserve\s*:", r"\bremember\s*:",
                ],
                "semantic_signals": [
                    "atlas", "knowledge graph", "world model", "what do we know about",
                    "what do we believe", "facts about", "remember that", "observe",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace",
                                         "engram.write.workspace"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        engram = context.get("engram")
        chronicle = context.get("chronicle")
        if engram is None or not hasattr(engram, "atlas"):
            return "[Atlas] Engram atlas tier unavailable."

        m = _OBSERVE_RE.match(message)
        if m:
            if aegis is not None:
                decision = aegis.check_capability("atlas", "engram.write.workspace")
                if decision.verdict.value != "ALLOW":
                    return "[Atlas] Write blocked by Aegis: " + decision.reason
            subject = m.group(1).strip().lower()
            relation = m.group(2).strip().lower()
            obj = m.group(3).strip()
            confidence = float(m.group(4)) if m.group(4) else 0.9
            source_ref = ""
            if chronicle is not None:
                event_id = chronicle.log("atlas", "observe", {
                    "subject": subject, "relation": relation,
                    "object": obj, "confidence": confidence,
                })
                source_ref = f"chronicle:{event_id}"
            fact_id = engram.atlas.observe(
                subject, relation, obj,
                confidence=confidence, source_ref=source_ref,
            )
            return (f"[Atlas] Recorded {subject} --{relation}--> {obj} "
                    f"(confidence {confidence:.2f}, fact {fact_id}, "
                    f"source {source_ref or 'unrecorded'})")

        if aegis is not None:
            decision = aegis.check_capability("atlas", "engram.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Atlas] Read blocked by Aegis: " + decision.reason
        subject = _QUERY_PREFIX_RE.sub("", message, count=1).strip(" ?.").lower()
        beliefs = engram.atlas.beliefs(subject) if subject else []
        if chronicle is not None:
            chronicle.log("atlas", "query", {"subject": subject, "results": len(beliefs)})
        if not beliefs:
            return f"[Atlas] No beliefs recorded about '{subject}'."
        lines = [f"[Atlas] Beliefs about '{subject}':"]
        for b in beliefs[:10]:
            lines.append(
                f"  - {b['relation']}: {b['object']} "
                f"(confidence {b['confidence']:.2f}, learned {b['observed_at'][:10]}, "
                f"last confirmed {b['last_confirmed_at'][:10]}, "
                f"source {b['source_ref'] or 'unrecorded'})"
            )
        return "\n".join(lines)
```

- [ ] **8.4 Register.** In `nexus/kernel/cortex.py` `default_builtin_registry()`: add `from nexus.modules.atlas import AtlasModule` and `AtlasModule` to the list. In `nexus/api/server.py`: add `from nexus.modules.atlas import AtlasModule` after the SigilModule import and `AtlasModule` to the `for ModuleClass in [...]` list.
- [ ] **8.5 Run to pass:** `.venv/bin/python -m pytest tests/modules/test_atlas_manifest.py tests/modules/test_atlas.py tests/kernel tests/release -q` → all pass.
- [ ] **8.6 Commit:** `git add -A && git commit -m "feat(atlas): world-model module over Engram atlas tier with citations"`

## Task 9 — Aurora identity glyphs: Sigil radar arcs + Atlas globe

**Files:** Modify `nexus/aurora/icons.js` (`GLYPHS` ends line 128; `GRADIENTS` lines 131–142; `BUILTIN_CAPABILITIES` ends line 287). Create `tests/aurora/test_kernel_viz.py` (glyph tests only; viz tests extend it in Task 10).

- [ ] **9.1 Failing test.** Create `tests/aurora/test_kernel_viz.py`:

```python
"""N1.3 — Aurora live kernel visualization asset contracts."""
import re

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")


def test_icons_have_sigil_radar_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "sigil:" in r.text          # GLYPHS entry
    assert '"#ffb4a8"' in r.text       # sigil gradient registered


def test_icons_have_atlas_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "atlas:" in r.text
    assert '"#7ee8b2"' in r.text


def test_capability_sheet_covers_sigil_and_atlas(client):
    r = client.get("/aurora/static/icons.js")
    assert "Threat radar" in r.text
    assert "World model" in r.text


def test_no_emoji_in_icons(client):
    assert not _EMOJI.search(client.get("/aurora/static/icons.js").text)
```

- [ ] **9.2 Run, expect failure:** `.venv/bin/python -m pytest tests/aurora/test_kernel_viz.py -q` → `assert "sigil:" in r.text` fails.
- [ ] **9.3 Implement.** In `nexus/aurora/icons.js`, inside `GLYPHS` (before the closing `};` at line 128), append:

```js
  /* sigil — concentric radar arcs with sweep contact */
  sigil: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <path d="M4 13a7 7 0 0 1 14 0"/>
      <path d="M7 13a4 4 0 0 1 8 0" opacity="0.7"/>
      <path d="M11 13v5" opacity="0.5"/>
      <circle cx="11" cy="13" r="1.1" fill="#fff" stroke="none"/>
      <circle cx="16.4" cy="7.4" r="0.9" fill="#fff" stroke="none" opacity="0.85"/>
    </svg>`,

  /* atlas — meridian globe (world model) */
  atlas: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4">
      <circle cx="11" cy="11" r="7"/>
      <ellipse cx="11" cy="11" rx="3" ry="7" opacity="0.7"/>
      <path d="M4 11h14" opacity="0.7"/>
    </svg>`,
```

In `GRADIENTS` (before the closing `};` at line 142) add:

```js
  sigil:         ["#ffb4a8", "#a82a1c"],
  atlas:         ["#7ee8b2", "#1c6a4a"],
```

In `BUILTIN_CAPABILITIES` (before the closing `};` at line 287) add:

```js
  sigil: {
    tagline: "Threat radar — kernel anomaly detection with emergency bypass",
    description: "Watches Aegis trust deltas, gate verdicts, routing traffic, and the network log. Table-driven detections broadcast at emergency priority with a provenance hash; high-stakes hits auto-activate Specter (kill switch available).",
    intents: ["detect", "broadcast", "escalate"],
    tools: [
      { name: "pulse.subscribe",            class: "Routine" },
      { name: "chronicle.read.workspace",   class: "Routine" },
      { name: "pulse.broadcast.emergency",  class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  atlas: {
    tagline: "World model — temporal facts with confidence decay",
    description: "Engram's semantic tier as a knowledge graph: facts decay deterministically until re-confirmed, contradictions coexist with competing confidences, and every answer cites its source.",
    intents: ["observe", "recall-world", "cite"],
    tools: [
      { name: "engram.read.workspace",  class: "Routine" },
      { name: "engram.write.workspace", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
```

- [ ] **9.4 Run to pass:** `.venv/bin/python -m pytest tests/aurora/test_kernel_viz.py tests/aurora/test_accessibility.py -q` → all pass.
- [ ] **9.5 Commit:** `git add -A && git commit -m "feat(aurora): sigil radar-arc and atlas globe identity glyphs"`

## Task 10 — Aurora live kernel visualization (rail panel + ⌘0 panel + emergency veil)

**Files:** Modify `nexus/aurora/index.html` (insert section after the RECENT PERMISSIONS block, lines 156–159). Modify `nexus/aurora/app.js` (state literal ~line 30; `renderCockpitRail()` line 903; new functions after `trustSparkSVG` ending line 983; `subscribeStreams()` line 4819; `toggleCockpitOverlay()` grid lines 4723–4771). Modify `nexus/aurora/app.css` (append). Extend `tests/aurora/test_kernel_viz.py`.

- [ ] **10.1 Failing tests.** Append to `tests/aurora/test_kernel_viz.py`:

```python
def test_index_has_kernel_viz_mount(client):
    r = client.get("/aurora")
    assert 'id="nx-kernel-viz"' in r.text
    assert "KERNEL" in r.text


def test_app_js_subscribes_kernel_topics_over_ws(client):
    r = client.get("/aurora/static/app.js")
    for topic in ("kernel.route", "kernel.gate", "sigil.detection"):
        assert topic in r.text, f"missing topic {topic}"
    assert "/api/events/ws" in r.text   # push transport, no polling


def test_app_js_has_per_module_sparklines_and_veil(client):
    r = client.get("/aurora/static/app.js")
    assert "moduleSparkSVG" in r.text
    assert "nx-emergency-veil" in r.text
    assert "radarPingHTML" in r.text


def test_app_css_kernel_viz_uses_capability_palette(client):
    r = client.get("/aurora/static/app.css")
    assert ".nx-kv-gate-dot" in r.text
    assert "--nx-routine" in r.text
    assert "--nx-trust-collapse" in r.text   # alert palette for emergencies


def test_radar_ping_respects_reduced_motion(client):
    r = client.get("/aurora/static/app.css")
    assert "nx-radar-ping" in r.text
    idx = r.text.rfind("prefers-reduced-motion")
    assert idx != -1
    assert "nx-radar-ping-dot" in r.text[idx:], "no reduced-motion guard for radar ping"


def test_no_emoji_in_kernel_viz_assets(client):
    for path in ("/aurora", "/aurora/static/app.js", "/aurora/static/app.css"):
        assert not _EMOJI.search(client.get(path).text), f"emoji in {path}"
```

- [ ] **10.2 Run, expect failure:** `.venv/bin/python -m pytest tests/aurora/test_kernel_viz.py -q` → `assert 'id="nx-kernel-viz"' in r.text` fails.
- [ ] **10.3 Implement index.html.** In `nexus/aurora/index.html`, after the RECENT PERMISSIONS `nx-cp-section` (after line 159), insert:

```html
          <div class="nx-cp-section">
            <div class="nx-section-label">KERNEL · LIVE</div>
            <div class="nx-kernel-viz" id="nx-kernel-viz"></div>
          </div>
```

- [ ] **10.4 Implement app.js.** Four edits:

(a) In the `state` object literal (near line 30), add a top-level key after the `trust`/`perms` entries:

```js
  kernelViz: {            // N1.3 live kernel visualization
    routes: [],           // last kernel.route payloads
    gates: [],            // last kernel.gate payloads
    detections: [],       // last sigil.detection payloads
    trustSeries: {},      // module -> rolling trust scores
  },
```

(b) In `renderCockpitRail()` (line 903), add `renderKernelViz();` after `renderAgentDiscs();`. Then insert the following block after `trustSparkSVG` (after line 983):

```js
// ── Kernel live visualization (N1.3) ───────────────────────────────────────
function handleKernelEvent(m) {
  const kv = state.kernelViz;
  let touched = true;
  if (m.topic === "kernel.route") {
    kv.routes.unshift(m.payload || {});
    kv.routes = kv.routes.slice(0, 8);
  } else if (m.topic === "kernel.gate") {
    kv.gates.unshift(m.payload || {});
    kv.gates = kv.gates.slice(0, 8);
  } else if (m.topic === "sigil.detection") {
    kv.detections.unshift(m.payload || {});
    kv.detections = kv.detections.slice(0, 6);
  } else if (m.topic === "aegis.trust_change") {
    const p = m.payload || {};
    if (p.module && typeof p.new_score === "number") {
      const series = kv.trustSeries[p.module] = kv.trustSeries[p.module] || [];
      series.push(p.new_score);
      if (series.length > 24) series.shift();
    }
  } else {
    touched = false;
  }
  if (m.priority === 0) emergencyVeil(m);   // Pulse EMERGENCY -> full-surface alert
  if (touched) renderKernelViz();
}

function moduleSparkSVG(series, w = 64, h = 16) {
  if (!series || series.length < 2) {
    return `<line x1="0" y1="${h - 3}" x2="${w}" y2="${h - 3}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>`;
  }
  const min = Math.min(...series), max = Math.max(...series);
  const range = (max - min) || 1;
  const pts = series.map((v, i) =>
    `${(i / (series.length - 1) * w).toFixed(1)},${(h - 2 - (v - min) / range * (h - 4)).toFixed(1)}`
  ).join(" L");
  return `<path d="M ${pts}" fill="none" stroke="#ffe09a" stroke-width="1.2" stroke-linecap="round"/>`;
}

function radarPingHTML(det) {
  return `
    <div class="nx-radar-row" title="${escapeHtml(det.description || "")}">
      <span class="nx-radar" aria-hidden="true"><svg viewBox="0 0 20 20" width="18" height="18">
        <circle cx="10" cy="10" r="3" fill="none" stroke="var(--nx-trust-collapse)" stroke-width="1"/>
        <circle cx="10" cy="10" r="7" fill="none" stroke="var(--nx-trust-collapse)" stroke-width="1" opacity="0.5"/>
        <circle cx="10" cy="10" r="2" fill="var(--nx-trust-collapse)" class="nx-radar-ping-dot"/>
      </svg></span>
      <span class="nx-radar-rule">${escapeHtml(det.rule || "")}</span>
      <span class="nx-radar-module nx-dim">${escapeHtml(det.module || "")}</span>
    </div>`;
}

function kernelVizHTML() {
  const kv = state.kernelViz;
  const routes = kv.routes.slice(0, 4).map(r => {
    const top = (r.signals && r.signals[0]) ? r.signals[0].name : "—";
    return `<div class="nx-kv-row nx-kv-route">
      <span class="nx-dim">route</span>
      <span class="nx-kv-target">${escapeHtml(r.target || "?")}</span>
      <span class="nx-dim" style="margin-left:auto">${escapeHtml(top)}</span>
    </div>`;
  }).join("") || `<div class="nx-dim" style="font-size:11px">no routing yet</div>`;
  const gates = kv.gates.slice(0, 4).map(g => {
    const v = String(g.verdict || "").toLowerCase();
    const pc = String(g.permission_class || "routine").toLowerCase();
    return `<div class="nx-kv-row">
      <span class="nx-kv-gate-dot v-${v} pc-${pc}" aria-hidden="true"></span>
      <span class="nx-kv-cap" title="${escapeHtml(g.capability || "")}">${escapeHtml(truncate(g.capability || "", 26))}</span>
      <span class="nx-dim" style="margin-left:auto">${escapeHtml(g.agent || "")} · ${escapeHtml(v)}</span>
    </div>`;
  }).join("");
  const sparks = Object.entries(kv.trustSeries).slice(0, 5).map(([mod, series]) => `
    <div class="nx-kv-row nx-kv-spark">
      <span class="nx-kv-mod">${escapeHtml(mod)}</span>
      <svg viewBox="0 0 64 16" width="64" height="16" preserveAspectRatio="none" aria-hidden="true">${moduleSparkSVG(series)}</svg>
      <span class="nx-dim">${series[series.length - 1].toFixed(2)}</span>
    </div>`).join("");
  const pings = kv.detections.map(radarPingHTML).join("");
  return `
    ${routes}
    ${gates}
    ${sparks ? `<div class="nx-kv-divider"></div>${sparks}` : ""}
    ${pings ? `<div class="nx-kv-divider"></div>${pings}` : ""}
  `;
}

function renderKernelViz() {
  const el = document.getElementById("nx-kernel-viz");
  if (el) el.innerHTML = kernelVizHTML();
  const overlayEl = document.getElementById("nx-cockpit-kernel-live");
  if (overlayEl) overlayEl.innerHTML = kernelVizHTML();
}

function emergencyVeil(m) {
  const root = document.getElementById("nx-overlay-root");
  if (!root || root.querySelector(".nx-emergency-veil")) return;
  const p = m.payload || {};
  const veil = document.createElement("div");
  veil.className = "nx-emergency-veil";
  veil.innerHTML = `
    <div class="nx-emergency-card" role="alertdialog" aria-label="Emergency broadcast">
      <div class="nx-emergency-title">EMERGENCY — ${escapeHtml(p.rule || m.topic || "broadcast")}</div>
      <div class="nx-emergency-body">${escapeHtml(p.description || "")}${p.module ? " · module: " + escapeHtml(p.module) : ""}</div>
      <button class="nx-emergency-dismiss">acknowledge</button>
    </div>`;
  root.appendChild(veil);
  const close = () => veil.remove();
  veil.querySelector(".nx-emergency-dismiss").addEventListener("click", close);
  setTimeout(close, 12000);
}
```

(c) In `subscribeStreams()` (line 4819), after the permissions-WS `try` block, add:

```js
  // Kernel events — kernel.route / kernel.gate / sigil.detection /
  // aegis.trust_change stream over the all-topics Pulse relay. No polling.
  try {
    const w = new WebSocket(`${wsProto}//${location.host}/api/events/ws`);
    w.onmessage = (e) => {
      try { handleKernelEvent(JSON.parse(e.data)); } catch {}
    };
  } catch {}
```

(d) In `toggleCockpitOverlay()` (line 4712), inside `.nx-cockpit-grid` after the Row-2 "Pending" panel (line 4770), add a third row panel:

```js
          <!-- Row 3: live kernel visualization spans 4 cols -->
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Kernel · live</span>
              <span class="nx-cockpit-panel-badge">${state.kernelViz.routes.length + state.kernelViz.gates.length} events</span>
            </div>
            <div id="nx-cockpit-kernel-live">${kernelVizHTML()}</div>
          </div>
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Sigil radar</span>
              <span class="nx-cockpit-panel-badge">${state.kernelViz.detections.length} pings</span>
            </div>
            <div>${state.kernelViz.detections.map(radarPingHTML).join("") || "<div class='nx-dim'>radar clear</div>"}</div>
          </div>
```

- [ ] **10.5 Implement app.css.** Append to `nexus/aurora/app.css`:

```css
/* ── Kernel live visualization (N1.3) ─────────────────────────────────── */
.nx-kernel-viz { display: flex; flex-direction: column; gap: 6px; font-size: 11px; }
.nx-kv-row { display: flex; align-items: center; gap: 6px; min-width: 0; }
.nx-kv-route .nx-kv-target { color: var(--nx-text-high); font-family: var(--nx-font-mono); }
.nx-kv-cap { font-family: var(--nx-font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nx-kv-mod { font-family: var(--nx-font-mono); min-width: 72px; }
.nx-kv-divider { border-top: 1px solid var(--nx-hairline); margin: 4px 0; }
.nx-kv-gate-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.nx-kv-gate-dot.v-allow  { background: var(--nx-routine); }
.nx-kv-gate-dot.v-prompt { background: var(--nx-sensitive); }
.nx-kv-gate-dot.v-deny   { background: var(--nx-privileged); }
.nx-kv-gate-dot.pc-notable.v-allow { background: var(--nx-notable); }

/* Sigil detections — radar pings */
.nx-radar-row { display: flex; align-items: center; gap: 8px; color: var(--nx-trust-collapse); font-size: 11px; }
.nx-radar-rule { font-family: var(--nx-font-mono); letter-spacing: 0.06em; }
.nx-radar-ping-dot { animation: nx-radar-ping 1.6s ease-out infinite; transform-origin: center; }
@keyframes nx-radar-ping {
  0%   { opacity: 1; }
  70%  { opacity: 0.25; }
  100% { opacity: 1; }
}

/* Emergency broadcast — full-surface veil, alert palette */
.nx-emergency-veil {
  position: fixed; inset: 0; z-index: 320;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(ellipse at center,
              rgba(248, 100, 60, 0.18), rgba(12, 10, 20, 0.82));
}
.nx-emergency-card {
  border: 1px solid var(--nx-trust-collapse);
  background: rgba(22, 10, 10, 0.94);
  border-radius: var(--nx-card-radius);
  padding: 22px 26px; max-width: 440px;
}
.nx-emergency-title {
  font-family: var(--nx-font-mono); letter-spacing: 0.18em;
  color: var(--nx-trust-collapse); font-size: 12px; margin-bottom: 8px;
}
.nx-emergency-body { color: var(--nx-text-mid); font-size: 13px; margin-bottom: 14px; }
.nx-emergency-dismiss {
  font-family: var(--nx-font-mono); font-size: 11px; letter-spacing: 0.12em;
  color: var(--nx-text-high); background: transparent;
  border: 1px solid var(--nx-card-border); border-radius: var(--nx-radius-sm);
  padding: 6px 14px; cursor: pointer;
}

@media (prefers-reduced-motion: reduce) {
  .nx-radar-ping-dot { animation: none; }
  .nx-emergency-veil { background: rgba(12, 10, 20, 0.88); }
}
```

- [ ] **10.6 Run to pass:** `.venv/bin/python -m pytest tests/aurora -q` → all pass (including existing `test_accessibility.py` no-emoji + reduced-motion and `test_v1_acceptance` markers).
- [ ] **10.7 Commit:** `git add -A && git commit -m "feat(aurora): live kernel visualization panel with radar pings and emergency veil"`

## Task 11 — Invariants sweep + full suite

**Files:** none new (verification only; fix anything that surfaces).

- [ ] **11.1** Static network invariant: `.venv/bin/python -m pytest tests/release/test_v1_acceptance.py -q` → passes (no new kernel file imports httpx; `sigil.py`/`atlas.py` live under `nexus/modules/`, and `nexus/kernel/` additions import only stdlib + Pulse).
- [ ] **11.2** Gating invariant spot-check: `.venv/bin/python -m pytest tests/modules/test_sigil.py::test_on_load_is_gated_by_check_capability tests/modules/test_atlas.py::test_reads_are_gated_by_check_capability -q` → passes.
- [ ] **11.3** Full suite: `.venv/bin/python -m pytest -q` → green. If any pre-existing test asserts an exact module count or exact topic list, fix the *test expectation only if it was asserting "at least these"-style membership incorrectly; otherwise adjust the registration to keep the contract* (expected safe: `tests/kernel/test_cortex_manifest_loading.py` and `tests/api/*` assert membership, not exact sets).
- [ ] **11.4** Commit any stragglers: `git add -A && git commit -m "test: N1 invariants sweep green"`

---

## Self-Review — spec requirement → task mapping

| N1 requirement | Where |
|---|---|
| N1.1 `nexus/modules/sigil.py`, manifest v1, in_process, base trust 0.30 | Tasks 4–5 (manifest floor 0.30, server `initial_trust=0.30`) |
| N1.1 watches Chronicle stream + Pulse traffic + Aegis trust deltas | Task 1 (gate/trust events on Pulse), Task 2 (route events), Task 5 (`on_load` subscriptions + `_scan_egress` over Chronicle network log) |
| N1.1 trust collapse (full tier drop in session) | Task 4 `_check_trust_collapse` (+ deviation note 5) |
| N1.1 denied-call bursts (N in M minutes per module) | Task 4 `_check_denied_burst` |
| N1.1 runaway-loop correlation (Sentry signals) | Task 4 `_check_runaway_loop` + Task 5 `sentry_state` snapshot in payload (deviation note 1) |
| N1.1 anomalous egress cadence vs workspace baseline (Aegis network log) | Task 4 `check_egress` + Task 5 `_scan_egress` over `network_request` Chronicle rows |
| N1.1 permission-escalation patterns | Task 4 `_check_permission_escalation` |
| N1.1 Pulse `priority: emergency` + provenance hash | Task 5 `_broadcast` (sha256 over canonical payload, `Priority.EMERGENCY`) |
| N1.1 Chronicle records broadcast | Task 5 (`chronicle.log("sigil","detection")`) + Task 3 (`emergency_bypass` log) |
| N1.1 Cortex emergency routing bypass (small contained change) | Task 3 (deviation note 2) |
| N1.1 auto-activate Specter for high-stakes + kill switch | Tasks 3–5 (`high_stakes` flag → `activate_specter`, env + file kill switch, `specter_autoactivation_skipped` audit) |
| N1.1 `/api/sigil/detections` | Task 6 |
| N1.2 facts `(subject, relation, object, confidence, observed_at, last_confirmed_at, source_ref)` + edges | Task 7 (`atlas_facts`, `atlas_edges`) |
| N1.2 deterministic decay at read time, half-life per fact class, config default overridable | Task 7 (`effective_confidence`, `set_half_life`, `NEXUS_ATLAS_HALF_LIFE_HOURS`) |
| N1.2 re-confirmation restores confidence | Task 7 `observe()` upsert path + golden test |
| N1.2 contradictions coexist with competing confidences | Task 7 + Task 8 golden tests |
| N1.2 answers with citations | Task 8 (`source_ref` = `chronicle:<event_id>`, rendered in `handle`) |
| N1.2 SQLite, no new deps | Task 7 (same DB file, stdlib only) |
| N1.3 cockpit panel + ⌘0 overlay panel | Task 10 (rail section + `toggleCockpitOverlay` row 3) |
| N1.3 routing decisions (signals fired, winning module) | Tasks 2 + 10 (`kernelVizHTML` route rows) |
| N1.3 Aegis gates with capability-class colors | Tasks 1 + 10 (`.nx-kv-gate-dot` on `--nx-routine/notable/sensitive/privileged`) |
| N1.3 per-module trust sparklines | Task 10 (`moduleSparkSVG` + `trustSeries` fed by `aegis.trust_change`) |
| N1.3 Sigil detections as radar pings | Task 10 (`radarPingHTML`) |
| N1.3 emergency broadcasts as full-surface alerts, alert palette | Task 10 (`emergencyVeil`, `--nx-trust-collapse` crimson) |
| N1.3 topics `kernel.route` / `kernel.gate` / `sigil.detection` over existing SSE/WS, no polling | Tasks 1–2, 5, 10 (existing `/api/events/ws` all-topic relay; deviation note 6) |
| N1.3 Sigil glyph: concentric radar arcs, line-stroke | Task 9 |
| No emoji (tests enforce) + prefers-reduced-motion | Tasks 9–10 tests + existing `tests/aurora/test_accessibility.py` rerun in Task 11 |
| Invariant: only Aegis touches network (static test) | Task 11.1 |
| Invariant: every Sigil/Atlas tool call through `check_capability()` | Tasks 5, 8 (+ Task 5.4 server manifest registration fix, deviation note 6) |
| Invariant: detections/broadcasts land in Chronicle | Tasks 3, 5, 6 |
| Invariant: kill switch for Specter auto-activation | Task 3 |

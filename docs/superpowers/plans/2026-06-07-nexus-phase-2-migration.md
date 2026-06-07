# NEXUS Phase 2 — Built-in Migration Implementation Plan (Phase 2 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the 9 cognitive modules (Council, Specter, Autonomic, Oracle, Wraith, Legacy, Consciousness, Sentry, Echo) plus the `agent_dispatcher` ("agents") onto the new agent manifest system from Phase 1. Cortex stops reading the hardcoded `_INTENT_DEFS` and starts reading intents from a manifest registry. After this phase, every "thing that runs intelligence" inside NEXUS is a unified agent — built-ins look like catalog agents from the runtime's perspective. Existing routing tests must keep passing.

**Architecture:**
- A new `BuiltinRegistry` (`nexus/agents/registry.py`) discovers `NexusModule` subclasses, calls `.manifest()` on each, and exposes the list to the kernel.
- Each module gains a `manifest()` classmethod whose `intents[]` is a one-to-one port of its current `_INTENT_DEFS` entry. Capabilities, identity marks, and trust floors are declared per-module.
- `Cortex.IntentClassifier` is refactored to build its intent list from manifests instead of the hardcoded `_INTENT_DEFS`. Existing scoring weights and behaviour are preserved exactly.
- Kernel boot wires the registry into Aegis (`register_manifest` for each) and into Cortex (intent loading from manifests).

**Tech Stack:** Python 3.11+, pydantic 2 (manifest model), pytest. No new runtime dependencies — this phase is purely a refactor that consolidates the source of truth.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — §13 (Migration of the existing 9 modules), §6 (Manifest), §4.1 (Cortex routing).

**Prior phase:** `docs/superpowers/plans/2026-06-06-nexus-foundation.md` — completed at git tag `phase-1-foundation`. The `Manifest`, `InProcessAgent`, `Aegis.register_manifest()`, `NexusModule.manifest()` ABC method (currently raising `NotImplementedError`) are all in place.

---

## Pre-flight

Before starting any task:

- Confirm you are on a clean working tree on branch `nexus-phase-2` (created fresh from `phase-1-foundation` tag, or via a worktree at `.worktrees/nexus-phase-2`).
- Confirm `git log --oneline -1 phase-1-foundation` resolves — your branch should descend from that tag.
- Run `pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3` and confirm the count starts at **703 passing** (the foundation baseline plus the 41 new Phase 1 tests). Pre-existing 28 failures + 65 collection errors remain out of scope.
- Activate the venv: `source .venv/bin/activate`.

**File structure additions for Phase 2:**

```
nexus/
├── agents/
│   ├── registry.py             (new) — BuiltinRegistry: discovery + load
│   └── manifest.py             (unchanged)
└── modules/
    ├── council.py              (modify — add manifest() classmethod)
    ├── specter.py              (modify)
    ├── autonomic.py            (modify)
    ├── oracle.py               (modify)
    ├── wraith.py               (modify)
    ├── legacy.py               (modify)
    ├── consciousness.py        (modify)
    ├── sentry.py               (modify)
    ├── echo.py                 (modify — Privileged declaration)
    └── agent_dispatcher.py     (modify — slug "agents")
└── kernel/
    └── cortex.py               (modify — read intents from registry)

tests/
├── agents/
│   ├── test_registry.py        (new)
│   └── test_phase_2_routing_smoke.py  (new — end-to-end)
└── modules/
    ├── test_council_manifest.py        (new)
    ├── test_specter_manifest.py        (new)
    ├── ... (one per migrated module)
    └── test_agent_dispatcher_manifest.py
```

The existing `tests/kernel/test_cortex.py` is preserved as-is — its routing tests are the regression target.

---

## Task 1 · `BuiltinRegistry` — discover & register built-in manifests

**Why:** A single place that knows which built-in modules exist, calls `.manifest()` on each, and hands the list to Aegis + Cortex. This is the spine the rest of the phase hangs on.

**Files:**
- Create: `nexus/agents/registry.py`
- Create: `tests/agents/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agents/test_registry.py`:

```python
"""Tests for the BuiltinRegistry — discovers and registers built-in agent manifests."""
from __future__ import annotations

import pytest

from nexus.agents.registry import BuiltinRegistry
from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule


class _ModA(NexusModule):
    name = "mod-a"
    description = "module A"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "mod-a", "name": "mod-a", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:mod-a", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "DO_A", "patterns": [r"\bdo-a\b"],
                         "semantic_signals": ["do a"], "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return "a"


class _ModB(NexusModule):
    name = "mod-b"
    description = "module B"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "mod-b", "name": "mod-b", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:mod-b", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "DO_B", "patterns": [r"\bdo-b\b"],
                         "semantic_signals": ["do b"], "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return "b"


def test_registry_loads_explicit_module_classes():
    """A registry built from explicit module classes exposes each manifest."""
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    slugs = sorted(reg.slugs())
    assert slugs == ["mod-a", "mod-b"]


def test_registry_iter_manifests_returns_validated_manifest_objects():
    reg = BuiltinRegistry.from_modules([_ModA])
    manifests = list(reg.manifests())
    assert len(manifests) == 1
    assert isinstance(manifests[0], Manifest)
    assert manifests[0].slug == "mod-a"


def test_registry_iter_module_class_pairs():
    """`pairs()` yields (manifest, module_class) so callers can both register
    the manifest with Aegis and instantiate the module for InProcessAgent."""
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    pairs = dict((m.slug, cls) for m, cls in reg.pairs())
    assert pairs == {"mod-a": _ModA, "mod-b": _ModB}


def test_register_into_aegis(tmp_path):
    """Helper that calls aegis.register_manifest() for every built-in."""
    from nexus.kernel.aegis import Aegis
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    reg.register_all(aegis)
    assert aegis.get_manifest("mod-a") is not None
    assert aegis.get_manifest("mod-b") is not None


def test_module_without_manifest_raises_at_registry_build():
    """A module whose manifest() raises NotImplementedError must surface at build time."""

    class _Broken(NexusModule):
        name = "broken"
        description = "no manifest"
        version = "0.1.0"

        async def handle(self, message, context):
            return ""

    with pytest.raises(NotImplementedError):
        BuiltinRegistry.from_modules([_Broken])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_registry.py -v
```

Expected: ImportError on `nexus.agents.registry`.

- [ ] **Step 3: Implement `nexus/agents/registry.py`**

```python
"""
BuiltinRegistry — discovers and loads built-in agent manifests.

Phase 2 uses the explicit `from_modules([...])` constructor — the
controlling code knows which 10 built-ins to load. A later phase may
add auto-discovery via a plugin entry point.
"""
from __future__ import annotations

from typing import Iterable, Iterator, TYPE_CHECKING

from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class BuiltinRegistry:
    def __init__(self, entries: list[tuple[Manifest, type[NexusModule]]]):
        self._entries = entries

    # ── construction ────────────────────────────────────────────────────

    @classmethod
    def from_modules(cls, module_classes: Iterable[type[NexusModule]]) -> "BuiltinRegistry":
        """Build a registry from explicit module classes. Calls .manifest()
        on each — if any raises NotImplementedError, the build fails fast.
        """
        entries: list[tuple[Manifest, type[NexusModule]]] = []
        for module_cls in module_classes:
            manifest = module_cls.manifest()  # raises if not implemented
            entries.append((manifest, module_cls))
        return cls(entries)

    # ── queries ─────────────────────────────────────────────────────────

    def slugs(self) -> list[str]:
        return [m.slug for m, _ in self._entries]

    def manifests(self) -> Iterator[Manifest]:
        for m, _ in self._entries:
            yield m

    def pairs(self) -> Iterator[tuple[Manifest, type[NexusModule]]]:
        yield from self._entries

    def __len__(self) -> int:
        return len(self._entries)

    # ── side effects ────────────────────────────────────────────────────

    def register_all(self, aegis: "Aegis") -> None:
        """Register every built-in manifest with Aegis."""
        for manifest, _ in self._entries:
            aegis.register_manifest(manifest)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_registry.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Full regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 708 passing (703 + 5 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/agents/registry.py tests/agents/test_registry.py
git commit -m "feat(agents): add BuiltinRegistry for discovering built-in manifests"
```

---

## Task 2 · Migrate Council (proves the pattern)

**Why:** Council is the largest, most-visible built-in — and the safest first migration because Cortex's `_INTENT_DEFS[DELIBERATE]` already aliases to it. We port the manifest, prove the registry can register it, and confirm Cortex still routes `should i...` queries the same way.

**Files:**
- Modify: `nexus/modules/council.py` (add `manifest()` classmethod only)
- Create: `tests/modules/test_council_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/modules/test_council_manifest.py`:

```python
"""Tests for the Council module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest, PermissionClass
from nexus.modules.council import CouncilModule


def test_council_manifest_loads():
    m = CouncilModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "council"
    assert m.system is True


def test_council_declares_deliberate_intent():
    m = CouncilModule.manifest()
    names = [i.name for i in m.intents]
    assert "DELIBERATE" in names


def test_council_intent_includes_signature_patterns():
    """The deliberate intent must keep the patterns Cortex currently uses."""
    m = CouncilModule.manifest()
    deliberate = next(i for i in m.intents if i.name == "DELIBERATE")
    pattern_text = "\n".join(deliberate.patterns)
    # A few signature patterns from the existing _INTENT_DEFS
    assert "should\\s+i" in pattern_text
    assert "decid" in pattern_text or "decision" in pattern_text
    assert "ethic" in pattern_text


def test_council_only_declares_routine_capabilities():
    """Council does no fs/network/process — purely cognitive."""
    m = CouncilModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_council_runtime_is_in_process():
    m = CouncilModule.manifest()
    assert m.runtime.transport == "in_process"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/modules/test_council_manifest.py -v
```

Expected: `NotImplementedError` from the default `manifest()` in `NexusModule`.

- [ ] **Step 3: Add `manifest()` to `nexus/modules/council.py`**

Open the file and locate the `CouncilModule` class definition. Add the following classmethod inside the class (location: just after the `version` attribute and before any methods). Do not modify any other code in the file:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "council",
            "name": "council",
            "tagline": "Four-lens deliberation: ethical, verification, lateral, synthesis.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus", "url": "https://github.com/AllStreets/ONEXUS"},
            "category": "deliberation",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:council",
                                  "gradient": ["#ffd2a0", "#c47a32"]}},
            "intents": [{
                "name": "DELIBERATE",
                "patterns": [
                    r"\bshould\s+i\b", r"\bpros\s+and\s+cons\b", r"\bweigh\b", r"\btrade-?off\b",
                    r"\bdeliberat\w*\b", r"\bnegotiat\w*\b", r"\bethic(al|s)?\b", r"\bmoral(ly)?\b",
                    r"\bright\s+thing\b", r"\bdecide\b", r"\bdecision\b", r"\bcouncil\b",
                    r"\bwhat\s+if\b.*\bvs\b", r"\badvise\b", r"\bsimulat\w*\b",
                    r"\bperspective\b", r"\bdebate\b", r"\bconsider\b",
                ],
                "semantic_signals": [
                    "should i", "pros and cons", "what if", "weigh options", "ethical question",
                    "negotiate", "decision", "deliberate", "multiple perspectives", "trade-off",
                    "think through", "advise me", "help me decide", "is it right to",
                    "simulation", "synthesis", "verification", "lateral thinking",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace"],
                    "Notable": [],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.50, "default_tier": "MONITOR"},
        })
```

The `from nexus.agents.manifest import Manifest` is intentionally inline (lazy) to avoid a hard import at module load — same pattern Task 4 used for the ABC.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/modules/test_council_manifest.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Confirm Council's existing tests still pass**

```bash
pytest tests/modules/test_council.py -v 2>&1 | tail -10
```

Expected: same pass/fail breakdown as baseline. The manifest addition is purely additive.

- [ ] **Step 6: Full regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 713 passing (708 + 5 new), 28 failed (baseline).

- [ ] **Step 7: Commit**

```bash
git add nexus/modules/council.py tests/modules/test_council_manifest.py
git commit -m "feat(council): declare v1 manifest with DELIBERATE intent"
```

---

## Task 3 · Migrate Specter, Autonomic, Oracle

**Why:** Three modules with the same shape as Council — purely cognitive, only declare `Routine` capabilities. Batched into one task because each repeats the Council pattern.

**Files:**
- Modify: `nexus/modules/specter.py`
- Modify: `nexus/modules/autonomic.py`
- Modify: `nexus/modules/oracle.py`
- Create: `tests/modules/test_specter_manifest.py`
- Create: `tests/modules/test_autonomic_manifest.py`
- Create: `tests/modules/test_oracle_manifest.py`

- [ ] **Step 1: Write the three test files (template-based)**

For each of (specter, CHALLENGE), (autonomic, AUTOMATE), (oracle, ANTICIPATE), create a test file mirroring `test_council_manifest.py`. Use this template — replace `{module}`, `{Class}`, `{intent_name}`, and `{signature_pattern_substr}` for each.

`tests/modules/test_specter_manifest.py`:

```python
"""Tests for the Specter module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.specter import SpecterModule


def test_specter_manifest_loads():
    m = SpecterModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "specter"
    assert m.system is True


def test_specter_declares_challenge_intent():
    m = SpecterModule.manifest()
    names = [i.name for i in m.intents]
    assert "CHALLENGE" in names


def test_specter_intent_includes_signature_patterns():
    m = SpecterModule.manifest()
    intent = next(i for i in m.intents if i.name == "CHALLENGE")
    pattern_text = "\n".join(intent.patterns)
    assert "red\\s+team" in pattern_text or "red-team" in pattern_text or "red team" in pattern_text or "redteam" in pattern_text or "red_team" in pattern_text or "red" in pattern_text
    assert "devil" in pattern_text.lower()


def test_specter_only_declares_routine_capabilities():
    m = SpecterModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_specter_runtime_is_in_process():
    m = SpecterModule.manifest()
    assert m.runtime.transport == "in_process"
```

`tests/modules/test_autonomic_manifest.py`:

```python
"""Tests for the Autonomic module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.autonomic import AutonomicModule


def test_autonomic_manifest_loads():
    m = AutonomicModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "autonomic"
    assert m.system is True


def test_autonomic_declares_automate_intent():
    m = AutonomicModule.manifest()
    names = [i.name for i in m.intents]
    assert "AUTOMATE" in names


def test_autonomic_intent_includes_signature_patterns():
    m = AutonomicModule.manifest()
    intent = next(i for i in m.intents if i.name == "AUTOMATE")
    pattern_text = "\n".join(intent.patterns)
    assert "automat" in pattern_text
    assert "routine" in pattern_text


def test_autonomic_declares_process_spawn_as_notable():
    """Autonomic needs to spawn subprocesses for routines — declared Notable."""
    m = AutonomicModule.manifest()
    assert "process.spawn" in m.capabilities.declared.notable


def test_autonomic_runtime_is_in_process():
    m = AutonomicModule.manifest()
    assert m.runtime.transport == "in_process"
```

`tests/modules/test_oracle_manifest.py`:

```python
"""Tests for the Oracle module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.oracle import OracleModule


def test_oracle_manifest_loads():
    m = OracleModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "oracle"
    assert m.system is True


def test_oracle_declares_anticipate_intent():
    m = OracleModule.manifest()
    names = [i.name for i in m.intents]
    assert "ANTICIPATE" in names


def test_oracle_intent_includes_signature_patterns():
    m = OracleModule.manifest()
    intent = next(i for i in m.intents if i.name == "ANTICIPATE")
    pattern_text = "\n".join(intent.patterns)
    assert "predict" in pattern_text
    assert "anticipat" in pattern_text


def test_oracle_only_declares_routine_capabilities():
    m = OracleModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_oracle_runtime_is_in_process():
    m = OracleModule.manifest()
    assert m.runtime.transport == "in_process"
```

- [ ] **Step 2: Run all three test files; verify they fail**

```bash
pytest tests/modules/test_specter_manifest.py tests/modules/test_autonomic_manifest.py tests/modules/test_oracle_manifest.py -v
```

Expected: all fail with `NotImplementedError`.

- [ ] **Step 3: Add `manifest()` classmethod to each of the three modules**

For each module file, add `@classmethod manifest()` using the same shape as Council. Use these per-module dictionaries (paste in full — do not abbreviate):

**`nexus/modules/specter.py`:** add inside the `SpecterModule` class.

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "specter",
            "name": "specter",
            "tagline": "Adversarial review: red-team audits, counter-arguments, failure modes.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "deliberation",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:specter",
                                  "gradient": ["#ff9eb8", "#8c2e54"]}},
            "intents": [{
                "name": "CHALLENGE",
                "patterns": [
                    r"\bstress\s+test\b", r"\bred\s+team\b", r"\bdevil'?s?\s+advocate\b",
                    r"\bwhat\s+could\s+go\s+wrong\b", r"\brisk\s+analysis\b",
                    r"\bcounter-?argument\b", r"\bchallenge\s+(this|that|my)\b",
                    r"\bvulnerabilit\w*\b", r"\bharden\b", r"\bweakness\w*\b",
                    r"\bpoke\s+holes?\b", r"\bspecter\b",
                ],
                "semantic_signals": [
                    "stress test", "red team", "devil's advocate", "what could go wrong",
                    "risk analysis", "counter-argument", "challenge this", "find flaws",
                    "adversarial", "worst case", "attack surface", "poke holes",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.40, "default_tier": "ADVISOR"},
        })
```

**`nexus/modules/autonomic.py`:** add inside the `AutonomicModule` class.

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "autonomic",
            "name": "autonomic",
            "tagline": "Earned autonomy: learns routines, proposes actions, acts within trust boundaries.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "automation",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:autonomic",
                                  "gradient": ["#c8a0ff", "#5e3a9c"]}},
            "intents": [{
                "name": "AUTOMATE",
                "patterns": [
                    r"\bautomat\w*\b", r"\broutine\b", r"\bautopilot\b", r"\bautonomous\b",
                    r"\bon\s+my\s+behalf\b", r"\bhandle\s+it\b", r"\btake\s+care\s+of\b",
                    r"\bmanage\s+for\s+me\b", r"\bdo\s+it\s+for\s+me\b", r"\bautonomic\b",
                    r"\btrust\s+status\b", r"\bdomain\s+trust\b", r"\bdelegat\w*\b",
                ],
                "semantic_signals": [
                    "do this automatically", "handle it", "take care of", "automate",
                    "routine", "on my behalf", "manage for me", "autonomous",
                    "trust management", "delegate", "run on autopilot",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace"],
                    "Notable": ["process.spawn"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })
```

**`nexus/modules/oracle.py`:** add inside the `OracleModule` class.

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "oracle",
            "name": "oracle",
            "tagline": "Anticipatory pattern detection: trigger rules, threats, early warnings.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "monitoring",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:oracle",
                                  "gradient": ["#a8e8ff", "#346b9c"]}},
            "intents": [{
                "name": "ANTICIPATE",
                "patterns": [
                    r"\bpredict\w*\b", r"\banticipat\w*\b", r"\btrigger\b", r"\balert\b",
                    r"\bmonitor\b", r"\bscan\b", r"\bpattern\s+(detect|scan)\w*\b",
                    r"\bwatch\s+for\b", r"\bearly\s+warning\b", r"\bthreat\s+detect\w*\b",
                    r"\boracle\b", r"\bforecast\b", r"\btrend\b",
                ],
                "semantic_signals": [
                    "predict", "anticipate", "trigger", "alert", "monitor",
                    "scan for patterns", "watch for", "early warning", "threat detection",
                    "forecast", "trend analysis", "what's coming",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.40, "default_tier": "ADVISOR"},
        })
```

- [ ] **Step 4: Run all three new test files**

```bash
pytest tests/modules/test_specter_manifest.py tests/modules/test_autonomic_manifest.py tests/modules/test_oracle_manifest.py -v
```

Expected: 15 passed (5 per file × 3).

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 728 passing (713 + 15 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/modules/specter.py nexus/modules/autonomic.py nexus/modules/oracle.py \
        tests/modules/test_specter_manifest.py tests/modules/test_autonomic_manifest.py \
        tests/modules/test_oracle_manifest.py
git commit -m "feat(modules): declare manifests for specter, autonomic, oracle"
```

---

## Task 4 · Migrate Wraith, Legacy, Consciousness, Sentry

**Why:** Four more cognitive modules. Wraith declares `process.spawn` (Notable) for phantoms. The others are Routine-only.

**Files:**
- Modify: `nexus/modules/wraith.py`, `legacy.py`, `consciousness.py`, `sentry.py`
- Create: `tests/modules/test_wraith_manifest.py`, `test_legacy_manifest.py`, `test_consciousness_manifest.py`, `test_sentry_manifest.py`

- [ ] **Step 1: Write the four test files**

Each follows the Council template. Show only the per-module distinctive content.

`tests/modules/test_wraith_manifest.py`:

```python
"""Tests for the Wraith module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.wraith import WraithModule


def test_wraith_manifest_loads():
    m = WraithModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "wraith"
    assert m.system is True


def test_wraith_declares_spawn_intent():
    m = WraithModule.manifest()
    assert "SPAWN" in [i.name for i in m.intents]


def test_wraith_intent_includes_spawn_patterns():
    m = WraithModule.manifest()
    intent = next(i for i in m.intents if i.name == "SPAWN")
    text = "\n".join(intent.patterns)
    assert "spawn" in text
    assert "sub-?agent" in text or "sub_agent" in text or "subagent" in text


def test_wraith_declares_process_spawn_notable():
    """Wraith spawns ephemeral subprocesses — declared Notable."""
    m = WraithModule.manifest()
    assert "process.spawn" in m.capabilities.declared.notable


def test_wraith_runtime_is_in_process():
    m = WraithModule.manifest()
    assert m.runtime.transport == "in_process"
```

`tests/modules/test_legacy_manifest.py`:

```python
"""Tests for the Legacy module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.legacy import LegacyModule


def test_legacy_manifest_loads():
    m = LegacyModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "legacy"
    assert m.system is True


def test_legacy_declares_crystallize_intent():
    m = LegacyModule.manifest()
    assert "CRYSTALLIZE" in [i.name for i in m.intents]


def test_legacy_intent_includes_signature_patterns():
    m = LegacyModule.manifest()
    intent = next(i for i in m.intents if i.name == "CRYSTALLIZE")
    text = "\n".join(intent.patterns)
    assert "crystallize" in text
    assert "playbook" in text


def test_legacy_only_declares_routine_capabilities():
    m = LegacyModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_legacy_runtime_is_in_process():
    m = LegacyModule.manifest()
    assert m.runtime.transport == "in_process"
```

`tests/modules/test_consciousness_manifest.py`:

```python
"""Tests for the Consciousness module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.consciousness import ConsciousnessModule


def test_consciousness_manifest_loads():
    m = ConsciousnessModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "consciousness"
    assert m.system is True


def test_consciousness_declares_reflect_intent():
    m = ConsciousnessModule.manifest()
    assert "REFLECT" in [i.name for i in m.intents]


def test_consciousness_intent_includes_signature_patterns():
    m = ConsciousnessModule.manifest()
    intent = next(i for i in m.intents if i.name == "REFLECT")
    text = "\n".join(intent.patterns)
    assert "journal" in text
    assert "reflect" in text or "introspect" in text


def test_consciousness_only_declares_routine_capabilities():
    m = ConsciousnessModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_consciousness_runtime_is_in_process():
    m = ConsciousnessModule.manifest()
    assert m.runtime.transport == "in_process"
```

`tests/modules/test_sentry_manifest.py`:

```python
"""Tests for the Sentry module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.sentry import SentryModule


def test_sentry_manifest_loads():
    m = SentryModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "sentry"
    assert m.system is True


def test_sentry_declares_regulate_intent():
    m = SentryModule.manifest()
    assert "REGULATE" in [i.name for i in m.intents]


def test_sentry_intent_includes_signature_patterns():
    m = SentryModule.manifest()
    intent = next(i for i in m.intents if i.name == "REGULATE")
    text = "\n".join(intent.patterns)
    assert "focus" in text or "fatigue" in text
    assert "cognitive" in text or "flow" in text


def test_sentry_only_declares_routine_capabilities():
    m = SentryModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_sentry_runtime_is_in_process():
    m = SentryModule.manifest()
    assert m.runtime.transport == "in_process"
```

- [ ] **Step 2: Run all four test files; verify they fail**

```bash
pytest tests/modules/test_wraith_manifest.py tests/modules/test_legacy_manifest.py \
       tests/modules/test_consciousness_manifest.py tests/modules/test_sentry_manifest.py -v
```

Expected: all fail with `NotImplementedError`.

- [ ] **Step 3: Add manifests to each module**

**`nexus/modules/wraith.py`:** inside `WraithModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "wraith",
            "name": "wraith",
            "tagline": "Ephemeral sub-agent spawner with death clocks.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "orchestration",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:wraith",
                                  "gradient": ["#9affc8", "#2a6a4e"]}},
            "intents": [{
                "name": "SPAWN",
                "patterns": [
                    r"\bspawn\b", r"\bparallel\s+task\b", r"\bsimultaneous(ly)?\b",
                    r"\bmulti-?task\b", r"\bbackground\s+(work|task|job)\b",
                    r"\bresearch\s+\w+\s+and\s+\w+\b", r"\bwraith\b",
                    r"\bsub-?agent\b", r"\bfork\b",
                ],
                "semantic_signals": [
                    "spawn", "parallel tasks", "research X and Y simultaneously",
                    "multi-task", "background work", "sub-agent", "fork off",
                    "do both at once", "work on these in parallel",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace"],
                    "Notable": ["process.spawn"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.35, "default_tier": "ADVISOR"},
        })
```

**`nexus/modules/legacy.py`:** inside `LegacyModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "legacy",
            "name": "legacy",
            "tagline": "Knowledge crystallization: playbooks, heuristics, distilled wisdom.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "knowledge",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:legacy",
                                  "gradient": ["#ffd680", "#9c6a1a"]}},
            "intents": [{
                "name": "CRYSTALLIZE",
                "patterns": [
                    r"\bcrystallize\b", r"\bdistill\b", r"\bplaybook\b", r"\bframework\b",
                    r"\bheuristic\b", r"\bwhat\s+have\s+i\s+learned\b",
                    r"\bpattern\s+extract\w*\b", r"\bwisdom\b", r"\blegacy\b",
                    r"\blesson\w*\s+learned\b", r"\bknowledge\s+base\b",
                ],
                "semantic_signals": [
                    "distill knowledge", "playbook", "what have I learned", "framework",
                    "heuristics", "crystallize", "lessons learned", "codify knowledge",
                    "extract patterns", "wisdom", "build a guide from experience",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.50, "default_tier": "MONITOR"},
        })
```

**`nexus/modules/consciousness.py`:** inside `ConsciousnessModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "consciousness",
            "name": "consciousness",
            "tagline": "Self-reflection: journals, contradictions, dreams, reasoning traces.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reflection",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:consciousness",
                                  "gradient": ["#e0c8ff", "#5a3a8c"]}},
            "intents": [{
                "name": "REFLECT",
                "patterns": [
                    r"\bhow\s+are\s+you\b", r"\bjournal\b", r"\bself[- ]?reflect\w*\b",
                    r"\bintrospect\w*\b", r"\bconsciousness\b", r"\breasoning\s+trace\b",
                    r"\bcontradiction\b", r"\bdream\b", r"\bwhat\s+are\s+you\s+(doing|thinking)\b",
                    r"\bimplicit\s+goals?\b", r"\bemergent\b", r"\bshow\s+reasoning\b",
                    r"\bwhy\s+do\s+you\s+think\b", r"\bhow\s+did\s+you\b",
                ],
                "semantic_signals": [
                    "journal", "self-reflection", "introspection", "how are you",
                    "reasoning trace", "contradictions", "dreams", "consciousness",
                    "emergent goals", "what are you doing", "implicit goals",
                    "provenance", "show your reasoning", "how did you decide",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.40, "default_tier": "ADVISOR"},
        })
```

**`nexus/modules/sentry.py`:** inside `SentryModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "sentry",
            "name": "sentry",
            "tagline": "Cognitive regulation: focus, fatigue, stress, flow state.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "monitoring",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:sentry",
                                  "gradient": ["#ffb878", "#8c4218"]}},
            "intents": [{
                "name": "REGULATE",
                "patterns": [
                    r"\bcognitive\b", r"\bfocus\b", r"\bfatigue\b", r"\bstress\b",
                    r"\bflow\s+state\b", r"\benergy\b", r"\btired\b",
                    r"\bhow\s+am\s+i\s+doing\b", r"\bmental\s+state\b",
                    r"\bsentry\b", r"\bworkload\b", r"\bburn-?out\b",
                ],
                "semantic_signals": [
                    "cognitive state", "focus", "fatigue", "stress level",
                    "flow state", "energy", "how am I doing", "mental state",
                    "workload", "burnout", "am I overloaded",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.40, "default_tier": "ADVISOR"},
        })
```

- [ ] **Step 4: Run all four new test files**

```bash
pytest tests/modules/test_wraith_manifest.py tests/modules/test_legacy_manifest.py \
       tests/modules/test_consciousness_manifest.py tests/modules/test_sentry_manifest.py -v
```

Expected: 20 passed (5 per file × 4).

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 748 passing (728 + 20 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/modules/wraith.py nexus/modules/legacy.py nexus/modules/consciousness.py \
        nexus/modules/sentry.py tests/modules/test_wraith_manifest.py \
        tests/modules/test_legacy_manifest.py tests/modules/test_consciousness_manifest.py \
        tests/modules/test_sentry_manifest.py
git commit -m "feat(modules): declare manifests for wraith, legacy, consciousness, sentry"
```

---

## Task 5 · Migrate Echo (declares Privileged `engram.read.global`)

**Why:** Echo is the only built-in that declares a Privileged capability — `engram.read.global` — because behavioural fingerprinting needs cross-workspace memory visibility. This is the spec's only built-in Privileged grant (§13.2).

**Files:**
- Modify: `nexus/modules/echo.py`
- Create: `tests/modules/test_echo_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the Echo module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.echo import EchoModule


def test_echo_manifest_loads():
    m = EchoModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "echo"
    assert m.system is True


def test_echo_declares_profile_intent():
    m = EchoModule.manifest()
    assert "PROFILE" in [i.name for i in m.intents]


def test_echo_intent_includes_signature_patterns():
    m = EchoModule.manifest()
    intent = next(i for i in m.intents if i.name == "PROFILE")
    text = "\n".join(intent.patterns)
    assert "fingerprint" in text
    assert "profile" in text


def test_echo_declares_engram_read_global_as_privileged():
    """Echo is the only built-in with a Privileged capability — cross-workspace memory read."""
    m = EchoModule.manifest()
    assert "engram.read.global" in m.capabilities.declared.privileged


def test_echo_runtime_is_in_process():
    m = EchoModule.manifest()
    assert m.runtime.transport == "in_process"
```

- [ ] **Step 2: Run the test; verify it fails**

```bash
pytest tests/modules/test_echo_manifest.py -v
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 3: Add `manifest()` to `nexus/modules/echo.py`**

Inside `EchoModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "echo",
            "name": "echo",
            "tagline": "Behavioural fingerprinting and social graph — knows how you think.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "user-modeling",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:echo",
                                  "gradient": ["#a8e8ff", "#346b9c"]}},
            "intents": [{
                "name": "PROFILE",
                "patterns": [
                    r"\bbehavioral\b", r"\bfingerprint\b", r"\bstyle\b.*\banalyz\w*\b",
                    r"\bprofile\b", r"\bwriting\s+style\b", r"\bwho\s+is\b",
                    r"\brelationship\b", r"\bsocial\s+graph\b", r"\bcontact\b",
                    r"\buser\s+model\w*\b", r"\becho\b", r"\bpersonalit\w*\b",
                ],
                "semantic_signals": [
                    "behavioral patterns", "fingerprint", "user profile", "writing style",
                    "who is", "relationships", "social graph", "contacts",
                    "user modeling", "personality", "how do I usually",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace"],
                    "Notable": [],
                    "Sensitive": [],
                    "Privileged": ["engram.read.global"],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.50, "default_tier": "MONITOR"},
        })
```

- [ ] **Step 4: Run the test**

```bash
pytest tests/modules/test_echo_manifest.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 753 passing (748 + 5 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/modules/echo.py tests/modules/test_echo_manifest.py
git commit -m "feat(echo): declare v1 manifest with Privileged engram.read.global"
```

---

## Task 6 · Migrate `agent_dispatcher` (slug "agents")

**Why:** The 10th intent (SUMMON) is owned by the agent dispatcher module. Its `name` class attribute is `"agents"` — so its manifest slug is `"agents"`.

**Files:**
- Modify: `nexus/modules/agent_dispatcher.py`
- Create: `tests/modules/test_agent_dispatcher_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the AgentDispatcher module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.agent_dispatcher import AgentDispatcherModule


def test_dispatcher_manifest_loads():
    m = AgentDispatcherModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "agents"
    assert m.system is True


def test_dispatcher_declares_summon_intent():
    m = AgentDispatcherModule.manifest()
    assert "SUMMON" in [i.name for i in m.intents]


def test_dispatcher_intent_includes_signature_patterns():
    m = AgentDispatcherModule.manifest()
    intent = next(i for i in m.intents if i.name == "SUMMON")
    text = "\n".join(intent.patterns)
    assert "summon" in text
    assert "launch" in text or "list" in text or "agent" in text


def test_dispatcher_declares_inter_agent_call_capability():
    """Dispatcher launches catalog agents — needs inter-agent dispatch capability."""
    m = AgentDispatcherModule.manifest()
    # Either Notable or Routine — the dispatcher's interactions are bounded to catalog operations
    assert (
        "inter_agent.call.*" in m.capabilities.declared.notable
        or "inter_agent.list" in m.capabilities.declared.routine
    )


def test_dispatcher_runtime_is_in_process():
    m = AgentDispatcherModule.manifest()
    assert m.runtime.transport == "in_process"
```

- [ ] **Step 2: Run the test; verify it fails**

```bash
pytest tests/modules/test_agent_dispatcher_manifest.py -v
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 3: Add `manifest()` to `nexus/modules/agent_dispatcher.py`**

Inside `AgentDispatcherModule`:

```python
    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "agents",
            "name": "agents",
            "tagline": "Console surface for browsing and summoning runnable agents.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "orchestration",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:agents",
                                  "gradient": ["#c8c8ff", "#3a3a8c"]}},
            "intents": [{
                "name": "SUMMON",
                "patterns": [
                    r"\bsummon\b", r"\blaunch\s+agent\b", r"\bstart\s+agent\b",
                    r"\bstop\s+agent\b", r"\bdismiss\s+agent\b", r"\bkill\s+agent\b",
                    r"\binvoke\s+agent\b", r"\blist\s+agents?\b", r"\bagent\s+catalog\b",
                    r"\brunning\s+agents?\b", r"\bonexus[- ]?agents?\b",
                    r"\bsearch\s+agents?\b", r"\bfind\s+agent\b",
                ],
                "semantic_signals": [
                    "summon", "launch agent", "start agent", "stop agent",
                    "list agents", "running agents", "agent catalog",
                    "find agent", "search agents", "invoke agent",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace", "inter_agent.list"],
                    "Notable": ["inter_agent.call.*", "process.spawn"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })
```

- [ ] **Step 4: Run the test**

```bash
pytest tests/modules/test_agent_dispatcher_manifest.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 758 passing (753 + 5 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/modules/agent_dispatcher.py tests/modules/test_agent_dispatcher_manifest.py
git commit -m "feat(agents): declare v1 manifest for agent_dispatcher (SUMMON intent, slug 'agents')"
```

---

## Task 7 · Refactor Cortex to read intents from manifests

**Why:** With all 10 manifests in place, Cortex can stop hardcoding `_INTENT_DEFS`. Instead it accepts a `BuiltinRegistry` at construction and builds its intent list from the registered manifests' `intents[]`.

This is the most delicate task — it changes a production code path that has existing tests. The goal is byte-identical routing behaviour: the same message that routes to `council` today must keep routing to `council` after the refactor.

**Files:**
- Modify: `nexus/kernel/cortex.py`
- Create: `tests/kernel/test_cortex_manifest_loading.py`

- [ ] **Step 1: Confirm baseline cortex behaviour**

Run the existing cortex tests and record the exact pass/fail count:

```bash
pytest tests/kernel/test_cortex.py -v 2>&1 | tail -10
```

Save the output. You will compare this exact set after the refactor.

- [ ] **Step 2: Write the new test**

`tests/kernel/test_cortex_manifest_loading.py`:

```python
"""Tests for Cortex loading intents from a manifest registry instead of hardcoded defs."""
from __future__ import annotations

import re
import pytest

from nexus.agents.manifest import Manifest
from nexus.agents.registry import BuiltinRegistry
from nexus.kernel.cortex import IntentClassifier
from nexus.modules.base import NexusModule


class _Stub(NexusModule):
    name = "stub"
    description = "stub"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "stub", "name": "stub", "version": "0.1.0",
            "system": True, "publisher": {"type": "org", "handle": "t"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:stub", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "FROBBLE",
                         "patterns": [r"\bfrobble\b", r"\bspecial-frob\b"],
                         "semantic_signals": ["please frobble"],
                         "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return ""


def test_classifier_loads_from_registry():
    """A classifier built from a registry sees the registry's intents."""
    reg = BuiltinRegistry.from_modules([_Stub])
    classifier = IntentClassifier.from_registry(reg)
    scored = classifier.classify("please frobble this for me")
    assert len(scored) >= 1
    assert scored[0].module == "stub"
    assert scored[0].name == "FROBBLE"


def test_classifier_from_registry_matches_default_behavior_for_council():
    """A classifier built from the default builtin registry routes 'should i...'
    to council, exactly like the hardcoded _INTENT_DEFS did."""
    from nexus.kernel.cortex import default_builtin_registry
    reg = default_builtin_registry()
    classifier = IntentClassifier.from_registry(reg)
    scored = classifier.classify("should i refactor the auth module?")
    assert scored[0].module == "council"
    assert scored[0].name == "DELIBERATE"


def test_classifier_from_registry_routes_specter():
    from nexus.kernel.cortex import default_builtin_registry
    classifier = IntentClassifier.from_registry(default_builtin_registry())
    scored = classifier.classify("stress test this design")
    assert scored[0].module == "specter"
    assert scored[0].name == "CHALLENGE"


def test_classifier_from_registry_routes_oracle():
    from nexus.kernel.cortex import default_builtin_registry
    classifier = IntentClassifier.from_registry(default_builtin_registry())
    scored = classifier.classify("monitor for threat patterns")
    assert scored[0].module == "oracle"


def test_classifier_default_constructor_still_works():
    """The no-arg constructor preserves backward compatibility by loading the default registry."""
    classifier = IntentClassifier()
    # The default classifier should know about council
    scored = classifier.classify("should i decide between these options?")
    modules = [s.module for s in scored]
    assert "council" in modules
```

- [ ] **Step 3: Run the new tests; verify they fail**

```bash
pytest tests/kernel/test_cortex_manifest_loading.py -v
```

Expected: `IntentClassifier.from_registry` and `default_builtin_registry` do not exist.

- [ ] **Step 4: Refactor `nexus/kernel/cortex.py`**

The strategy: keep `_INTENT_DEFS` as a private fallback (Phase 2 does not delete it yet — we will in Phase 3 once the registry boot is wired). Add:

1. A `default_builtin_registry()` function at the module level that imports the 10 module classes and builds a registry.
2. An `IntentClassifier.from_registry(registry)` classmethod.
3. An `_load_intents_from_registry(registry)` internal method.
4. The existing `IntentClassifier()` no-arg constructor now calls `from_registry(default_builtin_registry())` instead of `_load_intents()`.

Find the existing `IntentClassifier.__init__` and `_load_intents` methods. Replace them with the following (preserve every other method in the class — the scoring logic does not change):

```python
class IntentClassifier:
    """
    Semantic intent classification engine.
    Uses layered scoring: regex patterns, semantic phrase matching,
    structural analysis, and routing context to rank intents.
    """

    def __init__(self, intents: list[Intent] | None = None) -> None:
        self._intents: list[Intent] = []
        self._routing_history: deque[str] = deque(maxlen=5)
        if intents is not None:
            self._intents = list(intents)
        else:
            # Phase 2: default to loading from the built-in registry.
            try:
                registry = default_builtin_registry()
                self._intents = self._intents_from_registry(registry)
            except Exception:
                # Fallback to the legacy hardcoded defs if registry boot fails
                # (for example, when an existing test instantiates an Aegis-less classifier).
                self._load_intents_legacy()

    @classmethod
    def from_registry(cls, registry: "BuiltinRegistry") -> "IntentClassifier":
        instance = cls.__new__(cls)
        instance._intents = instance._intents_from_registry(registry)
        instance._routing_history = deque(maxlen=5)
        return instance

    # ── intent construction ──────────────────────────────────────────────

    def _intents_from_registry(self, registry: "BuiltinRegistry") -> list[Intent]:
        out: list[Intent] = []
        for manifest in registry.manifests():
            for intent_decl in manifest.intents:
                out.append(Intent(
                    name=intent_decl.name,
                    module=manifest.slug,
                    description=manifest.tagline,
                    patterns=_compile(intent_decl.patterns),
                    semantic_signals=list(intent_decl.semantic_signals),
                ))
        return out

    def _load_intents_legacy(self) -> None:
        """Fallback: build from the hardcoded `_INTENT_DEFS` (preserved during Phase 2)."""
        for defn in _INTENT_DEFS:
            self._intents.append(Intent(
                name=defn["name"],
                module=defn["module"],
                description=defn["description"],
                patterns=_compile(defn["patterns"]),
                semantic_signals=defn["semantic_signals"],
            ))
```

At the top of `cortex.py` add the import (TYPE_CHECKING-guarded to avoid circulars at module load):

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from nexus.agents.registry import BuiltinRegistry
```

At the bottom of the module (below the `IntentClassifier` class) add:

```python
def default_builtin_registry() -> "BuiltinRegistry":
    """Build the registry of the 10 built-in NexusModule classes.

    Lazy imports — these modules import the kernel transitively, so
    a module-level import here would create a circular dependency at
    `import nexus.kernel.cortex` time.
    """
    from nexus.agents.registry import BuiltinRegistry
    from nexus.modules.council import CouncilModule
    from nexus.modules.specter import SpecterModule
    from nexus.modules.autonomic import AutonomicModule
    from nexus.modules.oracle import OracleModule
    from nexus.modules.wraith import WraithModule
    from nexus.modules.legacy import LegacyModule
    from nexus.modules.consciousness import ConsciousnessModule
    from nexus.modules.sentry import SentryModule
    from nexus.modules.echo import EchoModule
    from nexus.modules.agent_dispatcher import AgentDispatcherModule

    return BuiltinRegistry.from_modules([
        CouncilModule, SpecterModule, AutonomicModule, OracleModule,
        WraithModule, LegacyModule, ConsciousnessModule, SentryModule,
        EchoModule, AgentDispatcherModule,
    ])
```

- [ ] **Step 5: Run the new tests**

```bash
pytest tests/kernel/test_cortex_manifest_loading.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run the existing cortex tests — they MUST all still pass**

```bash
pytest tests/kernel/test_cortex.py -v 2>&1 | tail -20
```

Expected: identical pass/fail breakdown to the Step 1 baseline. If anything regresses, STOP and investigate before continuing.

- [ ] **Step 7: Full regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 763 passing (758 + 5 new), 28 failed (baseline). If failures increased, the manifest-loading path broke an existing assumption — debug before moving on.

- [ ] **Step 8: Commit**

```bash
git add nexus/kernel/cortex.py tests/kernel/test_cortex_manifest_loading.py
git commit -m "refactor(cortex): load intents from BuiltinRegistry (manifest-driven)"
```

---

## Task 8 · Wire registry into kernel boot — Aegis sees built-ins

**Why:** Cortex now reads manifests, but Aegis still doesn't know about the built-ins. `register_manifest()` was never called for them. This task adds a boot helper that's called by the CLI startup paths.

**Files:**
- Modify: `nexus/kernel/cortex.py` (small — add `_register_builtins_with_aegis()` helper)
- Create: `tests/kernel/test_cortex_aegis_wiring.py`
- Modify: `nexus/cli.py` (small — call the helper in the kernel boot path)

- [ ] **Step 1: Write the failing test**

`tests/kernel/test_cortex_aegis_wiring.py`:

```python
"""Tests that built-in manifests get registered with Aegis at Cortex construction."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.config import NexusConfig


@pytest.fixture
def kernel(tmp_path):
    config = NexusConfig(data_dir=str(tmp_path))
    config.ensure_dirs()
    engram = Engram(str(tmp_path / "engram.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_builtin_manifests()
    return aegis


def test_council_manifest_is_registered_with_aegis(kernel):
    aegis = kernel
    assert aegis.get_manifest("council") is not None


def test_all_ten_builtins_register(kernel):
    aegis = kernel
    expected = ["council", "specter", "autonomic", "oracle", "wraith",
                "legacy", "consciousness", "sentry", "echo", "agents"]
    for slug in expected:
        assert aegis.get_manifest(slug) is not None, f"{slug} not registered"


def test_idempotent_registration(kernel):
    """Calling register_builtin_manifests twice is safe — second call is a no-op."""
    aegis = kernel
    # The fixture already called it once; calling again should not raise
    from nexus.kernel.cortex import default_builtin_registry
    default_builtin_registry().register_all(aegis)
    assert aegis.get_manifest("council") is not None
```

- [ ] **Step 2: Run the test; verify it fails**

```bash
pytest tests/kernel/test_cortex_aegis_wiring.py -v
```

Expected: `Cortex.register_builtin_manifests` does not exist.

- [ ] **Step 3: Add the helper to `nexus/kernel/cortex.py`**

Add this method to the `Cortex` class (placement: after `register_module`, before `_build_context`):

```python
    def register_builtin_manifests(self) -> None:
        """Register every built-in module's manifest with Aegis.

        Called once at kernel boot. Idempotent — registering the same
        manifest twice overwrites the dict entry but does not duplicate
        any DB rows (Aegis seeds trust only if the row is at 0.0).
        """
        registry = default_builtin_registry()
        registry.register_all(self._aegis)
        self._chronicle.log("cortex", "builtins_registered", {
            "slugs": registry.slugs(),
        })
```

- [ ] **Step 4: Wire it into the CLI boot path**

Open `nexus/cli.py`. Find the function (or functions) that construct the kernel and load modules — typically `_build_kernel()` or similar. Locate the point AFTER `Cortex(...)` is instantiated and BEFORE `cortex.initialize_modules()` is awaited.

Add this line:

```python
cortex.register_builtin_manifests()
```

If the CLI has multiple kernel-construction sites (e.g., `run`, `serve`, `tui`, `dashboard`), add the line in each. To find them:

```bash
grep -n "Cortex(" nexus/cli.py
```

For each match, inspect the surrounding ~10 lines and add the call after Cortex construction. Do NOT modify any other behaviour in the CLI.

- [ ] **Step 5: Run the test**

```bash
pytest tests/kernel/test_cortex_aegis_wiring.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Verify the CLI still boots**

```bash
python -c "from nexus.cli import main; print('cli imports')" 2>&1
```

Expected: `cli imports` printed; no exceptions.

If you have time and want extra confidence, run `onexus status` briefly (it doesn't take any input):

```bash
python -m nexus.cli status 2>&1 | head -5
```

Expected: succeeds without traceback (the actual output may say "no kernel yet" — that's fine).

- [ ] **Step 7: Full regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 766 passing (763 + 3 new), 28 failed (baseline).

- [ ] **Step 8: Commit**

```bash
git add nexus/kernel/cortex.py nexus/cli.py tests/kernel/test_cortex_aegis_wiring.py
git commit -m "feat(kernel): register built-in manifests with Aegis at boot"
```

---

## Task 9 · End-to-end routing smoke test (manifest-driven)

**Why:** Prove that the whole stack — manifest → registry → Cortex classifier → Aegis check_capability — is wired together and a real `cortex.process()` call still routes correctly with the new code path.

**Files:**
- Create: `tests/agents/test_phase_2_routing_smoke.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke test for Phase 2 — manifest-driven routing.

Builds a real kernel (Cortex + Aegis + Chronicle + Engram + Pulse),
registers built-in manifests, registers the real cognitive modules,
and verifies that messages route to the expected built-ins.
"""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.config import NexusConfig

from nexus.modules.council import CouncilModule
from nexus.modules.specter import SpecterModule
from nexus.modules.oracle import OracleModule


@pytest.fixture
async def kernel(tmp_path):
    config = NexusConfig(data_dir=str(tmp_path))
    config.ensure_dirs()
    engram = Engram(str(tmp_path / "engram.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_builtin_manifests()

    # Register the three modules we care about for routing
    council = CouncilModule()
    specter = SpecterModule()
    oracle = OracleModule()
    for m in (council, specter, oracle):
        cortex.register_module(m)
        aegis.set_policy(m.name, allowed=True, initial_trust=0.60)

    await cortex.initialize_modules()
    return cortex


@pytest.mark.asyncio
async def test_deliberate_query_routes_to_council(kernel):
    cortex = kernel
    response = await cortex.process("should i refactor the auth module?")
    # The response will be council's text. We assert routing via Chronicle.
    chronicle = cortex._chronicle
    routes = chronicle.list("cortex", "route", limit=10)
    assert any(r.data["target"] == "council" for r in routes)


@pytest.mark.asyncio
async def test_challenge_query_routes_to_specter(kernel):
    cortex = kernel
    await cortex.process("red team this design")
    chronicle = cortex._chronicle
    routes = chronicle.list("cortex", "route", limit=10)
    assert any(r.data["target"] == "specter" for r in routes)


@pytest.mark.asyncio
async def test_aegis_has_manifest_for_unregistered_module(kernel):
    """Even modules not yet `register_module()`'d still have manifests in Aegis."""
    cortex = kernel
    aegis = cortex._aegis
    # Echo wasn't register_module()'d in this fixture, but its manifest is registered
    assert aegis.get_manifest("echo") is not None
```

The Chronicle helper `chronicle.list(source, event, limit=N)` exists in the current code. If the signature is different, adapt: it may be `chronicle.recent()` or similar — inspect `nexus/kernel/chronicle.py` if the test fails on the API call.

- [ ] **Step 2: Run the test**

```bash
pytest tests/agents/test_phase_2_routing_smoke.py -v
```

Expected: 3 passed.

If a chronicle API mismatch surfaces, adapt the test to whatever the actual API is. The intent — "routing decision was logged" — is what matters.

- [ ] **Step 3: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 769 passing (766 + 3 new), 28 failed (baseline).

- [ ] **Step 4: Commit**

```bash
git add tests/agents/test_phase_2_routing_smoke.py
git commit -m "test(agents): end-to-end smoke for manifest-driven routing"
```

---

## Task 10 · Documentation + final regression + milestone tag

**Why:** Capture the new patterns and tag the milestone so Phase 3 can branch from a known-good point.

**Files:**
- Modify: `docs/agents/foundation.md` (add a "Phase 2 — Built-in Migration" section at the end)

- [ ] **Step 1: Update the foundation doc**

Append the following section to the bottom of `docs/agents/foundation.md`:

```markdown
---

## Phase 2 — Built-in Migration

All 10 built-in modules (the 9 cognitive modules + `agent_dispatcher`)
now ship with v1 manifests. Cortex's `IntentClassifier` reads intents
from a `BuiltinRegistry` (`nexus.agents.registry.BuiltinRegistry`) at
construction time, falling back to the legacy `_INTENT_DEFS` only when
the registry build fails.

### How a new built-in module joins the registry

1. Add `manifest()` classmethod to the module class:

   ```python
   class MyBuiltin(NexusModule):
       name = "my-builtin"
       description = "..."
       version = "0.1.0"

       @classmethod
       def manifest(cls):
           from nexus.agents.manifest import Manifest
           return Manifest.model_validate({...})

       async def handle(self, message, context):
           ...
   ```

2. Add the module class to `default_builtin_registry()` in
   `nexus/kernel/cortex.py`.

3. Done. Cortex picks up the new intents automatically; Aegis sees the
   manifest after `cortex.register_builtin_manifests()` runs at boot.

### Trust floors per built-in (current)

| Slug | Floor | Tier |
|---|---|---|
| council | 0.50 | MONITOR |
| legacy | 0.50 | MONITOR |
| echo | 0.50 | MONITOR |
| oracle | 0.40 | ADVISOR |
| specter | 0.40 | ADVISOR |
| consciousness | 0.40 | ADVISOR |
| sentry | 0.40 | ADVISOR |
| wraith | 0.35 | ADVISOR |
| autonomic | 0.30 | ADVISOR |
| agents | 0.30 | ADVISOR |

These are the trust scores Aegis seeds for each built-in on first
registration. They can be raised by `record_outcome(success=True)` or
lowered by `record_outcome(success=False)` over time, exactly like
catalog agents.
```

- [ ] **Step 2: Commit the docs**

```bash
git add docs/agents/foundation.md
git commit -m "docs(agents): Phase 2 — built-in migration"
```

- [ ] **Step 3: Verify regression baseline**

Compare the failing-test set to the Phase 1 baseline.

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | grep -E "^FAILED" | awk '{print $2}' | sort > /tmp/phase_2_failures.txt
diff .baseline_failures.txt /tmp/phase_2_failures.txt && echo "[FAILURE SET IDENTICAL TO BASELINE]"
```

Expected: `[FAILURE SET IDENTICAL TO BASELINE]`.

- [ ] **Step 4: Tag the milestone**

```bash
git tag -a phase-2-migration -m "Phase 2 migration complete: 10 built-ins on manifests, Cortex reads from registry

- All 9 cognitive modules + agent_dispatcher ship v1 manifests
- BuiltinRegistry discovers + registers them
- Cortex.IntentClassifier reads intents from manifests
- Aegis.register_manifest called for all 10 at kernel boot
- Existing routing behaviour preserved (test_cortex.py unchanged)
- 28 baseline failures + 65 collection errors unchanged

Final suite: 769 passing (703 → 769, +66 new tests)."
git log --oneline | head -15
```

- [ ] **Step 5: Push branch (if remote tracking is desired) — optional**

```bash
git push -u origin nexus-phase-2  # optional
git push origin phase-2-migration  # optional, sends the tag
```

Phase 2 is complete. Path to Phase 3 (workspaces) is unblocked.

---

## Self-Review (against the design spec)

**1. Spec coverage check**

| Spec section | Implementing task | Notes |
|---|---|---|
| §13.1 InProcessAgent shim (already from Phase 1) | — | Phase 1 task 8 |
| §13.2 Manifests for the 9 + dispatcher | Tasks 2–6 | All 10 manifests including Echo's Privileged engram.read.global |
| §13.3 cortex._INTENT_DEFS replaced by manifest-driven loading | Task 7 | Legacy defs kept as fallback during Phase 2; Phase 3 will delete |
| §4.1 Cortex reads manifest intents | Task 7 | classifier.from_registry + default_builtin_registry |
| Aegis.register_manifest called for built-ins at boot | Task 8 | cortex.register_builtin_manifests + CLI wiring |
| End-to-end routing still works | Task 9 | Smoke test against real kernel |

**2. Placeholder scan**

No "TBD" / "TODO" / "implement later" in this plan. The chronicle API call in Task 9 is the one place where the implementer may need to adapt to the actual signature — that contingency is documented inline.

**3. Type consistency**

`Manifest`, `BuiltinRegistry`, `IntentClassifier`, `default_builtin_registry`, `Cortex.register_builtin_manifests` — all spelled identically across the tasks where they appear. Module class names (`CouncilModule`, etc.) match what's in the existing codebase.

**4. Open issues for Phase 3**

- The legacy `_INTENT_DEFS` and `_load_intents_legacy()` fallback in Cortex are preserved during Phase 2 for safety. Phase 3 (workspaces) will delete them once we're confident every code path has switched to the registry.
- The CLI wiring in Task 8 modifies one or more `Cortex(` construction sites; if there are >3 sites or any are non-obvious, consider extracting a `boot_kernel(config)` helper in Phase 3.

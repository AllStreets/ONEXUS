# NEXUS Phase 3 — Workspace Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the workspace layer atop the Phase 1+2 foundation. After this phase, every workspace has typed persisted state (`workspace.json`), a room manager, Engram partitioning, a SQLite-backed grants store, six templates, a mood engine, a process supervisor, and workspace-aware Cortex routing.

**Baseline:** 769 passing tests (Phase 2 complete).

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — sections 7 (Workspace System), 8 (Routing), 11 (Mood Atlas).

---

## Task 1 · WorkspaceConfig pydantic model

**Why:** Every workspace's persisted state lives in `workspace.json`. This task defines the typed schema for that file, including validation, convenience helpers, and serialization. Nothing writes the file yet — that's Task 2 (WorkspaceManager).

**Files:**
- Create: `nexus/workspaces/__init__.py` (empty)
- Create: `nexus/workspaces/config.py`
- Create: `tests/workspaces/__init__.py` (empty)
- Create: `tests/workspaces/test_config.py`

### Step 1: Write the failing tests

Create `tests/workspaces/test_config.py`:

```python
"""Tests for WorkspaceConfig — the pydantic model for workspace.json."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone, RoutingPin


def _valid_config_dict() -> dict:
    return {
        "schema_version": 1,
        "workspace_id": "client-work-7b3a",
        "name": "Client Work",
        "tone": "INDIGO",
        "roots": ["/Users/alice/client-project"],
        "resident_agents": ["aider", "council"],
        "routing_pins": [
            {"intent": "CODE", "agent": "aider"},
        ],
        "mood_biases": {},
        "created_at": "2026-06-07T00:00:00Z",
        "last_active_at": "2026-06-07T00:00:00Z",
    }


def test_valid_config_loads():
    cfg = WorkspaceConfig.model_validate(_valid_config_dict())
    assert cfg.workspace_id == "client-work-7b3a"
    assert cfg.tone is WorkspaceTone.INDIGO
    assert len(cfg.resident_agents) == 2


def test_workspace_id_must_be_kebab_case():
    d = _valid_config_dict()
    d["workspace_id"] = "Bad ID"
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_schema_version_must_be_1():
    d = _valid_config_dict()
    d["schema_version"] = 2
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_routing_pin_requires_exactly_one_of_intent_or_category():
    d = _valid_config_dict()
    # Both set — should fail
    d["routing_pins"] = [{"intent": "CODE", "category": "coding", "agent": "aider"}]
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_routing_pin_with_only_category():
    d = _valid_config_dict()
    d["routing_pins"] = [{"category": "coding", "agent": "council"}]
    cfg = WorkspaceConfig.model_validate(d)
    pin = cfg.routing_pins[0]
    assert pin.category == "coding"
    assert pin.intent is None


def test_resolved_roots_returns_paths(tmp_path):
    d = _valid_config_dict()
    d["roots"] = [str(tmp_path)]
    cfg = WorkspaceConfig.model_validate(d)
    roots = cfg.resolved_roots()
    assert roots[0] == tmp_path.resolve()


def test_pin_for_intent_lookup():
    d = _valid_config_dict()
    d["routing_pins"] = [
        {"intent": "CODE", "agent": "aider"},
        {"category": "research", "agent": "council"},
    ]
    cfg = WorkspaceConfig.model_validate(d)
    assert cfg.pin_for_intent("CODE") == "aider"
    assert cfg.pin_for_intent("MISSING") is None
    assert cfg.pin_for_category("research") == "council"
```

### Step 2: Run tests to confirm ImportError

```bash
pytest tests/workspaces/test_config.py -v
```

Expected: ImportError — `nexus.workspaces.config` does not exist yet.

### Step 3: Implement `nexus/workspaces/config.py`

Create `nexus/workspaces/__init__.py` (empty), then create `nexus/workspaces/config.py`:

```python
"""
WorkspaceConfig — the pydantic model for workspace.json.

Every workspace persists its state to workspace.json using this schema.
Covers: filesystem roots, resident agents, routing pins, home tone,
mood biases, and timestamps.

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7.
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WorkspaceTone(str, Enum):
    INDIGO = "INDIGO"
    MAGENTA = "MAGENTA"
    SAGE = "SAGE"
    PLUM = "PLUM"
    AMBER = "AMBER"


class RoutingPin(BaseModel):
    """Maps one intent OR one category to a preferred agent slug.

    Exactly one of ``intent`` or ``category`` must be provided.
    """
    model_config = ConfigDict(extra="forbid")

    intent: str | None = None
    category: str | None = None
    agent: str

    @model_validator(mode="after")
    def _exactly_one_key(self) -> "RoutingPin":
        has_intent = self.intent is not None
        has_category = self.category is not None
        if has_intent == has_category:  # both set or neither set
            raise ValueError(
                "RoutingPin must specify exactly one of 'intent' or 'category', "
                f"got intent={self.intent!r}, category={self.category!r}"
            )
        return self


class WorkspaceConfig(BaseModel):
    """The persisted configuration for a single workspace (workspace.json)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    workspace_id: str
    name: str
    tone: WorkspaceTone = WorkspaceTone.INDIGO
    roots: list[str] = Field(default_factory=list)
    resident_agents: list[str] = Field(default_factory=list)
    routing_pins: list[RoutingPin] = Field(default_factory=list)
    mood_biases: dict[str, float] = Field(default_factory=dict)
    created_at: str = ""
    last_active_at: str = ""

    # ── validators ────────────────────────────────────────────────────────

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id_kebab(cls, v: str) -> str:
        if not _WORKSPACE_ID_RE.match(v):
            raise ValueError(
                f"workspace_id must be kebab-case, start with a lowercase letter, "
                f"and be 1–64 chars; got {v!r}"
            )
        return v

    # ── convenience helpers ───────────────────────────────────────────────

    def resolved_roots(self) -> list[Path]:
        """Return filesystem roots as resolved Path objects."""
        return [Path(r).resolve() for r in self.roots]

    def pin_for_intent(self, intent: str) -> str | None:
        """Return the preferred agent slug for a given intent, or None."""
        for pin in self.routing_pins:
            if pin.intent == intent:
                return pin.agent
        return None

    def pin_for_category(self, category: str) -> str | None:
        """Return the preferred agent slug for a given category, or None."""
        for pin in self.routing_pins:
            if pin.category == category:
                return pin.agent
        return None
```

### Step 4: Run the new tests

```bash
pytest tests/workspaces/test_config.py -v
```

Expected: 7 passed.

### Step 5: Regression check

```bash
pytest --continue-on-collection-errors --tb=no -q
```

Expected: ≥ 776 passing (769 + 7 new).

### Step 6: Commit

```bash
git add nexus/workspaces/__init__.py nexus/workspaces/config.py \
        tests/workspaces/__init__.py tests/workspaces/test_config.py
git commit -m "feat(workspaces): add WorkspaceConfig pydantic model with RoutingPin"
```

---

## Task 2 · WorkspaceManager

**Status: DONE** — commit `160984e`

`nexus/workspaces/manager.py` — CRUD + active pointer.
Storage: `<root>/.active` + `<root>/<id>/workspace.json`.
8 tests in `tests/workspaces/test_manager.py`.

---

## Task 3 · Engram.partition()

**Status: DONE** — commit `3360c39`

`Engram.partition(workspace_root)` added to `nexus/kernel/engram.py`.
Creates `<ws_root>/engram/episodic.sqlite` — fully isolated per workspace.
6 tests in `tests/workspaces/test_engram_partition.py`.

---

## Task 4 · SQLite-backed grants store

**Status: DONE** — commit `cdc3877`

`nexus/workspaces/grants.py` — `GrantsStore` with grant/revoke/has/list.
Unique constraint on (agent_slug, capability, scope). Idempotent grant().
11 tests in `tests/workspaces/test_grants.py`.

---

## Task 5 · Six built-in workspace templates

**Status: DONE** — commit `c7c04af`

`nexus/workspaces/templates.py` — `TEMPLATES` dict + `apply_template()`.
Templates: coding/INDIGO, design/MAGENTA, research/SAGE, writing/PLUM,
personal/AMBER, blank. 14 tests in `tests/workspaces/test_templates.py`.

---

## Task 6 · MoodEngine

**Status: DONE** — commit `b71a87f`

`nexus/workspaces/mood.py` — `MoodEngine.evaluate(MoodSignals) → MoodResult`.
8 mood states (Alert > Watchful > Routing > Creative > Deliberating > Reflective
> Deep Flow > Calm Focus). 3 trust overlays. Tone-to-CSS gradient hints.
24 tests in `tests/workspaces/test_mood.py`.

---

## Task 7 · WorkspaceRuntime (process supervisor)

**Status: DONE** — commit `0f3d3af`

`nexus/workspaces/runtime.py` — `WorkspaceRuntime` with register_external/
register_module, activate() SIGCONT/flag-clear, deactivate() SIGSTOP/flag-set,
stop_all() terminate. 15 tests in `tests/workspaces/test_runtime.py`.

---

## Task 8 · Cortex pin resolution

**Status: DONE** — commit `c39c55e`

`Cortex.set_workspace_config(WorkspaceConfig)` loads routing pins.
Pin check happens before semantic scoring; falls through if agent unloaded.
7 tests in `tests/workspaces/test_cortex_pins.py`.

---

## Task 9 · CLI workspace commands

**Status: DONE** — commit `c8c6978`

`onexus workspace list/create/switch/destroy` added to `nexus/cli.py`.
create supports --name/--id/--tone/--template. list marks active with *.
11 CLI tests in `tests/workspaces/test_cli_workspace.py`.

---

## Task 10 · End-to-end smoke test

**Status: DONE** — commit `1d57691`

`tests/workspaces/test_e2e_smoke.py` — single test exercises all 8 subsystems:
template → Engram partition → GrantsStore → Runtime pause/wake → Cortex pins
→ MoodEngine → destroy. 1 test, all layers wired.

---

## Task 11 · Docs + tag phase-3

**Status: DONE** — plan updated, phase-3 tag pushed.

**Final test count:** 873 passing (784 baseline + 89 new workspace-layer tests).
Zero regressions. 28 pre-existing failures unchanged (aegis attribute errors,
legacy integration failures — unrelated to workspace layer).

**New modules delivered:**
- `nexus/workspaces/manager.py`
- `nexus/workspaces/grants.py`
- `nexus/workspaces/templates.py`
- `nexus/workspaces/mood.py`
- `nexus/workspaces/runtime.py`
- `nexus/kernel/engram.py` (partition() added)
- `nexus/kernel/cortex.py` (set_workspace_config() + pin resolution added)
- `nexus/cli.py` (workspace group added)

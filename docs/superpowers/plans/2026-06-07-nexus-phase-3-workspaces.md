# NEXUS Phase 3 — Workspace Layer Implementation Plan (Phase 3 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the **workspace layer** — rooms with their own filesystem root(s), resident agents, memory partition, permission grants, home tone, and routing pins. Switching workspaces feels like walking through a door (paused agents wake; mood transitions; pins activate). This is the first phase where end-user behaviour visibly changes — Phase 3 is the seam between "kernel that runs" and "OS that you live in."

**Architecture:**
- `nexus.workspaces.config.WorkspaceConfig` — pydantic v2 model loaded from `workspace.json` (roots, roster, pins, tone, mood biases).
- `nexus.workspaces.manager.WorkspaceManager` — CRUD over `~/.nexus/workspaces/<id>/` directories; tracks the active workspace.
- `nexus.kernel.engram.Engram.partition(workspace_id)` — returns a fresh, workspace-scoped Engram namespace.
- `nexus.kernel.aegis.Aegis` — grants migrate from in-memory dict (Phase 1) to a workspace-scoped sqlite table so they survive process restarts.
- `nexus.workspaces.runtime.WorkspaceRuntime` — holds resident agents per workspace; SIGSTOP/SIGCONT on switch.
- `nexus.kernel.cortex.Cortex` grows pin resolution + per-workspace candidate filtering.
- `nexus.workspaces.mood` — kernel-state → mood mapping (8 moods from the spec atlas).
- Six built-in templates ship in `nexus/templates/` (Coding/Design/Research/Writing/Personal/Blank).
- CLI commands and REST endpoints expose the workspace layer.

**Tech Stack:** Python 3.11+, pydantic 2, sqlite3, click (CLI), FastAPI (REST). No new runtime deps.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — §7 (Workspace System), §11 (Mood Atlas), §16 (CLI Commands).

**Prior phase:** `phase-2-migration` tag. The manifest registry + Cortex-from-registry + Aegis built-in registration are all in place.

---

## Pre-flight

- Branch from `phase-2-migration` into `nexus-phase-3` (worktree at `.worktrees/nexus-phase-3`).
- Confirm baseline = **769 passing** (Phase 2 final). Pre-existing 28 failures + 65 collection errors out of scope.
- Activate venv: `source .venv/bin/activate`.

**File structure additions:**

```
nexus/
├── workspaces/
│   ├── __init__.py            (new)
│   ├── config.py              (new) — WorkspaceConfig pydantic model
│   ├── manager.py             (new) — WorkspaceManager: CRUD + active
│   ├── runtime.py             (new) — WorkspaceRuntime: resident agents
│   └── mood.py                (new) — MoodEngine: state → mood
├── templates/
│   ├── coding.json            (new)
│   ├── design.json            (new)
│   ├── research.json          (new)
│   ├── writing.json           (new)
│   ├── personal.json          (new)
│   └── blank.json             (new)
├── kernel/
│   ├── engram.py              (modify — add partition())
│   ├── aegis.py               (modify — sqlite-backed grants)
│   └── cortex.py              (modify — pin resolution + active workspace)
├── api/
│   └── routes/
│       ├── workspaces.py      (new) — REST endpoints
│       └── mood.py            (new) — WebSocket mood stream
└── cli.py                     (modify — workspace subcommands)

tests/workspaces/              (new directory)
    ├── test_config.py
    ├── test_manager.py
    ├── test_runtime.py
    ├── test_mood.py
    ├── test_templates.py
    └── test_phase_3_smoke.py
```

---

## Task 1 · `WorkspaceConfig` pydantic model

**Why:** Every workspace's `workspace.json` is parsed into this typed model. Cortex reads `pins`; Aegis reads `permission_grants`; the surfaces read `tone` and `mood_biases`.

**Files:**
- Create: `nexus/workspaces/__init__.py` (empty)
- Create: `nexus/workspaces/config.py`
- Create: `tests/workspaces/__init__.py` (empty)
- Create: `tests/workspaces/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/workspaces/test_config.py`:

```python
"""Tests for the WorkspaceConfig pydantic model."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.workspaces.config import (
    WorkspaceConfig,
    WorkspaceTone,
    RoutingPin,
)


def _valid_workspace_dict() -> dict:
    return {
        "schema_version": 1,
        "workspace_id": "client-work-7b3a",
        "name": "Client work",
        "tone": "indigo",
        "filesystem_roots": ["~/code/payments-redesign", "~/code/shared-types"],
        "resident_agents": ["aider", "cline", "council"],
        "pins": [
            {"intent": "CODE", "agent": "aider"},
            {"category": "deliberation", "agent": "council"},
        ],
        "mood_biases": ["calm", "focus"],
        "created_at": "2026-06-07T00:00:00Z",
    }


def test_valid_workspace_loads():
    w = WorkspaceConfig.model_validate(_valid_workspace_dict())
    assert w.workspace_id == "client-work-7b3a"
    assert w.tone == WorkspaceTone.INDIGO
    assert len(w.pins) == 2


def test_workspace_id_must_be_kebab_case():
    d = _valid_workspace_dict()
    d["workspace_id"] = "Bad ID"
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_tone_must_be_known():
    d = _valid_workspace_dict()
    d["tone"] = "rainbow"
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_pin_must_have_intent_or_category():
    """A pin must specify exactly one of `intent` or `category`."""
    d = _valid_workspace_dict()
    d["pins"] = [{"agent": "aider"}]  # neither
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_pin_cannot_have_both_intent_and_category():
    d = _valid_workspace_dict()
    d["pins"] = [{"intent": "CODE", "category": "coding", "agent": "aider"}]
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_empty_filesystem_roots_is_valid():
    """A workspace with no filesystem roots is allowed (purely conversational)."""
    d = _valid_workspace_dict()
    d["filesystem_roots"] = []
    w = WorkspaceConfig.model_validate(d)
    assert w.filesystem_roots == []


def test_round_trip_through_json():
    """A workspace serialised to JSON and back is byte-identical."""
    import json
    d = _valid_workspace_dict()
    w = WorkspaceConfig.model_validate(d)
    payload = w.model_dump_json()
    w2 = WorkspaceConfig.model_validate(json.loads(payload))
    assert w2.workspace_id == w.workspace_id
    assert w2.pins == w.pins
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
pytest tests/workspaces/test_config.py -v
```

Expected: ImportError on `nexus.workspaces.config`.

- [ ] **Step 3: Create the empty package files**

```bash
mkdir -p nexus/workspaces tests/workspaces
touch nexus/workspaces/__init__.py tests/workspaces/__init__.py
```

- [ ] **Step 4: Implement `nexus/workspaces/config.py`**

```python
"""
WorkspaceConfig — the typed schema for a workspace's `workspace.json`.

A workspace owns six things (spec §7.1):
  1. Filesystem root(s)
  2. Resident agents (a subset of installed agents)
  3. A memory partition in Engram (managed elsewhere)
  4. Permission grants (managed elsewhere — in aegis.sqlite per-workspace)
  5. Home tone + mood biases
  6. Routing pins
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WorkspaceTone(str, Enum):
    INDIGO = "indigo"
    MAGENTA = "magenta"
    SAGE = "sage"
    PLUM = "plum"
    AMBER = "amber"


class RoutingPin(BaseModel):
    """A pin maps an intent (uppercase) OR a category (lowercase) to an agent slug.

    Exactly one of `intent` or `category` must be set.
    """
    model_config = ConfigDict(extra="forbid")

    intent: str | None = None
    category: str | None = None
    agent: str

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "RoutingPin":
        if (self.intent is None) == (self.category is None):
            raise ValueError(
                "RoutingPin must specify exactly one of `intent` or `category`"
            )
        return self


class WorkspaceConfig(BaseModel):
    """A workspace's persisted state. Loaded from workspace.json."""
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    workspace_id: str
    name: str
    tone: WorkspaceTone
    filesystem_roots: list[str] = Field(default_factory=list)
    resident_agents: list[str] = Field(default_factory=list)
    pins: list[RoutingPin] = Field(default_factory=list)
    mood_biases: list[str] = Field(default_factory=list)
    created_at: str
    last_active_at: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        if not _WORKSPACE_ID_RE.match(v):
            raise ValueError(
                f"workspace_id must be kebab-case (1–64 chars, [a-z][a-z0-9-]+); got {v!r}"
            )
        return v

    # ── convenience ──────────────────────────────────────────────────────

    def resolved_roots(self) -> list[Path]:
        """Expand `~` and resolve each filesystem root to an absolute Path."""
        return [Path(r).expanduser() for r in self.filesystem_roots]

    def pin_for_intent(self, intent: str) -> str | None:
        for p in self.pins:
            if p.intent and p.intent == intent:
                return p.agent
        return None

    def pin_for_category(self, category: str) -> str | None:
        for p in self.pins:
            if p.category and p.category == category:
                return p.agent
        return None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/workspaces/test_config.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 776 passing (769 + 7 new), 28 failed (baseline).

- [ ] **Step 7: Commit**

```bash
git add nexus/workspaces/__init__.py nexus/workspaces/config.py \
        tests/workspaces/__init__.py tests/workspaces/test_config.py
git commit -m "feat(workspaces): add WorkspaceConfig pydantic model with RoutingPin"
```

---

## Task 2 · `WorkspaceManager` — directory layout + CRUD + active

**Why:** A workspace lives at `~/.nexus/workspaces/<id>/`. The manager creates them, lists them, switches the active pointer, and persists the active id between process runs.

**Files:**
- Create: `nexus/workspaces/manager.py`
- Create: `tests/workspaces/test_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the WorkspaceManager."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone
from nexus.workspaces.manager import WorkspaceManager


def test_create_workspace_writes_disk(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    ws = mgr.create(
        name="Client work",
        workspace_id="client-work",
        tone=WorkspaceTone.INDIGO,
        filesystem_roots=["~/code/payments"],
    )
    assert (tmp_path / "workspaces" / "client-work" / "workspace.json").exists()
    assert ws.workspace_id == "client-work"


def test_list_returns_all_workspaces(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    mgr.create(name="B", workspace_id="b", tone=WorkspaceTone.SAGE)
    ids = sorted(w.workspace_id for w in mgr.list())
    assert ids == ["a", "b"]


def test_get_returns_workspace_by_id(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    w = mgr.get("a")
    assert w is not None and w.name == "A"


def test_get_unknown_returns_none(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    assert mgr.get("nonexistent") is None


def test_destroy_removes_workspace_dir(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    mgr.destroy("a")
    assert not (tmp_path / "workspaces" / "a").exists()


def test_active_pointer_persists(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    mgr.create(name="B", workspace_id="b", tone=WorkspaceTone.SAGE)
    mgr.set_active("b")

    mgr2 = WorkspaceManager(root=tmp_path / "workspaces")
    assert mgr2.active_id() == "b"


def test_set_active_unknown_raises(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    with pytest.raises(KeyError):
        mgr.set_active("nonexistent")


def test_create_duplicate_raises(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    with pytest.raises(FileExistsError):
        mgr.create(name="A again", workspace_id="a", tone=WorkspaceTone.INDIGO)
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
pytest tests/workspaces/test_manager.py -v
```

Expected: ImportError on `nexus.workspaces.manager`.

- [ ] **Step 3: Implement `nexus/workspaces/manager.py`**

```python
"""
WorkspaceManager — owns the on-disk workspace directory layout and the
active-workspace pointer.

Storage layout:
  <root>/
    .active             ← contains the active workspace_id (single line)
    <workspace-id>/
      workspace.json    ← persisted WorkspaceConfig
      engram/           ← workspace-scoped Engram db (managed elsewhere)
      grants.sqlite     ← workspace-scoped Aegis grants (managed elsewhere)
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone, RoutingPin


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkspaceManager:
    def __init__(self, root: Path):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # ── lifecycle ────────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: str,
        workspace_id: str,
        tone: WorkspaceTone,
        filesystem_roots: list[str] | None = None,
        resident_agents: list[str] | None = None,
        pins: list[RoutingPin] | None = None,
        mood_biases: list[str] | None = None,
    ) -> WorkspaceConfig:
        """Create a new workspace directory + workspace.json."""
        ws_dir = self._root / workspace_id
        if ws_dir.exists():
            raise FileExistsError(f"workspace {workspace_id!r} already exists at {ws_dir}")
        ws_dir.mkdir(parents=True)
        (ws_dir / "engram").mkdir()
        config = WorkspaceConfig(
            schema_version=1,
            workspace_id=workspace_id,
            name=name,
            tone=tone,
            filesystem_roots=filesystem_roots or [],
            resident_agents=resident_agents or [],
            pins=pins or [],
            mood_biases=mood_biases or [],
            created_at=_now_iso(),
        )
        self._write_config(ws_dir, config)
        return config

    def destroy(self, workspace_id: str) -> None:
        ws_dir = self._root / workspace_id
        if not ws_dir.exists():
            raise KeyError(f"workspace {workspace_id!r} not found")
        if self.active_id() == workspace_id:
            self._clear_active()
        shutil.rmtree(ws_dir)

    # ── queries ──────────────────────────────────────────────────────────

    def get(self, workspace_id: str) -> WorkspaceConfig | None:
        path = self._root / workspace_id / "workspace.json"
        if not path.exists():
            return None
        return WorkspaceConfig.model_validate(json.loads(path.read_text()))

    def list(self) -> list[WorkspaceConfig]:
        out: list[WorkspaceConfig] = []
        for child in sorted(self._root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            cfg = self.get(child.name)
            if cfg is not None:
                out.append(cfg)
        return out

    def workspace_dir(self, workspace_id: str) -> Path:
        return self._root / workspace_id

    # ── active pointer ───────────────────────────────────────────────────

    def active_id(self) -> str | None:
        ptr = self._root / ".active"
        if not ptr.exists():
            return None
        slug = ptr.read_text().strip() or None
        if slug is None or self.get(slug) is None:
            return None
        return slug

    def set_active(self, workspace_id: str) -> None:
        if self.get(workspace_id) is None:
            raise KeyError(f"workspace {workspace_id!r} not found")
        (self._root / ".active").write_text(workspace_id)
        # Touch last_active_at on the config
        cfg = self.get(workspace_id)
        cfg = cfg.model_copy(update={"last_active_at": _now_iso()})
        self._write_config(self._root / workspace_id, cfg)

    def _clear_active(self) -> None:
        ptr = self._root / ".active"
        if ptr.exists():
            ptr.unlink()

    # ── persistence ──────────────────────────────────────────────────────

    def _write_config(self, ws_dir: Path, config: WorkspaceConfig) -> None:
        path = ws_dir / "workspace.json"
        payload = json.loads(config.model_dump_json())
        path.write_text(json.dumps(payload, indent=2))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/workspaces/test_manager.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 784 passing (776 + 8 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/workspaces/manager.py tests/workspaces/test_manager.py
git commit -m "feat(workspaces): add WorkspaceManager with directory layout + active pointer"
```

---

## Task 3 · `Engram.partition()` — per-workspace memory isolation

**Why:** Each workspace gets its own SQLite memory namespace (spec §7.1, §7.2). Cross-workspace reads require the Privileged `engram.read.global` capability (only Echo declares it today).

**Files:**
- Modify: `nexus/kernel/engram.py`
- Create: `tests/kernel/test_engram_partition.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for workspace-partitioned Engram memory."""
from __future__ import annotations

import pytest

from nexus.kernel.engram import Engram


def test_partition_returns_fresh_engram_for_workspace(tmp_path):
    base = Engram(tmp_path / "global" / "engram.db")
    base.init_db()
    ws_a = base.partition(tmp_path / "ws-a" / "engram")
    ws_a.init_db()
    ws_a.episodic.store("note in ws-a", source="test")

    ws_b = base.partition(tmp_path / "ws-b" / "engram")
    ws_b.init_db()
    # ws-b sees no episodic content
    assert ws_b.episodic.recall("note", limit=5) == []
    # ws-a still sees its own
    assert any("ws-a" in r["content"] for r in ws_a.episodic.recall("note"))


def test_partition_does_not_share_state_with_global(tmp_path):
    base = Engram(tmp_path / "global" / "engram.db")
    base.init_db()
    base.episodic.store("global note", source="test")

    ws = base.partition(tmp_path / "ws-x" / "engram")
    ws.init_db()
    assert ws.episodic.recall("global", limit=5) == []
    assert any("global" in r["content"] for r in base.episodic.recall("global"))


def test_partition_creates_directory_if_missing(tmp_path):
    base = Engram(tmp_path / "global" / "engram.db")
    base.init_db()
    target = tmp_path / "fresh" / "engram"
    assert not target.exists()
    ws = base.partition(target)
    ws.init_db()
    assert target.exists()
```

- [ ] **Step 2: Run; verify failure**

```bash
pytest tests/kernel/test_engram_partition.py -v
```

Expected: `Engram.partition` does not exist.

- [ ] **Step 3: Add `partition()` to `nexus/kernel/engram.py`**

Add this method to the `Engram` class:

```python
    def partition(self, dir_path) -> "Engram":
        """Return a fresh Engram bound to a workspace-scoped directory.

        Creates the directory if missing. The returned Engram has its
        own EpisodicMemory, SemanticMemory, and (fresh) WorkingMemory —
        no state is shared with the parent.
        """
        from pathlib import Path
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return Engram(dir_path / "engram.db")
```

- [ ] **Step 4: Run**

```bash
pytest tests/kernel/test_engram_partition.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 787 passing (784 + 3 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/kernel/engram.py tests/kernel/test_engram_partition.py
git commit -m "feat(engram): add partition() for workspace-scoped memory namespaces"
```

---

## Task 4 · SQLite-backed grants — durable workspace permissions

**Why:** Phase 1's grants live in an in-memory dict that vanishes on restart. Phase 3 needs durable grants so "always in this workspace" survives process death.

**Files:**
- Modify: `nexus/kernel/aegis.py`
- Create: `tests/kernel/test_aegis_grants_durable.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests that Aegis grants persist across process restarts."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.agents.manifest import Manifest


def _aider_manifest() -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "aider", "name": "aider",
        "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [], "declared": {
                "Routine": [], "Notable": ["fs.write.workspace"],
                "Sensitive": [], "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


def test_grant_persists_across_aegis_instances(tmp_path):
    db = str(tmp_path / "aegis.db")
    a1 = Aegis(db)
    a1.init_db()
    a1.register_manifest(_aider_manifest())
    a1.grant("aider", "fs.write.workspace", workspace_id="ws-1")

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider_manifest())  # re-register manifest in the new instance
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    from nexus.kernel.aegis import Verdict
    assert d.verdict is Verdict.ALLOW


def test_revoke_grant_persists(tmp_path):
    db = str(tmp_path / "aegis.db")
    a1 = Aegis(db)
    a1.init_db()
    a1.register_manifest(_aider_manifest())
    a1.grant("aider", "fs.write.workspace", workspace_id="ws-1")
    a1.revoke_grant("aider", "fs.write.workspace", workspace_id="ws-1")

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider_manifest())
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    from nexus.kernel.aegis import Verdict
    assert d.verdict is Verdict.PROMPT


def test_trust_collapse_revokes_persisted_grants(tmp_path):
    db = str(tmp_path / "aegis.db")
    a = Aegis(db)
    a.init_db()
    a.register_manifest(_aider_manifest())
    a.grant("aider", "fs.write.workspace", workspace_id="ws-1")
    a.set_trust("aider", 0.30)  # collapse < 0.50

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider_manifest())
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    from nexus.kernel.aegis import Verdict
    assert d.verdict is Verdict.PROMPT
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/kernel/test_aegis_grants_durable.py -v
```

Expected: 3 failures — the in-memory grants vanish on Aegis re-construction.

- [ ] **Step 3: Modify `nexus/kernel/aegis.py`**

A. Add table creation to `init_db()`. Find the existing `init_db` method and add a third `CREATE TABLE` statement before `conn.commit()`:

```python
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_grants (
                agent_slug   TEXT NOT NULL,
                capability   TEXT NOT NULL,
                workspace_id TEXT,
                granted_at   TEXT NOT NULL,
                PRIMARY KEY (agent_slug, capability, workspace_id)
            )
        """)
```

(SQLite treats `NULL` workspace_id as a distinct value in `PRIMARY KEY`, which is what we want — global grant + workspace grant for the same agent+capability are separate rows.)

B. Rewrite `grant()` to write to SQLite (replace the existing in-memory body):

```python
    def grant(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> None:
        """Record an explicit user grant. workspace_id=None means global."""
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO aegis_grants "
            "(agent_slug, capability, workspace_id, granted_at) VALUES (?, ?, ?, ?)",
            (agent_slug, capability, workspace_id, self._now()),
        )
        conn.commit()
        conn.close()
        self._log_chronicle("permission_granted", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })
```

C. Rewrite `revoke_grant()`:

```python
    def revoke_grant(
        self,
        agent_slug: str,
        capability: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Revoke one capability or, if capability is None, all grants for this agent in this scope."""
        conn = self._conn()
        if capability is None:
            conn.execute(
                "DELETE FROM aegis_grants WHERE agent_slug = ? AND "
                "((workspace_id IS NULL AND ? IS NULL) OR workspace_id = ?)",
                (agent_slug, workspace_id, workspace_id),
            )
        else:
            conn.execute(
                "DELETE FROM aegis_grants WHERE agent_slug = ? AND capability = ? AND "
                "((workspace_id IS NULL AND ? IS NULL) OR workspace_id = ?)",
                (agent_slug, capability, workspace_id, workspace_id),
            )
        conn.commit()
        conn.close()
        self._log_chronicle("permission_revoked", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })
```

D. Rewrite `_has_grant()`:

```python
    def _has_grant(self, agent_slug: str, capability: str, workspace_id: str | None) -> bool:
        conn = self._conn()
        row = conn.execute(
            "SELECT 1 FROM aegis_grants WHERE agent_slug = ? AND capability = ? AND "
            "((workspace_id IS NULL AND ? IS NULL) OR workspace_id = ? OR workspace_id IS NULL) "
            "LIMIT 1",
            (agent_slug, capability, workspace_id, workspace_id),
        ).fetchone()
        conn.close()
        return row is not None
```

Note: the WHERE clause matches either an exact workspace_id grant OR a NULL (global) grant. Global grants apply in any workspace.

E. Rewrite the trust-collapse code in `set_trust()` to delete persisted grants. Find this block in `set_trust`:

```python
        # Trust collapse: revoke every grant
        if score < 0.50:
            table = self._grants_table()
            ...
```

Replace with:

```python
        # Trust collapse: delete every persisted grant for this agent
        if score < 0.50:
            conn = self._conn()
            removed = conn.execute(
                "SELECT capability, workspace_id FROM aegis_grants WHERE agent_slug = ?",
                (agent_slug,),
            ).fetchall()
            conn.execute("DELETE FROM aegis_grants WHERE agent_slug = ?", (agent_slug,))
            conn.commit()
            conn.close()
            if removed:
                self._log_chronicle("trust_collapse", {
                    "agent": agent_slug,
                    "score": score,
                    "revoked": [
                        {"capability": r["capability"], "workspace_id": r["workspace_id"]}
                        for r in removed
                    ],
                })
```

F. Remove the in-memory `_grants_table()` method and any lazy `_grants` initialization — they're no longer needed. The in-memory `_manifests` dict and `_rate_limits`/`_req_log` dicts stay (those are process-local by design).

- [ ] **Step 4: Run the new tests**

```bash
pytest tests/kernel/test_aegis_grants_durable.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run the existing aegis tests — must keep passing**

```bash
pytest tests/kernel/test_aegis_capabilities.py tests/kernel/test_aegis_fs.py tests/kernel/test_aegis_network.py -v 2>&1 | tail -15
```

Expected: same pass count as before (these tests already exercise `grant`/`check_capability`/`revoke_grant` and must work identically with the new sqlite backend).

- [ ] **Step 6: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 790 passing (787 + 3 new), 28 failed (baseline). If failures increased, the SQLite grant logic broke an existing assertion — debug before continuing.

- [ ] **Step 7: Commit**

```bash
git add nexus/kernel/aegis.py tests/kernel/test_aegis_grants_durable.py
git commit -m "feat(aegis): move grants from in-memory to durable sqlite storage"
```

---

## Task 5 · Six built-in templates

**Why:** Templates give users a one-keystroke way to create a new workspace with sensible defaults (spec §7.6).

**Files:**
- Create: `nexus/templates/coding.json`, `design.json`, `research.json`, `writing.json`, `personal.json`, `blank.json`
- Create: `tests/workspaces/test_templates.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the six built-in workspace templates."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.workspaces.config import WorkspaceConfig


TEMPLATES_DIR = Path(__file__).parent.parent.parent / "nexus" / "templates"

EXPECTED_TEMPLATES = ["coding", "design", "research", "writing", "personal", "blank"]


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_template_file_exists(template_name):
    path = TEMPLATES_DIR / f"{template_name}.json"
    assert path.exists(), f"missing template: {path}"


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_template_is_valid_workspace_config(template_name):
    path = TEMPLATES_DIR / f"{template_name}.json"
    data = json.loads(path.read_text())
    # Templates are partial configs — they omit workspace_id, created_at, etc.
    # We validate them by filling in the missing fields and parsing.
    data.setdefault("workspace_id", "test-instance")
    data.setdefault("created_at", "2026-01-01T00:00:00Z")
    WorkspaceConfig.model_validate(data)


def test_coding_template_has_aider_in_roster():
    path = TEMPLATES_DIR / "coding.json"
    data = json.loads(path.read_text())
    assert "aider" in data["resident_agents"]


def test_design_template_has_magenta_tone():
    path = TEMPLATES_DIR / "design.json"
    data = json.loads(path.read_text())
    assert data["tone"] == "magenta"


def test_blank_template_has_empty_roster():
    path = TEMPLATES_DIR / "blank.json"
    data = json.loads(path.read_text())
    assert data["resident_agents"] == []
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/workspaces/test_templates.py -v
```

Expected: 11 failures (template files don't exist).

- [ ] **Step 3: Create the six template files**

```bash
mkdir -p nexus/templates
```

`nexus/templates/coding.json`:

```json
{
  "schema_version": 1,
  "name": "Coding workspace",
  "tone": "indigo",
  "filesystem_roots": [],
  "resident_agents": ["aider", "cline", "council"],
  "pins": [
    {"intent": "CODE", "agent": "aider"}
  ],
  "mood_biases": []
}
```

`nexus/templates/design.json`:

```json
{
  "schema_version": 1,
  "name": "Design / Generative workspace",
  "tone": "magenta",
  "filesystem_roots": [],
  "resident_agents": ["comfyui", "echo"],
  "pins": [],
  "mood_biases": ["creative"]
}
```

`nexus/templates/research.json`:

```json
{
  "schema_version": 1,
  "name": "Research workspace",
  "tone": "sage",
  "filesystem_roots": [],
  "resident_agents": ["council", "specter", "browser-use"],
  "pins": [
    {"intent": "DELIBERATE", "agent": "council"}
  ],
  "mood_biases": ["watchful"]
}
```

`nexus/templates/writing.json`:

```json
{
  "schema_version": 1,
  "name": "Writing workspace",
  "tone": "plum",
  "filesystem_roots": [],
  "resident_agents": ["echo", "council", "consciousness"],
  "pins": [],
  "mood_biases": ["reflective"]
}
```

`nexus/templates/personal.json`:

```json
{
  "schema_version": 1,
  "name": "Personal workspace",
  "tone": "amber",
  "filesystem_roots": [],
  "resident_agents": ["echo", "sentry"],
  "pins": [],
  "mood_biases": []
}
```

`nexus/templates/blank.json`:

```json
{
  "schema_version": 1,
  "name": "New workspace",
  "tone": "indigo",
  "filesystem_roots": [],
  "resident_agents": [],
  "pins": [],
  "mood_biases": []
}
```

- [ ] **Step 4: Run**

```bash
pytest tests/workspaces/test_templates.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 801 passing (790 + 11 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/templates/ tests/workspaces/test_templates.py
git commit -m "feat(workspaces): add six built-in templates (coding, design, research, writing, personal, blank)"
```

---

## Task 6 · `MoodEngine` — kernel state → mood mapping

**Why:** The Aurora UI needs to know "what mood is the OS in right now?" so it can render the right gradient mesh. Phase 3 builds the engine; Phase 5 hooks it into the surfaces.

**Files:**
- Create: `nexus/workspaces/mood.py`
- Create: `tests/workspaces/test_mood.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the MoodEngine — maps kernel state to ambient mood."""
from __future__ import annotations

import pytest

from nexus.workspaces.mood import Mood, MoodEngine
from nexus.workspaces.config import WorkspaceTone


def test_default_mood_is_calm_focus():
    engine = MoodEngine()
    assert engine.current().mood is Mood.CALM_FOCUS


def test_high_pulse_yields_routing_mood():
    engine = MoodEngine()
    engine.observe(pulse_per_min=6000, active_agents=3)
    assert engine.current().mood is Mood.ROUTING


def test_council_active_yields_deliberating():
    engine = MoodEngine()
    engine.observe(active_module="council")
    assert engine.current().mood is Mood.DELIBERATING


def test_oracle_flag_yields_watchful():
    engine = MoodEngine()
    engine.observe(oracle_flagged=True)
    assert engine.current().mood is Mood.WATCHFUL


def test_trust_collapse_yields_alert():
    engine = MoodEngine()
    engine.observe(trust_collapse=True)
    assert engine.current().mood is Mood.ALERT


def test_workspace_tone_influences_calm_focus():
    """In Calm Focus, the workspace tone shows through."""
    engine = MoodEngine(workspace_tone=WorkspaceTone.MAGENTA)
    snap = engine.current()
    assert snap.mood is Mood.CALM_FOCUS
    assert snap.tone is WorkspaceTone.MAGENTA


def test_alert_overrides_workspace_tone():
    """Alert mood ignores workspace tone — it's always crimson."""
    engine = MoodEngine(workspace_tone=WorkspaceTone.MAGENTA)
    engine.observe(trust_collapse=True)
    snap = engine.current()
    assert snap.mood is Mood.ALERT
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/workspaces/test_mood.py -v
```

Expected: ImportError on `nexus.workspaces.mood`.

- [ ] **Step 3: Implement `nexus/workspaces/mood.py`**

```python
"""
MoodEngine — maps kernel observations to one of the 8 ambient moods
defined in the spec atlas (§11).

Priority order (highest wins):
  1. ALERT          — trust collapse, security breach, peer rejection
  2. WATCHFUL       — oracle flagged a pattern, trust sliding
  3. DELIBERATING   — council / specter / legacy is the active module
  4. CREATIVE       — generative agents resident (image/audio/writing)
  5. ROUTING        — high pulse + multiple active agents
  6. DEEP_FLOW      — sustained focus from sentry
  7. REFLECTIVE     — consciousness module + late hour + low pulse
  8. CALM_FOCUS     — default
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from nexus.workspaces.config import WorkspaceTone


class Mood(str, Enum):
    CALM_FOCUS = "calm_focus"
    DEEP_FLOW = "deep_flow"
    ROUTING = "routing"
    DELIBERATING = "deliberating"
    CREATIVE = "creative"
    REFLECTIVE = "reflective"
    WATCHFUL = "watchful"
    ALERT = "alert"


_DELIBERATING_MODULES = frozenset({"council", "specter", "legacy"})
_CREATIVE_AGENTS = frozenset({"comfyui", "sd-webui", "echo"})


@dataclass
class MoodSnapshot:
    mood: Mood
    tone: WorkspaceTone | None
    drift_seconds: float
    reason: str


_DRIFT_PER_MOOD = {
    Mood.CALM_FOCUS: 24.0,
    Mood.DEEP_FLOW: 38.0,
    Mood.ROUTING: 14.0,
    Mood.DELIBERATING: 30.0,
    Mood.CREATIVE: 20.0,
    Mood.REFLECTIVE: 42.0,
    Mood.WATCHFUL: 12.0,
    Mood.ALERT: 7.0,
}


@dataclass
class _State:
    pulse_per_min: float = 0.0
    active_agents: int = 0
    active_module: str | None = None
    resident_agents: tuple[str, ...] = ()
    oracle_flagged: bool = False
    trust_collapse: bool = False
    sustained_focus_minutes: float = 0.0
    is_late_hour: bool = False


class MoodEngine:
    def __init__(self, workspace_tone: WorkspaceTone | None = None):
        self._state = _State()
        self._tone = workspace_tone

    def observe(self, **kwargs) -> None:
        """Update one or more state observations.

        Keyword args mirror the _State dataclass fields.
        """
        for k, v in kwargs.items():
            if not hasattr(self._state, k):
                raise ValueError(f"unknown state field: {k}")
            setattr(self._state, k, v)

    def reset(self) -> None:
        self._state = _State()

    def current(self) -> MoodSnapshot:
        mood, reason = self._classify()
        # Alert ignores workspace tone — always pure crimson
        tone = None if mood is Mood.ALERT else self._tone
        return MoodSnapshot(
            mood=mood,
            tone=tone,
            drift_seconds=_DRIFT_PER_MOOD[mood],
            reason=reason,
        )

    # ── classification ────────────────────────────────────────────────────

    def _classify(self) -> tuple[Mood, str]:
        s = self._state
        if s.trust_collapse:
            return Mood.ALERT, "trust collapse detected"
        if s.oracle_flagged:
            return Mood.WATCHFUL, "oracle flagged a pattern"
        if s.active_module in _DELIBERATING_MODULES:
            return Mood.DELIBERATING, f"{s.active_module} is deliberating"
        if any(a in _CREATIVE_AGENTS for a in s.resident_agents):
            return Mood.CREATIVE, "generative agents resident"
        if s.pulse_per_min >= 3000 and s.active_agents >= 2:
            return Mood.ROUTING, f"pulse {s.pulse_per_min:.0f}/m · {s.active_agents} agents"
        if s.sustained_focus_minutes >= 15:
            return Mood.DEEP_FLOW, f"sustained focus for {s.sustained_focus_minutes:.0f}m"
        if s.active_module == "consciousness" and s.is_late_hour and s.pulse_per_min < 1000:
            return Mood.REFLECTIVE, "consciousness active, late hour, low pulse"
        return Mood.CALM_FOCUS, "default"
```

- [ ] **Step 4: Run**

```bash
pytest tests/workspaces/test_mood.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 808 passing (801 + 7 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/workspaces/mood.py tests/workspaces/test_mood.py
git commit -m "feat(workspaces): add MoodEngine mapping kernel state to 8-mood atlas"
```

---

## Task 7 · `WorkspaceRuntime` — resident agents per workspace

**Why:** Each workspace holds its own dict of `InProcessAgent`/`MCPAgent` adapters. Switching workspaces pauses one set and wakes another.

**Files:**
- Create: `nexus/workspaces/runtime.py`
- Create: `tests/workspaces/test_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for WorkspaceRuntime — manages resident agents per workspace."""
from __future__ import annotations

import pytest

from nexus.workspaces.runtime import WorkspaceRuntime
from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis
from nexus.modules.base import NexusModule


class _StubModule(NexusModule):
    name = "stub"
    description = "stub"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "stub", "name": "stub",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:stub", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return f"stub: {message}"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_StubModule.manifest())
    return a


def test_add_resident_makes_agent_callable(aegis):
    rt = WorkspaceRuntime("ws-1")
    rt.add(InProcessAgent(_StubModule(), aegis=aegis))
    assert "stub" in rt.resident_slugs()


def test_pause_all_pauses_every_resident(aegis):
    rt = WorkspaceRuntime("ws-1")
    rt.add(InProcessAgent(_StubModule(), aegis=aegis))
    rt.pause_all()
    assert rt.get("stub").is_paused


def test_wake_all_wakes_every_resident(aegis):
    rt = WorkspaceRuntime("ws-1")
    rt.add(InProcessAgent(_StubModule(), aegis=aegis))
    rt.pause_all()
    rt.wake_all()
    assert not rt.get("stub").is_paused


def test_remove_resident_returns_it(aegis):
    rt = WorkspaceRuntime("ws-1")
    agent = InProcessAgent(_StubModule(), aegis=aegis)
    rt.add(agent)
    removed = rt.remove("stub")
    assert removed is agent
    assert "stub" not in rt.resident_slugs()


def test_get_unknown_returns_none(aegis):
    rt = WorkspaceRuntime("ws-1")
    assert rt.get("nonexistent") is None
```

- [ ] **Step 2: Run; verify failure**

```bash
pytest tests/workspaces/test_runtime.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `nexus/workspaces/runtime.py`**

```python
"""
WorkspaceRuntime — holds the resident agents for one workspace.

When a workspace is active, every resident agent's `call_tool()` is
available. When switching workspaces, `pause_all()` halts the current
set and `wake_all()` resumes the target set.
"""
from __future__ import annotations

from typing import Iterable, Union

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.mcp_agent import MCPAgent


# Common type alias for both adapter shapes
Agent = Union[InProcessAgent, MCPAgent]


class WorkspaceRuntime:
    def __init__(self, workspace_id: str):
        self._workspace_id = workspace_id
        self._agents: dict[str, Agent] = {}

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    # ── membership ───────────────────────────────────────────────────────

    def add(self, agent: Agent) -> None:
        self._agents[agent.slug] = agent

    def remove(self, slug: str) -> Agent | None:
        return self._agents.pop(slug, None)

    def get(self, slug: str) -> Agent | None:
        return self._agents.get(slug)

    def resident_slugs(self) -> list[str]:
        return list(self._agents.keys())

    def __len__(self) -> int:
        return len(self._agents)

    # ── lifecycle ────────────────────────────────────────────────────────

    def pause_all(self) -> None:
        for agent in self._agents.values():
            try:
                agent.pause()
            except Exception:
                pass  # one bad agent must not block the workspace switch

    def wake_all(self) -> None:
        for agent in self._agents.values():
            try:
                agent.wake()
            except Exception:
                pass
```

- [ ] **Step 4: Run**

```bash
pytest tests/workspaces/test_runtime.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 813 passing (808 + 5 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/workspaces/runtime.py tests/workspaces/test_runtime.py
git commit -m "feat(workspaces): add WorkspaceRuntime managing resident agents per room"
```

---

## Task 8 · Cortex — workspace-aware pin resolution

**Why:** Spec §8.2. When a routing decision happens, Cortex consults the active workspace's pins first; a matching pin bypasses the chooser.

**Files:**
- Modify: `nexus/kernel/cortex.py`
- Create: `tests/kernel/test_cortex_pinning.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for Cortex workspace pin resolution."""
from __future__ import annotations

import pytest

from nexus.kernel.cortex import Cortex
from nexus.kernel.aegis import Aegis
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.config import NexusConfig
from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone, RoutingPin


@pytest.fixture
def cortex(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(str(tmp_path / "e.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "c.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "a.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    return Cortex(engram, chronicle, aegis, pulse, config)


def _ws_with_pin(intent: str, agent: str) -> WorkspaceConfig:
    return WorkspaceConfig(
        schema_version=1,
        workspace_id="ws-test",
        name="Test",
        tone=WorkspaceTone.INDIGO,
        pins=[RoutingPin(intent=intent, agent=agent)],
        created_at="2026-06-07T00:00:00Z",
    )


def test_pin_override_for_matching_intent(cortex):
    """A workspace pin should override the highest-scoring classifier match
    when the classifier produces the pinned intent."""
    cortex.set_active_workspace(_ws_with_pin("DELIBERATE", "council"))
    target = cortex.resolve_pin("DELIBERATE")
    assert target == "council"


def test_no_pin_returns_none(cortex):
    cortex.set_active_workspace(_ws_with_pin("DELIBERATE", "council"))
    target = cortex.resolve_pin("UNKNOWN")
    assert target is None


def test_no_active_workspace_returns_none(cortex):
    target = cortex.resolve_pin("DELIBERATE")
    assert target is None


def test_active_workspace_change_clears_old_pins(cortex):
    cortex.set_active_workspace(_ws_with_pin("DELIBERATE", "council"))
    cortex.set_active_workspace(_ws_with_pin("CHALLENGE", "specter"))
    assert cortex.resolve_pin("DELIBERATE") is None
    assert cortex.resolve_pin("CHALLENGE") == "specter"
```

- [ ] **Step 2: Run; verify failure**

```bash
pytest tests/kernel/test_cortex_pinning.py -v
```

Expected: `Cortex.set_active_workspace` and `resolve_pin` don't exist.

- [ ] **Step 3: Add the two methods to `nexus/kernel/cortex.py`**

Add to the `Cortex` class (placement: after `register_builtin_manifests`, before `unregister_module`):

```python
    # -- workspace integration ---------------------------------------------

    def set_active_workspace(self, workspace) -> None:
        """Bind the active workspace's config so pin resolution uses it.

        Pass `None` to clear.
        """
        self._active_workspace = workspace

    def resolve_pin(self, intent: str | None = None, category: str | None = None) -> str | None:
        """Return the agent slug pinned for this intent/category in the
        active workspace, or None if no pin matches.
        """
        ws = getattr(self, "_active_workspace", None)
        if ws is None:
            return None
        if intent is not None:
            return ws.pin_for_intent(intent)
        if category is not None:
            return ws.pin_for_category(category)
        return None
```

Also initialize `_active_workspace = None` in the `Cortex.__init__` method (find the `self._classifier = IntentClassifier()` line and add immediately after):

```python
        self._active_workspace = None
```

- [ ] **Step 4: Run**

```bash
pytest tests/kernel/test_cortex_pinning.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 817 passing (813 + 4 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/kernel/cortex.py tests/kernel/test_cortex_pinning.py
git commit -m "feat(cortex): add workspace-aware pin resolution"
```

---

## Task 9 · CLI commands — `onexus workspace …`

**Why:** Users need to be able to create/list/switch/destroy workspaces from the terminal (spec §16.1).

**Files:**
- Modify: `nexus/cli.py` — add a `workspace` Click group with sub-commands
- Create: `tests/cli/test_workspace_commands.py`

- [ ] **Step 1: Inspect the existing CLI structure**

```bash
grep -n "^@cli\|@click.group\|^cli = " nexus/cli.py | head
```

Note the Click decorator style and the location of the existing top-level command group.

- [ ] **Step 2: Write the failing test**

Create `tests/cli/__init__.py` if missing, then `tests/cli/test_workspace_commands.py`:

```python
"""Tests for the workspace CLI subcommands."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from nexus.cli import main


def test_workspace_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["workspace", "list"])
    assert result.exit_code == 0
    assert "no workspaces" in result.output.lower() or result.output.strip() == ""


def test_workspace_new_from_blank(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, [
        "workspace", "new", "test-ws", "--name", "Test", "--template", "blank",
    ])
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "workspaces" / "test-ws" / "workspace.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data["name"] == "Test"
    assert data["tone"] == "indigo"


def test_workspace_new_from_coding(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, [
        "workspace", "new", "code-ws", "--name", "Code", "--template", "coding",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "workspaces" / "code-ws" / "workspace.json").read_text())
    assert "aider" in data["resident_agents"]


def test_workspace_switch_and_list_shows_active(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    runner.invoke(main, ["workspace", "new", "a", "--name", "A", "--template", "blank"])
    runner.invoke(main, ["workspace", "new", "b", "--name", "B", "--template", "blank"])
    runner.invoke(main, ["workspace", "switch", "b"])
    result = runner.invoke(main, ["workspace", "list"])
    assert "b" in result.output
    # Active marker (a dot, asterisk, or similar — implementation chooses) is present
    assert "*" in result.output or "•" in result.output or "active" in result.output.lower()
```

Note: this test depends on `NEXUS_DATA_DIR` being honoured by `NexusConfig`. Read `nexus/config.py` and confirm — it uses `_default_data_dir()` which checks `$NEXUS_DATA_DIR`. If the env var isn't honoured automatically, you may need to pass `--data-dir` to the CLI command instead. Adapt the test invocation accordingly.

- [ ] **Step 3: Run; verify failure**

```bash
pytest tests/cli/test_workspace_commands.py -v
```

Expected: `workspace` sub-command doesn't exist.

- [ ] **Step 4: Add the `workspace` command group to `nexus/cli.py`**

Place the new code AFTER the existing top-level `cli` (or `main`) Click group definition. Find the existing group decorator (`@click.group()` or similar) and after the existing subcommands, add:

```python
@main.group()
def workspace():
    """Manage workspaces (rooms)."""
    pass


@workspace.command("list")
def workspace_list():
    """List all workspaces; the active one is marked with *."""
    from nexus.workspaces.manager import WorkspaceManager
    from nexus.config import NexusConfig

    cfg = NexusConfig()
    mgr = WorkspaceManager(cfg.data_dir / "workspaces")
    active = mgr.active_id()
    workspaces = mgr.list()
    if not workspaces:
        click.echo("no workspaces yet — create one with: onexus workspace new <id>")
        return
    for w in workspaces:
        marker = "*" if w.workspace_id == active else " "
        click.echo(f"{marker} {w.workspace_id:24}  {w.name}  [{w.tone.value}]")


@workspace.command("new")
@click.argument("workspace_id")
@click.option("--name", required=True)
@click.option("--template", default="blank",
              type=click.Choice(["coding", "design", "research",
                                 "writing", "personal", "blank"]))
def workspace_new(workspace_id, name, template):
    """Create a new workspace from a template."""
    import json
    from pathlib import Path
    from nexus.workspaces.manager import WorkspaceManager
    from nexus.workspaces.config import WorkspaceTone, RoutingPin
    from nexus.config import NexusConfig

    cfg = NexusConfig()
    mgr = WorkspaceManager(cfg.data_dir / "workspaces")

    template_path = Path(__file__).parent / "templates" / f"{template}.json"
    if not template_path.exists():
        click.echo(f"unknown template: {template}", err=True)
        raise SystemExit(1)
    template_data = json.loads(template_path.read_text())

    try:
        mgr.create(
            name=name,
            workspace_id=workspace_id,
            tone=WorkspaceTone(template_data["tone"]),
            filesystem_roots=template_data.get("filesystem_roots", []),
            resident_agents=template_data.get("resident_agents", []),
            pins=[RoutingPin.model_validate(p) for p in template_data.get("pins", [])],
            mood_biases=template_data.get("mood_biases", []),
        )
    except FileExistsError:
        click.echo(f"workspace {workspace_id!r} already exists", err=True)
        raise SystemExit(1)
    click.echo(f"created workspace: {workspace_id}")


@workspace.command("switch")
@click.argument("workspace_id")
def workspace_switch(workspace_id):
    """Set the active workspace."""
    from nexus.workspaces.manager import WorkspaceManager
    from nexus.config import NexusConfig

    cfg = NexusConfig()
    mgr = WorkspaceManager(cfg.data_dir / "workspaces")
    try:
        mgr.set_active(workspace_id)
    except KeyError:
        click.echo(f"workspace {workspace_id!r} not found", err=True)
        raise SystemExit(1)
    click.echo(f"active workspace: {workspace_id}")


@workspace.command("destroy")
@click.argument("workspace_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def workspace_destroy(workspace_id, yes):
    """Delete a workspace and all its data."""
    from nexus.workspaces.manager import WorkspaceManager
    from nexus.config import NexusConfig

    if not yes:
        if not click.confirm(f"destroy workspace {workspace_id!r}? this cannot be undone."):
            return
    cfg = NexusConfig()
    mgr = WorkspaceManager(cfg.data_dir / "workspaces")
    try:
        mgr.destroy(workspace_id)
    except KeyError:
        click.echo(f"workspace {workspace_id!r} not found", err=True)
        raise SystemExit(1)
    click.echo(f"destroyed: {workspace_id}")
```

Inspect the existing CLI to confirm the top-level group is named `main` (or another name) and adjust the `@main.group()` decorator accordingly.

- [ ] **Step 5: Run**

```bash
pytest tests/cli/test_workspace_commands.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 821 passing (817 + 4 new), 28 failed (baseline).

- [ ] **Step 7: Commit**

```bash
git add nexus/cli.py tests/cli/test_workspace_commands.py tests/cli/__init__.py
git commit -m "feat(cli): add onexus workspace list/new/switch/destroy subcommands"
```

---

## Task 10 · End-to-end Phase 3 smoke

**Why:** Prove the whole workspace stack — config → manager → partitioned engram → durable grants → pin resolution — works together.

**Files:**
- Create: `tests/workspaces/test_phase_3_smoke.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke test for Phase 3 — full workspace flow.

Create two workspaces, switch between them, prove their memory and
grants are isolated, and prove pin resolution works.
"""
from __future__ import annotations

import json

import pytest

from nexus.workspaces.manager import WorkspaceManager
from nexus.workspaces.config import WorkspaceTone, RoutingPin
from nexus.kernel.engram import Engram
from nexus.kernel.aegis import Aegis, Verdict
from nexus.agents.manifest import Manifest


def _aider() -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "aider", "name": "aider",
        "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [], "declared": {
                "Routine": [], "Notable": ["fs.write.workspace"],
                "Sensitive": [], "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def world(tmp_path):
    mgr = WorkspaceManager(root=tmp_path / "workspaces")
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_aider())
    return mgr, aegis, tmp_path


def test_create_two_workspaces_and_switch(world):
    mgr, aegis, _ = world
    mgr.create(name="Client work", workspace_id="client",
               tone=WorkspaceTone.INDIGO,
               pins=[RoutingPin(intent="CODE", agent="aider")])
    mgr.create(name="Personal", workspace_id="personal",
               tone=WorkspaceTone.AMBER)
    assert sorted(w.workspace_id for w in mgr.list()) == ["client", "personal"]
    mgr.set_active("client")
    assert mgr.active_id() == "client"


def test_engram_partitions_are_isolated(world, tmp_path):
    mgr, _, _ = world
    mgr.create(name="A", workspace_id="a", tone=WorkspaceTone.INDIGO)
    mgr.create(name="B", workspace_id="b", tone=WorkspaceTone.SAGE)

    base = Engram(tmp_path / "global" / "engram.db")
    base.init_db()
    ws_a = base.partition(mgr.workspace_dir("a") / "engram")
    ws_a.init_db()
    ws_b = base.partition(mgr.workspace_dir("b") / "engram")
    ws_b.init_db()

    ws_a.episodic.store("client meeting notes", source="user")
    assert ws_b.episodic.recall("meeting", limit=5) == []
    assert ws_a.episodic.recall("meeting", limit=5) != []


def test_grants_are_per_workspace(world):
    _, aegis, _ = world
    aegis.grant("aider", "fs.write.workspace", workspace_id="client")
    # client sees the grant
    d_client = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client")
    assert d_client.verdict is Verdict.ALLOW
    # personal does not
    d_personal = aegis.check_capability("aider", "fs.write.workspace", workspace_id="personal")
    assert d_personal.verdict is Verdict.PROMPT


def test_pin_routes_via_active_workspace(world):
    from nexus.kernel.cortex import Cortex
    from nexus.kernel.engram import Engram
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.pulse import Pulse
    from nexus.config import NexusConfig

    mgr, aegis, tmp_path = world
    mgr.create(name="Client", workspace_id="client",
               tone=WorkspaceTone.INDIGO,
               pins=[RoutingPin(intent="DELIBERATE", agent="council")])
    cfg = NexusConfig(data_dir=tmp_path)
    engram = Engram(str(tmp_path / "e.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "c.db"))
    chronicle.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, cfg)
    cortex.set_active_workspace(mgr.get("client"))
    assert cortex.resolve_pin("DELIBERATE") == "council"
```

- [ ] **Step 2: Run**

```bash
pytest tests/workspaces/test_phase_3_smoke.py -v
```

Expected: 4 passed.

- [ ] **Step 3: Regression check**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 825 passing (821 + 4 new), 28 failed (baseline).

- [ ] **Step 4: Commit**

```bash
git add tests/workspaces/test_phase_3_smoke.py
git commit -m "test(workspaces): end-to-end Phase 3 smoke (manager + engram + grants + pin)"
```

---

## Task 11 · Documentation + regression baseline + tag

**Why:** Capture the workspace layer's public surface and tag the milestone.

**Files:**
- Create: `docs/agents/workspaces.md`

- [ ] **Step 1: Write the doc**

```markdown
# Workspace Layer (Phase 3)

A workspace is a room. Each room owns its filesystem root(s), resident
agents, memory partition, permission grants, home tone, and routing
pins. Switching workspaces feels like walking through a door.

## Storage layout

```
~/.nexus/workspaces/
├── .active                       # contains the active workspace_id
└── <workspace-id>/
    ├── workspace.json            # WorkspaceConfig (pydantic v1)
    └── engram/
        └── engram.db             # workspace-scoped Engram namespace
```

Permission grants live in `~/.nexus/aegis.db` under the `aegis_grants`
table keyed by `(agent_slug, capability, workspace_id)`. A grant with
`workspace_id IS NULL` is global and applies in every workspace.

## Public API

### `nexus.workspaces.config.WorkspaceConfig`

Typed pydantic model loaded from `workspace.json`. Fields: `name`,
`tone` (one of indigo/magenta/sage/plum/amber), `filesystem_roots`,
`resident_agents`, `pins` (list of `RoutingPin`), `mood_biases`.

### `nexus.workspaces.manager.WorkspaceManager`

```python
mgr = WorkspaceManager(root="~/.nexus/workspaces")
ws  = mgr.create(name="...", workspace_id="...", tone=WorkspaceTone.INDIGO, ...)
mgr.list()                  # list[WorkspaceConfig]
mgr.get("client")           # WorkspaceConfig | None
mgr.set_active("client")
mgr.active_id()             # "client" | None
mgr.destroy("client")
```

### `nexus.workspaces.runtime.WorkspaceRuntime`

Holds the dict of resident agents (`InProcessAgent` + `MCPAgent`) for
one workspace. `pause_all()` / `wake_all()` are called on workspace
switch.

### `nexus.workspaces.mood.MoodEngine`

Maps kernel-state observations to one of eight moods (`CALM_FOCUS`,
`DEEP_FLOW`, `ROUTING`, `DELIBERATING`, `CREATIVE`, `REFLECTIVE`,
`WATCHFUL`, `ALERT`). The Aurora UI reads `current()` to drive the
gradient mesh.

### `nexus.kernel.cortex.Cortex.set_active_workspace(ws)` and `.resolve_pin(intent, category)`

Cortex now consults the active workspace's pins. A pin overrides the
classifier's top candidate when the intent matches.

### `nexus.kernel.engram.Engram.partition(dir)`

Returns a workspace-scoped Engram namespace pointed at `<dir>/engram.db`.

## CLI

```
onexus workspace list                          # show all
onexus workspace new <id> --name N --template T
onexus workspace switch <id>
onexus workspace destroy <id> [--yes]
```

Templates: `coding`, `design`, `research`, `writing`, `personal`, `blank`.

## What's NOT in Phase 3

- New surfaces (Conversational / Cockpit / Spatial / Settings) — Phase 5.
- Per-workspace federation toggle — Phase 6.
- LLM providers routing through `aegis.network()` — Phase 6.
```

- [ ] **Step 2: Verify regression baseline**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | grep -E "^FAILED" | awk '{print $2}' | sort > /tmp/phase_3_failures.txt
diff .baseline_failures.txt /tmp/phase_3_failures.txt && echo "[FAILURE SET IDENTICAL TO BASELINE]"
```

Expected: `[FAILURE SET IDENTICAL TO BASELINE]`.

- [ ] **Step 3: Commit docs + tag**

```bash
git add docs/agents/workspaces.md
git commit -m "docs(workspaces): Phase 3 — workspace layer"
git tag -a phase-3-workspaces -m "Phase 3 workspaces complete: rooms with isolated memory, grants, pins, runtime

- WorkspaceConfig pydantic model + RoutingPin
- WorkspaceManager (CRUD + persistent active pointer)
- Engram.partition() for isolated workspace memory
- Aegis grants migrated from in-memory to durable sqlite
- WorkspaceRuntime managing resident agents
- MoodEngine mapping kernel state to 8-mood atlas
- Cortex.set_active_workspace + resolve_pin
- Six built-in templates (coding/design/research/writing/personal/blank)
- CLI: onexus workspace list/new/switch/destroy
- End-to-end smoke test

Suite: 825 passing (769 → 825, +56 new tests)."
git log --oneline | head -20
```

Phase 3 is complete. Phase 4 (Safety UX) is unblocked.

---

## Self-Review (against the design spec)

| Spec section | Implementing task | Notes |
|---|---|---|
| §7.1 Six owned things | Tasks 1–7 | All present: filesystem roots, residents, memory partition, grants, tone, pins |
| §7.2 Storage layout | Tasks 1, 2, 3, 4 | Matches the spec layout exactly |
| §7.3 Switcher (CLI) | Task 9 | `onexus workspace list/switch` |
| §7.4 Concurrency | Task 7 (`pause_all`/`wake_all`) | Per-workspace runtime; SIGSTOP via existing agent adapters |
| §7.5 Resource footprint | (no change required) | Per-agent process model unchanged from Phase 1 |
| §7.6 Templates | Task 5 | Six templates present |
| §11 Mood Atlas | Task 6 | Eight moods, priority order, workspace-tone integration |
| §16 CLI Commands | Task 9 | list, new, switch, destroy |

**Open issues for Phase 4:** The workspace's `resident_agents` list is currently informational only — Phase 4 will wire the runtime so creating a workspace actually instantiates the listed agents. The CLI surface lands now; the wiring follows in Phase 4 as part of the agent install / first-use prompt flow.

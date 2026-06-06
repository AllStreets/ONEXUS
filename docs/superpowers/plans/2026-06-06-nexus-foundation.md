# NEXUS Foundation Implementation Plan (Phase 1 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the data-model + runtime-class foundation for the agent OS. After this phase, the manifest schema, the agent adapters (`InProcessAgent` + `MCPAgent`), and the new Aegis capability/filesystem/network methods all exist and are unit-tested. **No user-visible behaviour changes yet** — existing tests still pass. This unblocks all six remaining phases.

**Architecture:** Add new code alongside existing code. Define `nexus/agents/manifest.py` (pydantic models + JSON Schema), `nexus/agents/in_process_agent.py`, `nexus/agents/mcp_agent.py`. Extend `nexus/kernel/aegis.py` with three new public methods (`check_capability`, `fs`, `network`). Refactor `nexus/modules/base.py` to add `manifest()` + `tools()` to the `NexusModule` ABC. Tests live under `tests/agents/` and `tests/kernel/`.

**Tech Stack:** Python 3.11+, pydantic 2 (already an `api`-extras dep — promoted to core for this phase), `mcp` Python library (already used by the existing MCP server), `httpx` (already a `federation`-extras dep — promoted to core), pytest + pytest-asyncio.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — sections 4 (Kernel), 5 (Agent Runtime), 6 (Manifest Schema v1), 9 (Safety Model).

---

## Pre-flight

Before starting any task:

- Confirm you are on a clean working tree on branch `main` or a feature branch off `main`.
- Run the existing test suite once to confirm baseline green: `pytest -x -q`.
- Confirm `python -c "import pydantic, httpx, mcp"` succeeds (these are existing deps but in optional extras).

---

## Task 1 · Promote pydantic + httpx to core deps; create file skeletons

**Why:** `pydantic` is used by the new manifest models; `httpx` is the network library for `aegis.network()`. They exist in optional extras today but the foundation phase needs them unconditionally.

**Files:**
- Modify: `pyproject.toml`
- Create: `nexus/agents/manifest.py` (empty skeleton)
- Create: `nexus/agents/in_process_agent.py` (empty skeleton)
- Create: `nexus/agents/mcp_agent.py` (empty skeleton)
- Create: `nexus/schemas/__init__.py` (empty)
- Create: `nexus/schemas/manifest.v1.json` (empty placeholder — populated in Task 3)
- Create: `tests/agents/__init__.py` (empty)
- Create: `tests/agents/test_manifest.py` (empty)
- Create: `tests/agents/test_in_process_agent.py` (empty)
- Create: `tests/agents/test_mcp_agent.py` (empty)

- [ ] **Step 1: Update pyproject.toml**

Find the `dependencies` array (around line 7) and replace it. Show your replacement:

```toml
dependencies = [
    "click>=8.1",
    "pydantic>=2.0",
    "httpx>=0.27",
    "mcp>=0.9",
]
```

Then remove `httpx>=0.27` from `[project.optional-dependencies].federation` and `[project.optional-dependencies].test` (it will still resolve via the core dep). Leave `pydantic` in `api` (a transitive dep is fine, but core is the authoritative source).

- [ ] **Step 2: Create file skeletons**

Run from the repo root:

```bash
mkdir -p nexus/schemas tests/agents
touch nexus/agents/manifest.py nexus/agents/in_process_agent.py nexus/agents/mcp_agent.py
touch nexus/schemas/__init__.py nexus/schemas/manifest.v1.json
touch tests/agents/__init__.py
touch tests/agents/test_manifest.py tests/agents/test_in_process_agent.py tests/agents/test_mcp_agent.py
```

- [ ] **Step 3: Reinstall the package**

```bash
pip install -e .
```

Expected: exits 0; pydantic, httpx, mcp resolved.

- [ ] **Step 4: Confirm existing tests still pass**

```bash
pytest -x -q
```

Expected: all green. If anything fails, stop and investigate before continuing.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml nexus/agents/ nexus/schemas/ tests/agents/
git commit -m "chore: promote pydantic + httpx + mcp to core deps; scaffold agent runtime files"
```

---

## Task 2 · Manifest pydantic models

**Why:** Every agent (built-in or third-party) needs a typed, validated manifest. Pydantic gives us validation, JSON Schema export, and ergonomics.

**Files:**
- Modify: `nexus/agents/manifest.py`
- Modify: `tests/agents/test_manifest.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/agents/test_manifest.py` and write:

```python
"""Tests for the v1 agent manifest model."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.agents.manifest import (
    Manifest,
    ToolDescriptor,
    Capabilities,
    Publisher,
    IdentityMark,
    RuntimeConfig,
    TrustConfig,
    PermissionClass,
)


def _valid_manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "aider",
        "name": "aider",
        "tagline": "Pair-programming in your terminal.",
        "version": "0.74.0",
        "system": False,
        "publisher": {"type": "org", "handle": "Aider-AI", "url": "https://github.com/Aider-AI"},
        "category": "coding",
        "tags": ["coding", "cli"],
        "license": "Apache-2.0",
        "identity": {"mark": {"kind": "svg", "path": "./icon.svg",
                              "gradient": ["#9aa8ff", "#4d5bcf"]}},
        "intents": [{"name": "code", "patterns": ["edit", "fix"],
                     "semantic_signals": ["fix this"], "weight": 1.0}],
        "capabilities": {
            "tools": [{"name": "edit_file", "class": "Notable",
                       "scope": "fs.write.workspace"}],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["fs.write.workspace"],
                "Sensitive": [],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "aider-mcp", "args": [],
                    "env_keys": ["OPENAI_API_KEY"]},
        "trust": {"floor": 0.55, "default_tier": "ADVISOR"},
        "compatibility": {"nexus_version": ">=1.0.0"},
    }


def test_valid_manifest_loads():
    m = Manifest.model_validate(_valid_manifest_dict())
    assert m.slug == "aider"
    assert m.system is False
    assert m.capabilities.tools[0].permission_class is PermissionClass.NOTABLE


def test_slug_must_be_kebab_case():
    d = _valid_manifest_dict()
    d["slug"] = "Bad Slug"
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)


def test_manifest_version_must_be_1():
    d = _valid_manifest_dict()
    d["manifest_version"] = 2
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)


def test_tool_scope_must_be_declared():
    """A tool referencing a capability scope must appear in declared[its_class]."""
    d = _valid_manifest_dict()
    d["capabilities"]["tools"][0]["scope"] = "fs.write.workspace"
    d["capabilities"]["declared"]["Notable"] = []  # remove it
    with pytest.raises(ValidationError) as exc:
        Manifest.model_validate(d)
    assert "scope" in str(exc.value).lower()


def test_system_agent_can_declare_privileged():
    d = _valid_manifest_dict()
    d["system"] = True
    d["slug"] = "echo"
    d["capabilities"]["declared"]["Privileged"] = ["engram.read.global"]
    m = Manifest.model_validate(d)
    assert "engram.read.global" in m.capabilities.declared.privileged


def test_runtime_in_process_requires_no_command():
    d = _valid_manifest_dict()
    d["runtime"] = {"transport": "in_process", "command": "", "args": [], "env_keys": []}
    m = Manifest.model_validate(d)
    assert m.runtime.transport == "in_process"


def test_trust_floor_bounded():
    d = _valid_manifest_dict()
    d["trust"]["floor"] = 1.5
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_manifest.py -v
```

Expected: import errors — `Manifest`, `PermissionClass`, etc., don't exist yet.

- [ ] **Step 3: Implement `nexus/agents/manifest.py`**

Replace the empty file with:

```python
"""
Agent manifest v1 — typed model + JSON Schema export.

Every NEXUS agent (built-in or third-party) declares its identity,
intents, capabilities, and runtime via this manifest. Cortex reads
`intents`; Aegis reads `capabilities`; the runtime reads `runtime`;
the surfaces read `identity`.

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §6.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class PermissionClass(str, Enum):
    ROUTINE = "Routine"
    NOTABLE = "Notable"
    SENSITIVE = "Sensitive"
    PRIVILEGED = "Privileged"


class TrustTierName(str, Enum):
    OBSERVER = "OBSERVER"
    ADVISOR = "ADVISOR"
    MONITOR = "MONITOR"
    EXECUTOR = "EXECUTOR"
    AUTONOMOUS = "AUTONOMOUS"


class Publisher(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["org", "individual"]
    handle: str
    url: str | None = None


class IdentityMark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description='"svg" or "builtin:<slug>"')
    path: str | None = None
    gradient: list[str] = Field(default_factory=list, max_length=4)


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mark: IdentityMark


class IntentDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    patterns: list[str] = Field(default_factory=list)
    semantic_signals: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0, le=2.0)


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    permission_class: PermissionClass = Field(alias="class")
    scope: str | None = None


class DeclaredCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routine: list[str] = Field(default_factory=list, alias="Routine")
    notable: list[str] = Field(default_factory=list, alias="Notable")
    sensitive: list[str] = Field(default_factory=list, alias="Sensitive")
    privileged: list[str] = Field(default_factory=list, alias="Privileged")

    def all(self) -> list[str]:
        return [*self.routine, *self.notable, *self.sensitive, *self.privileged]

    def for_class(self, cls: PermissionClass) -> list[str]:
        return {
            PermissionClass.ROUTINE: self.routine,
            PermissionClass.NOTABLE: self.notable,
            PermissionClass.SENSITIVE: self.sensitive,
            PermissionClass.PRIVILEGED: self.privileged,
        }[cls]


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[ToolDescriptor] = Field(default_factory=list)
    declared: DeclaredCapabilities = Field(default_factory=DeclaredCapabilities)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["stdio", "sse", "in_process"]
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env_keys: list[str] = Field(default_factory=list)


class TrustConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor: float = Field(default=0.0, ge=0.0, le=1.0)
    default_tier: TrustTierName = TrustTierName.OBSERVER


class Compatibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nexus_version: str = ">=1.0.0"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    github: str | None = None
    huggingface: str | None = None
    homepage: str | None = None


class Manifest(BaseModel):
    """The v1 agent manifest."""
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal[1]
    slug: str
    name: str
    tagline: str = ""
    version: str
    system: bool = False
    publisher: Publisher
    category: str
    tags: list[str] = Field(default_factory=list)
    license: str = "Unknown"
    source: Source = Field(default_factory=Source)
    identity: Identity
    intents: list[IntentDecl] = Field(default_factory=list)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    runtime: RuntimeConfig
    trust: TrustConfig = Field(default_factory=TrustConfig)
    compatibility: Compatibility = Field(default_factory=Compatibility)

    # ── validators ────────────────────────────────────────────────────────

    @field_validator("slug")
    @classmethod
    def _slug_kebab(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                f"slug must be kebab-case, start with a lowercase letter, "
                f"and be 1–64 chars; got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _tool_scopes_declared(self) -> "Manifest":
        """Every tool.scope must appear in capabilities.declared[its_class]."""
        for tool in self.capabilities.tools:
            if tool.scope is None:
                continue
            declared = self.capabilities.declared.for_class(tool.permission_class)
            if tool.scope not in declared:
                raise ValueError(
                    f"tool {tool.name!r} references scope {tool.scope!r} which "
                    f"is not declared under {tool.permission_class.value}"
                )
        return self

    # ── convenience helpers ───────────────────────────────────────────────

    @classmethod
    def from_path(cls, path: str | Path) -> "Manifest":
        data = json.loads(Path(path).read_text())
        return cls.model_validate(data)

    def tool(self, name: str) -> ToolDescriptor | None:
        for t in self.capabilities.tools:
            if t.name == name:
                return t
        return None

    def declares(self, capability: str) -> PermissionClass | None:
        """Which class does this manifest declare a capability under (if any)?"""
        d = self.capabilities.declared
        for cls in PermissionClass:
            if capability in d.for_class(cls):
                return cls
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_manifest.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add nexus/agents/manifest.py tests/agents/test_manifest.py
git commit -m "feat(agents): add v1 manifest pydantic model with validation"
```

---

## Task 3 · Export JSON Schema; add CLI validator

**Why:** Third-party agent authors need a JSON Schema to validate manifests outside Python. Catalog CI will use it.

**Files:**
- Modify: `nexus/schemas/manifest.v1.json` (overwrite the empty placeholder)
- Create: `nexus/agents/_schema_export.py` (small helper that exports JSON Schema)
- Modify: `tests/agents/test_manifest.py` (add schema-roundtrip test)

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/test_manifest.py`:

```python
def test_schema_export_is_valid_json_schema():
    """The exported JSON Schema must parse and reject the same invalid manifests."""
    import json as _json
    import jsonschema  # standard test-time dep (pytest brings it transitively)
    from nexus.agents._schema_export import export_schema
    from pathlib import Path

    schema_path = Path("nexus/schemas/manifest.v1.json")
    schema = _json.loads(schema_path.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)

    # Valid manifest passes
    jsonschema.validate(_valid_manifest_dict(), schema)

    # Bad slug fails
    bad = _valid_manifest_dict()
    bad["slug"] = "Bad Slug"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
```

If `jsonschema` is not yet a test dep, add it to `pyproject.toml` `[project.optional-dependencies].test`:

```toml
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "jsonschema>=4.0",
]
```

Then `pip install -e ".[test]"`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/agents/test_manifest.py::test_schema_export_is_valid_json_schema -v
```

Expected: ImportError on `nexus.agents._schema_export`.

- [ ] **Step 3: Implement `nexus/agents/_schema_export.py`**

```python
"""Export the v1 manifest pydantic model as JSON Schema (Draft 2020-12)."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.agents.manifest import Manifest

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "manifest.v1.json"


def export_schema() -> dict:
    """Generate the JSON Schema dict for Manifest."""
    return Manifest.model_json_schema(mode="validation")


def write_schema() -> Path:
    """Write the schema to nexus/schemas/manifest.v1.json and return the path."""
    _SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SCHEMA_PATH.write_text(json.dumps(export_schema(), indent=2))
    return _SCHEMA_PATH


if __name__ == "__main__":
    path = write_schema()
    print(f"Wrote schema to {path}")
```

- [ ] **Step 4: Generate the schema file**

```bash
python -m nexus.agents._schema_export
```

Expected output: `Wrote schema to .../nexus/schemas/manifest.v1.json`. The file is populated with the JSON Schema.

- [ ] **Step 5: Run the test to verify it passes**

```bash
pytest tests/agents/test_manifest.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add nexus/agents/_schema_export.py nexus/schemas/manifest.v1.json tests/agents/test_manifest.py pyproject.toml
git commit -m "feat(agents): export manifest v1 as JSON Schema"
```

---

## Task 4 · Refactor `NexusModule` with `manifest()` + `tools()`

**Why:** Built-in cognitive modules become unified agents (spec §13). They need a way to declare their manifest and their callable tools. We add abstract methods with sensible defaults so the existing 9 modules don't all break at once.

**Files:**
- Modify: `nexus/modules/base.py`
- Create: `tests/modules/test_base.py`

- [ ] **Step 1: Inspect the existing module to know what to preserve**

```bash
cat nexus/modules/base.py
```

Note: the existing class has `name`, `description`, `version`, `requires_network`, `handle()`, `_log_outbound()`, `on_load()`, `on_unload()`. All must keep working.

- [ ] **Step 2: Write the failing test**

Create `tests/modules/test_base.py`:

```python
"""Tests for the refactored NexusModule ABC."""
from __future__ import annotations

import pytest

from nexus.modules.base import NexusModule
from nexus.agents.manifest import Manifest, PermissionClass


class _StubModule(NexusModule):
    name = "stub"
    description = "test stub"
    version = "0.0.1"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "stub",
            "name": "stub",
            "tagline": "for tests",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:stub", "gradient": ["#ffffff", "#888888"]}},
            "intents": [{"name": "stub", "patterns": ["^stub"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"]},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        return f"stub: {message}"


def test_module_must_provide_manifest():
    """A concrete NexusModule subclass must define manifest()."""

    class _Bad(NexusModule):
        name = "bad"
        description = "missing manifest"
        version = "0.0.1"

        async def handle(self, message, context):
            return ""

    with pytest.raises(NotImplementedError):
        _Bad.manifest()


def test_module_tools_default_to_handle():
    """If a module doesn't override tools(), it exposes 'handle' as the sole tool."""
    m = _StubModule()
    tools = m.tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "handle"
    assert tools[0]["class"] == "Routine"


def test_module_manifest_is_a_valid_manifest():
    m = _StubModule.manifest()
    assert m.slug == "stub"
    assert m.system is True
    assert m.tool("handle").permission_class is PermissionClass.ROUTINE
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest tests/modules/test_base.py -v
```

Expected: fails — `NexusModule.manifest()` does not exist.

- [ ] **Step 4: Modify `nexus/modules/base.py`**

Replace the entire file with:

```python
"""
Base class for all Nexus modules.

A NexusModule is the in-process implementation of a built-in agent.
It exposes:
  - identity (name, description, version)
  - a Manifest (so it can be unified with catalog agents)
  - one or more tools (callable surfaces; default = the single `handle` tool)
  - lifecycle hooks (on_load / on_unload)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexus.agents.manifest import Manifest


class NexusModule(ABC):
    name: str
    description: str
    version: str
    requires_network: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return
        for method_name in ("analyze", "handle"):
            method = getattr(cls, method_name, None)
            if method is not None:
                import inspect
                try:
                    src = inspect.getsource(method)
                    if "raise NotImplementedError" in src and "must implement" in src:
                        return
                except (OSError, TypeError):
                    pass
        for attr in ("name", "description", "version"):
            if not hasattr(cls, attr) or not getattr(cls, attr):
                raise TypeError(f"Module {cls.__name__} must define '{attr}'")

    @abstractmethod
    async def handle(self, message: str, context: dict[str, Any]) -> str:
        """Process a user message and return a response string."""

    # ── unified-agent surface ────────────────────────────────────────────

    @classmethod
    def manifest(cls) -> "Manifest":
        """Return the agent manifest for this module.

        Concrete modules MUST override this. During Phase 2 (migration)
        each of the 9 built-ins ships its own override. Until then,
        this raises so subclasses can't accidentally forget.
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement manifest() — see Phase 2 migration."
        )

    def tools(self) -> list[dict[str, Any]]:
        """Return MCP-shaped tool descriptors for the runtime to expose.

        Default: a single `handle` tool of class Routine. Modules with
        multiple distinct tool surfaces override this.
        """
        return [{
            "name": "handle",
            "class": "Routine",
            "description": getattr(self, "description", ""),
        }]

    # ── legacy chronicle helper (preserved) ──────────────────────────────

    def _log_outbound(self, context: dict[str, Any], destination: str, summary: str) -> None:
        chronicle = context.get("chronicle")
        if chronicle:
            chronicle.log(self.name, "outbound_data", {
                "destination": destination,
                "summary": summary[:500],
            })

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        pass

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        pass

    def __repr__(self) -> str:
        return f"<Module:{self.name} v{self.version}>"
```

- [ ] **Step 5: Create `tests/modules/__init__.py` if missing**

```bash
test -f tests/modules/__init__.py || touch tests/modules/__init__.py
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
pytest tests/modules/test_base.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Run the full test suite to confirm no regression**

```bash
pytest -x -q
```

Expected: green. Existing modules call `handle()` only; the new abstract `manifest()` raises if invoked but is never invoked during existing tests because nothing calls it yet.

- [ ] **Step 8: Commit**

```bash
git add nexus/modules/base.py tests/modules/test_base.py tests/modules/__init__.py
git commit -m "feat(modules): add manifest() + tools() to NexusModule ABC"
```

---

## Task 5 · Aegis · `check_capability` (capability arbiter)

**Why:** Spec §4.5 + §9. Every tool call routes through `aegis.check_capability()` to determine Allow / Prompt / Deny based on the manifest, trust tier, and permission grants. This task adds the method (with an in-memory grants store for now — workspace persistence is Phase 3).

**Files:**
- Modify: `nexus/kernel/aegis.py`
- Create: `tests/kernel/test_aegis_capabilities.py`

- [ ] **Step 1: Write the failing test**

Create `tests/kernel/test_aegis_capabilities.py`:

```python
"""Tests for Aegis.check_capability — the capability arbiter."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexus.kernel.aegis import Aegis, CapabilityDecision, Verdict
from nexus.agents.manifest import Manifest, PermissionClass


def _aider_manifest() -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": "aider",
        "name": "aider",
        "version": "1.0.0",
        "system": False,
        "publisher": {"type": "org", "handle": "Aider-AI"},
        "category": "coding",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [
                {"name": "edit_file", "class": "Notable", "scope": "fs.write.workspace"},
                {"name": "search_repo", "class": "Routine"},
            ],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["fs.write.workspace"],
                "Sensitive": ["process.shell"],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "aider-mcp"},
        "trust": {"floor": 0.55, "default_tier": "ADVISOR"},
    })


@pytest.fixture
def aegis(tmp_path):
    db = tmp_path / "aegis.sqlite"
    a = Aegis(str(db))
    a.register_manifest(_aider_manifest())
    return a


def test_routine_capability_always_allowed(aegis):
    d = aegis.check_capability("aider", "fs.read.workspace")
    assert d.verdict is Verdict.ALLOW


def test_undeclared_capability_denied(aegis):
    d = aegis.check_capability("aider", "fs.write.home")
    assert d.verdict is Verdict.DENY
    assert "undeclared" in d.reason.lower()


def test_notable_at_observer_tier_prompts(aegis):
    # trust starts at 0.0 (OBSERVER) for new agents
    d = aegis.check_capability("aider", "fs.write.workspace")
    assert d.verdict is Verdict.PROMPT
    assert d.permission_class is PermissionClass.NOTABLE


def test_notable_at_executor_tier_auto_grants(aegis):
    # bump trust to Executor (0.75+)
    aegis.set_trust("aider", 0.80)
    d = aegis.check_capability("aider", "fs.write.workspace")
    assert d.verdict is Verdict.ALLOW
    assert "executor" in d.reason.lower() or "auto" in d.reason.lower()


def test_sensitive_at_executor_still_prompts(aegis):
    aegis.set_trust("aider", 0.80)
    d = aegis.check_capability("aider", "process.shell")
    assert d.verdict is Verdict.PROMPT
    assert d.permission_class is PermissionClass.SENSITIVE


def test_workspace_grant_overrides_prompt(aegis):
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d.verdict is Verdict.ALLOW


def test_grant_does_not_leak_across_workspaces(aegis):
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="other")
    assert d.verdict is Verdict.PROMPT


def test_trust_collapse_revokes_grants(aegis):
    aegis.set_trust("aider", 0.80)
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    aegis.set_trust("aider", 0.40)  # collapse below 0.50
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d.verdict is Verdict.PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/kernel/test_aegis_capabilities.py -v
```

Expected: ImportError on `CapabilityDecision`, `Verdict`, and the new methods.

- [ ] **Step 3: Extend `nexus/kernel/aegis.py`**

Open `nexus/kernel/aegis.py` and append (after the existing `Aegis` class methods but inside the file). First, add imports at the top — find the existing `from typing import Any, Optional` and add below:

```python
from dataclasses import dataclass
from enum import Enum

from nexus.agents.manifest import Manifest, PermissionClass
```

Then before the `Aegis` class, add:

```python
class Verdict(str, Enum):
    ALLOW = "ALLOW"
    PROMPT = "PROMPT"
    DENY = "DENY"


@dataclass(frozen=True)
class CapabilityDecision:
    verdict: Verdict
    reason: str
    permission_class: PermissionClass | None = None
```

Then add these methods on `Aegis` (inside the class). Place them after the existing trust methods (after `set_trust` / `get_trust` / `get_tier` — whatever order they're in):

```python
    # ── manifest registry ────────────────────────────────────────────────

    def register_manifest(self, manifest: Manifest) -> None:
        """Register an agent's manifest so check_capability can read it."""
        if not hasattr(self, "_manifests"):
            self._manifests: dict[str, Manifest] = {}
        self._manifests[manifest.slug] = manifest
        # Seed trust at the manifest's floor if not set
        if self.get_trust(manifest.slug) == 0.0 and manifest.trust.floor > 0:
            self.set_trust(manifest.slug, manifest.trust.floor)

    def get_manifest(self, slug: str) -> Manifest | None:
        return getattr(self, "_manifests", {}).get(slug)

    # ── grant storage (in-memory for Phase 1; SQLite in Phase 3) ────────

    def _grants_table(self) -> dict[tuple[str, str | None], set[str]]:
        if not hasattr(self, "_grants"):
            self._grants: dict[tuple[str, str | None], set[str]] = {}
        return self._grants

    def grant(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> None:
        """Record an explicit user grant. workspace_id=None means global."""
        table = self._grants_table()
        key = (agent_slug, workspace_id)
        table.setdefault(key, set()).add(capability)
        self._log_chronicle("permission_granted", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })

    def revoke(
        self,
        agent_slug: str,
        capability: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Revoke one capability or, if capability is None, all grants for this agent in this scope."""
        table = self._grants_table()
        key = (agent_slug, workspace_id)
        if capability is None:
            table.pop(key, None)
        elif key in table:
            table[key].discard(capability)
        self._log_chronicle("permission_revoked", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })

    def _has_grant(self, agent_slug: str, capability: str, workspace_id: str | None) -> bool:
        table = self._grants_table()
        if capability in table.get((agent_slug, workspace_id), set()):
            return True
        # Also check the global scope (workspace_id=None)
        if workspace_id is not None and capability in table.get((agent_slug, None), set()):
            return True
        return False

    # ── trust collapse handler ──────────────────────────────────────────

    def set_trust(self, agent_slug: str, score: float) -> None:
        # Preserve existing set_trust behaviour (write to DB). If parent
        # already defines set_trust, this becomes an override; we call
        # through, then handle collapse.
        score = max(0.0, min(1.0, score))
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trust (module, score, updated_at) VALUES (?,?,?)",
                (agent_slug, score, self._now()),
            )
        # Trust collapse: revoke every auto-grant (i.e., every grant we
        # made implicitly through the Executor auto-grant path). For
        # Phase 1, we treat ALL grants as user-pinned and only revoke
        # if score falls below 0.50 — the user can re-grant.
        if score < 0.50:
            table = self._grants_table()
            removed: list[tuple[str, str | None, str]] = []
            for (agent, ws), caps in list(table.items()):
                if agent != agent_slug:
                    continue
                for cap in list(caps):
                    caps.discard(cap)
                    removed.append((agent, ws, cap))
                if not caps:
                    table.pop((agent, ws), None)
            if removed:
                self._log_chronicle("trust_collapse", {
                    "agent": agent_slug,
                    "score": score,
                    "revoked": [
                        {"capability": c, "workspace_id": ws} for _, ws, c in removed
                    ],
                })

    # ── the arbiter ─────────────────────────────────────────────────────

    def check_capability(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> CapabilityDecision:
        """Decide whether `agent_slug` may use `capability` in `workspace_id`.

        Algorithm:
          1. Find the manifest. No manifest → DENY.
          2. Find which class the manifest declares this capability under.
             Not declared → DENY (undeclared).
          3. Routine → always ALLOW.
          4. If user has an explicit grant for this scope → ALLOW.
          5. Notable + trust ≥ 0.75 (EXECUTOR) → ALLOW (auto-grant).
          6. Privileged → never auto-grant; must be granted explicitly
             via Settings → PROMPT (effectively DENY for auto paths).
          7. Otherwise → PROMPT.
        """
        manifest = self.get_manifest(agent_slug)
        if manifest is None:
            return CapabilityDecision(
                Verdict.DENY,
                f"no manifest registered for agent {agent_slug!r}",
            )

        cls = manifest.declares(capability)
        if cls is None:
            return CapabilityDecision(
                Verdict.DENY,
                f"capability {capability!r} undeclared in manifest",
            )

        # Routine — silent forever
        if cls is PermissionClass.ROUTINE:
            return CapabilityDecision(Verdict.ALLOW, "routine", cls)

        # Explicit grant trumps everything below
        if self._has_grant(agent_slug, capability, workspace_id):
            return CapabilityDecision(Verdict.ALLOW, "explicit grant", cls)

        trust = self.get_trust(agent_slug)

        # Trust-gated auto-grant
        if cls is PermissionClass.NOTABLE and trust >= 0.75:
            return CapabilityDecision(
                Verdict.ALLOW,
                f"executor tier auto-grant (trust={trust:.2f})",
                cls,
            )

        # Privileged — never granted from a check; user must use Settings
        if cls is PermissionClass.PRIVILEGED:
            return CapabilityDecision(
                Verdict.PROMPT,
                "privileged capabilities require Settings → Security",
                cls,
            )

        return CapabilityDecision(
            Verdict.PROMPT,
            f"{cls.value.lower()} capability requires user approval",
            cls,
        )
```

Notes:
- If `Aegis` already has a `set_trust` method with a different signature, **preserve the existing signature** and add the trust-collapse logic inside it; don't introduce a conflicting overload. Inspect the existing method first by reading `nexus/kernel/aegis.py` end-to-end and edit in place.

- [ ] **Step 4: Create `tests/kernel/__init__.py` if missing**

```bash
test -f tests/kernel/__init__.py || touch tests/kernel/__init__.py
```

- [ ] **Step 5: Run the new tests**

```bash
pytest tests/kernel/test_aegis_capabilities.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Confirm no regressions**

```bash
pytest -x -q
```

Expected: green. The existing `Aegis` tests pass because we extended, not replaced.

- [ ] **Step 7: Commit**

```bash
git add nexus/kernel/aegis.py tests/kernel/test_aegis_capabilities.py tests/kernel/__init__.py
git commit -m "feat(aegis): add check_capability + grants + trust-collapse revocation"
```

---

## Task 6 · Aegis · `fs()` filesystem broker

**Why:** Spec §4.5 + §9. All agent filesystem access flows through `aegis.fs()`, which enforces workspace-root containment and capability checks.

**Files:**
- Modify: `nexus/kernel/aegis.py`
- Create: `tests/kernel/test_aegis_fs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/kernel/test_aegis_fs.py`:

```python
"""Tests for Aegis.fs — the filesystem broker."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.agents.manifest import Manifest


def _agent_manifest(slug: str, declared_routine: list[str], declared_notable: list[str]) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": slug, "name": slug, "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [],
            "declared": {
                "Routine": declared_routine,
                "Notable": declared_notable,
                "Sensitive": [],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


def test_read_inside_workspace_allowed(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()
    (root / "hello.txt").write_text("hi")

    with aegis.fs("a", root / "hello.txt", mode="r", workspace_roots=[root]) as f:
        assert f.read() == "hi"


def test_read_outside_workspace_denied(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("nope")

    with pytest.raises(PermissionDenied):
        aegis.fs("a", outside, mode="r", workspace_roots=[root])


def test_write_without_declared_notable_denied(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    # declares ONLY read
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()

    with pytest.raises(PermissionDenied):
        aegis.fs("a", root / "out.txt", mode="w", workspace_roots=[root])


def test_write_with_grant_allowed(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], ["fs.write.workspace"]))
    aegis.grant("a", "fs.write.workspace", workspace_id="ws-1")

    root = tmp_path / "ws"
    root.mkdir()

    with aegis.fs("a", root / "out.txt", mode="w",
                  workspace_roots=[root], workspace_id="ws-1") as f:
        f.write("ok")

    assert (root / "out.txt").read_text() == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/kernel/test_aegis_fs.py -v
```

Expected: `Aegis.fs` does not exist.

- [ ] **Step 3: Add `fs()` to `nexus/kernel/aegis.py`**

Append within the `Aegis` class:

```python
    # ── filesystem broker ───────────────────────────────────────────────

    def fs(
        self,
        agent_slug: str,
        path,
        *,
        mode: str = "r",
        workspace_roots: list = None,
        workspace_id: str | None = None,
    ):
        """Mediated file access for an agent.

        Returns an open file handle (context manager) or raises
        PermissionDenied. Logs every call to Chronicle.
        """
        from pathlib import Path

        target = Path(path).resolve()
        roots = [Path(r).resolve() for r in (workspace_roots or [])]

        # 1. Containment: must be under at least one root
        if not any(_is_within(target, r) for r in roots):
            self._log_chronicle("fs_access_denied", {
                "agent": agent_slug, "path": str(target),
                "mode": mode, "reason": "outside_workspace_roots",
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"fs:{mode}:{target}")

        # 2. Capability
        cap = "fs.write.workspace" if any(c in mode for c in ("w", "a", "+")) else "fs.read.workspace"
        decision = self.check_capability(agent_slug, cap, workspace_id=workspace_id)
        if decision.verdict.value != "ALLOW":
            self._log_chronicle("fs_access_denied", {
                "agent": agent_slug, "path": str(target),
                "mode": mode, "reason": decision.reason,
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"fs:{mode}:{target}")

        self._log_chronicle("fs_access", {
            "agent": agent_slug, "path": str(target),
            "mode": mode, "workspace_id": workspace_id,
        })
        return open(target, mode)
```

Add this helper at the module level (above the `Aegis` class):

```python
def _is_within(child, parent) -> bool:
    """True if child is parent or a descendant of parent."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/kernel/test_aegis_fs.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Confirm no regressions**

```bash
pytest -x -q
```

- [ ] **Step 6: Commit**

```bash
git add nexus/kernel/aegis.py tests/kernel/test_aegis_fs.py
git commit -m "feat(aegis): add fs() broker with workspace-root containment"
```

---

## Task 7 · Aegis · `network()` gateway

**Why:** Spec §4.5 + §9.5 + §15. The kernel must perform zero direct network I/O. All outbound goes through `aegis.network()` which enforces the agent's declared `network.outbound.<domain>` allow-list, rate-limits per agent, and logs to Chronicle.

**Files:**
- Modify: `nexus/kernel/aegis.py`
- Create: `tests/kernel/test_aegis_network.py`

- [ ] **Step 1: Write the failing test**

Create `tests/kernel/test_aegis_network.py`:

```python
"""Tests for Aegis.network — the outbound HTTP gateway."""
from __future__ import annotations

import pytest
import httpx

from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.agents.manifest import Manifest


def _agent_with_domains(slug: str, domains: list[str]) -> Manifest:
    declared_notable = [f"network.outbound.{d}" for d in domains]
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": slug, "name": slug, "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [],
            "declared": {
                "Routine": [], "Sensitive": [], "Privileged": [],
                "Notable": declared_notable,
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "aegis.db"))
    a.register_manifest(_agent_with_domains("a", ["example.com"]))
    a.grant("a", "network.outbound.example.com")  # global grant
    return a


@pytest.mark.asyncio
async def test_allowed_domain_passes(aegis, respx_mock):
    """A declared + granted domain returns the response."""
    respx_mock.get("https://example.com/").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    resp = await aegis.network("a", "https://example.com/", method="GET")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_undeclared_domain_denied(aegis):
    with pytest.raises(PermissionDenied):
        await aegis.network("a", "https://evil.com/", method="GET")


@pytest.mark.asyncio
async def test_declared_but_not_granted_prompts(aegis):
    aegis.register_manifest(_agent_with_domains("b", ["example.com"]))
    # No grant; default trust is OBSERVER; Notable requires grant or Executor
    with pytest.raises(PermissionDenied):
        await aegis.network("b", "https://example.com/", method="GET")


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_threshold(aegis, respx_mock):
    """Per-agent rate limit (default 60 rpm) blocks burst."""
    respx_mock.get("https://example.com/").mock(
        return_value=httpx.Response(200, json={})
    )
    aegis.set_rate_limit("a", per_minute=2)
    await aegis.network("a", "https://example.com/", method="GET")
    await aegis.network("a", "https://example.com/", method="GET")
    with pytest.raises(PermissionDenied):
        await aegis.network("a", "https://example.com/", method="GET")
```

If `respx` is not yet a test dep, add it to `pyproject.toml` `[project.optional-dependencies].test`:

```toml
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "jsonschema>=4.0",
    "respx>=0.21",
]
```

Then `pip install -e ".[test]"`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/kernel/test_aegis_network.py -v
```

Expected: `Aegis.network` and `set_rate_limit` don't exist.

- [ ] **Step 3: Add `network()` and rate-limiting to `nexus/kernel/aegis.py`**

Add at the top of `aegis.py` next to the other imports:

```python
import time
from collections import deque
from urllib.parse import urlparse
```

Append within the `Aegis` class:

```python
    # ── network gateway ─────────────────────────────────────────────────

    DEFAULT_RATE_LIMIT_PER_MIN = 60

    def set_rate_limit(self, agent_slug: str, per_minute: int) -> None:
        if not hasattr(self, "_rate_limits"):
            self._rate_limits: dict[str, int] = {}
        self._rate_limits[agent_slug] = per_minute

    def _rate_limit(self, agent_slug: str) -> int:
        return getattr(self, "_rate_limits", {}).get(agent_slug, self.DEFAULT_RATE_LIMIT_PER_MIN)

    def _request_log(self, agent_slug: str) -> deque:
        if not hasattr(self, "_req_log"):
            self._req_log: dict[str, deque] = {}
        return self._req_log.setdefault(agent_slug, deque())

    def _check_rate_limit(self, agent_slug: str) -> bool:
        """Return True if a request is allowed; False if rate-limited."""
        log = self._request_log(agent_slug)
        now = time.monotonic()
        cutoff = now - 60.0
        while log and log[0] < cutoff:
            log.popleft()
        if len(log) >= self._rate_limit(agent_slug):
            return False
        log.append(now)
        return True

    async def network(
        self,
        agent_slug: str,
        url: str,
        *,
        method: str = "GET",
        workspace_id: str | None = None,
        **httpx_kwargs,
    ):
        """Outbound HTTP for an agent. Returns an httpx.Response.

        Raises PermissionDenied if the agent's manifest doesn't declare
        the URL's domain, if the user hasn't granted it, if the agent
        is over its rate limit, or if Aegis is otherwise denying.
        """
        import httpx as _httpx

        domain = urlparse(url).hostname or ""
        capability = f"network.outbound.{domain}"

        decision = self.check_capability(agent_slug, capability, workspace_id=workspace_id)
        if decision.verdict.value != "ALLOW":
            self._log_chronicle("network_request_denied", {
                "agent": agent_slug, "url": url, "method": method,
                "reason": decision.reason, "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"network:{method}:{url}")

        if not self._check_rate_limit(agent_slug):
            self._log_chronicle("network_request_denied", {
                "agent": agent_slug, "url": url, "method": method,
                "reason": "rate_limit",
                "limit_per_minute": self._rate_limit(agent_slug),
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"network:rate_limit:{url}")

        async with _httpx.AsyncClient() as client:
            resp = await client.request(method, url, **httpx_kwargs)

        self._log_chronicle("network_request", {
            "agent": agent_slug, "url": url, "method": method,
            "status": resp.status_code,
            "bytes_in": len(resp.content),
            "workspace_id": workspace_id,
        })
        return resp
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/kernel/test_aegis_network.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Confirm no regressions**

```bash
pytest -x -q
```

- [ ] **Step 6: Commit**

```bash
git add nexus/kernel/aegis.py tests/kernel/test_aegis_network.py pyproject.toml
git commit -m "feat(aegis): add network() gateway with allow-list + rate limit + chronicle log"
```

---

## Task 8 · `InProcessAgent` adapter

**Why:** Spec §13.1. Built-in modules need a uniform `call_tool()` surface so Cortex and the runtime treat them identically to subprocess MCP agents. Zero subprocess cost; goes through Aegis like every other agent.

**Files:**
- Modify: `nexus/agents/in_process_agent.py`
- Create: `tests/agents/test_in_process_agent.py` (already empty)

- [ ] **Step 1: Write the failing test**

Replace `tests/agents/test_in_process_agent.py`:

```python
"""Tests for InProcessAgent — the adapter that makes a NexusModule speak the agent protocol."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule
from nexus.kernel.aegis import Aegis, Verdict


class _GreeterModule(NexusModule):
    name = "greeter"
    description = "says hi"
    version = "1.0.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "greeter", "name": "greeter", "version": "1.0.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:greeter", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "greet", "patterns": ["^hi"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": []},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        return f"hello, {message}"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.register_manifest(_GreeterModule.manifest())
    return a


@pytest.mark.asyncio
async def test_call_tool_dispatches_to_module(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "world", "context": {}})
    assert result == "hello, world"


@pytest.mark.asyncio
async def test_paused_agent_refuses_calls(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    agent.pause()
    with pytest.raises(RuntimeError) as exc:
        await agent.call_tool("handle", {"message": "x", "context": {}})
    assert "paused" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_woken_agent_responds_again(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    agent.pause()
    agent.wake()
    result = await agent.call_tool("handle", {"message": "x", "context": {}})
    assert result == "hello, x"


@pytest.mark.asyncio
async def test_unknown_tool_raises(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    with pytest.raises(KeyError):
        await agent.call_tool("nonexistent", {})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_in_process_agent.py -v
```

Expected: `InProcessAgent` is empty / undefined.

- [ ] **Step 3: Implement `nexus/agents/in_process_agent.py`**

```python
"""
InProcessAgent — adapter that wraps a NexusModule and exposes the
same `call_tool()` interface as an external MCP-served agent.

Built-in modules run as InProcessAgents; the runtime treats them
identically to subprocess agents but pays no IPC cost.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class InProcessAgent:
    def __init__(self, module: NexusModule, *, aegis: "Aegis | None" = None):
        self._module = module
        self._aegis = aegis
        self._paused = False
        self._manifest = type(module).manifest()
        # Build a name → tool descriptor map
        self._tools_by_name = {t["name"]: t for t in module.tools()}

    @property
    def slug(self) -> str:
        return self._manifest.slug

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def wake(self) -> None:
        self._paused = False

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        if self._paused:
            raise RuntimeError(
                f"agent {self.slug!r} is paused; switch to its workspace to wake it"
            )

        if tool_name not in self._tools_by_name:
            raise KeyError(
                f"agent {self.slug!r} has no tool {tool_name!r}; "
                f"declared: {list(self._tools_by_name)}"
            )

        # Tools map onto module methods. For now the only tool is `handle`.
        if tool_name == "handle":
            message = args.get("message", "")
            context = args.get("context", {})
            return await self._module.handle(message, context)

        # Future: dispatch to other declared tools by method name.
        method = getattr(self._module, tool_name, None)
        if method is None:
            raise AttributeError(
                f"agent {self.slug!r} declares tool {tool_name!r} but the "
                f"module has no method by that name"
            )
        return await method(**args)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/agents/test_in_process_agent.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add nexus/agents/in_process_agent.py tests/agents/test_in_process_agent.py
git commit -m "feat(agents): add InProcessAgent adapter with pause/wake"
```

---

## Task 9 · `MCPAgent` adapter

**Why:** Spec §5.1, §5.3. Third-party agents run as subprocesses that speak MCP over stdio. The runtime needs a uniform `call_tool()` adapter on top of the `mcp` Python client.

**Files:**
- Modify: `nexus/agents/mcp_agent.py`
- Create: `tests/agents/test_mcp_agent.py` (already empty)

- [ ] **Step 1: Write the failing test**

Replace `tests/agents/test_mcp_agent.py`:

```python
"""Tests for MCPAgent — the subprocess MCP-over-stdio adapter.

These tests run a tiny in-repo fake MCP server (Python script) so we
don't depend on any external agent being installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nexus.agents.mcp_agent import MCPAgent
from nexus.agents.manifest import Manifest


def _echo_manifest(command: list[str]) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": "echoer", "name": "echoer", "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [{"name": "echo", "patterns": ["echo"], "weight": 1.0}],
        "capabilities": {
            "tools": [{"name": "echo", "class": "Routine"}],
            "declared": {"Routine": []},
        },
        "runtime": {"transport": "stdio", "command": command[0], "args": command[1:]},
    })


@pytest.fixture
def fake_server_path(tmp_path):
    """Write a tiny MCP server stub that echoes."""
    path = tmp_path / "echo_server.py"
    path.write_text(
        "import asyncio, sys\n"
        "from mcp.server import Server\n"
        "from mcp.server.stdio import stdio_server\n"
        "from mcp.types import Tool, TextContent\n"
        "\n"
        "srv = Server('echoer')\n"
        "\n"
        "@srv.list_tools()\n"
        "async def list_tools():\n"
        "    return [Tool(name='echo', description='echo', inputSchema={'type':'object','properties':{'message':{'type':'string'}}})]\n"
        "\n"
        "@srv.call_tool()\n"
        "async def call_tool(name, arguments):\n"
        "    return [TextContent(type='text', text=f\"echo:{arguments.get('message','')}\")]\n"
        "\n"
        "async def main():\n"
        "    async with stdio_server() as (r, w):\n"
        "        await srv.run(r, w, srv.create_initialization_options())\n"
        "\n"
        "asyncio.run(main())\n"
    )
    return path


@pytest.mark.asyncio
async def test_launches_subprocess_and_calls_tool(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    try:
        result = await agent.call_tool("echo", {"message": "hi"})
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_pause_and_wake_preserve_state(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    try:
        agent.pause()
        with pytest.raises(RuntimeError):
            await agent.call_tool("echo", {"message": "x"})
        agent.wake()
        result = await agent.call_tool("echo", {"message": "back"})
        assert "echo:back" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_stop_kills_subprocess(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    pid = agent.pid
    assert pid is not None
    await agent.stop()
    # After stop, the process should not exist
    import os
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_mcp_agent.py -v
```

Expected: `MCPAgent` is empty.

- [ ] **Step 3: Implement `nexus/agents/mcp_agent.py`**

```python
"""
MCPAgent — adapter that launches an external MCP server subprocess and
exposes the same `call_tool()` interface as InProcessAgent.

Uses the `mcp` Python library's stdio client to communicate with the
subprocess. Supports pause (SIGSTOP) and wake (SIGCONT).
"""
from __future__ import annotations

import os
import signal
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nexus.agents.manifest import Manifest


class MCPAgent:
    def __init__(self, manifest: Manifest):
        self._manifest = manifest
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._pid: int | None = None
        self._paused = False

    @property
    def slug(self) -> str:
        return self._manifest.slug

    @property
    def pid(self) -> int | None:
        return self._pid

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._session is not None:
            return
        rc = self._manifest.runtime
        params = StdioServerParameters(
            command=rc.command,
            args=rc.args,
            env={k: os.environ[k] for k in rc.env_keys if k in os.environ},
        )
        self._stack = AsyncExitStack()
        reader, writer = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(reader, writer))
        await self._session.initialize()
        # Capture the subprocess PID from the underlying transport. The
        # mcp library exposes it on the connection's process handle.
        self._pid = getattr(self._stack, "_subprocess_pid", None) or \
                    getattr(reader, "_subprocess_pid", None)
        # Fallback: most stdio_client implementations attach the Popen
        # object to the writer; capture its pid if available.
        if self._pid is None:
            proc = getattr(writer, "_process", None) or getattr(reader, "_process", None)
            if proc is not None and hasattr(proc, "pid"):
                self._pid = proc.pid

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        # The mcp library's stdio_client should reap the child on aclose.
        # If we still have a PID, double-tap it.
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self._pid = None

    # ── pause / wake ────────────────────────────────────────────────────

    def pause(self) -> None:
        self._paused = True
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                pass

    def wake(self) -> None:
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGCONT)
            except (ProcessLookupError, PermissionError):
                pass
        self._paused = False

    # ── tool call ───────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, args: dict[str, Any]):
        if self._paused:
            raise RuntimeError(f"agent {self.slug!r} is paused; wake before calling")
        if self._session is None:
            raise RuntimeError(f"agent {self.slug!r} is not started; call start() first")
        return await self._session.call_tool(tool_name, arguments=args)
```

Note: the exact attribute name for the subprocess PID varies across `mcp` library versions. If the tests can't pick up `pid`, inspect with `pip show mcp` and adjust the fallback chain. The Phase 2 migration will normalise this.

- [ ] **Step 4: Run tests**

```bash
pytest tests/agents/test_mcp_agent.py -v
```

Expected: 3 passed.

If `pid` retrieval fails (the third test fails with `pid is None`), debug by inspecting the `mcp` library:

```bash
python -c "from mcp.client.stdio import stdio_client; help(stdio_client)"
```

…and add the right attribute to the fallback chain.

- [ ] **Step 5: Commit**

```bash
git add nexus/agents/mcp_agent.py tests/agents/test_mcp_agent.py
git commit -m "feat(agents): add MCPAgent subprocess adapter with SIGSTOP/SIGCONT"
```

---

## Task 10 · Integration smoke test

**Why:** Confirm the new pieces wire together. We don't yet have the workspace layer, but we can assemble an Aegis + manifest + InProcessAgent end-to-end and prove a capability check actually gates a tool call.

**Files:**
- Create: `tests/agents/test_foundation_integration.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke test for the Phase 1 foundation."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis, Verdict
from nexus.modules.base import NexusModule


class _FileWriter(NexusModule):
    """A built-in module that writes a file via aegis.fs()."""
    name = "writer"
    description = "writes files"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "writer", "name": "writer", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:writer", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "write", "patterns": ["write"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Notable",
                           "scope": "fs.write.workspace"}],
                "declared": {
                    "Routine": [],
                    "Notable": ["fs.write.workspace"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        aegis = context["aegis"]
        ws_root = context["workspace_root"]
        target = ws_root / "out.txt"
        with aegis.fs("writer", target, mode="w",
                      workspace_roots=[ws_root], workspace_id="ws-1") as f:
            f.write(message)
        return f"wrote {target}"


@pytest.mark.asyncio
async def test_capability_gates_tool_call(tmp_path):
    """Without a grant or Executor trust, the tool's fs.write call is denied."""
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_FileWriter.manifest())

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    # OBSERVER trust + no grant → PROMPT verdict → PermissionDenied at write
    from nexus.kernel.aegis import PermissionDenied
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "hi", "context": context})


@pytest.mark.asyncio
async def test_executor_trust_enables_write(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_FileWriter.manifest())
    aegis.set_trust("writer", 0.80)  # EXECUTOR

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    result = await agent.call_tool("handle", {"message": "ok", "context": context})
    assert "wrote" in result
    assert (ws_root / "out.txt").read_text() == "ok"


@pytest.mark.asyncio
async def test_trust_collapse_revokes_then_denies(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.register_manifest(_FileWriter.manifest())

    # User grants explicitly
    aegis.grant("writer", "fs.write.workspace", workspace_id="ws-1")
    aegis.set_trust("writer", 0.30)  # ADVISOR — would normally prompt, but grant exists

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    # Works while granted
    await agent.call_tool("handle", {"message": "first", "context": context})
    assert (ws_root / "out.txt").read_text() == "first"

    # Trust collapses → grants revoked → next call denies
    aegis.set_trust("writer", 0.20)  # below 0.50
    from nexus.kernel.aegis import PermissionDenied
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "second", "context": context})
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/agents/test_foundation_integration.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Run the full suite**

```bash
pytest -x -q
```

Expected: all green. The foundation is in place.

- [ ] **Step 4: Commit**

```bash
git add tests/agents/test_foundation_integration.py
git commit -m "test(agents): end-to-end foundation smoke test"
```

---

## Task 11 · Document the foundation phase

**Why:** The next phase (migration) needs a one-page reference for the new types.

**Files:**
- Create: `docs/agents/foundation.md`

- [ ] **Step 1: Write the doc**

```markdown
# Agent Runtime Foundation (Phase 1)

The minimum runtime surface every NEXUS agent — built-in or third-party —
goes through.

## Manifest

`nexus.agents.manifest.Manifest` — pydantic v2 model. See
`nexus/schemas/manifest.v1.json` for the JSON Schema.

```python
from nexus.agents.manifest import Manifest
m = Manifest.from_path("/path/to/manifest.json")
```

## Permission classes

`nexus.agents.manifest.PermissionClass` — `ROUTINE / NOTABLE / SENSITIVE / PRIVILEGED`.

A tool descriptor names its class via `"class": "Notable"` in the JSON.
The class drives every Aegis decision (Section 9 of the design spec).

## Aegis

Three new public methods on `nexus.kernel.aegis.Aegis`:

- `register_manifest(manifest)` — make an agent's manifest visible to the arbiter.
- `check_capability(agent_slug, capability, workspace_id=None) → CapabilityDecision`
  with `verdict ∈ {ALLOW, PROMPT, DENY}`.
- `fs(agent, path, mode=..., workspace_roots=[...], workspace_id=...)` — context-managed file handle, raises `PermissionDenied`.
- `network(agent, url, method="GET", workspace_id=..., **httpx_kwargs)` — async, returns `httpx.Response`, raises `PermissionDenied`.

Grants:
- `grant(agent, capability, workspace_id=None)` — workspace_id=None means global.
- `revoke(agent, capability=None, workspace_id=None)` — capability=None revokes all in scope.

Trust collapse (< 0.50) automatically revokes all grants for that agent.

## Agent adapters

- `nexus.agents.in_process_agent.InProcessAgent(module, aegis=...)` — wraps a `NexusModule`.
- `nexus.agents.mcp_agent.MCPAgent(manifest)` — subprocess MCP-over-stdio.

Both expose:
- `start()` (MCPAgent only) / `stop()` / `pause()` / `wake()`
- `async call_tool(tool_name, args) -> Any`
- `slug` property

## What's NOT here yet

- Workspaces (Phase 3).
- Routing changes (manifests aren't yet consulted by Cortex — Phase 2 wires the 9 built-ins in).
- First-use prompt UI / install review UI (Phase 4 + Phase 5).
- Network gateway for the existing LLM providers (Phase 6).

Cross-reference: `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/agents/foundation.md
git commit -m "docs(agents): foundation phase reference"
```

---

## Final · Phase 1 completion

- [ ] **Step 1: Run the full test suite once more**

```bash
pytest -q
```

Expected: all green.

- [ ] **Step 2: Run lint / type-check if configured**

```bash
# If the project has ruff/mypy configured:
ruff check nexus/agents/ nexus/kernel/aegis.py tests/ 2>/dev/null || true
mypy nexus/agents/ nexus/kernel/aegis.py 2>/dev/null || true
```

Treat warnings as warnings; only block on errors that touch the new files.

- [ ] **Step 3: Tag the milestone**

```bash
git tag -a phase-1-foundation -m "Phase 1 foundation complete: manifest, agent adapters, Aegis arbiter"
git log --oneline | head -15
```

Phase 1 is complete. The new types exist and are tested; nothing in the existing system is broken; the path is clear for Phase 2 (migrating the 9 built-ins onto manifests).

---

## Self-Review (against the design spec)

**1. Spec coverage check**

| Spec section | Implementing task | Notes |
|---|---|---|
| §4.5 Aegis grows capability/fs/network | Tasks 5, 6, 7 | `check_capability`, `fs`, `network` all added with chronicle logging |
| §5.1 Process model (in-process built-ins + external) | Tasks 8, 9 | `InProcessAgent` and `MCPAgent` both present |
| §5.4 Capability filter on tool calls | Task 10 integration test | Tool call → aegis.check → fs/network |
| §6 Manifest schema v1 (all fields) | Tasks 2, 3 | Pydantic model + JSON Schema export |
| §9.1 Four permission classes | Task 2 (enum), Task 5 (arbiter logic) | All four behave per spec |
| §9.4 Trust collapse revokes auto-grants | Task 5 | Tested in test_trust_collapse_revokes_grants and test_trust_collapse_revokes_then_denies |
| §9.5 Network gateway with allow-list + rate-limit + chronicle | Task 7 | Tested |
| §13.1 InProcessAgent shim | Task 8 | Built |

**2. Out of scope for Phase 1 (intentional):**
- Workspace layer (Phase 3).
- Migrating existing 9 modules to actually use the new manifest (Phase 2).
- First-use prompt UI (Phase 4).
- All new surfaces — Conversational, Cockpit, Spatial, Settings (Phase 5).
- LLM providers routing through `aegis.network()` (Phase 6).

These are explicitly deferred. The foundation lays the data model so each subsequent phase has a stable surface to build on.

**3. Placeholder scan:** all code blocks contain actual content; no TODO/TBD in the plan.

**4. Type consistency:** `Manifest`, `PermissionClass`, `Verdict`, `CapabilityDecision`, `InProcessAgent`, `MCPAgent` — all spelled identically across all tasks where they appear.

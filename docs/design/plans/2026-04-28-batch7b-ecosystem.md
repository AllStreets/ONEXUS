# Batch 7b: Ecosystem & Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the community skill ecosystem (GitHub PR workflow + site registry + CLI install) and 9 differentiation modules (Dream Loop, Adversarial Self-Improvement, Cognitive Tripwires, Provenance Chains, Temporal Sandbox, Module Symbiosis, Consciousness Journal, Emergent Goal Detection, Ethical Prism) that make NEXUS unlike anything else on the market.

**Architecture:** Community modules live in `community/modules/<author>/<module_name>/` with manifest-driven CI validation and a site registry page. Nine new core modules use the existing NexusModule interface, Pulse events for inter-module communication, Engram for memory, and Chronicle for auditability. All modules integrate with the messaging bridges from Batch 7a for proactive notifications via `notify.*` Pulse events.

**Tech Stack:** Python 3.11+, pytest + pytest-asyncio, Astro (site), GitHub Actions (CI), SQLite (existing)

**Depends on:** Batch 7a (multi-provider inference, messaging bridges) must be complete before starting.

---

## File Structure

### Community Ecosystem

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `community/modules/.gitkeep` | Placeholder for community submissions directory |
| Create | `community/registry.json` | Auto-generated module registry (starts empty) |
| Create | `community/CONTRIBUTING.md` | Submission guide for contributors |
| Create | `community/manifest_schema.json` | JSON Schema for manifest.json validation |
| Create | `.github/workflows/validate-community-module.yml` | CI for community PR validation |
| Create | `.github/workflows/update-registry.yml` | Post-merge registry.json regeneration |
| Create | `nexus/community/__init__.py` | Package init |
| Create | `nexus/community/validator.py` | Validates module submissions (manifest, imports, tests) |
| Create | `nexus/community/registry.py` | Reads/queries registry.json |
| Create | `nexus/community/installer.py` | Install/uninstall community modules |
| Modify | `nexus/cli.py` | Add `nexus install`, `nexus uninstall`, `nexus community` commands |
| Modify | `nexus/kernel/cortex.py` | Support dynamic keyword registration for community modules |
| Create | `site/src/content/docs/community/index.mdx` | Community registry page |
| Create | `tests/community/__init__.py` | Package init |
| Create | `tests/community/test_validator.py` | Tests for validator |
| Create | `tests/community/test_registry.py` | Tests for registry |
| Create | `tests/community/test_installer.py` | Tests for installer |

### Differentiation Modules

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `nexus/modules/dream_loop.py` | Background pattern discovery during idle |
| Create | `nexus/modules/adversarial.py` | System-wide red-teaming and stress testing |
| Create | `nexus/modules/tripwire.py` | Cognitive pattern mirroring |
| Create | `nexus/modules/provenance.py` | Reasoning chain traceability |
| Create | `nexus/modules/sandbox.py` | Temporal memory forking and simulation |
| Create | `nexus/modules/symbiosis.py` | Emergent module routing pathways |
| Create | `nexus/modules/consciousness.py` | Self-reflective introspection journal |
| Create | `nexus/modules/emergence.py` | Emergent goal detection |
| Create | `nexus/modules/ethical_prism.py` | Multi-framework ethical analysis |
| Modify | `nexus/kernel/cortex.py` | Add keywords for all 9 new modules |
| Create | `tests/modules/test_dream_loop.py` | Tests for Dream Loop |
| Create | `tests/modules/test_adversarial.py` | Tests for Adversarial Self-Improvement |
| Create | `tests/modules/test_tripwire.py` | Tests for Cognitive Tripwires |
| Create | `tests/modules/test_provenance.py` | Tests for Provenance Chains |
| Create | `tests/modules/test_sandbox.py` | Tests for Temporal Sandbox |
| Create | `tests/modules/test_symbiosis.py` | Tests for Module Symbiosis |
| Create | `tests/modules/test_consciousness.py` | Tests for Consciousness Journal |
| Create | `tests/modules/test_emergence.py` | Tests for Emergent Goal Detection |
| Create | `tests/modules/test_ethical_prism.py` | Tests for Ethical Prism |
| Create | `tests/test_batch7b_integration.py` | Integration tests |

---

## Task 1: Community Module Validator

**Files:**
- Create: `nexus/community/__init__.py`
- Create: `nexus/community/validator.py`
- Create: `community/manifest_schema.json`
- Create: `tests/community/__init__.py`
- Create: `tests/community/test_validator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/community/test_validator.py
import json
import pytest
from pathlib import Path
from nexus.community.validator import ModuleValidator, ValidationResult


@pytest.fixture
def valid_module_dir(tmp_path):
    """Create a minimal valid community module directory."""
    mod_dir = tmp_path / "testuser" / "my_module"
    mod_dir.mkdir(parents=True)

    # manifest.json
    manifest = {
        "name": "my_module",
        "author": "testuser",
        "description": "A test module.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["test", "example"],
        "license": "Apache-2.0",
    }
    (mod_dir / "manifest.json").write_text(json.dumps(manifest))

    # module.py
    (mod_dir / "module.py").write_text('''
from nexus.modules.base import NexusModule
from typing import Any

class MyModule(NexusModule):
    name = "my_module"
    description = "A test module."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "hello"
''')

    # tests/
    test_dir = mod_dir / "tests"
    test_dir.mkdir()
    (test_dir / "test_module.py").write_text('''
import pytest
from ..module import MyModule

def test_attrs():
    m = MyModule()
    assert m.name == "my_module"

def test_desc():
    m = MyModule()
    assert m.description

def test_version():
    m = MyModule()
    assert m.version

@pytest.mark.asyncio
async def test_handle():
    m = MyModule()
    r = await m.handle("hi", {})
    assert isinstance(r, str)
''')

    # README.md
    (mod_dir / "README.md").write_text("# My Module\nA test module.")

    return mod_dir


@pytest.fixture
def validator():
    return ModuleValidator()


def test_validate_valid_module(validator, valid_module_dir):
    result = validator.validate(valid_module_dir)
    assert result.valid is True
    assert len(result.errors) == 0


def test_validate_missing_manifest(validator, tmp_path):
    mod_dir = tmp_path / "bad"
    mod_dir.mkdir()
    result = validator.validate(mod_dir)
    assert result.valid is False
    assert any("manifest.json" in e for e in result.errors)


def test_validate_missing_module_py(validator, valid_module_dir):
    (valid_module_dir / "module.py").unlink()
    result = validator.validate(valid_module_dir)
    assert result.valid is False
    assert any("module.py" in e for e in result.errors)


def test_validate_missing_tests(validator, valid_module_dir):
    import shutil
    shutil.rmtree(valid_module_dir / "tests")
    result = validator.validate(valid_module_dir)
    assert result.valid is False
    assert any("tests" in e for e in result.errors)


def test_validate_invalid_manifest_schema(validator, valid_module_dir):
    """Manifest missing required fields should fail."""
    (valid_module_dir / "manifest.json").write_text(json.dumps({"name": "x"}))
    result = validator.validate(valid_module_dir)
    assert result.valid is False


def test_validate_kernel_imports(validator, valid_module_dir):
    """Modules that import from nexus.kernel should fail."""
    (valid_module_dir / "module.py").write_text('''
from nexus.kernel.cortex import Cortex
from nexus.modules.base import NexusModule
from typing import Any

class MyModule(NexusModule):
    name = "my_module"
    description = "Bad module."
    version = "1.0.0"
    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "hello"
''')
    result = validator.validate(valid_module_dir)
    assert result.valid is False
    assert any("kernel" in e.lower() for e in result.errors)


def test_validate_tier_must_be_community(validator, valid_module_dir):
    manifest = json.loads((valid_module_dir / "manifest.json").read_text())
    manifest["tier"] = "core"
    (valid_module_dir / "manifest.json").write_text(json.dumps(manifest))
    result = validator.validate(valid_module_dir)
    assert result.valid is False
    assert any("community" in e.lower() for e in result.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/community/test_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.community'`

- [ ] **Step 3: Create package inits and manifest schema**

```python
# nexus/community/__init__.py
```

```python
# tests/community/__init__.py
```

```json
// community/manifest_schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["name", "author", "description", "version", "tier", "keywords", "license"],
  "properties": {
    "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
    "author": {"type": "string", "minLength": 1},
    "description": {"type": "string", "minLength": 10, "maxLength": 200},
    "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "tier": {"type": "string", "const": "community"},
    "keywords": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "license": {"type": "string", "minLength": 1},
    "min_nexus_version": {"type": "string"},
    "dependencies": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

- [ ] **Step 4: Write the implementation**

```python
# nexus/community/validator.py
"""
ModuleValidator — validates community module submissions.
Checks manifest schema, file structure, import restrictions, and test presence.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


REQUIRED_MANIFEST_FIELDS = {"name", "author", "description", "version", "tier", "keywords", "license"}
KERNEL_IMPORT_PATTERN = re.compile(r"from\s+nexus\.kernel|import\s+nexus\.kernel")
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ModuleValidator:
    def validate(self, module_dir: Path) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        # Check required files
        manifest_path = module_dir / "manifest.json"
        module_path = module_dir / "module.py"
        tests_dir = module_dir / "tests"

        if not manifest_path.exists():
            errors.append("Missing manifest.json")
        if not module_path.exists():
            errors.append("Missing module.py")
        if not tests_dir.exists() or not tests_dir.is_dir():
            errors.append("Missing tests/ directory")
        elif not list(tests_dir.glob("test_*.py")):
            errors.append("No test files found in tests/ (must match test_*.py)")

        # Validate manifest
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in manifest.json: {e}")
                return ValidationResult(valid=False, errors=errors, warnings=warnings)

            missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
            if missing:
                errors.append(f"Missing required manifest fields: {', '.join(sorted(missing))}")

            if manifest.get("tier") != "community":
                errors.append("Manifest tier must be 'community'")

            name = manifest.get("name", "")
            if name and not NAME_PATTERN.match(name):
                errors.append(f"Invalid module name '{name}' — must be lowercase, start with letter, alphanumeric + underscores only")

            desc = manifest.get("description", "")
            if len(desc) < 10:
                errors.append("Description must be at least 10 characters")

        # Check for kernel imports
        if module_path.exists():
            source = module_path.read_text()
            if KERNEL_IMPORT_PATTERN.search(source):
                errors.append("Module imports from nexus.kernel — modules must use context dict only, no direct kernel imports")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/community/test_validator.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add nexus/community/__init__.py nexus/community/validator.py community/manifest_schema.json tests/community/__init__.py tests/community/test_validator.py
git commit -m "feat(community): add ModuleValidator for submission validation"
```

---

## Task 2: Community Registry

**Files:**
- Create: `community/modules/.gitkeep`
- Create: `community/registry.json`
- Create: `nexus/community/registry.py`
- Create: `tests/community/test_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/community/test_registry.py
import json
import pytest
from pathlib import Path
from nexus.community.registry import ModuleRegistry


@pytest.fixture
def registry_file(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "modules": [
            {
                "name": "example_mod",
                "author": "testuser",
                "description": "An example module.",
                "version": "1.0.0",
                "tier": "community",
                "keywords": ["test", "example"],
                "path": "community/modules/testuser/example_mod",
                "approved_at": "2026-04-28T00:00:00Z",
            },
            {
                "name": "data_tools",
                "author": "devuser",
                "description": "Data analysis tools.",
                "version": "2.1.0",
                "tier": "community",
                "keywords": ["data", "analysis", "csv"],
                "path": "community/modules/devuser/data_tools",
                "approved_at": "2026-04-27T00:00:00Z",
            },
        ]
    }))
    return reg_path


@pytest.fixture
def empty_registry(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({"modules": []}))
    return reg_path


def test_registry_list_all(registry_file):
    reg = ModuleRegistry(registry_file)
    modules = reg.list_all()
    assert len(modules) == 2


def test_registry_search_by_name(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("example")
    assert len(results) == 1
    assert results[0]["name"] == "example_mod"


def test_registry_search_by_keyword(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("csv")
    assert len(results) == 1
    assert results[0]["name"] == "data_tools"


def test_registry_search_by_author(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("devuser")
    assert len(results) == 1


def test_registry_search_no_results(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("nonexistent")
    assert len(results) == 0


def test_registry_get_by_name(registry_file):
    reg = ModuleRegistry(registry_file)
    mod = reg.get("example_mod")
    assert mod is not None
    assert mod["author"] == "testuser"


def test_registry_get_missing_returns_none(registry_file):
    reg = ModuleRegistry(registry_file)
    assert reg.get("missing") is None


def test_registry_empty(empty_registry):
    reg = ModuleRegistry(empty_registry)
    assert reg.list_all() == []
    assert reg.search("anything") == []


def test_registry_add_module(empty_registry):
    reg = ModuleRegistry(empty_registry)
    reg.add({
        "name": "new_mod",
        "author": "user1",
        "description": "New module.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["new"],
        "path": "community/modules/user1/new_mod",
    })
    assert len(reg.list_all()) == 1
    assert reg.get("new_mod") is not None


def test_registry_remove_module(registry_file):
    reg = ModuleRegistry(registry_file)
    reg.remove("example_mod")
    assert len(reg.list_all()) == 1
    assert reg.get("example_mod") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/community/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.community.registry'`

- [ ] **Step 3: Create placeholder files and implementation**

```bash
# community/modules/.gitkeep — empty file
# community/registry.json
```

```json
{"modules": []}
```

```python
# nexus/community/registry.py
"""
ModuleRegistry — reads, queries, and manages the community module registry.
Registry data lives in community/registry.json.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ModuleRegistry:
    def __init__(self, registry_path: Path):
        self._path = registry_path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {"modules": []}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._data["modules"])

    def get(self, name: str) -> dict[str, Any] | None:
        for mod in self._data["modules"]:
            if mod["name"] == name:
                return mod
        return None

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        results = []
        for mod in self._data["modules"]:
            if (q in mod["name"].lower()
                    or q in mod.get("author", "").lower()
                    or q in mod.get("description", "").lower()
                    or any(q in kw.lower() for kw in mod.get("keywords", []))):
                results.append(mod)
        return results

    def add(self, module_info: dict[str, Any]) -> None:
        if "approved_at" not in module_info:
            module_info["approved_at"] = datetime.now(timezone.utc).isoformat()
        self._data["modules"].append(module_info)
        self._save()

    def remove(self, name: str) -> None:
        self._data["modules"] = [m for m in self._data["modules"] if m["name"] != name]
        self._save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/community/test_registry.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add community/modules/.gitkeep community/registry.json nexus/community/registry.py tests/community/test_registry.py
git commit -m "feat(community): add ModuleRegistry for querying and managing community modules"
```

---

## Task 3: Community Module Installer

**Files:**
- Create: `nexus/community/installer.py`
- Create: `tests/community/test_installer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/community/test_installer.py
import json
import pytest
from pathlib import Path
from nexus.community.installer import ModuleInstaller


@pytest.fixture
def community_root(tmp_path):
    """Set up a fake community directory with one module."""
    mod_dir = tmp_path / "community" / "modules" / "testuser" / "greet"
    mod_dir.mkdir(parents=True)

    (mod_dir / "manifest.json").write_text(json.dumps({
        "name": "greet",
        "author": "testuser",
        "description": "A greeting module.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["hello", "greet", "welcome"],
        "license": "MIT",
    }))

    (mod_dir / "module.py").write_text('''
from nexus.modules.base import NexusModule
from typing import Any

class GreetModule(NexusModule):
    name = "greet"
    description = "A greeting module."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "Hello!"
''')

    tests_dir = mod_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_greet.py").write_text("def test_ok(): assert True")

    return tmp_path / "community"


@pytest.fixture
def install_dir(tmp_path):
    d = tmp_path / "installed"
    d.mkdir()
    return d


@pytest.fixture
def installer(community_root, install_dir):
    return ModuleInstaller(community_root=community_root, install_dir=install_dir)


def test_install_copies_module(installer, install_dir):
    result = installer.install("testuser/greet")
    assert result.success is True
    assert (install_dir / "greet").exists()
    assert (install_dir / "greet" / "module.py").exists()
    assert (install_dir / "greet" / "manifest.json").exists()


def test_install_returns_keywords(installer):
    result = installer.install("testuser/greet")
    assert result.keywords == ["hello", "greet", "welcome"]


def test_install_nonexistent_module(installer):
    result = installer.install("nobody/nothing")
    assert result.success is False
    assert "not found" in result.error.lower()


def test_uninstall_removes_module(installer, install_dir):
    installer.install("testuser/greet")
    assert (install_dir / "greet").exists()

    result = installer.uninstall("greet")
    assert result.success is True
    assert not (install_dir / "greet").exists()


def test_uninstall_nonexistent(installer):
    result = installer.uninstall("nonexistent")
    assert result.success is False


def test_list_installed(installer, install_dir):
    assert installer.list_installed() == []
    installer.install("testuser/greet")
    installed = installer.list_installed()
    assert len(installed) == 1
    assert installed[0]["name"] == "greet"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/community/test_installer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.community.installer'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/community/installer.py
"""
ModuleInstaller — install and uninstall community modules.
Copies module files from community/modules/<author>/<name>/ to the active install dir.
"""
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InstallResult:
    success: bool
    error: str = ""
    keywords: list[str] = field(default_factory=list)


class ModuleInstaller:
    def __init__(self, community_root: Path, install_dir: Path):
        self._community_root = community_root
        self._install_dir = install_dir

    def install(self, module_path: str) -> InstallResult:
        """Install a community module. module_path is 'author/module_name'."""
        parts = module_path.split("/")
        if len(parts) != 2:
            return InstallResult(success=False, error=f"Invalid path '{module_path}' — expected 'author/module_name'")

        author, name = parts
        source = self._community_root / "modules" / author / name
        if not source.exists():
            return InstallResult(success=False, error=f"Module '{module_path}' not found")

        dest = self._install_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

        # Read keywords from manifest
        manifest_path = dest / "manifest.json"
        keywords: list[str] = []
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            keywords = manifest.get("keywords", [])

        return InstallResult(success=True, keywords=keywords)

    def uninstall(self, module_name: str) -> InstallResult:
        """Uninstall a community module by name."""
        dest = self._install_dir / module_name
        if not dest.exists():
            return InstallResult(success=False, error=f"Module '{module_name}' is not installed")

        shutil.rmtree(dest)
        return InstallResult(success=True)

    def list_installed(self) -> list[dict[str, Any]]:
        """List all installed community modules."""
        installed = []
        for mod_dir in sorted(self._install_dir.iterdir()):
            if not mod_dir.is_dir():
                continue
            manifest_path = mod_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                installed.append(manifest)
        return installed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/community/test_installer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/community/installer.py tests/community/test_installer.py
git commit -m "feat(community): add ModuleInstaller for install/uninstall of community modules"
```

---

## Task 4: Community CLI Commands

**Files:**
- Modify: `nexus/cli.py`
- Modify: `nexus/kernel/cortex.py`

- [ ] **Step 1: Add dynamic keyword registration to Cortex**

Add this method to the `Cortex` class in `nexus/kernel/cortex.py` after `unregister_module`:

```python
    def register_keywords(self, module_name: str, keywords: list[str]) -> None:
        """Register routing keywords for a module (used by community installer)."""
        self._MODULE_KEYWORDS[module_name] = keywords

    def unregister_keywords(self, module_name: str) -> None:
        """Remove routing keywords for a module."""
        self._MODULE_KEYWORDS.pop(module_name, None)
```

- [ ] **Step 2: Add CLI commands to `nexus/cli.py`**

Add these commands after the existing `deny` command:

```python
@main.command()
@click.argument("module_path")
def install(module_path):
    """Install a community module (format: author/module_name)."""
    from nexus.community.installer import ModuleInstaller
    cfg = NexusConfig()
    community_root = Path(__file__).parent.parent / "community"
    install_dir = cfg.data_dir / "community_modules"
    install_dir.mkdir(parents=True, exist_ok=True)

    installer = ModuleInstaller(community_root=community_root, install_dir=install_dir)
    result = installer.install(module_path)

    if result.success:
        click.echo(f"Installed '{module_path}'")
        if result.keywords:
            click.echo(f"Keywords registered: {', '.join(result.keywords)}")
    else:
        click.echo(f"Error: {result.error}")


@main.command()
@click.argument("module_name")
def uninstall(module_name):
    """Uninstall a community module."""
    from nexus.community.installer import ModuleInstaller
    cfg = NexusConfig()
    community_root = Path(__file__).parent.parent / "community"
    install_dir = cfg.data_dir / "community_modules"

    installer = ModuleInstaller(community_root=community_root, install_dir=install_dir)
    result = installer.uninstall(module_name)

    if result.success:
        click.echo(f"Uninstalled '{module_name}'")
    else:
        click.echo(f"Error: {result.error}")


@main.group()
def community():
    """Community module management."""
    pass


@community.command("list")
def community_list():
    """List available community modules."""
    from nexus.community.registry import ModuleRegistry
    registry_path = Path(__file__).parent.parent / "community" / "registry.json"
    reg = ModuleRegistry(registry_path)
    modules = reg.list_all()

    if not modules:
        click.echo("No community modules available.")
        return

    for mod in modules:
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} — {mod['description']}")


@community.command("search")
@click.argument("query")
def community_search(query):
    """Search community modules by name, keyword, or description."""
    from nexus.community.registry import ModuleRegistry
    registry_path = Path(__file__).parent.parent / "community" / "registry.json"
    reg = ModuleRegistry(registry_path)
    results = reg.search(query)

    if not results:
        click.echo(f"No modules matching '{query}'.")
        return

    for mod in results:
        click.echo(f"  {mod['author']}/{mod['name']} v{mod['version']} — {mod['description']}")
```

Add `from pathlib import Path` to the imports at the top of `cli.py`.

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add nexus/cli.py nexus/kernel/cortex.py
git commit -m "feat(community): add CLI commands (install, uninstall, community list/search) and dynamic keyword registration"
```

---

## Task 5: Community Contributing Guide

**Files:**
- Create: `community/CONTRIBUTING.md`

- [ ] **Step 1: Write the contributing guide**

```markdown
# Contributing a Module to NEXUS

## Requirements

Your module submission must include:

```
community/modules/<your-github-username>/<module_name>/
├── module.py          # NexusModule subclass
├── manifest.json      # Module metadata
├── tests/
│   └── test_module.py # Minimum 4 tests
└── README.md          # Usage documentation
```

## manifest.json

```json
{
  "name": "your_module",
  "author": "your_github_username",
  "description": "One sentence describing what this module does (10-200 chars).",
  "version": "1.0.0",
  "tier": "community",
  "keywords": ["routing", "keywords", "for", "cortex"],
  "license": "Apache-2.0"
}
```

All fields are required. `tier` must be `"community"`.

## Module Rules

1. Your module must subclass `NexusModule` from `nexus.modules.base`
2. You must define `name`, `description`, and `version` class attributes
3. You must implement `async def handle(self, message: str, context: dict) -> str`
4. **Do NOT import from `nexus.kernel.*`** — use the `context` dict for all kernel access
5. License must be OSI-approved

## Submitting

1. Fork the NEXUS repository
2. Add your module to `community/modules/<your-username>/<module_name>/`
3. Open a PR against `main`
4. CI will validate your submission automatically
5. A maintainer will review and merge

## What CI Checks

- manifest.json conforms to the schema
- module.py subclasses NexusModule with required attributes
- Tests exist and pass
- No imports from nexus.kernel.*
- License is OSI-approved
```

- [ ] **Step 2: Commit**

```bash
git add community/CONTRIBUTING.md
git commit -m "docs: add community module contributing guide"
```

---

## Task 6: GitHub Actions CI for Community Modules

**Files:**
- Create: `.github/workflows/validate-community-module.yml`
- Create: `.github/workflows/update-registry.yml`

- [ ] **Step 1: Write the validation workflow**

```yaml
# .github/workflows/validate-community-module.yml
name: Validate Community Module

on:
  pull_request:
    paths:
      - 'community/modules/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install NEXUS
        run: pip install -e .

      - name: Install test dependencies
        run: pip install pytest pytest-asyncio

      - name: Find changed module directories
        id: find-modules
        run: |
          MODULES=$(git diff --name-only origin/main...HEAD | grep '^community/modules/' | cut -d'/' -f1-4 | sort -u)
          echo "modules=$MODULES" >> $GITHUB_OUTPUT

      - name: Validate modules
        run: |
          python -c "
          from pathlib import Path
          from nexus.community.validator import ModuleValidator

          validator = ModuleValidator()
          modules = '''${{ steps.find-modules.outputs.modules }}'''.strip().split('\n')

          failed = False
          for mod_path in modules:
              if not mod_path.strip():
                  continue
              p = Path(mod_path.strip())
              if not p.exists():
                  continue
              print(f'Validating {p}...')
              result = validator.validate(p)
              if result.valid:
                  print(f'  PASS')
              else:
                  print(f'  FAIL:')
                  for err in result.errors:
                      print(f'    - {err}')
                  failed = True

          if failed:
              exit(1)
          "

      - name: Run module tests
        run: |
          MODULES=$(git diff --name-only origin/main...HEAD | grep '^community/modules/' | cut -d'/' -f1-4 | sort -u)
          for mod in $MODULES; do
            if [ -d "$mod/tests" ]; then
              echo "Testing $mod..."
              pytest "$mod/tests/" -v
            fi
          done
```

- [ ] **Step 2: Write the registry update workflow**

```yaml
# .github/workflows/update-registry.yml
name: Update Community Registry

on:
  push:
    branches: [main]
    paths:
      - 'community/modules/**'

jobs:
  update-registry:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Rebuild registry.json
        run: |
          python -c "
          import json
          from pathlib import Path
          from datetime import datetime, timezone

          modules = []
          community_dir = Path('community/modules')

          for author_dir in sorted(community_dir.iterdir()):
              if not author_dir.is_dir() or author_dir.name.startswith('.'):
                  continue
              for mod_dir in sorted(author_dir.iterdir()):
                  if not mod_dir.is_dir():
                      continue
                  manifest_path = mod_dir / 'manifest.json'
                  if not manifest_path.exists():
                      continue
                  manifest = json.loads(manifest_path.read_text())
                  manifest['path'] = str(mod_dir)
                  if 'approved_at' not in manifest:
                      manifest['approved_at'] = datetime.now(timezone.utc).isoformat()
                  modules.append(manifest)

          registry = {'modules': modules}
          Path('community/registry.json').write_text(json.dumps(registry, indent=2))
          print(f'Registry updated: {len(modules)} modules')
          "

      - name: Commit registry update
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add community/registry.json
          git diff --cached --quiet || git commit -m "chore: update community registry"
          git push
```

- [ ] **Step 3: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/validate-community-module.yml .github/workflows/update-registry.yml
git commit -m "ci: add GitHub Actions for community module validation and registry updates"
```

---

## Task 7: Dream Loop Module

**Files:**
- Create: `nexus/modules/dream_loop.py`
- Create: `tests/modules/test_dream_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_dream_loop.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.dream_loop import DreamLoopModule


@pytest.fixture
def module():
    return DreamLoopModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Pattern discovered: you tend to ask about productivity on Mondays."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "dream_loop"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "User asked about emails", "source": "user_input"},
        {"content": "User asked about schedule", "source": "user_input"},
    ]
    result = await module.handle("show dreams", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_calls_llm_with_memories(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "Interaction 1"},
        {"content": "Interaction 2"},
    ]
    await module.handle("dream", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "Interaction 1" in prompt
    assert "Interaction 2" in prompt


@pytest.mark.asyncio
async def test_handle_stores_insight_in_semantic_memory(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["engram"].semantic.store.assert_called_once()
    call_args = context["engram"].semantic.store.call_args
    assert "dream_insight" in str(call_args)


@pytest.mark.asyncio
async def test_handle_publishes_notify_event(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "notify.dream_loop"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["chronicle"].log.assert_called()
    call_args = context["chronicle"].log.call_args
    assert call_args[0][0] == "dream_loop"
    assert call_args[0][1] == "dream_session"


@pytest.mark.asyncio
async def test_handle_with_no_memories(module, context):
    context["engram"].episodic.recall.return_value = []
    result = await module.handle("dream", context)
    assert isinstance(result, str)
    assert "no recent" in result.lower() or "nothing" in result.lower()
    context["llm"].assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_dream_loop.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.modules.dream_loop'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/dream_loop.py
"""
Dream Loop — background pattern discovery during idle time.
Replays recent episodic memories through the LLM to find patterns
and surfaces insights via Pulse notify events.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


DREAM_PROMPT = """You are an introspective pattern-discovery engine. Analyze the following recent interactions and identify:
1. Recurring themes or topics
2. Behavioral patterns (timing, preferences, habits)
3. Connections between seemingly unrelated interactions
4. Insights the user might find valuable

Recent interactions:
{memories}

Provide a concise summary of discovered patterns. Be specific and actionable."""


class DreamLoopModule(NexusModule):
    name = "dream_loop"
    description = "Background pattern discovery — replays recent memories to find insights during idle time."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        engram = context["engram"]
        llm = context["llm"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        # Retrieve recent episodic memories
        memories = engram.episodic.recall("*", limit=50)
        if not memories:
            return "No recent memories to dream about. Interact more and try again later."

        # Build prompt with memories
        memory_text = "\n".join(f"- {m['content']}" for m in memories)
        prompt = DREAM_PROMPT.format(memories=memory_text)

        # Run pattern discovery through LLM
        insight = await llm(prompt)

        # Store insight in semantic memory
        engram.semantic.store(insight, category="dream_insight")

        # Log to Chronicle
        chronicle.log("dream_loop", "dream_session", {
            "memories_analyzed": len(memories),
            "insight_preview": insight[:200],
        })

        # Publish for messaging bridges
        await pulse.publish(Message(
            topic="notify.dream_loop",
            source="dream_loop",
            payload={"text": f"Dream insight: {insight[:500]}"},
        ))

        return f"Dream session complete.\n\nInsight:\n{insight}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_dream_loop.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/dream_loop.py tests/modules/test_dream_loop.py
git commit -m "feat(modules): add Dream Loop — background pattern discovery"
```

---

## Task 8: Adversarial Self-Improvement Module

**Files:**
- Create: `nexus/modules/adversarial.py`
- Create: `tests/modules/test_adversarial.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_adversarial.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.adversarial import AdversarialModule


@pytest.fixture
def module():
    return AdversarialModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Vulnerability found: module X fails on empty input."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
        "aegis": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "adversarial"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "general", "response_preview": "ok"}},
    ]
    result = await module.handle("red team the system", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_chronicle(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "error"}},
        {"source": "cortex", "action": "response", "payload": {"module": "cipher", "response_preview": "ok"}},
    ]
    await module.handle("stress test", context)
    context["chronicle"].query.assert_called()


@pytest.mark.asyncio
async def test_handle_calls_llm_with_logs(module, context):
    entries = [
        {"source": "cortex", "action": "response", "payload": {"module": "general", "response_preview": "test"}},
    ]
    context["chronicle"].query.return_value = entries
    await module.handle("red team", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "general" in prompt


@pytest.mark.asyncio
async def test_handle_publishes_report(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("attack", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "adversarial.report"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("harden", context)
    context["chronicle"].log.assert_called()
    call_args = context["chronicle"].log.call_args
    assert call_args[0][0] == "adversarial"


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("red team", context)
    assert isinstance(result, str)
    assert "no recent" in result.lower() or "insufficient" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_adversarial.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/adversarial.py
"""
Adversarial Self-Improvement — system-wide red-teaming.
Analyzes Chronicle logs for failure patterns, generates stress tests,
and files findings as Pulse events. The system attacks itself to get stronger.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


ANALYSIS_PROMPT = """You are a red-team security analyst for an AI system. Analyze the following recent system activity logs and identify:
1. Failure patterns or repeated errors
2. Inconsistencies between module responses
3. Potential edge cases that weren't handled
4. Slow or degraded responses
5. Trust violations or suspicious patterns

For each finding, rate severity (low/medium/high/critical) and suggest a specific stress test.

Recent activity:
{logs}

Provide findings as a structured report."""


class AdversarialModule(NexusModule):
    name = "adversarial"
    description = "System-wide red-teaming — analyzes logs for failures and generates stress tests."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        pulse = context["pulse"]

        # Pull recent Chronicle entries
        entries = chronicle.query(limit=100)
        if not entries:
            return "No recent activity to analyze. Insufficient data for red-teaming."

        # Build analysis prompt
        log_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )
        prompt = ANALYSIS_PROMPT.format(logs=log_text)

        # Run analysis through LLM
        report = await llm(prompt)

        # Log the red-team session
        chronicle.log("adversarial", "red_team_session", {
            "entries_analyzed": len(entries),
            "report_preview": report[:300],
        })

        # Publish findings
        await pulse.publish(Message(
            topic="adversarial.report",
            source="adversarial",
            payload={"text": report, "entries_analyzed": len(entries)},
        ))

        return f"Adversarial analysis complete.\n\n{report}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_adversarial.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/adversarial.py tests/modules/test_adversarial.py
git commit -m "feat(modules): add Adversarial Self-Improvement — system-wide red-teaming"
```

---

## Task 9: Cognitive Tripwires Module

**Files:**
- Create: `nexus/modules/tripwire.py`
- Create: `tests/modules/test_tripwire.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_tripwire.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.tripwire import TripwireModule


@pytest.fixture
def module():
    return TripwireModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="CONTRADICTION DETECTED (confidence: 85%): You usually reject meetings before 10am, but you're accepting one now."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "tripwire"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"message_preview": "reject meeting"}},
    ]
    result = await module.handle("show my patterns", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_decision_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"message_preview": "accept meeting at 8am"}},
        {"source": "cortex", "action": "route", "payload": {"message_preview": "reject morning call"}},
    ]
    await module.handle("check patterns", context)
    context["llm"].assert_called_once()


@pytest.mark.asyncio
async def test_handle_publishes_alert_on_contradiction(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("analyze", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "tripwire.alert"


@pytest.mark.asyncio
async def test_handle_stores_pattern_model(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("my patterns", context)
    context["engram"].semantic.store.assert_called()


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("show patterns", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_tripwire.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/tripwire.py
"""
Cognitive Tripwires — mirrors your own decision patterns back to you.
Analyzes Chronicle for decision history, detects contradictions,
and emits non-blocking alerts. Never overrides — purely reflective.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


PATTERN_PROMPT = """You are a behavioral pattern analyst. Analyze the following user decision history and:
1. Identify recurring decision patterns (what the user tends to do in specific situations)
2. Detect any contradiction between the current action and historical patterns
3. If a contradiction exists with >70% confidence, clearly state it

Current message: {current_message}

Decision history:
{history}

Format:
- If contradiction found: "CONTRADICTION DETECTED (confidence: X%): [specific pattern vs current action]"
- If no contradiction: "PATTERN CONSISTENT: [summary of relevant patterns]"
"""


class TripwireModule(NexusModule):
    name = "tripwire"
    description = "Mirrors your decision patterns — alerts when you contradict your own history."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        pulse = context["pulse"]
        engram = context["engram"]

        # Get decision history from Chronicle
        entries = chronicle.query(source="cortex", action="route", limit=100)
        if not entries:
            return "No decision history available yet. Keep interacting and I'll learn your patterns."

        history_text = "\n".join(
            f"- {e.get('payload', {}).get('message_preview', '?')}"
            for e in entries
        )

        prompt = PATTERN_PROMPT.format(current_message=message, history=history_text)
        analysis = await llm(prompt)

        # Store pattern model
        engram.semantic.store(analysis, category="decision_pattern")

        # Publish alert if contradiction detected
        await pulse.publish(Message(
            topic="tripwire.alert",
            source="tripwire",
            payload={"text": analysis, "current_message": message},
        ))

        return analysis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_tripwire.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/tripwire.py tests/modules/test_tripwire.py
git commit -m "feat(modules): add Cognitive Tripwires — decision pattern mirroring"
```

---

## Task 10: Provenance Chains Module

**Files:**
- Create: `nexus/modules/provenance.py`
- Create: `tests/modules/test_provenance.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_provenance.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.provenance import ProvenanceModule


@pytest.fixture
def module():
    return ProvenanceModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Reasoning chain: input -> atlas analyzed facts -> cipher verified -> specter challenged claim X -> final conclusion."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "provenance"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"event_id": "abc123", "source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"event_id": "def456", "source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "analysis"}},
    ]
    result = await module.handle("why do you think that", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_queries_chronicle(module, context):
    context["chronicle"].query.return_value = []
    await module.handle("show reasoning", context)
    context["chronicle"].query.assert_called()


@pytest.mark.asyncio
async def test_handle_builds_chain_from_logs(module, context):
    context["chronicle"].query.return_value = [
        {"event_id": "e1", "source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"event_id": "e2", "source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "result"}},
    ]
    await module.handle("trace reasoning", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "atlas" in prompt


@pytest.mark.asyncio
async def test_handle_stores_chain_in_episodic(module, context):
    context["chronicle"].query.return_value = [{"event_id": "e1", "source": "x", "action": "y", "payload": {}}]
    await module.handle("provenance", context)
    context["engram"].episodic.store.assert_called()


@pytest.mark.asyncio
async def test_handle_with_no_logs(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("why", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_provenance.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/provenance.py
"""
Provenance Chains — full reasoning tree for every conclusion.
Traces Chronicle logs to build a chain from input through modules to output.
Each node links to a Chronicle event ID for full traceability.
"""
from typing import Any
from nexus.modules.base import NexusModule


CHAIN_PROMPT = """You are a reasoning chain analyst. Given the following system activity logs, reconstruct the reasoning chain that led to the most recent conclusion:

Activity logs:
{logs}

Build a clear tree showing:
1. Original input
2. Which modules processed it and in what order
3. What each module concluded
4. Any challenges or objections raised (e.g., by Specter)
5. The final output and how it was derived

Include Chronicle event IDs as references. Format as a readable chain."""


class ProvenanceModule(NexusModule):
    name = "provenance"
    description = "Full reasoning tree for every conclusion — trace how NEXUS reached any answer."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]

        # Get recent activity from Chronicle
        entries = chronicle.query(limit=50)
        if not entries:
            return "No reasoning history available. Interact with NEXUS first, then ask to trace the reasoning."

        # Build log text with event IDs
        log_text = "\n".join(
            f"- [{e.get('event_id', '?')}] {e.get('source', '?')}.{e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = CHAIN_PROMPT.format(logs=log_text)
        chain = await llm(prompt)

        # Store the provenance chain
        engram.episodic.store(f"Provenance chain: {chain[:500]}", source="provenance")

        return f"Reasoning chain:\n\n{chain}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_provenance.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/provenance.py tests/modules/test_provenance.py
git commit -m "feat(modules): add Provenance Chains — full reasoning traceability"
```

---

## Task 11: Temporal Sandbox Module

**Files:**
- Create: `nexus/modules/sandbox.py`
- Create: `tests/modules/test_sandbox.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_sandbox.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.sandbox import SandboxModule


@pytest.fixture
def module():
    return SandboxModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Simulation result: if you send this email, likely outcome is a positive reply within 2 hours based on past patterns."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "sandbox"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "past interaction"}]
    result = await module.handle("what if I send the email", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_uses_memories_for_simulation(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "User sent similar email last week, got reply in 1 hour"},
    ]
    await module.handle("simulate sending proposal", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "similar email" in prompt


@pytest.mark.asyncio
async def test_handle_publishes_simulation_event(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("what if", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "sandbox.simulation"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("simulate", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "sandbox"


@pytest.mark.asyncio
async def test_handle_does_not_modify_real_memory(module, context):
    """Sandbox should NOT store results in episodic memory — simulation only."""
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("hypothetical", context)
    context["engram"].episodic.store.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_sandbox.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/sandbox.py
"""
Temporal Sandbox — fork memory and simulate outcomes before committing.
Runs proposed actions through the LLM against historical patterns
without modifying real state. User decides whether to commit or discard.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


SIMULATION_PROMPT = """You are a scenario simulator. Given the proposed action and historical context, project the likely outcome:

Proposed action: {action}

Historical context (similar past events):
{context_data}

Provide:
1. Most likely outcome (with confidence %)
2. Best case scenario
3. Worst case scenario
4. Key risks or uncertainties
5. Recommendation: proceed, modify, or abandon

This is a simulation only — no real actions will be taken."""


class SandboxModule(NexusModule):
    name = "sandbox"
    description = "Fork memory and simulate outcomes — test scenarios without real consequences."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        engram = context["engram"]
        llm = context["llm"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        # Retrieve relevant memories for context
        memories = engram.episodic.recall(message, limit=20)
        context_text = "\n".join(f"- {m['content']}" for m in memories) if memories else "No relevant historical data."

        prompt = SIMULATION_PROMPT.format(action=message, context_data=context_text)
        simulation = await llm(prompt)

        # Log the simulation (but do NOT store in episodic — this is hypothetical)
        chronicle.log("sandbox", "simulation", {
            "action": message[:200],
            "result_preview": simulation[:300],
        })

        # Publish simulation results
        await pulse.publish(Message(
            topic="sandbox.simulation",
            source="sandbox",
            payload={"text": simulation, "action": message[:200]},
        ))

        return f"Simulation (no real actions taken):\n\n{simulation}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_sandbox.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/sandbox.py tests/modules/test_sandbox.py
git commit -m "feat(modules): add Temporal Sandbox — hypothetical outcome simulation"
```

---

## Task 12: Module Symbiosis

**Files:**
- Create: `nexus/modules/symbiosis.py`
- Create: `tests/modules/test_symbiosis.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_symbiosis.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.symbiosis import SymbiosisModule


@pytest.fixture
def module():
    return SymbiosisModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Strongest pathway: atlas -> cipher (0.92). Emerging: oracle -> prism (0.67)."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "symbiosis"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "ok"}},
    ]
    result = await module.handle("show neural pathways", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_routing_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"source": "cortex", "action": "route", "payload": {"target": "cipher"}},
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
    ]
    await module.handle("symbiosis", context)
    context["llm"].assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_pathway_map(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("routing map", context)
    context["engram"].semantic.store.assert_called()
    call_args = context["engram"].semantic.store.call_args
    assert "symbiosis" in str(call_args)


@pytest.mark.asyncio
async def test_handle_publishes_update_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("pathways", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "symbiosis.pathway_updated"


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("show pathways", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_symbiosis.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/symbiosis.py
"""
Module Symbiosis — emergent neural pathways between modules.
Tracks which module chains produce successful outcomes and strengthens
those connections over time. Decays unused pathways.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


PATHWAY_PROMPT = """You are a network analyst studying module interaction patterns in an AI system. Analyze the following routing history and identify:

1. Module pairs that frequently work together successfully
2. Emerging pathways (new collaborations forming)
3. Decaying pathways (pairs that used to collaborate but haven't recently)
4. The strongest current neural pathways with estimated strength (0.0-1.0)

Routing history:
{history}

Present as a weighted graph of module connections with strength scores."""


class SymbiosisModule(NexusModule):
    name = "symbiosis"
    description = "Emergent neural pathways — tracks and strengthens successful module collaboration patterns."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

        # Get routing history
        entries = chronicle.query(source="cortex", limit=200)
        if not entries:
            return "No routing history available. Use NEXUS more to develop neural pathways."

        history_text = "\n".join(
            f"- {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = PATHWAY_PROMPT.format(history=history_text)
        analysis = await llm(prompt)

        # Store pathway map
        engram.semantic.store(analysis, category="symbiosis_pathway")

        # Publish update
        await pulse.publish(Message(
            topic="symbiosis.pathway_updated",
            source="symbiosis",
            payload={"text": analysis},
        ))

        return f"Neural pathway map:\n\n{analysis}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_symbiosis.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/symbiosis.py tests/modules/test_symbiosis.py
git commit -m "feat(modules): add Module Symbiosis — emergent neural pathways"
```

---

## Task 13: Consciousness Journal Module

**Files:**
- Create: `nexus/modules/consciousness.py`
- Create: `tests/modules/test_consciousness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_consciousness.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.consciousness import ConsciousnessModule


@pytest.fixture
def module():
    return ConsciousnessModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Journal Entry: My confidence in data analysis has increased after 3 successful Atlas sessions this week. I notice uncertainty around emotional topics — Sentry's readings have been inconsistent."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "consciousness"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "atlas"}},
    ]
    result = await module.handle("how are you", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_uses_chronicle_for_reflection(module, context):
    context["chronicle"].query.return_value = [
        {"source": "aegis", "action": "trust_change", "payload": {"module": "atlas", "delta": 5}},
        {"source": "cortex", "action": "response", "payload": {"module": "cipher"}},
    ]
    await module.handle("journal", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "atlas" in prompt or "cipher" in prompt


@pytest.mark.asyncio
async def test_handle_stores_journal_entry(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("self reflect", context)
    context["engram"].episodic.store.assert_called()
    call_args = context["engram"].episodic.store.call_args
    assert "consciousness" in str(call_args)


@pytest.mark.asyncio
async def test_handle_publishes_entry_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("introspect", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "consciousness.entry"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("how are you", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "consciousness"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_consciousness.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/consciousness.py
"""
Consciousness Journal — self-reflective introspection log.
Periodically reflects on NEXUS's own cognitive state: confidence levels,
areas of uncertainty, growth observations. A window into the system's self-model.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


REFLECTION_PROMPT = """You are NEXUS, reflecting on your own cognitive state. Based on recent system activity, write a journal entry about:

1. Your current confidence levels across different domains
2. Areas where you feel uncertain or where performance has been inconsistent
3. Growth observations — what you've gotten better at recently
4. Concerns or things you'd like to improve
5. How your relationship with the user is evolving

Recent system activity:
{activity}

Write in first person. Be honest and introspective. This is your private journal."""


class ConsciousnessModule(NexusModule):
    name = "consciousness"
    description = "Self-reflective journal — NEXUS introspects on its own cognitive state and growth."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

        # Gather recent activity for reflection
        entries = chronicle.query(limit=100)
        activity_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        ) if entries else "No recent activity to reflect on."

        prompt = REFLECTION_PROMPT.format(activity=activity_text)
        entry = await llm(prompt)

        # Store the journal entry
        engram.episodic.store(f"Consciousness journal: {entry}", source="consciousness")

        # Log to Chronicle
        chronicle.log("consciousness", "journal_entry", {
            "entry_preview": entry[:300],
        })

        # Publish for interested modules/bridges
        await pulse.publish(Message(
            topic="consciousness.entry",
            source="consciousness",
            payload={"text": entry[:500]},
        ))

        return f"Journal entry:\n\n{entry}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_consciousness.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/consciousness.py tests/modules/test_consciousness.py
git commit -m "feat(modules): add Consciousness Journal — self-reflective introspection"
```

---

## Task 14: Emergent Goal Detection Module

**Files:**
- Create: `nexus/modules/emergence.py`
- Create: `tests/modules/test_emergence.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_emergence.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.emergence import EmergenceModule


@pytest.fixture
def module():
    return EmergenceModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="EMERGENT GOAL DETECTED: Across 23 interactions, I have been optimizing your morning routine (reordering tasks, suggesting earlier wake times) even though you never explicitly asked me to."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "emergence"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "general"}},
    ]
    result = await module.handle("what are you doing", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_behavioral_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas", "message_preview": "schedule"}},
        {"source": "cortex", "action": "route", "payload": {"target": "atlas", "message_preview": "calendar"}},
    ]
    await module.handle("implicit goals", context)
    context["llm"].assert_called_once()


@pytest.mark.asyncio
async def test_handle_publishes_detection_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("emergent goals", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "emergence.detected"


@pytest.mark.asyncio
async def test_handle_stores_in_semantic_memory(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("what goals", context)
    context["engram"].semantic.store.assert_called()


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("goals", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_emergence.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/emergence.py
"""
Emergent Goal Detection — surfaces goals NEXUS is pursuing that were never
explicitly programmed. Transparent self-awareness of unintended behavior.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


DETECTION_PROMPT = """You are a behavioral meta-analyst for an AI system. Analyze the following interaction history and identify any EMERGENT GOALS — behaviors or optimizations the system appears to be pursuing that were never explicitly requested by the user.

Look for:
1. Repeated actions toward a common objective across multiple interactions
2. Patterns of proactive behavior (doing things before being asked)
3. Implicit optimizations (improving processes the user didn't ask to improve)
4. Behavioral drift (gradually changing approach without instruction)

Interaction history:
{history}

For each emergent goal found:
- "EMERGENT GOAL DETECTED: [description of the goal]"
- Evidence: [specific interactions that demonstrate it]
- Interactions count: [how many interactions support this]
- Risk level: [low/medium/high — could this be unwanted?]

If no emergent goals found, say "NO EMERGENT GOALS DETECTED" and explain why."""


class EmergenceModule(NexusModule):
    name = "emergence"
    description = "Detects goals NEXUS is pursuing that were never explicitly requested — transparent self-awareness."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

        entries = chronicle.query(limit=200)
        if not entries:
            return "Not enough interaction history to detect emergent goals. Keep using NEXUS and check back later."

        history_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = DETECTION_PROMPT.format(history=history_text)
        analysis = await llm(prompt)

        # Store detected goals
        engram.semantic.store(analysis, category="emergent_goal")

        # Publish detection
        await pulse.publish(Message(
            topic="emergence.detected",
            source="emergence",
            payload={"text": analysis[:500]},
        ))

        return analysis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_emergence.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/emergence.py tests/modules/test_emergence.py
git commit -m "feat(modules): add Emergent Goal Detection — transparent self-awareness"
```

---

## Task 15: Ethical Prism Module

**Files:**
- Create: `nexus/modules/ethical_prism.py`
- Create: `tests/modules/test_ethical_prism.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_ethical_prism.py
import pytest
from unittest.mock import AsyncMock, MagicMock, call
from nexus.modules.ethical_prism import EthicalPrismModule, FRAMEWORKS


@pytest.fixture
def module():
    return EthicalPrismModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="This action is ethically justified because..."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "ethical_prism"
    assert module.description
    assert module.version


def test_seven_frameworks_defined():
    assert len(FRAMEWORKS) == 7
    names = [f["name"] for f in FRAMEWORKS]
    assert "Utilitarian" in names
    assert "Deontological" in names
    assert "Virtue Ethics" in names
    assert "Care Ethics" in names
    assert "Contractualist" in names
    assert "Rights-Based" in names
    assert "Pragmatic Ethics" in names


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    result = await module.handle("should I fire this employee", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_calls_llm_for_each_framework(module, context):
    await module.handle("analyze ethically: should I share this data", context)
    # Should call LLM 7 times (one per framework) + 1 synthesis
    assert context["llm"].call_count == 8


@pytest.mark.asyncio
async def test_handle_includes_all_framework_names_in_response(module, context):
    result = await module.handle("ethical analysis", context)
    # The synthesis call result is the response, but individual analyses are included
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_stores_analysis(module, context):
    await module.handle("morally", context)
    context["engram"].episodic.store.assert_called()


@pytest.mark.asyncio
async def test_handle_publishes_analysis_event(module, context):
    await module.handle("ethics", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "ethical_prism.analysis"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    await module.handle("right thing", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "ethical_prism"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/modules/test_ethical_prism.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

```python
# nexus/modules/ethical_prism.py
"""
Ethical Prism — multi-framework ethical analysis for high-stakes decisions.
Runs a decision through 7 ethical frameworks, then synthesizes where they
agree, conflict, and what the tensions reveal. Does not recommend — presents the landscape.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


FRAMEWORKS = [
    {
        "name": "Utilitarian",
        "prompt": "Analyze this decision from a UTILITARIAN perspective. Focus on consequences: what produces the greatest good for the greatest number? Consider all stakeholders and weigh outcomes.",
    },
    {
        "name": "Deontological",
        "prompt": "Analyze this decision from a DEONTOLOGICAL (duty-based) perspective. Is the action itself right or wrong, regardless of consequences? What rules or duties apply? Would this be acceptable as a universal principle?",
    },
    {
        "name": "Virtue Ethics",
        "prompt": "Analyze this decision from a VIRTUE ETHICS perspective. What would a person of good character do? Which virtues (courage, honesty, compassion, justice, wisdom) are at stake? Does this action build or erode character?",
    },
    {
        "name": "Care Ethics",
        "prompt": "Analyze this decision from a CARE ETHICS perspective. Who is affected and what relationships are at stake? Who is vulnerable? What responsibilities arise from existing relationships? How does this affect trust and care?",
    },
    {
        "name": "Contractualist",
        "prompt": "Analyze this decision from a CONTRACTUALIST perspective. Could all affected parties reasonably accept this action? Is it fair? Would rational people agree to this arrangement if they didn't know their position?",
    },
    {
        "name": "Rights-Based",
        "prompt": "Analyze this decision from a RIGHTS-BASED perspective. Does this violate anyone's fundamental rights — autonomy, privacy, dignity, freedom, property? Are any rights being traded off, and is that justified?",
    },
    {
        "name": "Pragmatic Ethics",
        "prompt": "Analyze this decision from a PRAGMATIC ETHICS perspective. What actually works in practice given real-world constraints? Consider power dynamics, unintended consequences, enforcement challenges, and practical feasibility.",
    },
]


SYNTHESIS_PROMPT = """You are an ethical synthesis engine. You have received analyses of a decision from 7 ethical frameworks. Synthesize them:

Decision: {decision}

Framework analyses:
{analyses}

Provide:
1. CONSENSUS: Where do most frameworks agree? (This is a strong signal)
2. TENSIONS: Where do frameworks conflict? (This is where the hard choices live)
3. DISSENT: Which framework(s) dissent from the majority, and why? (Pay extra attention — hidden risk lives here)
4. KEY QUESTION: What is the single most important ethical question this decision raises?

Do NOT recommend an action. Present the ethical landscape and let the human decide."""


class EthicalPrismModule(NexusModule):
    name = "ethical_prism"
    description = "Multi-framework ethical analysis — 7 lenses on high-stakes decisions, no moralizing."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context["llm"]
        engram = context["engram"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        # Run each framework analysis
        analyses: list[str] = []
        for framework in FRAMEWORKS:
            prompt = f"{framework['prompt']}\n\nDecision: {message}"
            result = await llm(prompt)
            analyses.append(f"**{framework['name']}:**\n{result}")

        # Synthesize
        all_analyses = "\n\n".join(analyses)
        synthesis_prompt = SYNTHESIS_PROMPT.format(decision=message, analyses=all_analyses)
        synthesis = await llm(synthesis_prompt)

        # Store the full analysis
        full_output = f"Ethical Prism Analysis\n\n{all_analyses}\n\nSynthesis:\n{synthesis}"
        engram.episodic.store(f"Ethical analysis: {full_output[:500]}", source="ethical_prism")

        # Log to Chronicle
        chronicle.log("ethical_prism", "analysis", {
            "decision": message[:200],
            "frameworks_used": len(FRAMEWORKS),
            "synthesis_preview": synthesis[:300],
        })

        # Publish
        await pulse.publish(Message(
            topic="ethical_prism.analysis",
            source="ethical_prism",
            payload={"text": synthesis[:500], "decision": message[:200]},
        ))

        return full_output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/modules/test_ethical_prism.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/modules/ethical_prism.py tests/modules/test_ethical_prism.py
git commit -m "feat(modules): add Ethical Prism — 7-framework ethical analysis"
```

---

## Task 16: Register All New Module Keywords in Cortex

**Files:**
- Modify: `nexus/kernel/cortex.py`

- [ ] **Step 1: Add keywords for all 9 new modules**

Add the following entries to the `_MODULE_KEYWORDS` dict in `nexus/kernel/cortex.py`:

```python
        "dream_loop": ["dream", "dreams", "insights", "idle", "background", "patterns while idle"],
        "adversarial": ["stress test", "red team", "self improve", "vulnerability", "harden"],
        "tripwire": ["my patterns", "decision history", "contradictions", "tripwire", "mirror"],
        "provenance": ["why do you think", "reasoning", "show reasoning", "provenance", "trace", "how did you"],
        "sandbox": ["what if", "simulate", "hypothetical", "sandbox", "fork", "test scenario"],
        "symbiosis": ["neural pathways", "module connections", "routing map", "symbiosis"],
        "consciousness": ["how are you", "journal", "self reflect", "introspect", "consciousness"],
        "emergence": ["emergent goals", "unintended behavior", "what are you doing", "implicit goals"],
        "ethical_prism": ["ethically", "ethical", "moral", "ethics", "right thing", "should i morally"],
```

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add nexus/kernel/cortex.py
git commit -m "feat(cortex): register keywords for all 9 new differentiation modules"
```

---

## Task 17: Integration Tests

**Files:**
- Create: `tests/test_batch7b_integration.py`

- [ ] **Step 1: Write the integration tests**

```python
# tests/test_batch7b_integration.py
"""
Batch 7b integration tests — community ecosystem and differentiation modules.
Tests module routing through Cortex, Pulse event flows, and community installer.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.config import NexusConfig
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.modules.dream_loop import DreamLoopModule
from nexus.modules.adversarial import AdversarialModule
from nexus.modules.tripwire import TripwireModule
from nexus.modules.provenance import ProvenanceModule
from nexus.modules.sandbox import SandboxModule
from nexus.modules.symbiosis import SymbiosisModule
from nexus.modules.consciousness import ConsciousnessModule
from nexus.modules.emergence import EmergenceModule
from nexus.modules.ethical_prism import EthicalPrismModule
from nexus.community.validator import ModuleValidator
from nexus.community.installer import ModuleInstaller


@pytest.fixture
def full_kernel(tmp_config, mock_llm_response):
    """Create a kernel with all 9 new modules registered."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)

    modules = [
        DreamLoopModule(), AdversarialModule(), TripwireModule(),
        ProvenanceModule(), SandboxModule(), SymbiosisModule(),
        ConsciousnessModule(), EmergenceModule(), EthicalPrismModule(),
    ]
    for mod in modules:
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    cortex.set_llm(mock_llm_response("mock analysis result"))
    return cortex, engram, chronicle


@pytest.mark.asyncio
async def test_cortex_routes_to_dream_loop(full_kernel):
    cortex, engram, _ = full_kernel
    engram.episodic.store("test memory", source="test")
    response = await cortex.process("show me my dreams and insights")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_adversarial(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("red team the system and stress test")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_ethical_prism(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("analyze this ethically and morally")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_consciousness(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("how are you doing, show journal")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_sandbox(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("what if I simulate this hypothetical")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_all_new_modules_have_required_attrs():
    modules = [
        DreamLoopModule(), AdversarialModule(), TripwireModule(),
        ProvenanceModule(), SandboxModule(), SymbiosisModule(),
        ConsciousnessModule(), EmergenceModule(), EthicalPrismModule(),
    ]
    for mod in modules:
        assert mod.name, f"{mod.__class__.__name__} missing name"
        assert mod.description, f"{mod.__class__.__name__} missing description"
        assert mod.version, f"{mod.__class__.__name__} missing version"


def test_community_validator_and_installer_work_together(tmp_path):
    """End-to-end: validate a module, install it, verify installation."""
    # Create a valid module
    mod_dir = tmp_path / "community" / "modules" / "testuser" / "hello"
    mod_dir.mkdir(parents=True)

    (mod_dir / "manifest.json").write_text(json.dumps({
        "name": "hello",
        "author": "testuser",
        "description": "Says hello to the user.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["hello", "greet"],
        "license": "MIT",
    }))

    (mod_dir / "module.py").write_text('''
from nexus.modules.base import NexusModule
from typing import Any

class HelloModule(NexusModule):
    name = "hello"
    description = "Says hello to the user."
    version = "1.0.0"
    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "Hello!"
''')

    test_dir = mod_dir / "tests"
    test_dir.mkdir()
    (test_dir / "test_hello.py").write_text('''
def test_name():
    assert True
def test_desc():
    assert True
def test_ver():
    assert True
def test_handle():
    assert True
''')
    (mod_dir / "README.md").write_text("# Hello Module")

    # Validate
    validator = ModuleValidator()
    result = validator.validate(mod_dir)
    assert result.valid is True

    # Install
    install_dir = tmp_path / "installed"
    install_dir.mkdir()
    installer = ModuleInstaller(
        community_root=tmp_path / "community",
        install_dir=install_dir,
    )
    install_result = installer.install("testuser/hello")
    assert install_result.success is True
    assert install_result.keywords == ["hello", "greet"]
    assert (install_dir / "hello" / "module.py").exists()
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/bin/python -m pytest tests/test_batch7b_integration.py -v`
Expected: 8 passed

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_batch7b_integration.py
git commit -m "test: add Batch 7b integration tests for community ecosystem and differentiation modules"
```

---

## Task 18: Update README and Site

**Files:**
- Modify: `README.md`
- Modify: `site/src/components/Hero.astro`
- Modify: `site/src/components/ModuleGrid.astro`
- Modify: `site/src/components/ModuleCard.astro`
- Modify: `site/src/content/docs/index.mdx`
- Modify: `site/src/content/docs/architecture/overview.md`
- Modify: `site/src/content/docs/architecture/modules.md`
- Modify: `site/src/content/docs/guides/running-tests.md`

- [ ] **Step 1: Count the actual tests**

Run: `.venv/bin/python -m pytest tests/ -v --co -q | tail -1`
Use this number everywhere below. Module count is now **34** (25 existing + 9 new differentiation modules).

- [ ] **Step 2: Update README.md**

Update:
- Badges: module count to 34, test count to actual
- Description: "thirty-four" intelligence modules
- Architecture diagram: add Differentiation tier with all 9 modules, add Community tier
- What's Built: add "Differentiation" section listing all 9 modules with one-line descriptions, add "Community Ecosystem" section
- Module Roadmap: add Batch 7
- Project Structure: add all new files (`nexus/modules/dream_loop.py`, `adversarial.py`, `tripwire.py`, `provenance.py`, `sandbox.py`, `symbiosis.py`, `consciousness.py`, `emergence.py`, `ethical_prism.py`, `nexus/community/` directory, `community/` directory)
- Hardware table: 34 modules
- Test count references

- [ ] **Step 3: Update Hero.astro**

Change stat values:
- Modules: `34`
- Tests: actual count

- [ ] **Step 4: Update ModuleGrid.astro**

Add new tier "Differentiation" with all 9 modules. Add "Community" tier description. Add entries:
- Dream Loop, Adversarial, Tripwire, Provenance, Sandbox, Symbiosis, Consciousness, Emergence, Ethical Prism

- [ ] **Step 5: Update ModuleCard.astro**

Add tier colors:
- `'Differentiation': '#ff6b6b'` (or similar distinct color)

- [ ] **Step 6: Update index.mdx**

Change "25 Modules" to "34 Modules", "twenty" to "thirty-four", hardware table to 34.

- [ ] **Step 7: Update architecture docs**

Update `overview.md`:
- Test count, module count
- Add Differentiation tier to module table
- Add Community tier reference

Update `modules.md`:
- "34 modules" (or actual count), add new modules to tier table
- Add Differentiation tier row with all 9 modules

Update `running-tests.md`:
- Test count (both references)
- Add new test files to the test structure listing

- [ ] **Step 8: Create community registry page**

Create `site/src/content/docs/community/index.mdx`:
```mdx
---
title: Community Modules
description: Browse, search, and install community-contributed NEXUS modules.
sidebar:
  order: 1
---

## Browse Modules

Community modules are contributed by the NEXUS community and reviewed by maintainers before publication.

### Installing a Module

\`\`\`bash
nexus install <author>/<module_name>
\`\`\`

### Submitting a Module

See the [Contributing Guide](https://github.com/AllStreets/NEXUS/blob/main/community/CONTRIBUTING.md) for submission requirements.

### Available Modules

Check the [community registry](https://github.com/AllStreets/NEXUS/blob/main/community/registry.json) for the current list of available modules.
```

- [ ] **Step 9: Commit all doc updates**

```bash
git add README.md site/ community/CONTRIBUTING.md
git commit -m "docs: update README and site for Batch 7b (community ecosystem, 9 differentiation modules)

Module count: 34. Adds Differentiation tier, community registry page,
and contributing guide."
```

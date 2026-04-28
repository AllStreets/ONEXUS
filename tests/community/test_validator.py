import json
import pytest
from pathlib import Path
from nexus.community.validator import ModuleValidator, ValidationResult


@pytest.fixture
def valid_module_dir(tmp_path):
    mod_dir = tmp_path / "testuser" / "my_module"
    mod_dir.mkdir(parents=True)

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
    (valid_module_dir / "manifest.json").write_text(json.dumps({"name": "x"}))
    result = validator.validate(valid_module_dir)
    assert result.valid is False


def test_validate_kernel_imports(validator, valid_module_dir):
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

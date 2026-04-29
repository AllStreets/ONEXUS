"""
Tests for the package validator.
"""
from __future__ import annotations

import json
import os

import pytest

from nexus.sdk.validator import PackageValidator, ValidationResult


@pytest.fixture
def validator():
    return PackageValidator()


@pytest.fixture
def valid_module(tmp_path):
    """Create a minimal valid module package."""
    # manifest.json
    manifest = {
        "name": "test_mod",
        "author": "dev",
        "description": "A test module for validation",
        "version": "0.1.0",
        "tier": "community",
        "keywords": ["test"],
        "license": "MIT",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    # module.py
    (tmp_path / "module.py").write_text(
        'from nexus.modules.base import NexusModule\n'
        'class TestModModule(NexusModule):\n'
        '    name = "test_mod"\n'
        '    description = "A test module"\n'
        '    version = "0.1.0"\n'
        '    async def handle(self, message, context):\n'
        '        return "ok"\n'
    )

    # tests/
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_module.py").write_text(
        'def test_one(): pass\n'
        'def test_two(): pass\n'
        'def test_three(): pass\n'
        'def test_four(): pass\n'
    )

    # README.md
    (tmp_path / "README.md").write_text(
        "# test_mod\n\nA test module for validation. This has enough content to pass."
    )

    return tmp_path


@pytest.fixture
def valid_agent(tmp_path):
    """Create a minimal valid agent package."""
    manifest = {
        "name": "test_agent",
        "author": "dev",
        "description": "A test agent for validation",
        "version": "0.1.0",
        "tier": "community",
        "type": "agent",
        "keywords": ["test"],
        "license": "MIT",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    (tmp_path / "agent.py").write_text(
        'from nexus.agents.base import AgentModule\n'
        'class TestAgentAgent(AgentModule):\n'
        '    name = "test_agent"\n'
        '    description = "A test agent"\n'
        '    version = "0.1.0"\n'
        '    async def analyze(self, message, context):\n'
        '        return "ok"\n'
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_agent.py").write_text(
        'def test_one(): pass\n'
        'def test_two(): pass\n'
        'def test_three(): pass\n'
        'def test_four(): pass\n'
        'def test_five(): pass\n'
        'def test_six(): pass\n'
    )

    (tmp_path / "README.md").write_text(
        "# test_agent\n\nA test agent for validation. This has enough content to pass."
    )

    return tmp_path


def test_valid_module_passes(validator, valid_module):
    """A well-formed module package passes validation."""
    result = validator.validate(str(valid_module))
    assert result.valid is True
    assert result.errors == []


def test_valid_agent_passes(validator, valid_agent):
    """A well-formed agent package passes validation."""
    result = validator.validate(str(valid_agent))
    assert result.valid is True
    assert result.errors == []


def test_missing_manifest(validator, valid_module):
    """Missing manifest.json is an error."""
    os.remove(valid_module / "manifest.json")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("manifest.json not found" in e for e in result.errors)


def test_invalid_manifest_json(validator, valid_module):
    """Invalid JSON in manifest.json is an error."""
    (valid_module / "manifest.json").write_text("{bad json")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("not valid JSON" in e for e in result.errors)


def test_missing_manifest_fields(validator, valid_module):
    """Missing required fields in manifest.json are errors."""
    (valid_module / "manifest.json").write_text(json.dumps({"name": "x"}))
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("missing required fields" in e for e in result.errors)


def test_invalid_name_pattern(validator, valid_module):
    """Name not matching ^[a-z][a-z0-9_]*$ is an error."""
    manifest = json.loads((valid_module / "manifest.json").read_text())
    manifest["name"] = "BadName"
    (valid_module / "manifest.json").write_text(json.dumps(manifest))
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("name" in e and "must match" in e for e in result.errors)


def test_missing_code_file(validator, valid_module):
    """Missing module.py is an error."""
    os.remove(valid_module / "module.py")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("module.py not found" in e for e in result.errors)


def test_wrong_base_class(validator, valid_module):
    """Code that does not subclass NexusModule is an error."""
    (valid_module / "module.py").write_text(
        'class BadModule:\n'
        '    async def handle(self, message, context):\n'
        '        return "ok"\n'
    )
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("must subclass NexusModule" in e for e in result.errors)


def test_missing_handle_method(validator, valid_module):
    """Module without handle() is an error."""
    (valid_module / "module.py").write_text(
        'from nexus.modules.base import NexusModule\n'
        'class TestModModule(NexusModule):\n'
        '    name = "test_mod"\n'
        '    description = "A test module"\n'
        '    version = "0.1.0"\n'
    )
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("must implement handle()" in e for e in result.errors)


def test_kernel_imports_rejected(validator, valid_module):
    """Code that imports from nexus.kernel is an error."""
    (valid_module / "module.py").write_text(
        'from nexus.modules.base import NexusModule\n'
        'from nexus.kernel.pulse import Pulse\n'
        'class TestModModule(NexusModule):\n'
        '    name = "test_mod"\n'
        '    description = "A test module"\n'
        '    version = "0.1.0"\n'
        '    async def handle(self, message, context):\n'
        '        return "ok"\n'
    )
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("must not import from nexus.kernel" in e for e in result.errors)


def test_no_tests_directory(validator, valid_module):
    """Missing tests/ directory is an error."""
    import shutil
    shutil.rmtree(valid_module / "tests")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("tests/ directory not found" in e for e in result.errors)


def test_insufficient_tests(validator, valid_module):
    """Fewer than 4 tests for a module is an error."""
    (valid_module / "tests" / "test_module.py").write_text(
        'def test_one(): pass\n'
        'def test_two(): pass\n'
    )
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("minimum is 4" in e for e in result.errors)


def test_insufficient_agent_tests(validator, valid_agent):
    """Fewer than 6 tests for an agent is an error."""
    (valid_agent / "tests" / "test_agent.py").write_text(
        'def test_one(): pass\n'
        'def test_two(): pass\n'
        'def test_three(): pass\n'
    )
    result = validator.validate(str(valid_agent))
    assert result.valid is False
    assert any("minimum is 6" in e for e in result.errors)


def test_missing_readme(validator, valid_module):
    """Missing README.md is an error."""
    os.remove(valid_module / "README.md")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("README.md not found" in e for e in result.errors)


def test_empty_readme(validator, valid_module):
    """README.md with too little content is an error."""
    (valid_module / "README.md").write_text("# hi")
    result = validator.validate(str(valid_module))
    assert result.valid is False
    assert any("meaningful content" in e for e in result.errors)


def test_validation_result_dataclass():
    """ValidationResult is a proper dataclass."""
    result = ValidationResult(valid=True, errors=[], warnings=["minor issue"])
    assert result.valid is True
    assert result.errors == []
    assert result.warnings == ["minor issue"]


def test_agent_checks_analyze_method(validator, valid_agent):
    """Agent without analyze() is an error."""
    (valid_agent / "agent.py").write_text(
        'from nexus.agents.base import AgentModule\n'
        'class TestAgentAgent(AgentModule):\n'
        '    name = "test_agent"\n'
        '    description = "A test agent"\n'
        '    version = "0.1.0"\n'
    )
    result = validator.validate(str(valid_agent))
    assert result.valid is False
    assert any("must implement analyze()" in e for e in result.errors)

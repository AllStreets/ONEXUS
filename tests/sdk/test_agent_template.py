"""
Tests for the agent template generator.
"""
from __future__ import annotations

import json

from nexus.sdk.agent_template import generate_agent


def test_generate_agent_returns_all_files():
    """generate_agent() returns the four expected file paths."""
    files = generate_agent(
        name="scanner",
        description="Scans directories for file patterns",
        author="allstreets",
        keywords=["scan", "find files"],
    )
    assert "agent.py" in files
    assert "manifest.json" in files
    assert "tests/test_agent.py" in files
    assert "README.md" in files


def test_agent_py_has_correct_class():
    """Generated agent.py subclasses AgentModule with all four tier methods."""
    files = generate_agent(
        name="scanner",
        description="Scans directories",
        author="allstreets",
        keywords=["scan"],
    )
    source = files["agent.py"]
    assert "class ScannerAgent(AgentModule):" in source
    assert 'name = "scanner"' in source
    assert "from nexus.agents.base import AgentModule" in source
    assert "async def analyze(self" in source
    assert "async def suggest(self" in source
    assert "async def monitor(self" in source
    assert "async def coordinate(self" in source


def test_agent_py_no_kernel_imports():
    """Generated agent.py must not import from nexus.kernel."""
    files = generate_agent(
        name="test_agent",
        description="A test agent module",
        author="dev",
        keywords=["test"],
    )
    assert "nexus.kernel" not in files["agent.py"]


def test_manifest_json_valid_schema():
    """Generated manifest.json includes type: agent and matches schema."""
    files = generate_agent(
        name="scanner",
        description="Scans directories for file patterns",
        author="allstreets",
        keywords=["scan", "find files"],
        watch_events=["filesystem.changed"],
        coordination_targets=["vigil"],
    )
    data = json.loads(files["manifest.json"])
    assert data["name"] == "scanner"
    assert data["type"] == "agent"
    assert data["tier"] == "community"
    assert data["watch_events"] == ["filesystem.changed"]
    assert data["coordination_targets"] == ["vigil"]


def test_test_file_has_minimum_tests():
    """Generated test file has at least 6 test stubs."""
    files = generate_agent(
        name="scanner",
        description="Scans directories",
        author="allstreets",
        keywords=["scan"],
    )
    test_source = files["tests/test_agent.py"]
    test_count = test_source.count("def test_")
    assert test_count >= 6


def test_readme_has_trust_tier_table():
    """Generated README.md includes the trust tier table."""
    files = generate_agent(
        name="scanner",
        description="Scans directories for file patterns",
        author="allstreets",
        keywords=["scan"],
    )
    readme = files["README.md"]
    assert "Trust Tiers" in readme
    assert "SKILL" in readme
    assert "SOVEREIGN" in readme


def test_watch_events_in_code():
    """Watch events appear in agent.py class attributes."""
    files = generate_agent(
        name="scanner",
        description="Scans directories for patterns",
        author="dev",
        keywords=["scan"],
        watch_events=["filesystem.changed", "network.request"],
    )
    source = files["agent.py"]
    assert "filesystem.changed" in source
    assert "network.request" in source


def test_class_name_from_underscored_name():
    """Agent names with underscores produce PascalCase class names."""
    files = generate_agent(
        name="file_scanner",
        description="Scans files for patterns",
        author="dev",
        keywords=["scan"],
    )
    assert "class FileScannerAgent(AgentModule):" in files["agent.py"]

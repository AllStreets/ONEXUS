"""
Tests for the module template generator.
"""
from __future__ import annotations

import json

from nexus.sdk.module_template import generate_module


def test_generate_module_returns_all_files():
    """generate_module() returns the four expected file paths."""
    files = generate_module(
        name="summarizer",
        description="Summarizes text using the local LLM",
        author="allstreets",
        keywords=["summarize", "summary", "tldr"],
    )
    assert "module.py" in files
    assert "manifest.json" in files
    assert "tests/test_module.py" in files
    assert "README.md" in files


def test_module_py_has_correct_class():
    """Generated module.py subclasses NexusModule with correct attributes."""
    files = generate_module(
        name="summarizer",
        description="Summarizes text",
        author="allstreets",
        keywords=["summarize"],
    )
    source = files["module.py"]
    assert "class SummarizerModule(NexusModule):" in source
    assert 'name = "summarizer"' in source
    assert "async def handle(self" in source
    assert "from nexus.modules.base import NexusModule" in source


def test_module_py_no_kernel_imports():
    """Generated module.py must not import from nexus.kernel."""
    files = generate_module(
        name="test_mod",
        description="A test module",
        author="dev",
        keywords=["test"],
    )
    assert "nexus.kernel" not in files["module.py"]


def test_manifest_json_valid_schema():
    """Generated manifest.json matches the required schema."""
    files = generate_module(
        name="summarizer",
        description="Summarizes text using the local LLM",
        author="allstreets",
        keywords=["summarize", "summary"],
    )
    data = json.loads(files["manifest.json"])
    assert data["name"] == "summarizer"
    assert data["author"] == "allstreets"
    assert data["version"] == "0.1.0"
    assert data["tier"] == "community"
    assert isinstance(data["keywords"], list)
    assert "license" in data


def test_test_file_has_minimum_tests():
    """Generated test file has at least 4 test stubs."""
    files = generate_module(
        name="summarizer",
        description="Summarizes text",
        author="allstreets",
        keywords=["summarize"],
    )
    test_source = files["tests/test_module.py"]
    test_count = test_source.count("def test_")
    assert test_count >= 4


def test_readme_has_content():
    """Generated README.md has meaningful content."""
    files = generate_module(
        name="summarizer",
        description="Summarizes text using the local LLM",
        author="allstreets",
        keywords=["summarize", "summary"],
    )
    readme = files["README.md"]
    assert "summarizer" in readme
    assert "allstreets" in readme
    assert len(readme) >= 50


def test_class_name_from_underscored_name():
    """Module names with underscores produce PascalCase class names."""
    files = generate_module(
        name="file_scanner",
        description="Scans files for patterns",
        author="dev",
        keywords=["scan"],
    )
    assert "class FileScannerModule(NexusModule):" in files["module.py"]

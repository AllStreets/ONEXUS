"""
Tests for site/scripts/generate-docs.py

Uses importlib to handle the hyphenated module name.
"""
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "site" / "scripts"))
import importlib

generate_docs = importlib.import_module("generate-docs")
extract_module_info = generate_docs.extract_module_info
extract_cortex_keywords = generate_docs.extract_cortex_keywords
render_module_page = generate_docs.render_module_page
render_kernel_page = generate_docs.render_kernel_page
render_routing_page = generate_docs.render_routing_page


# ---------------------------------------------------------------------------
# extract_module_info
# ---------------------------------------------------------------------------

def test_extract_module_info_basic_class():
    source = textwrap.dedent("""
        \"\"\"Module-level docstring for testing.\"\"\"
        from nexus.modules.base import NexusModule
        from typing import Any

        class OracleModule(NexusModule):
            name = "oracle"
            description = "Anticipatory trigger engine"
            version = "0.2.0"

            def add_rule(self, rule: str) -> None:
                \"\"\"Add a new trigger rule.\"\"\"
                pass

            async def handle(self, message: str, context: dict) -> str:
                \"\"\"Handle incoming message.\"\"\"
                return ""
    """)
    info = extract_module_info(source, "oracle.py")
    assert info is not None
    assert info["class_name"] == "OracleModule"
    assert info["name"] == "oracle"
    assert info["description"] == "Anticipatory trigger engine"
    assert info["version"] == "0.2.0"
    assert "Module-level docstring" in info["module_docstring"]
    method_names = [m["name"] for m in info["methods"]]
    assert "handle" in method_names
    assert "add_rule" in method_names


def test_extract_module_info_with_dataclasses():
    source = textwrap.dedent("""
        from dataclasses import dataclass
        from nexus.modules.base import NexusModule

        @dataclass
        class TriggerRule:
            name: str
            threshold: float
            weight: float = 1.0

        class OracleModule(NexusModule):
            name = "oracle"
            description = "Test module"
            version = "0.1.0"

            async def handle(self, message: str, context: dict) -> str:
                return ""
    """)
    info = extract_module_info(source, "oracle.py")
    assert info is not None
    assert len(info["dataclasses"]) == 1
    dc = info["dataclasses"][0]
    assert dc["name"] == "TriggerRule"
    field_names = [f["name"] for f in dc["fields"]]
    assert "name" in field_names
    assert "threshold" in field_names
    assert "weight" in field_names
    # Check types
    weight_field = next(f for f in dc["fields"] if f["name"] == "weight")
    assert weight_field["type"] == "float"
    assert weight_field["default"] == "1.0"


def test_extract_module_info_skips_private_methods():
    source = textwrap.dedent("""
        from nexus.modules.base import NexusModule

        class SentryModule(NexusModule):
            name = "sentry"
            description = "Cognitive load model"
            version = "0.1.0"

            def public_method(self) -> None:
                \"\"\"This should appear.\"\"\"
                pass

            def _private_method(self) -> None:
                \"\"\"This should be skipped.\"\"\"
                pass

            def __dunder_method(self) -> None:
                \"\"\"Also skipped.\"\"\"
                pass

            async def handle(self, message: str, context: dict) -> str:
                \"\"\"Handle — should appear.\"\"\"
                return ""
    """)
    info = extract_module_info(source, "sentry.py")
    assert info is not None
    method_names = [m["name"] for m in info["methods"]]
    assert "public_method" in method_names
    assert "handle" in method_names
    assert "_private_method" not in method_names
    assert "__dunder_method" not in method_names


def test_extract_module_info_no_class_returns_none():
    source = textwrap.dedent("""
        # Just a plain Python file with no classes
        def some_function():
            pass

        SOME_CONST = 42
    """)
    result = extract_module_info(source, "no_class.py")
    assert result is None


# ---------------------------------------------------------------------------
# extract_cortex_keywords
# ---------------------------------------------------------------------------

def test_extract_cortex_keywords():
    source = textwrap.dedent("""
        class Cortex:
            _MODULE_KEYWORDS: dict[str, list[str]] = {
                "oracle": ["trigger", "alert", "monitor"],
                "sentry": ["cognitive", "focus", "fatigue"],
                "atlas": ["fact", "knowledge", "world model"],
            }
    """)
    keywords = extract_cortex_keywords(source)
    assert isinstance(keywords, dict)
    assert "oracle" in keywords
    assert "sentry" in keywords
    assert "atlas" in keywords
    assert "trigger" in keywords["oracle"]
    assert "cognitive" in keywords["sentry"]


def test_extract_cortex_keywords_empty_source():
    source = textwrap.dedent("""
        # No _MODULE_KEYWORDS here
        class SomeClass:
            pass
    """)
    result = extract_cortex_keywords(source)
    assert result == {}


# ---------------------------------------------------------------------------
# render_module_page
# ---------------------------------------------------------------------------

def test_render_module_page_has_frontmatter():
    info = {
        "class_name": "OracleModule",
        "name": "oracle",
        "description": "Anticipatory trigger engine",
        "version": "0.1.0",
        "module_docstring": "Oracle scans input for patterns.",
        "methods": [
            {
                "name": "handle",
                "signature": "handle(self, message: str, context: dict) -> str",
                "docstring": "Handle incoming message.",
                "is_async": True,
            }
        ],
        "dataclasses": [
            {
                "name": "TriggerRule",
                "fields": [
                    {"name": "name", "type": "str", "default": None},
                    {"name": "threshold", "type": "float", "default": None},
                ],
            }
        ],
    }
    keywords = ["trigger", "alert", "monitor"]
    page = render_module_page(info, keywords)
    assert "---" in page
    assert "oracle" in page.lower()
    assert "Anticipatory trigger engine" in page
    assert "trigger" in page
    assert "TriggerRule" in page
    assert "handle" in page


# ---------------------------------------------------------------------------
# render_kernel_page
# ---------------------------------------------------------------------------

def test_render_kernel_page_has_frontmatter():
    info = {
        "class_name": "Chronicle",
        "name": "chronicle",
        "description": "Immutable audit trail",
        "version": "0.1.0",
        "module_docstring": "Chronicle logs every Nexus action.",
        "methods": [
            {
                "name": "log",
                "signature": "log(self, source: str, action: str) -> str",
                "docstring": "Append an audit event.",
                "is_async": False,
            }
        ],
        "dataclasses": [],
    }
    page = render_kernel_page(info)
    assert "---" in page
    assert "chronicle" in page.lower()
    assert "Chronicle logs every Nexus action." in page or "Overview" in page


# ---------------------------------------------------------------------------
# render_routing_page
# ---------------------------------------------------------------------------

def test_render_routing_page():
    keywords = {
        "oracle": ["trigger", "alert", "monitor"],
        "sentry": ["cognitive", "focus", "fatigue"],
    }
    page = render_routing_page(keywords)
    assert "oracle" in page
    assert "sentry" in page
    assert "trigger" in page
    assert "cognitive" in page

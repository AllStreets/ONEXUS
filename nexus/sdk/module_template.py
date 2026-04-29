"""
Module template generator for NEXUS community modules.
"""
from __future__ import annotations

import json
import textwrap


def generate_module(
    name: str,
    description: str,
    author: str,
    keywords: list[str],
) -> dict[str, str]:
    """Generate all files for a new module. Returns {filepath: content}."""

    class_name = "".join(word.capitalize() for word in name.replace("-", "_").split("_")) + "Module"

    module_py = textwrap.dedent(f'''\
        """
        {class_name} -- {description}
        """
        from __future__ import annotations

        from typing import Any

        from nexus.modules.base import NexusModule


        class {class_name}(NexusModule):
            name = "{name}"
            description = "{description}"
            version = "0.1.0"
            requires_network = False

            async def handle(self, message: str, context: dict[str, Any]) -> str:
                """Process a user message and return a response string.

                TODO: Implement your module logic here.
                """
                raise NotImplementedError("Implement handle() for {name}")

            async def on_load(self, context: dict[str, Any] | None = None) -> None:
                """Called when the module is loaded into the kernel."""
                pass

            async def on_unload(self, context: dict[str, Any] | None = None) -> None:
                """Called when the module is unloaded from the kernel."""
                pass
    ''')

    manifest = json.dumps(
        {
            "name": name,
            "author": author,
            "description": description,
            "version": "0.1.0",
            "tier": "community",
            "keywords": keywords,
            "license": "MIT",
        },
        indent=2,
    ) + "\n"

    test_py = textwrap.dedent(f'''\
        """
        Tests for {class_name}.
        """
        from __future__ import annotations

        import pytest
        from unittest.mock import AsyncMock

        from module import {class_name}


        @pytest.fixture
        def module():
            return {class_name}()


        @pytest.fixture
        def context():
            return {{
                "engram": AsyncMock(),
                "chronicle": AsyncMock(),
                "aegis": AsyncMock(),
                "pulse": AsyncMock(),
                "llm": AsyncMock(return_value="LLM response"),
            }}


        def test_module_attributes(module):
            """Module declares required class attributes."""
            assert module.name == "{name}"
            assert module.description
            assert module.version == "0.1.0"


        def test_module_repr(module):
            """Module has a readable repr."""
            assert "{name}" in repr(module)


        @pytest.mark.asyncio
        async def test_handle_returns_string(module, context):
            """handle() returns a non-empty string."""
            # TODO: Replace with real input once handle() is implemented
            result = await module.handle("test input", context)
            assert isinstance(result, str)
            assert len(result) > 0


        @pytest.mark.asyncio
        async def test_handle_with_empty_input(module, context):
            """handle() handles empty input gracefully."""
            result = await module.handle("", context)
            assert isinstance(result, str)
    ''')

    readme_md = textwrap.dedent(f"""\
        # {name}

        > {description}

        **Author:** {author}
        **Version:** 0.1.0
        **Keywords:** {", ".join(keywords)}

        ## Installation

        ```bash
        nexus install {author}/{name}
        ```

        ## Usage

        Once installed, the module responds to messages containing its keywords.

        ## Development

        ```bash
        # Run tests
        pytest tests/ -v

        # Validate package before submitting
        nexus validate .
        ```

        ## License

        MIT
    """)

    return {
        "module.py": module_py,
        "manifest.json": manifest,
        "tests/test_module.py": test_py,
        "README.md": readme_md,
    }

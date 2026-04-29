"""
Agent template generator for NEXUS community agents.
"""
from __future__ import annotations

import json
import textwrap


def generate_agent(
    name: str,
    description: str,
    author: str,
    keywords: list[str],
    watch_events: list[str] | None = None,
    coordination_targets: list[str] | None = None,
) -> dict[str, str]:
    """Generate all files for a new agent. Returns {filepath: content}."""

    watch_events = watch_events or []
    coordination_targets = coordination_targets or []

    class_name = "".join(word.capitalize() for word in name.replace("-", "_").split("_")) + "Agent"

    watch_repr = repr(watch_events)
    coord_repr = repr(coordination_targets)

    agent_py = textwrap.dedent(f'''\
        """
        {class_name} -- {description}
        """
        from __future__ import annotations

        from typing import Any

        from nexus.agents.base import AgentModule


        class {class_name}(AgentModule):
            name = "{name}"
            description = "{description}"
            version = "0.1.0"
            requires_network = False

            watch_events = {watch_repr}
            coordination_targets = {coord_repr}

            async def analyze(self, message: str, context: dict[str, Any]) -> str:
                """Core analysis logic. Runs at every trust level.

                This method MUST work without an LLM connection (pattern-based).
                TODO: Implement your analysis logic here.
                """
                raise NotImplementedError("Implement analyze() for {name}")

            async def suggest(self, message: str, context: dict[str, Any]) -> str:
                """Proactive suggestions at ADVISOR+ trust.

                Return a suggestion string, or empty string for no suggestion.
                """
                return ""

            async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
                """Background event monitoring at MONITOR+ trust.

                Called when a subscribed Pulse event fires. Return a finding
                string to publish, or None to stay silent.
                """
                return None

            async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
                """Cross-agent coordination at SOVEREIGN trust.

                Route analysis results to other agents for combined analysis.
                """
                return ""

            async def on_load(self, context: dict[str, Any] | None = None) -> None:
                """Called when the agent is loaded into the kernel."""
                await super().on_load(context)

            async def on_unload(self, context: dict[str, Any] | None = None) -> None:
                """Called when the agent is unloaded from the kernel."""
                await super().on_unload(context)
    ''')

    manifest_data = {
        "name": name,
        "author": author,
        "description": description,
        "version": "0.1.0",
        "tier": "community",
        "type": "agent",
        "keywords": keywords,
        "license": "MIT",
    }
    if watch_events:
        manifest_data["watch_events"] = watch_events
    if coordination_targets:
        manifest_data["coordination_targets"] = coordination_targets

    manifest = json.dumps(manifest_data, indent=2) + "\n"

    test_py = textwrap.dedent(f'''\
        """
        Tests for {class_name}.
        """
        from __future__ import annotations

        import pytest
        from unittest.mock import AsyncMock

        from agent import {class_name}


        @pytest.fixture
        def agent():
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


        def test_agent_attributes(agent):
            """Agent declares required class attributes."""
            assert agent.name == "{name}"
            assert agent.description
            assert agent.version == "0.1.0"
            assert isinstance(agent.watch_events, list)
            assert isinstance(agent.coordination_targets, list)


        def test_agent_repr(agent):
            """Agent has a readable repr."""
            assert "{name}" in repr(agent)


        @pytest.mark.asyncio
        async def test_analyze_pattern_based(agent, context):
            """analyze() works with pattern-based input (no LLM)."""
            # TODO: Replace with real input once analyze() is implemented
            result = await agent.analyze("test input", context)
            assert isinstance(result, str)
            assert len(result) > 0


        @pytest.mark.asyncio
        async def test_analyze_with_llm(agent, context):
            """analyze() can use LLM when available."""
            context["llm"] = AsyncMock(return_value="LLM analysis")
            result = await agent.analyze("complex query", context)
            assert isinstance(result, str)


        @pytest.mark.asyncio
        async def test_suggest(agent, context):
            """suggest() returns a string (possibly empty)."""
            result = await agent.suggest("some context", context)
            assert isinstance(result, str)


        @pytest.mark.asyncio
        async def test_monitor(agent, context):
            """monitor() returns a string or None."""
            event = {{"topic": "test.event", "payload": {{}}}}
            result = await agent.monitor(event, context)
            assert result is None or isinstance(result, str)


        @pytest.mark.asyncio
        async def test_coordinate(agent, context):
            """coordinate() returns a string (possibly empty)."""
            result = await agent.coordinate("analysis result", context)
            assert isinstance(result, str)
    ''')

    # Build trust tier table for README
    trust_table = (
        "| Tier | Score | Behavior |\n"
        "|------|-------|----------|\n"
        "| SKILL | 0-24 | User invokes explicitly. No initiative. |\n"
        "| ADVISOR | 25-49 | Suggests actions when relevant context detected. |\n"
        "| MONITOR | 50-74 | Proactively watches events and reports findings. |\n"
        "| AUTONOMOUS | 75-99 | Acts within defined boundaries without asking. |\n"
        "| SOVEREIGN | 100 | Coordinates with other agents independently. |"
    )

    watch_section = ""
    if watch_events:
        watch_section = f"\n**Watch Events:** {', '.join(watch_events)}"

    coord_section = ""
    if coordination_targets:
        coord_section = f"\n**Coordination Targets:** {', '.join(coordination_targets)}"

    readme_md = textwrap.dedent(f"""\
        # {name}

        > {description}

        **Author:** {author}
        **Version:** 0.1.0
        **Type:** Agent
        **Keywords:** {", ".join(keywords)}{watch_section}{coord_section}

        ## Trust Tiers

        {trust_table}

        ## Installation

        ```bash
        nexus install {author}/{name}
        ```

        ## Usage

        This agent progresses through trust tiers as it demonstrates reliability.
        At each tier, additional capabilities unlock automatically.

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
        "agent.py": agent_py,
        "manifest.json": manifest,
        "tests/test_agent.py": test_py,
        "README.md": readme_md,
    }

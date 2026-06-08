"""Tests for the current_agent contextvar helpers."""
from __future__ import annotations

import asyncio
import pytest

from nexus.context import current_agent_slug, set_current_agent


def test_default_is_none():
    assert current_agent_slug() is None


def test_set_and_get():
    token = set_current_agent("aider")
    try:
        assert current_agent_slug() == "aider"
    finally:
        # Restore the previous value (None)
        from nexus.context import reset_current_agent
        reset_current_agent(token)
    assert current_agent_slug() is None


@pytest.mark.asyncio
async def test_isolated_across_tasks():
    """Each asyncio task sees its own current_agent value (contextvars semantics)."""
    from nexus.context import reset_current_agent

    seen: dict[str, str | None] = {}

    async def actor(name: str):
        token = set_current_agent(name)
        try:
            await asyncio.sleep(0.01)
            seen[name] = current_agent_slug()
        finally:
            reset_current_agent(token)

    await asyncio.gather(actor("a"), actor("b"), actor("c"))
    assert seen == {"a": "a", "b": "b", "c": "c"}


@pytest.mark.asyncio
async def test_contextmanager_helper():
    """`as_agent(slug)` async context manager: sets and restores cleanly."""
    from nexus.context import as_agent

    assert current_agent_slug() is None
    async with as_agent("council"):
        assert current_agent_slug() == "council"
    assert current_agent_slug() is None

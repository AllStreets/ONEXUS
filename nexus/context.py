"""
Per-task context for the currently-executing agent.

Set by InProcessAgent.call_tool / MCPAgent.call_tool before dispatch.
Read by KernelHttpClient + aegis.network() to determine which agent's
network policy applies.
"""
from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from typing import Optional

_current_agent: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "nexus_current_agent", default=None,
)


def current_agent_slug() -> Optional[str]:
    """Return the slug of the agent currently dispatching a tool call, or None."""
    return _current_agent.get()


def set_current_agent(slug: Optional[str]) -> contextvars.Token:
    """Set the current agent. Returns a token; pass it to reset_current_agent()."""
    return _current_agent.set(slug)


def reset_current_agent(token: contextvars.Token) -> None:
    """Restore the previous agent context."""
    _current_agent.reset(token)


@asynccontextmanager
async def as_agent(slug: Optional[str]):
    """Async context manager wrapping set/reset."""
    token = set_current_agent(slug)
    try:
        yield
    finally:
        reset_current_agent(token)

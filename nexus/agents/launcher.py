"""
AgentLauncher — process supervisor for runnable ONEXUS-Agents.

Owns the in-memory `_running` dict, exposes launch/stop/list operations
that don't depend on FastAPI Request, so both HTTP routes and the
in-kernel agent-dispatcher module can use the same service.
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("nexus.agents.launcher")

# Command allowlist for launching agent adapters. The catalog is a sibling
# repo refreshed nightly from upstream; an adapter manifest with
# ``runnable: true`` and an arbitrary ``command`` would otherwise be executed
# verbatim. Only these known MCP launcher binaries may be spawned. Operators
# can extend the set explicitly via NEXUS_AGENT_COMMAND_ALLOWLIST (a
# comma- or whitespace-separated list); they cannot be silently widened by a
# catalog update.
_DEFAULT_COMMAND_ALLOWLIST = frozenset(
    {
        "python",
        "python3",
        "node",
        "npx",
        "uv",
        "uvx",
        "deno",
        "bun",
        "docker",
        "aider-mcp",
    }
)


def _command_allowlist() -> frozenset[str]:
    extra = os.environ.get("NEXUS_AGENT_COMMAND_ALLOWLIST", "")
    if not extra.strip():
        return _DEFAULT_COMMAND_ALLOWLIST
    tokens = {t for t in extra.replace(",", " ").split() if t}
    return _DEFAULT_COMMAND_ALLOWLIST | tokens


def _command_basename(command: str) -> str:
    # Match on the bare program name so an absolute path to an allowed binary
    # is fine, but a path to a planted binary still has to clear the allowlist
    # by basename. Reject anything with shell metacharacters outright.
    return os.path.basename(command)


@dataclass
class RunningAgent:
    slug: str
    name: str
    category: str
    process: subprocess.Popen
    tools: list[str]
    trust_floor: float


class AgentLaunchError(Exception):
    """Raised when an agent cannot be launched (not found, not runnable, no command, etc.)."""

    def __init__(self, message: str, *, status: int = 500):
        super().__init__(message)
        self.status = status


class AgentLauncher:
    def __init__(self, catalog: Any, kernel: Any):
        self._catalog = catalog
        self._kernel = kernel
        self._running: dict[str, RunningAgent] = {}

    # -- queries -----------------------------------------------------------

    def is_running(self, slug: str) -> bool:
        agent = self._running.get(slug)
        if agent is None:
            return False
        if agent.process.poll() is not None:
            del self._running[slug]
            return False
        return True

    def get(self, slug: str) -> RunningAgent | None:
        if not self.is_running(slug):
            return None
        return self._running.get(slug)

    def list_running(self) -> list[RunningAgent]:
        # Reap dead processes lazily.
        dead = [s for s, a in self._running.items() if a.process.poll() is not None]
        for s in dead:
            del self._running[s]
        return list(self._running.values())

    # -- mutations ---------------------------------------------------------

    def launch(self, slug: str) -> RunningAgent:
        existing = self.get(slug)
        if existing:
            return existing

        entry = self._catalog.get_agent(slug)
        if not entry:
            raise AgentLaunchError(f"Agent '{slug}' not found", status=404)
        if not entry.runnable:
            raise AgentLaunchError(f"Agent '{slug}' is not runnable", status=400)

        adapter = self._catalog.load_adapter(entry)
        if not adapter:
            raise AgentLaunchError(f"Could not load adapter for '{slug}'")

        if not adapter.command:
            raise AgentLaunchError(f"Adapter for '{slug}' has no command", status=400)
        # Guard against a malicious/typo'd upstream manifest reaching exec.
        # Reject shell metacharacters (plain names and absolute paths quote to
        # themselves; anything with spaces/;/$/backticks does not), then
        # allowlist by program basename before we ever spawn.
        if shlex.quote(adapter.command) != adapter.command:
            raise AgentLaunchError(
                f"Adapter command for '{slug}' contains unsafe characters: "
                f"{adapter.command!r}",
                status=400,
            )
        base = _command_basename(adapter.command)
        if base not in _command_allowlist():
            raise AgentLaunchError(
                f"Adapter command '{adapter.command}' for '{slug}' is not on the "
                f"launch allowlist. If you trust it, add it to "
                f"NEXUS_AGENT_COMMAND_ALLOWLIST.",
                status=400,
            )

        env = dict(os.environ)
        if self._kernel.provider_router:
            for pname, provider in self._kernel.provider_router._providers.items():
                if hasattr(provider, "_api_key"):
                    if pname == "openai":
                        env.setdefault("OPENAI_API_KEY", provider._api_key)
                    elif pname == "anthropic":
                        env.setdefault("ANTHROPIC_API_KEY", provider._api_key)

        try:
            proc = subprocess.Popen(
                [adapter.command] + adapter.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            raise AgentLaunchError(
                f"Command '{adapter.command}' not found. Install the agent first."
            )
        except Exception as exc:
            raise AgentLaunchError(f"Failed to launch: {exc}")

        tools = adapter.capabilities.get("tools", [])
        running = RunningAgent(
            slug=slug,
            name=entry.name,
            category=entry.category,
            process=proc,
            tools=tools,
            trust_floor=adapter.trust_floor,
        )
        self._running[slug] = running

        self._kernel.aegis.set_policy(
            f"agent.{slug}", allowed=True,
            initial_trust=adapter.trust_floor,
        )
        self._kernel.chronicle.log("agents", "agent_launched", {
            "slug": slug, "name": entry.name,
            "pid": proc.pid, "tools": tools,
            "trust_floor": adapter.trust_floor,
        })
        return running

    def stop(self, slug: str) -> RunningAgent:
        agent = self._running.get(slug)
        if agent is None:
            raise AgentLaunchError(f"Agent '{slug}' is not running", status=404)
        if agent.process.poll() is None:
            agent.process.terminate()
            try:
                agent.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent.process.kill()
        self._kernel.chronicle.log("agents", "agent_stopped", {
            "slug": slug, "name": agent.name,
        })
        del self._running[slug]
        return agent

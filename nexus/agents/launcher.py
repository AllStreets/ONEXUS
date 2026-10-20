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

from nexus.agents.child_env import child_environment
from nexus.agents.confine import (
    ConfinedLaunch,
    Confinement,
    ConfinementError,
    docker_available,
    prepare,
)

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


def confinement_mode() -> str:
    """NEXUS_AGENT_CONFINEMENT: `prefer` (default) confines every adapter that declares a
    confinement block and records the rest as unconfined; `require` refuses to launch an
    unconfined agent at all; `off` runs everything as a child process (for debugging)."""
    mode = os.environ.get("NEXUS_AGENT_CONFINEMENT", "prefer").strip().lower()
    return mode if mode in {"prefer", "require", "off"} else "prefer"


@dataclass
class RunningAgent:
    slug: str
    name: str
    category: str
    process: subprocess.Popen
    tools: list[str]
    trust_floor: float
    confined: bool = False
    confinement: ConfinedLaunch | None = None


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

        # Red-team round 2 (R2-1, R2-2): the agent gets a small baseline plus the
        # variables its adapter declares, never the operator's whole environment, and
        # a provider key only when it declared that variable. See child_env.py.
        provider_keys: dict[str, str] = {}
        if self._kernel.provider_router:
            for pname, provider in self._kernel.provider_router._providers.items():
                key = getattr(provider, "_api_key", None)
                if key and pname == "openai":
                    provider_keys["OPENAI_API_KEY"] = key
                elif key and pname == "anthropic":
                    provider_keys["ANTHROPIC_API_KEY"] = key
        env = child_environment(adapter.env.keys(), provider_keys=provider_keys)

        # Red-team round 3 (R3-1..R3-3): an adapter that declares confinement runs in a
        # container that sees none of the operator's files and reaches only the hosts it
        # declared. See confine.py.
        mode = confinement_mode()
        try:
            conf = Confinement.from_adapter(getattr(adapter, "confinement", None)) if mode != "off" else None
        except ConfinementError as exc:
            raise AgentLaunchError(f"Adapter for '{slug}' has an invalid confinement block: {exc}", status=400)
        if conf is None and mode == "require":
            raise AgentLaunchError(
                f"'{slug}' declares no confinement and NEXUS_AGENT_CONFINEMENT=require, so it "
                f"will not run unconfined.", status=403,
            )
        confined: ConfinedLaunch | None = None
        if conf is not None:
            if not docker_available():
                raise AgentLaunchError(
                    f"'{slug}' declares confinement but Docker isn't available, so it will not "
                    f"run unconfined. Start Docker, or set NEXUS_AGENT_CONFINEMENT=off to debug.",
                    status=503,
                )
            try:
                confined = prepare(conf, slug, adapter.command, adapter.args, env.keys())
            except subprocess.CalledProcessError as exc:
                raise AgentLaunchError(f"Could not set up confinement for '{slug}': {exc.stderr or exc}")
            argv = confined.argv
        else:
            argv = [adapter.command] + adapter.args

        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            if confined:
                confined.cleanup()
            raise AgentLaunchError(
                f"Command '{argv[0]}' not found. Install the agent first."
            )
        except Exception as exc:
            if confined:
                confined.cleanup()
            raise AgentLaunchError(f"Failed to launch: {exc}")

        tools = adapter.capabilities.get("tools", [])
        running = RunningAgent(
            slug=slug,
            name=entry.name,
            category=entry.category,
            process=proc,
            tools=tools,
            trust_floor=adapter.trust_floor,
            confined=confined is not None,
            confinement=confined,
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
            "confined": confined is not None,
            "hosts": list(conf.hosts) if conf else None,
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
        if agent.confinement:
            agent.confinement.cleanup()
        self._kernel.chronicle.log("agents", "agent_stopped", {
            "slug": slug, "name": agent.name,
        })
        del self._running[slug]
        return agent

"""
AgentDispatcher — kernel-side console surface for the ONEXUS-Agents catalog.

Handles SUMMON intent ('summon X', 'launch X', 'list agents', 'stop X',
'agents <query>'). Wraps an AgentLauncher service that the API routes also
share, so process lifecycle stays in one place.

Registers unconditionally — even when the catalog cannot be loaded — so the
console always has a clear answer for agent-related queries instead of
silently falling back to council deliberation.
"""
from __future__ import annotations

import re
from typing import Any

from nexus.agents.launcher import AgentLauncher, AgentLaunchError
from nexus.modules.base import NexusModule


class AgentDispatcherModule(NexusModule):
    name = "agents"
    description = "Console surface for browsing and summoning runnable ONEXUS-Agents"
    version = "0.1.0"

    def __init__(
        self,
        catalog: Any | None = None,
        launcher: AgentLauncher | None = None,
        unavailable_reason: str | None = None,
    ):
        self._catalog = catalog
        self._launcher = launcher
        self._unavailable_reason = unavailable_reason

    def _unavailable(self) -> str:
        reason = self._unavailable_reason or "Catalog not configured."
        return (
            "[Agents] ONEXUS-Agents catalog is not available.\n"
            f"  Reason: {reason}\n"
            "  Fix: ensure /Users/<you>/Downloads/ONEXUS-Agents is readable by\n"
            "       the running python (System Settings → Privacy & Security →\n"
            "       Files and Folders → grant Downloads access), then restart."
        )

    # -- command parsing ---------------------------------------------------

    _SUMMON = re.compile(r"^(summon|launch|run|invoke|spawn-agent|start)\s+(.+)$", re.IGNORECASE)
    _STOP = re.compile(r"^(stop|kill|terminate|dismiss)\s+(.+)$", re.IGNORECASE)
    _LIST = re.compile(r"^(list|show|catalog)\b", re.IGNORECASE)
    _RUNNING = re.compile(r"\b(running|active)\b", re.IGNORECASE)
    _SEARCH = re.compile(r"^(search|find|agents?)\s+(.+)$", re.IGNORECASE)

    def _normalize_slug(self, raw: str) -> str:
        token = raw.strip().split()[0].lower()
        return token.strip(".,:;\"'")

    def _summarize_running(self) -> str:
        running = self._launcher.list_running()
        if not running:
            return "[Agents] No agents currently running."
        lines = [f"[Agents] {len(running)} running:"]
        for a in running:
            tools = ", ".join(a.tools[:3]) + ("…" if len(a.tools) > 3 else "")
            lines.append(f"  - {a.slug} ({a.name}) — PID {a.process.pid}; tools: {tools or 'none'}")
        return "\n".join(lines)

    def _summarize_catalog(self, limit: int = 10) -> str:
        runnable = self._catalog.list_agents(runnable_only=True)[:limit]
        total = len(self._catalog.list_agents())
        runnable_total = len(self._catalog.list_agents(runnable_only=True))
        lines = [
            f"[Agents] Catalog: {total} agents total, {runnable_total} runnable.",
            f"  Top {min(limit, runnable_total)} runnable by composite score:",
        ]
        for e in runnable:
            lines.append(f"  - {e.slug} — {e.name} ({e.category}) [{e.tagline[:60]}]")
        if runnable_total > limit:
            lines.append(f"  …and {runnable_total - limit} more. Try: agents <query>")
        return "\n".join(lines)

    def _summarize_search(self, query: str, limit: int = 8) -> str:
        results = self._catalog.search(query, limit=limit)
        if not results:
            return f"[Agents] No agents matching '{query}'."
        lines = [f"[Agents] {len(results)} match(es) for '{query}':"]
        for e in results:
            mark = "*" if e.runnable else " "
            lines.append(f"  {mark} {e.slug} — {e.name} ({e.category})")
        lines.append("  (* = runnable; summon <slug> to launch)")
        return "\n".join(lines)

    # -- main entry --------------------------------------------------------

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if self._catalog is None or self._launcher is None:
            return self._unavailable()

        text = message.strip()
        low = text.lower()

        if self._RUNNING.search(low) and "list" in low:
            return self._summarize_running()

        m = self._SUMMON.match(text)
        if m:
            slug = self._normalize_slug(m.group(2))
            try:
                if self._launcher.is_running(slug):
                    a = self._launcher.get(slug)
                    return (
                        f"[Agents] {a.name} ({slug}) already running — PID {a.process.pid}.\n"
                        f"  Tools: {', '.join(a.tools) or 'none'}"
                    )
                a = self._launcher.launch(slug)
            except AgentLaunchError as exc:
                return f"[Agents] Could not summon '{slug}': {exc}"
            return (
                f"[Agents] Summoned {a.name} ({slug}).\n"
                f"  PID: {a.process.pid}\n"
                f"  Tools: {', '.join(a.tools) or 'none'}\n"
                f"  Trust floor: {a.trust_floor:.2f}"
            )

        m = self._STOP.match(text)
        if m:
            slug = self._normalize_slug(m.group(2))
            try:
                a = self._launcher.stop(slug)
            except AgentLaunchError as exc:
                return f"[Agents] {exc}"
            return f"[Agents] Stopped {a.name} ({slug})."

        m = self._SEARCH.match(text)
        if m:
            query = m.group(2).strip()
            return self._summarize_search(query)

        if self._LIST.match(text):
            return self._summarize_catalog()

        # Default: show catalog overview + running summary
        parts = [self._summarize_catalog(limit=5), "", self._summarize_running()]
        return "\n".join(parts)

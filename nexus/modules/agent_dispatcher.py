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

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "agents",
            "name": "agents",
            "tagline": "Console surface for browsing and summoning runnable agents.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "orchestration",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:agents",
                                  "gradient": ["#c8c8ff", "#3a3a8c"]}},
            "intents": [{
                "name": "SUMMON",
                "patterns": [
                    r"\bsummon\b", r"\blaunch\s+agent\b", r"\bstart\s+agent\b",
                    r"\bstop\s+agent\b", r"\bdismiss\s+agent\b", r"\bkill\s+agent\b",
                    r"\binvoke\s+agent\b", r"\blist\s+agents?\b", r"\bagent\s+catalog\b",
                    r"\brunning\s+agents?\b", r"\bonexus[- ]?agents?\b",
                    r"\bsearch\s+agents?\b", r"\bfind\s+agent\b",
                ],
                "semantic_signals": [
                    "summon", "launch agent", "start agent", "stop agent",
                    "list agents", "running agents", "agent catalog",
                    "find agent", "search agents", "invoke agent",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace", "inter_agent.list"],
                    "Notable": ["inter_agent.call.*", "process.spawn"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

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

        # Natural-language fallback. The message landed on this module because
        # Cortex matched the word "agent"/"agents" — but it isn't a command
        # like "summon X" or "list". Treat it as a question about the catalog
        # and extract content nouns to search by, instead of dumping the top-5.
        topic = self._extract_topic(text)
        if topic:
            results = self._summarize_search(topic, limit=8)
            return (
                f"[Agents] Searching the catalog for: {topic}\n"
                f"{results}\n"
                "\n  Want a different angle? Try: agents <keyword>  ·  list  ·  running"
            )

        # Truly empty query — fall back to the catalog + running summary.
        parts = [self._summarize_catalog(limit=5), "", self._summarize_running()]
        return "\n".join(parts)

    # English stop-words we drop from a natural-language question so the
    # remaining tokens become a useful catalog search. Keep this small —
    # the catalog's search() already does its own tokenisation; we just
    # want to strip the obvious connectives.
    _STOPWORDS: frozenset[str] = frozenset({
        "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
        "is", "are", "was", "were", "be", "been", "being", "am",
        "do", "does", "did", "doing", "done",
        "should", "would", "could", "can", "may", "might", "must", "shall", "will",
        "have", "has", "had",
        "i", "me", "my", "mine", "myself",
        "you", "your", "yours", "yourself",
        "we", "us", "our", "ours",
        "they", "them", "their", "theirs",
        "it", "its", "this", "that", "these", "those",
        "the", "a", "an", "and", "or", "but", "if", "then", "than", "so",
        "to", "of", "in", "on", "at", "by", "for", "with", "from", "as",
        "about", "into", "over", "under", "up", "down", "out", "off",
        "use", "using", "used", "need", "needs", "needed", "want", "wanting", "wanted",
        "good", "best", "better", "great", "any", "some", "few", "many",
        "agent", "agents",   # the message is already routed here — these add no signal
        "please", "thanks", "help",
    })

    def _extract_topic(self, text: str) -> str:
        """Return the content words from `text` joined as a search query.

        Strips punctuation, lowercases, removes English stop-words and the
        word "agent(s)" itself (which is what caused this module to fire in
        the first place). Returns an empty string if nothing meaningful is
        left, which signals the caller to fall back to the default summary.
        """
        cleaned = re.sub(r"[^a-zA-Z0-9\s\-_]", " ", text).lower()
        tokens = [t for t in cleaned.split() if t and t not in self._STOPWORDS]
        # Drop tokens that are too short to carry meaning.
        tokens = [t for t in tokens if len(t) >= 3]
        return " ".join(tokens)

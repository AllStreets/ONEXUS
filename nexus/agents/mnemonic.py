"""
Mnemonic -- knowledge base and note retrieval agent.
Stores, indexes, and retrieves knowledge fragments using keyword matching
and semantic similarity (via LLM) for personal knowledge management.

Inspired by:
  - infiniflow/ragflow (Apache 2.0) -- RAG engine with agent capabilities
  - IntelLabs/fastRAG (Apache 2.0) -- efficient retrieval augmented generation
  - logseq/logseq (AGPL 3.0) -- local-first knowledge management
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class KnowledgeEntry:
    id: int
    title: str
    content: str
    tags: list[str]
    source: str


class MnemonicModule(AgentModule):
    name = "mnemonic"
    description = "Knowledge base agent -- stores, indexes, and retrieves notes and knowledge fragments"
    version = "0.1.0"

    watch_events: list[str] = ["knowledge.stored", "insight.generated"]
    coordination_targets: list[str] = ["compass", "scribe"]

    def __init__(self):
        self._entries: list[KnowledgeEntry] = []
        self._next_id: int = 1

    def store(self, title: str, content: str, tags: list[str] | None = None,
              source: str = "") -> KnowledgeEntry:
        """Store a knowledge entry."""
        if tags is None:
            tags = self._auto_tag(content)
        entry = KnowledgeEntry(
            id=self._next_id, title=title, content=content,
            tags=tags, source=source,
        )
        self._entries.append(entry)
        self._next_id += 1
        return entry

    def search(self, query: str, limit: int = 5) -> list[KnowledgeEntry]:
        """Search entries by keyword matching."""
        query_words = set(query.lower().split())
        scored: list[tuple[int, KnowledgeEntry]] = []

        for entry in self._entries:
            score = 0
            entry_text = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
            for word in query_words:
                if len(word) > 2 and word in entry_text:
                    score += 1
                    if word in entry.title.lower():
                        score += 2  # Title matches weighted higher
                    if word in entry.tags:
                        score += 1

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get(self, entry_id: int) -> KnowledgeEntry | None:
        """Get an entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def delete(self, entry_id: int) -> bool:
        """Delete an entry by ID."""
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries.pop(i)
                return True
        return False

    def list_tags(self) -> dict[str, int]:
        """List all tags with their counts."""
        tag_counts: dict[str, int] = {}
        for entry in self._entries:
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _auto_tag(text: str) -> list[str]:
        """Automatically generate tags from text content."""
        tags: list[str] = []

        # Extract hashtags
        hashtags = re.findall(r'#(\w+)', text)
        tags.extend(h.lower() for h in hashtags)

        # Common topic detection
        text_lower = text.lower()
        topic_keywords: dict[str, list[str]] = {
            "python": ["python", "pip", "virtualenv", "pytest"],
            "javascript": ["javascript", "node", "npm", "react", "vue"],
            "database": ["sql", "database", "query", "table", "schema"],
            "api": ["api", "endpoint", "rest", "graphql", "http"],
            "security": ["security", "vulnerability", "auth", "encryption"],
            "devops": ["docker", "kubernetes", "ci/cd", "deploy", "pipeline"],
            "ml": ["machine learning", "model", "training", "neural", "llm"],
        }
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(topic)

        return list(dict.fromkeys(tags))[:10]

    @staticmethod
    def detect_intent(message: str) -> str:
        """Detect if user wants to store, search, or manage knowledge."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("delete", "remove", "forget")):
            return "delete"
        if any(w in msg_lower for w in ("list", "all notes", "all entries", "show tags")):
            return "list"
        if any(w in msg_lower for w in ("find", "search", "recall", "what do i know", "look up")):
            return "search"
        if any(w in msg_lower for w in ("remember", "store", "save", "add to knowledge")):
            return "store"
        return "search"

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        intent = self.detect_intent(message)

        if intent == "store":
            # Extract title from first line or generate one
            lines = message.strip().split('\n')
            title_line = lines[0] if lines else message[:60]
            # Strip store keywords
            title = re.sub(r'^(remember|store|save|note|add)\s*(this|that|:)?\s*', '', title_line, flags=re.IGNORECASE).strip()
            if not title:
                title = message[:60]
            content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else message

            entry = self.store(title=title, content=content)

            if engram:
                try:
                    engram.episodic.store(
                        f"Knowledge stored: {title} (tags: {', '.join(entry.tags)})",
                        source=self.name,
                    )
                except Exception:
                    pass

            result = f"[Mnemonic] Stored (ID: {entry.id})\n"
            result += f"  Title: {entry.title}\n"
            if entry.tags:
                result += f"  Tags: {', '.join(entry.tags)}\n"
            return result

        if intent == "list":
            if not self._entries:
                return "[Mnemonic] Knowledge base is empty. Store notes with 'remember: ...'."
            tags = self.list_tags()
            lines = [f"[Mnemonic] Knowledge Base ({len(self._entries)} entries)"]
            for entry in self._entries:
                lines.append(f"  [{entry.id}] {entry.title}")
            if tags:
                lines.append(f"\n  Tags: {', '.join(f'{t}({c})' for t, c in list(tags.items())[:15])}")
            return "\n".join(lines)

        if intent == "delete":
            ids = re.findall(r'\b(\d+)\b', message)
            if ids:
                entry_id = int(ids[0])
                if self.delete(entry_id):
                    return f"[Mnemonic] Entry {entry_id} deleted."
                return f"[Mnemonic] Entry {entry_id} not found."
            return "[Mnemonic] Specify the entry ID to delete."

        # Search
        results = self.search(message)

        if not results and llm:
            prompt = (
                "The user is searching their knowledge base but no results were found.\n"
                f"Query: {message}\n\n"
                "Suggest: 1) Alternative search terms 2) Related topics to explore"
            )
            try:
                suggestion = await llm.complete(prompt)
                return f"[Mnemonic] No results found.\n\n{suggestion[:500]}"
            except Exception:
                pass

        if not results:
            return f"[Mnemonic] No entries match '{message[:50]}'. Store notes with 'remember: ...'."

        if engram:
            try:
                engram.episodic.store(
                    f"Knowledge search: '{message[:50]}' -> {len(results)} results",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Mnemonic] Search Results ({len(results)})"]
        for entry in results:
            lines.append(f"\n  [{entry.id}] {entry.title}")
            if entry.tags:
                lines.append(f"    Tags: {', '.join(entry.tags)}")
            lines.append(f"    {entry.content[:150]}")

        if llm and results:
            prompt = (
                f"Synthesize these knowledge entries to answer: {message}\n\n"
                + "\n".join(f"- {r.title}: {r.content[:200]}" for r in results)
            )
            try:
                synthesis = await llm.complete(prompt)
                lines.append(f"\n  -- Synthesis --\n  {synthesis[:800]}")
            except Exception:
                pass

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest storing important findings when valuable information is detected."""
        msg_lower = message.lower()
        suggestions: list[str] = []

        # Proactively suggest storing if message looks like a finding or insight
        finding_signals = ("discovered", "found that", "turns out", "note:", "important:", "key insight",
                           "tldr", "tl;dr", "summary:", "learned", "pro tip", "gotcha")
        if any(sig in msg_lower for sig in finding_signals):
            suggestions.append(
                "This message looks like a valuable finding. "
                "Use 'remember: ...' to store it in the knowledge base for future retrieval."
            )

        # Suggest indexing if knowledge base is growing without tags
        if self._entries:
            untagged = [e for e in self._entries if not e.tags]
            if len(untagged) > 3:
                suggestions.append(
                    f"{len(untagged)} entries are untagged. "
                    "Adding tags improves retrieval precision."
                )

        return " ".join(suggestions)

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for new knowledge and insight events and index them."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "knowledge.stored":
            title = payload.get("title") or payload.get("name", "unknown")
            content = payload.get("content") or payload.get("body", "")
            source = payload.get("source", "pulse")
            if title and content:
                entry = self.store(title=title, content=content, source=source)
                return (
                    f"Indexed new knowledge entry '{title}' (ID: {entry.id}, "
                    f"tags: {', '.join(entry.tags) if entry.tags else 'none'})."
                )
            return f"knowledge.stored event received for '{title}' but content was empty -- skipped."

        if topic == "insight.generated":
            insight = payload.get("insight") or payload.get("content", "")
            agent = payload.get("agent") or payload.get("source", "unknown")
            if insight:
                title = f"Insight from {agent}"
                entry = self.store(title=title, content=insight, source=agent)
                return (
                    f"Indexed insight from '{agent}' (ID: {entry.id}). "
                    "Available for future retrieval."
                )
            return None

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route learning resources to compass and meeting notes to scribe."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        lines: list[str] = []
        result_lower = analysis_result.lower()

        # Learning resources, tutorials, documentation go to compass for navigation
        learning_signals = ("tutorial", "guide", "documentation", "reference", "how to", "learn",
                             "course", "resource", "reading", "book", "article")
        if any(sig in result_lower for sig in learning_signals):
            try:
                compass_result = await cortex.send("compass", analysis_result, context)
                if compass_result:
                    lines.append(f"[compass] {compass_result}")
            except Exception:
                pass

        # Meeting notes, decisions, action items go to scribe for transcription
        meeting_signals = ("meeting", "standup", "decision", "action item", "notes:", "minutes",
                            "discussed", "agreed", "follow-up", "recap")
        if any(sig in result_lower for sig in meeting_signals):
            try:
                scribe_result = await cortex.send("scribe", analysis_result, context)
                if scribe_result:
                    lines.append(f"[scribe] {scribe_result}")
            except Exception:
                pass

        return "\n".join(lines)

# nexus/modules/weave.py
"""
Weave — social graph intelligence.
Maps contacts, tracks interaction frequency, detects decaying relationships,
and models who-knows-who connections.

Data pipeline: subscribes to cortex.response events via Pulse, automatically
detecting name mentions in messages and building the social graph.
"""
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from nexus.modules.base import NexusModule


class RelationshipHealth(Enum):
    ACTIVE = "active"
    STABLE = "stable"
    COOLING = "cooling"
    STALE = "stale"
    NEW = "new"


@dataclass
class Interaction:
    channel: str
    note: str
    timestamp: str


@dataclass
class Contact:
    id: str
    name: str
    tags: list[str]
    interactions: list[Interaction] = field(default_factory=list)
    interaction_count: int = 0
    links: list[dict[str, str]] = field(default_factory=list)


class WeaveModule(NexusModule):
    name = "weave"
    description = "Social graph intelligence — relationship mapping and health tracking"
    version = "0.1.0"

    # Words that look like names but aren't (capitalized at sentence start, etc.)
    _STOP_WORDS = frozenset({
        "the", "this", "that", "what", "when", "where", "which", "who", "how",
        "yes", "no", "not", "but", "and", "for", "are", "was", "were", "been",
        "has", "have", "had", "will", "would", "could", "should", "may", "might",
        "can", "did", "does", "just", "also", "very", "well", "here", "there",
        "then", "than", "now", "some", "any", "all", "every", "each", "both",
        "tell", "about", "know", "think", "help", "need", "want", "get", "make",
        "nexus", "module", "prism", "atlas", "cipher", "oracle", "sentry",
    })

    @staticmethod
    def _extract_names(text: str) -> list[str]:
        """Extract likely proper nouns (capitalized words not at sentence start)."""
        # Match capitalized words that aren't at the very start of the text
        candidates = re.findall(r'(?<=[.!?\s])\s*([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)', text)
        names = []
        for name in candidates:
            if name.lower() not in WeaveModule._STOP_WORDS:
                names.append(name)
        return names

    def __init__(self):
        self._contacts: dict[str, Contact] = {}
        self._name_index: dict[str, str] = {}  # name -> contact_id
        self._sub_id: str | None = None

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if context and "pulse" in context:
            self._sub_id = context["pulse"].subscribe(
                "cortex.response", self._on_response
            )

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        if self._sub_id and context and "pulse" in context:
            context["pulse"].unsubscribe(self._sub_id)
            self._sub_id = None

    async def _on_response(self, msg) -> None:
        payload = msg.payload
        module = payload.get("module", "unknown")
        message = payload.get("message", "")
        names = self._extract_names(message)
        for name in names:
            if name in self._name_index:
                contact_id = self._name_index[name]
                self.record_interaction(contact_id, channel=module, note=message[:100])
            else:
                contact = self.add_contact(name, tags=[module])
                self._name_index[name] = contact.id

    def add_contact(self, name: str, tags: list[str] | None = None) -> Contact:
        contact_id = uuid.uuid4().hex[:8]
        contact = Contact(id=contact_id, name=name, tags=tags or [])
        self._contacts[contact_id] = contact
        return contact

    def get_contact(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def record_interaction(self, contact_id: str, channel: str, note: str) -> None:
        contact = self._contacts.get(contact_id)
        if not contact:
            return
        ts = datetime.now(timezone.utc).isoformat()
        contact.interactions.append(Interaction(channel=channel, note=note, timestamp=ts))
        contact.interaction_count += 1

    def get_health(self, contact_id: str) -> RelationshipHealth:
        contact = self._contacts.get(contact_id)
        if not contact:
            return RelationshipHealth.NEW
        count = contact.interaction_count
        if count == 0:
            return RelationshipHealth.NEW
        if count >= 3:
            return RelationshipHealth.ACTIVE
        if count >= 1:
            return RelationshipHealth.STABLE
        return RelationshipHealth.COOLING

    def find_connections(self, tag: str) -> list[Contact]:
        return [c for c in self._contacts.values() if tag.lower() in [t.lower() for t in c.tags]]

    def reconnection_suggestions(self) -> list[Contact]:
        stale = []
        for contact in self._contacts.values():
            health = self.get_health(contact.id)
            if health in (RelationshipHealth.NEW, RelationshipHealth.STALE, RelationshipHealth.COOLING):
                stale.append(contact)
        return stale

    def add_link(self, from_id: str, to_id: str, relationship: str) -> None:
        contact = self._contacts.get(from_id)
        if contact:
            contact.links.append({"contact_id": to_id, "relationship": relationship})
        contact2 = self._contacts.get(to_id)
        if contact2:
            contact2.links.append({"contact_id": from_id, "relationship": relationship})

    def get_links(self, contact_id: str) -> list[dict[str, str]]:
        contact = self._contacts.get(contact_id)
        return contact.links if contact else []

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._contacts:
            return "[Weave] No contacts in the social graph yet."
        lines = [f"[Weave] Social graph: {len(self._contacts)} contact(s)"]
        for contact in self._contacts.values():
            health = self.get_health(contact.id)
            tags_str = ", ".join(contact.tags) if contact.tags else "no tags"
            lines.append(f"  - {contact.name} ({tags_str}) [{health.value}]")
            lines.append(f"    Interactions: {contact.interaction_count} | Links: {len(contact.links)}")
        suggestions = self.reconnection_suggestions()
        if suggestions:
            lines.append(f"  Reconnection suggestions: {', '.join(s.name for s in suggestions)}")
        return "\n".join(lines)

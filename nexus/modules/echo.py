# nexus/modules/echo.py
"""
Echo -- behavioral fingerprinting and social graph intelligence.

Absorbs: weave.

Observes how the user writes across domains, builds behavioral profiles,
scores new text for style match, and maintains a full social graph with
contact tracking, interaction history, relationship health scoring, and
reconnection suggestions.

Subscribes to cortex.response via Pulse to auto-detect names and build
the social graph passively.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


# ---------------------------------------------------------------------------
# Behavioral fingerprinting dataclasses (original Echo)
# ---------------------------------------------------------------------------

@dataclass
class BehavioralProfile:
    domain: str
    sample_count: int = 0
    avg_word_count: float = 0.0
    avg_sentence_length: float = 0.0
    top_phrases: list[str] = field(default_factory=list)
    formality_score: float = 0.5
    _word_counts: list[int] = field(default_factory=list, repr=False)
    _sentence_lengths: list[float] = field(default_factory=list, repr=False)
    _word_freq: Counter = field(default_factory=Counter, repr=False)


# ---------------------------------------------------------------------------
# Social graph dataclasses (absorbed from weave)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


_FORMAL_MARKERS = {
    "therefore", "however", "furthermore", "regarding", "consequently",
    "comprehensive", "pursuant", "accordingly",
}
_INFORMAL_MARKERS = {
    "hey", "lgtm", "fyi", "btw", "gonna", "wanna", "cool", "nice",
    "awesome", "yeah", "nope", "ship",
}

# Words that look like names but aren't
_NAME_STOP_WORDS = frozenset({
    "the", "this", "that", "what", "when", "where", "which", "who", "how",
    "yes", "no", "not", "but", "and", "for", "are", "was", "were", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "might",
    "can", "did", "does", "just", "also", "very", "well", "here", "there",
    "then", "than", "now", "some", "any", "all", "every", "each", "both",
    "tell", "about", "know", "think", "help", "need", "want", "get", "make",
    "nexus", "module", "prism", "atlas", "cipher", "oracle", "sentry",
    "echo", "council", "specter", "consciousness",
})


# ===========================================================================
# Echo Module
# ===========================================================================

class EchoModule(NexusModule):
    name = "echo"
    description = (
        "Behavioral fingerprinting and social graph intelligence -- "
        "writing style analysis, relationship mapping, health tracking"
    )
    version = "1.0.0"

    def __init__(self):
        # Behavioral fingerprinting state
        self._profiles: dict[str, BehavioralProfile] = {}

        # Social graph state (from weave)
        self._contacts: dict[str, Contact] = {}
        self._name_index: dict[str, str] = {}  # name -> contact_id

        # Pulse subscription
        self._sub_id: str | None = None

    # -------------------------------------------------------------------
    # Lifecycle -- Pulse subscription
    # -------------------------------------------------------------------

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if context and "pulse" in context:
            self._sub_id = context["pulse"].subscribe(
                "cortex.response", self._on_response
            )

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        if self._sub_id and context and "pulse" in context:
            context["pulse"].unsubscribe(self._sub_id)
            self._sub_id = None

    async def _on_response(self, msg: Message) -> None:
        """Passive Pulse handler -- auto-detect names and observe style."""
        payload = msg.payload
        module = payload.get("module", "unknown")
        if module == self.name:
            return
        message = payload.get("message", "")
        response = payload.get("response", "")

        # Auto-detect names for social graph
        names = self._extract_names(message)
        for name in names:
            if name in self._name_index:
                contact_id = self._name_index[name]
                self.record_interaction(contact_id, channel=module, note=message[:100])
            else:
                contact = self.add_contact(name, tags=[module])
                self._name_index[name] = contact.id

        # Auto-observe writing style (domain = module that handled it)
        if message.strip():
            self.observe(module, message)

    # ===================================================================
    # Behavioral fingerprinting (original Echo)
    # ===================================================================

    def observe(self, domain: str, text: str) -> None:
        """Record a text sample for a domain and update the profile."""
        if domain not in self._profiles:
            self._profiles[domain] = BehavioralProfile(domain=domain)
        profile = self._profiles[domain]
        profile.sample_count += 1

        words_list = _words(text)
        sents = _sentences(text)

        profile._word_counts.append(len(words_list))
        profile.avg_word_count = sum(profile._word_counts) / len(profile._word_counts)

        if sents:
            avg_sent = sum(len(_words(s)) for s in sents) / len(sents)
            profile._sentence_lengths.append(avg_sent)
            profile.avg_sentence_length = sum(profile._sentence_lengths) / len(profile._sentence_lengths)

        profile._word_freq.update(words_list)
        profile.top_phrases = [w for w, _ in profile._word_freq.most_common(10)]

        # Formality scoring
        formal_hits = sum(1 for w in words_list if w in _FORMAL_MARKERS)
        informal_hits = sum(1 for w in words_list if w in _INFORMAL_MARKERS)
        total = formal_hits + informal_hits
        if total > 0:
            new_formality = formal_hits / total
            alpha = 1.0 / profile.sample_count
            profile.formality_score = (1 - alpha) * profile.formality_score + alpha * new_formality

    def get_profile(self, domain: str) -> BehavioralProfile | None:
        return self._profiles.get(domain)

    def list_domains(self) -> list[str]:
        return list(self._profiles.keys())

    def match_style(self, domain: str, text: str) -> float:
        """Score how well a text matches the observed style for a domain (0.0-1.0)."""
        profile = self._profiles.get(domain)
        if not profile or profile.sample_count == 0:
            return 0.5

        words_list = _words(text)
        sents = _sentences(text)

        # Word count similarity
        wc_diff = abs(len(words_list) - profile.avg_word_count) / max(profile.avg_word_count, 1)
        wc_score = max(0, 1.0 - wc_diff)

        # Sentence length similarity
        sl_score = 0.5
        if sents and profile.avg_sentence_length > 0:
            avg_sl = sum(len(_words(s)) for s in sents) / len(sents)
            sl_diff = abs(avg_sl - profile.avg_sentence_length) / max(profile.avg_sentence_length, 1)
            sl_score = max(0, 1.0 - sl_diff)

        # Vocabulary overlap
        vocab_overlap = sum(1 for w in words_list if w in profile._word_freq) / max(len(words_list), 1)

        return round((wc_score * 0.3 + sl_score * 0.3 + vocab_overlap * 0.4), 3)

    # ===================================================================
    # Social graph (absorbed from weave)
    # ===================================================================

    @staticmethod
    def _extract_names(text: str) -> list[str]:
        """Extract likely proper nouns (capitalized words) from text."""
        candidates = re.findall(
            r'(?:(?<=[.!?\s])\s*|^)([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)',
            text,
        )
        names = []
        for name in candidates:
            if name.lower() not in _NAME_STOP_WORDS:
                names.append(name)
        return names

    def add_contact(self, name: str, tags: list[str] | None = None) -> Contact:
        contact_id = uuid.uuid4().hex[:8]
        contact = Contact(id=contact_id, name=name, tags=tags or [])
        self._contacts[contact_id] = contact
        self._name_index[name] = contact_id
        return contact

    def get_contact(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def find_contact_by_name(self, name: str) -> Contact | None:
        contact_id = self._name_index.get(name)
        return self._contacts.get(contact_id) if contact_id else None

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

        # Determine recency from the most recent interaction timestamp
        last_ts: datetime | None = None
        for interaction in contact.interactions:
            try:
                ts = datetime.fromisoformat(interaction.timestamp)
                if last_ts is None or ts > last_ts:
                    last_ts = ts
            except (ValueError, TypeError):
                pass

        if last_ts is not None:
            now = datetime.now(timezone.utc)
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            days_since = (now - last_ts).days
            if days_since > 90:
                return RelationshipHealth.STALE
            if days_since > 30:
                return RelationshipHealth.COOLING

        if count >= 3:
            return RelationshipHealth.ACTIVE
        return RelationshipHealth.STABLE

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

    # ===================================================================
    # handle()
    # ===================================================================

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()

        # Social graph mode
        if any(kw in lower for kw in ["contact", "social", "relationship", "reconnect", "who"]):
            return self._handle_social()

        # Default: behavioral profiles
        return self._handle_profiles()

    def _handle_profiles(self) -> str:
        if not self._profiles:
            return "[Echo] No behavioral observations recorded yet."
        lines = ["[Echo] Behavioral profiles:"]
        for domain, profile in self._profiles.items():
            lines.append(f"  [{domain}] {profile.sample_count} samples")
            lines.append(f"    Avg words: {profile.avg_word_count:.1f}")
            lines.append(f"    Avg sentence length: {profile.avg_sentence_length:.1f} words")
            lines.append(f"    Formality: {profile.formality_score:.2f}")
            if profile.top_phrases:
                lines.append(f"    Top vocabulary: {', '.join(profile.top_phrases[:5])}")
        return "\n".join(lines)

    def _handle_social(self) -> str:
        if not self._contacts:
            return "[Echo] No contacts in the social graph yet."
        lines = [f"[Echo] Social graph: {len(self._contacts)} contact(s)"]
        for contact in self._contacts.values():
            health = self.get_health(contact.id)
            tags_str = ", ".join(contact.tags) if contact.tags else "no tags"
            lines.append(f"  - {contact.name} ({tags_str}) [{health.value}]")
            lines.append(f"    Interactions: {contact.interaction_count} | Links: {len(contact.links)}")
        suggestions = self.reconnection_suggestions()
        if suggestions:
            lines.append(f"  Reconnection suggestions: {', '.join(s.name for s in suggestions)}")
        return "\n".join(lines)

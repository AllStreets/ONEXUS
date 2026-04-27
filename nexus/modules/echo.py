# nexus/modules/echo.py
"""
Echo — behavioral fingerprinting and skill transfer.
Observes how the user writes across domains, builds behavioral profiles,
and can score new text for style match. Patterns transfer across domains.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


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


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


_FORMAL_MARKERS = {"therefore", "however", "furthermore", "regarding", "consequently", "comprehensive", "pursuant", "accordingly"}
_INFORMAL_MARKERS = {"hey", "lgtm", "fyi", "btw", "gonna", "wanna", "cool", "nice", "awesome", "yeah", "nope", "ship"}


class EchoModule(NexusModule):
    name = "echo"
    description = "Behavioral fingerprinting — learns writing style and decision patterns"
    version = "0.1.0"

    def __init__(self):
        self._profiles: dict[str, BehavioralProfile] = {}

    def observe(self, domain: str, text: str) -> None:
        """Record a text sample for a domain and update the profile."""
        if domain not in self._profiles:
            self._profiles[domain] = BehavioralProfile(domain=domain)
        profile = self._profiles[domain]
        profile.sample_count += 1

        words = _words(text)
        sents = _sentences(text)

        profile._word_counts.append(len(words))
        profile.avg_word_count = sum(profile._word_counts) / len(profile._word_counts)

        if sents:
            avg_sent = sum(len(_words(s)) for s in sents) / len(sents)
            profile._sentence_lengths.append(avg_sent)
            profile.avg_sentence_length = sum(profile._sentence_lengths) / len(profile._sentence_lengths)

        profile._word_freq.update(words)
        profile.top_phrases = [w for w, _ in profile._word_freq.most_common(10)]

        # Formality scoring
        formal_hits = sum(1 for w in words if w in _FORMAL_MARKERS)
        informal_hits = sum(1 for w in words if w in _INFORMAL_MARKERS)
        total = formal_hits + informal_hits
        if total > 0:
            new_formality = formal_hits / total
            # Weighted rolling average
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

        words = _words(text)
        sents = _sentences(text)

        # Word count similarity
        wc_diff = abs(len(words) - profile.avg_word_count) / max(profile.avg_word_count, 1)
        wc_score = max(0, 1.0 - wc_diff)

        # Sentence length similarity
        sl_score = 0.5
        if sents and profile.avg_sentence_length > 0:
            avg_sl = sum(len(_words(s)) for s in sents) / len(sents)
            sl_diff = abs(avg_sl - profile.avg_sentence_length) / max(profile.avg_sentence_length, 1)
            sl_score = max(0, 1.0 - sl_diff)

        # Vocabulary overlap
        vocab_overlap = sum(1 for w in words if w in profile._word_freq) / max(len(words), 1)

        return round((wc_score * 0.3 + sl_score * 0.3 + vocab_overlap * 0.4), 3)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
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

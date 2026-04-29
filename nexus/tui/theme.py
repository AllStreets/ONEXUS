"""
NEXUS TUI theme -- dark color palette with trust-tier coloring.
"""
from __future__ import annotations

from rich.theme import Theme

NEXUS_THEME = Theme({
    "nexus.primary": "#00d4ff",
    "nexus.secondary": "#7c3aed",
    "nexus.success": "#10b981",
    "nexus.warning": "#f59e0b",
    "nexus.danger": "#ef4444",
    "nexus.surface": "#12121a",
    "nexus.border": "#1e1e2e",
    "nexus.text": "#e2e8f0",
    "nexus.text.dim": "#94a3b8",
    "nexus.trust.skill": "#ef4444",
    "nexus.trust.advisor": "#f59e0b",
    "nexus.trust.monitor": "#00d4ff",
    "nexus.trust.autonomous": "#10b981",
    "nexus.trust.sovereign": "#7c3aed",
})

# Block characters for trust bars
_FULL_BLOCK = "\u2588"
_LIGHT_SHADE = "\u2591"


def trust_color(score: int) -> str:
    """Return the Rich style name for a trust score tier."""
    if score >= 100:
        return "nexus.trust.sovereign"
    if score >= 75:
        return "nexus.trust.autonomous"
    if score >= 50:
        return "nexus.trust.monitor"
    if score >= 25:
        return "nexus.trust.advisor"
    return "nexus.trust.skill"


def trust_tier_name(score: int) -> str:
    """Return the human-readable tier name for a trust score."""
    if score >= 100:
        return "SOVEREIGN"
    if score >= 75:
        return "AUTONOMOUS"
    if score >= 50:
        return "MONITOR"
    if score >= 25:
        return "ADVISOR"
    return "SKILL"


def trust_bar(score: int, width: int = 10) -> str:
    """Return a block-character bar representation of a trust score.

    Example with score=80 and width=10: '\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2591\u2591'
    """
    score = max(0, min(100, score))
    filled = round(score / 100 * width)
    empty = width - filled
    return _FULL_BLOCK * filled + _LIGHT_SHADE * empty

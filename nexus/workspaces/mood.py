"""
MoodEngine — ambient 8-state mood system for the Aurora atmosphere.

Each workspace has a home tone (WorkspaceTone from WorkspaceConfig) and
a dynamic *mood* that responds to kernel conditions.  The MoodEngine
evaluates a set of signals and returns the current Mood, optional trust
event overlays, and CSS gradient hints for the frontend.

Eight moods (spec §11.1):
    Calm Focus   — default
    Deep Flow    — sustained focus detected (Sentry signal)
    Routing      — high Pulse rate, multiple agents active
    Deliberating — Council / Specter / Legacy is the active agent
    Creative     — generative agents resident or workspace tone = MAGENTA
    Reflective   — Consciousness active, low pulse, late hour
    Watchful     — Oracle flagged pattern, or trust sliding
    Alert        — trust collapse / security breach

Three transient overlays (spec §11.2):
    rising   — trust gained (+0.012 or larger)
    falling  — trust lost  (-0.022 or larger)
    collapse — trust below 0.50 after a fall

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §11.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── mood enumeration ──────────────────────────────────────────────────────────


class Mood(str, Enum):
    CALM_FOCUS = "Calm Focus"
    DEEP_FLOW = "Deep Flow"
    ROUTING = "Routing"
    DELIBERATING = "Deliberating"
    CREATIVE = "Creative"
    REFLECTIVE = "Reflective"
    WATCHFUL = "Watchful"
    ALERT = "Alert"


# ── overlay enumeration ───────────────────────────────────────────────────────


class TrustOverlay(str, Enum):
    RISING = "rising"    # warm gold wash (1.5 s)
    FALLING = "falling"  # cool steel wash (1.5 s)
    COLLAPSE = "collapse"  # hot crimson flash (persistent 30 s)


# ── per-mood metadata ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MoodSpec:
    """Visual and behavioural specification for a single mood."""

    mood: Mood
    hue_family: str          # human-readable colour description
    drift_seconds: int       # mesh drift speed
    priority: int            # higher = takes precedence over lower moods
    description: str


_MOOD_SPECS: dict[Mood, MoodSpec] = {
    Mood.ALERT: MoodSpec(
        mood=Mood.ALERT,
        hue_family="Crimson · coral glow · deep ember",
        drift_seconds=7,
        priority=100,
        description="Trust collapse, security breach, permission denied after grant.",
    ),
    Mood.WATCHFUL: MoodSpec(
        mood=Mood.WATCHFUL,
        hue_family="Brass · olive · slate · ember",
        drift_seconds=12,
        priority=80,
        description="Oracle pattern flagged, Specter auditing, or trust sliding.",
    ),
    Mood.ROUTING: MoodSpec(
        mood=Mood.ROUTING,
        hue_family="Electric magenta · bright cyan · indigo",
        drift_seconds=14,
        priority=70,
        description="High Pulse rate and multiple agents active simultaneously.",
    ),
    Mood.CREATIVE: MoodSpec(
        mood=Mood.CREATIVE,
        hue_family="Hot coral · tangerine · magenta · teal edge",
        drift_seconds=20,
        priority=60,
        description="Generative agents resident or workspace tone is MAGENTA.",
    ),
    Mood.DELIBERATING: MoodSpec(
        mood=Mood.DELIBERATING,
        hue_family="Amber · bronze · burgundy · cream",
        drift_seconds=30,
        priority=50,
        description="Council, Specter, or Legacy is the active deliberating agent.",
    ),
    Mood.REFLECTIVE: MoodSpec(
        mood=Mood.REFLECTIVE,
        hue_family="Near-monochrome plum · single rose ember",
        drift_seconds=42,
        priority=40,
        description="Consciousness active, low Pulse, late hour.",
    ),
    Mood.DEEP_FLOW: MoodSpec(
        mood=Mood.DEEP_FLOW,
        hue_family="Pine · jade · oceanic deep blue · gold ember",
        drift_seconds=38,
        priority=30,
        description="Sentry detects ≥ 15 min sustained focus, low context-switching.",
    ),
    Mood.CALM_FOCUS: MoodSpec(
        mood=Mood.CALM_FOCUS,
        hue_family="Indigo · violet · warm amber · undertone cyan",
        drift_seconds=24,
        priority=0,
        description="Default; nothing else takes priority.",
    ),
}

# Sorted by priority descending for fast evaluation
_MOOD_BY_PRIORITY: list[MoodSpec] = sorted(
    _MOOD_SPECS.values(), key=lambda m: m.priority, reverse=True
)


# ── signal bag ────────────────────────────────────────────────────────────────


@dataclass
class MoodSignals:
    """Kernel-state signals consumed by MoodEngine.evaluate().

    All fields are optional; defaults produce Calm Focus.
    """

    # Trust events
    trust_collapsed: bool = False          # any agent fell below 0.50
    trust_delta: float = 0.0              # most recent trust adjustment

    # Agent activity
    active_agent: str | None = None       # slug of the agent handling the turn
    active_agent_count: int = 0           # how many agents are currently active
    pulse_rate_above_baseline: bool = False  # Pulse events/s > normal idle

    # Sentry-detected focus state
    sustained_focus: bool = False          # Sentry: ≥ 15 min high-engagement

    # Oracle / Specter auditing
    oracle_pattern_flagged: bool = False
    specter_auditing: bool = False
    trust_sliding: bool = False            # any agent losing trust gradually

    # Workspace context
    workspace_tone: str = "INDIGO"         # WorkspaceTone.value
    workspace_mood_biases: dict[str, float] = field(default_factory=dict)

    # Time (UTC hour, 0-23).  None = use current time.
    hour_utc: int | None = None


# ── mood engine ───────────────────────────────────────────────────────────────


_DELIBERATING_AGENTS = {"council", "specter", "legacy"}
_CREATIVE_AGENTS = {"comfyui", "echo", "sd-webui"}
_LATE_HOURS = set(range(22, 24)) | set(range(0, 6))


class MoodEngine:
    """Evaluate kernel signals and produce the current mood + overlays.

    Usage
    -----
        engine = MoodEngine()
        signals = MoodSignals(active_agent="council", trust_collapsed=False)
        result = engine.evaluate(signals)
        print(result.mood)           # Mood.DELIBERATING
        print(result.overlay)        # None  (no trust event this turn)
    """

    def evaluate(self, signals: MoodSignals) -> "MoodResult":
        """Return a MoodResult for the current set of signals."""
        mood = self._select_mood(signals)
        overlay = self._select_overlay(signals)
        spec = _MOOD_SPECS[mood]
        return MoodResult(mood=mood, spec=spec, overlay=overlay, signals=signals)

    # ── mood selection (priority order) ───────────────────────────────────

    def _select_mood(self, s: MoodSignals) -> Mood:
        # Alert — highest priority
        if s.trust_collapsed:
            return Mood.ALERT

        # Watchful
        if s.oracle_pattern_flagged or s.specter_auditing or s.trust_sliding:
            return Mood.WATCHFUL

        # Routing
        if s.pulse_rate_above_baseline and s.active_agent_count > 1:
            return Mood.ROUTING

        # Creative — tone MAGENTA or generative agent active
        if s.workspace_tone == "MAGENTA" or (
            s.active_agent is not None and s.active_agent in _CREATIVE_AGENTS
        ):
            # Apply bias: if Creative bias is non-zero, let it through
            creative_bias = s.workspace_mood_biases.get("Creative", 0.0)
            if s.workspace_tone == "MAGENTA" or creative_bias > 0 or (
                s.active_agent in _CREATIVE_AGENTS
            ):
                return Mood.CREATIVE

        # Deliberating
        if s.active_agent is not None and s.active_agent in _DELIBERATING_AGENTS:
            return Mood.DELIBERATING

        # Reflective — consciousness active + low pulse + late hour
        hour = s.hour_utc if s.hour_utc is not None else datetime.now(timezone.utc).hour
        if s.active_agent == "consciousness" and not s.pulse_rate_above_baseline:
            return Mood.REFLECTIVE

        # Apply workspace mood biases for Reflective / Watchful
        reflective_bias = s.workspace_mood_biases.get("Reflective", 0.0)
        if reflective_bias > 0 and hour in _LATE_HOURS:
            return Mood.REFLECTIVE

        watchful_bias = s.workspace_mood_biases.get("Watchful", 0.0)
        if watchful_bias > 0 and s.active_agent in {"oracle", "specter"}:
            return Mood.WATCHFUL

        # Deep Flow
        if s.sustained_focus:
            return Mood.DEEP_FLOW

        # Default
        return Mood.CALM_FOCUS

    # ── overlay selection ─────────────────────────────────────────────────

    def _select_overlay(self, s: MoodSignals) -> TrustOverlay | None:
        if s.trust_collapsed:
            return TrustOverlay.COLLAPSE
        if s.trust_delta <= -0.022:
            return TrustOverlay.FALLING
        if s.trust_delta >= 0.012:
            return TrustOverlay.RISING
        return None

    # ── tone-to-css gradient hints ────────────────────────────────────────

    @staticmethod
    def tone_gradient(tone: str) -> tuple[str, str]:
        """Return (start_hex, end_hex) for a workspace home tone."""
        _TONE_GRADIENTS = {
            "INDIGO": ("#5a6cd0", "#2c3a78"),
            "MAGENTA": ("#c060a0", "#5e2050"),
            "SAGE": ("#88a888", "#3e5840"),
            "PLUM": ("#7e5ea0", "#2c1c44"),
            "AMBER": ("#e8a06c", "#844820"),
        }
        return _TONE_GRADIENTS.get(tone, ("#5a6cd0", "#2c3a78"))

    @staticmethod
    def mood_spec(mood: Mood) -> MoodSpec:
        """Return the MoodSpec for a given Mood."""
        return _MOOD_SPECS[mood]

    @staticmethod
    def all_specs() -> list[MoodSpec]:
        """Return all MoodSpec objects sorted by priority descending."""
        return list(_MOOD_BY_PRIORITY)


# ── result dataclass ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MoodResult:
    """The output of MoodEngine.evaluate()."""

    mood: Mood
    spec: MoodSpec
    overlay: TrustOverlay | None
    signals: MoodSignals

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood": self.mood.value,
            "hue_family": self.spec.hue_family,
            "drift_seconds": self.spec.drift_seconds,
            "overlay": self.overlay.value if self.overlay else None,
        }

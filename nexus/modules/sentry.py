"""
Sentry — cognitive load model.
Maintains a real-time estimate of the user's cognitive state based on
behavioral signals (typing speed, message frequency, time gaps).
Outputs a state vector: focus, fatigue, stress, flow.
"""
import time
from collections import deque
from dataclasses import dataclass
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class CognitiveState:
    focus: float = 0.5
    fatigue: float = 0.0
    stress: float = 0.0
    flow: bool = False

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "focus": round(self.focus, 2),
            "fatigue": round(self.fatigue, 2),
            "stress": round(self.stress, 2),
            "flow": self.flow,
        }


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


class SentryModule(NexusModule):
    name = "sentry"
    description = "Cognitive load model — tracks user focus, fatigue, stress, and flow"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "sentry",
            "name": "sentry",
            "tagline": "Cognitive regulation: focus, fatigue, stress, flow state.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "monitoring",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:sentry",
                                  "gradient": ["#ffb878", "#8c4218"]}},
            "intents": [{
                "name": "REGULATE",
                "patterns": [
                    r"\bcognitive\b", r"\bfocus\b", r"\bfatigue\b", r"\bstress\b",
                    r"\bflow\s+state\b", r"\benergy\b", r"\btired\b",
                    r"\bhow\s+am\s+i\s+doing\b", r"\bmental\s+state\b",
                    r"\bsentry\b", r"\bworkload\b", r"\bburn-?out\b",
                ],
                "semantic_signals": [
                    "cognitive state", "focus", "fatigue", "stress level",
                    "flow state", "energy", "how am I doing", "mental state",
                    "workload", "burnout", "am I overloaded",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.40, "default_tier": "ADVISOR"},
        })

    # Activity-window for frequency calculation (seconds).
    _FREQUENCY_WINDOW_S = 60.0
    # Calibration: messages-per-window that maps to frequency 1.0
    _FREQUENCY_SATURATION = 8
    # Time gap that maps to gap=1.0 (long pause)
    _GAP_SATURATION_S = 90.0
    # Typing-speed proxy: chars/sec that maps to typing=1.0
    _TYPING_SATURATION_CPS = 6.0

    def __init__(self):
        self._signals: dict[str, float] = {}
        self._state = CognitiveState()
        self._sub_id: str | None = None
        self._message_times: deque[float] = deque(maxlen=64)
        self._last_message_at: float | None = None

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        """Subscribe to cortex.response so Sentry auto-derives signals from console activity."""
        if context and "pulse" in context:
            self._sub_id = context["pulse"].subscribe(
                "cortex.response", self._on_cortex_response
            )

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        if self._sub_id and context and "pulse" in context:
            context["pulse"].unsubscribe(self._sub_id)
            self._sub_id = None

    async def _on_cortex_response(self, msg) -> None:
        payload = msg.payload or {}
        message_text = payload.get("message", "") or ""
        self.observe_message(message_text)

    def observe_message(self, message: str, *, now: float | None = None) -> None:
        """Derive behavioral signals from a single user message.

        Updates time_gap, message_frequency, and typing_speed automatically.
        Idempotent and safe to call from any thread/coroutine.
        """
        ts = now if now is not None else time.monotonic()

        # 1. Time gap since last message
        if self._last_message_at is not None:
            gap_s = max(0.0, ts - self._last_message_at)
            self._signals["time_gap"] = _clamp(gap_s / self._GAP_SATURATION_S)
        self._last_message_at = ts

        # 2. Message frequency over the last window
        self._message_times.append(ts)
        cutoff = ts - self._FREQUENCY_WINDOW_S
        while self._message_times and self._message_times[0] < cutoff:
            self._message_times.popleft()
        recent = len(self._message_times)
        self._signals["message_frequency"] = _clamp(recent / self._FREQUENCY_SATURATION)

        # 3. Typing-speed proxy: char count per implied compose time. We don't
        # have keystroke telemetry, so use message length / inter-message gap
        # as a coarse approximation, capped to a sane range.
        if len(message) > 0 and self._last_message_at is not None:
            # Use a 4-second floor so short pauses don't blow up the rate.
            implied_compose_s = max(4.0, ts - (self._message_times[-2] if len(self._message_times) >= 2 else ts - 4.0))
            cps = len(message) / implied_compose_s
            self._signals["typing_speed"] = _clamp(cps / self._TYPING_SATURATION_CPS)

        self._recalculate()

    def update_signal(self, signal_name: str, value: float) -> None:
        """Update a behavioral signal (0.0–1.0) and recalculate state."""
        self._signals[signal_name] = _clamp(value)
        self._recalculate()

    def _recalculate(self) -> None:
        typing = self._signals.get("typing_speed", 0.5)
        freq = self._signals.get("message_frequency", 0.5)
        gap = self._signals.get("time_gap", 0.3)

        # Focus: high typing speed + high frequency = focused
        self._state.focus = _clamp(typing * 0.5 + freq * 0.5)
        # Fatigue: low typing speed + high gap = fatigued
        self._state.fatigue = _clamp((1.0 - typing) * 0.5 + gap * 0.5)
        # Stress: high frequency + low gap = pressured
        self._state.stress = _clamp(freq * 0.4 + (1.0 - gap) * 0.3 + (1.0 - typing) * 0.3)
        # Flow: high focus, low fatigue, low stress
        self._state.flow = (
            self._state.focus > 0.6
            and self._state.fatigue < 0.4
            and self._state.stress < 0.5
        )

    def get_state(self) -> CognitiveState:
        return self._state

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        s = self._state
        signal_summary = (
            f"typing={self._signals.get('typing_speed', 0.5):.2f} "
            f"freq={self._signals.get('message_frequency', 0.5):.2f} "
            f"gap={self._signals.get('time_gap', 0.3):.2f}"
        )
        lines = [
            "[Sentry] Cognitive State:",
            f"  Focus:   {s.focus:.2f}",
            f"  Fatigue: {s.fatigue:.2f}",
            f"  Stress:  {s.stress:.2f}",
            f"  Flow:    {'active' if s.flow else 'inactive'}",
            f"  Signals: {signal_summary}",
        ]
        if s.flow:
            lines.append("  -> Flow state detected. Non-critical interrupts are suppressed.")
        if s.fatigue > 0.6:
            lines.append("  -> High fatigue detected. Consider taking a break.")
        if s.stress > 0.7:
            lines.append("  -> Elevated stress. Prioritizing only essential items.")
        if not self._message_times:
            lines.append("  -> No console activity observed yet — defaults shown.")
        return "\n".join(lines)

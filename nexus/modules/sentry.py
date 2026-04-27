"""
Sentry — cognitive load model.
Maintains a real-time estimate of the user's cognitive state based on
behavioral signals (typing speed, message frequency, time gaps).
Outputs a state vector: focus, fatigue, stress, flow.
"""
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

    def __init__(self):
        self._signals: dict[str, float] = {}
        self._state = CognitiveState()

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
        lines = [
            "[Sentry] Cognitive State:",
            f"  Focus:   {s.focus:.2f}",
            f"  Fatigue: {s.fatigue:.2f}",
            f"  Stress:  {s.stress:.2f}",
            f"  Flow:    {'active' if s.flow else 'inactive'}",
        ]
        if s.flow:
            lines.append("  -> Flow state detected. Non-critical interrupts are suppressed.")
        if s.fatigue > 0.6:
            lines.append("  -> High fatigue detected. Consider taking a break.")
        if s.stress > 0.7:
            lines.append("  -> Elevated stress. Prioritizing only essential items.")
        return "\n".join(lines)

"""REST endpoints for the workspace MoodEngine.

GET  /api/mood/current   — returns {mood, tone, drift_seconds, reason}
POST /api/mood/observe   — push state observations into the engine
WS   /api/mood/ws        — push mood snapshots every 2s
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict

from nexus.workspaces.mood import MoodEngine, MoodSignals


router = APIRouter(prefix="/api/mood", tags=["mood"])


# Mood severity — higher = more urgent. Lower-severity moods cannot displace
# a higher-severity mood until its hold period expires; the dashboard would
# otherwise flicker between e.g. alert and calm_focus when one signal source
# clears trust_collapsed before another reaffirms it.
_SEVERITY: dict[str, int] = {
    "alert": 6,
    "watchful": 5,
    "routing": 4,
    "deliberating": 3,
    "creative": 2,
    "deep_flow": 1,
    "reflective": 1,
    "calm_focus": 0,
}

# How long each mood holds before allowing a step-down (seconds).
_HOLD_SECONDS: dict[str, float] = {
    "alert": 10.0,
    "watchful": 6.0,
    "routing": 4.0,
    "deliberating": 4.0,
    "creative": 4.0,
    "deep_flow": 3.0,
    "reflective": 3.0,
    "calm_focus": 0.0,
}


@dataclass
class _MoodHold:
    """Tracks the last mood emitted and when it was set, for hold-down logic."""
    mood: str
    set_at: float


def _apply_hold(request_app_state, new_mood: str) -> str:
    """Return `new_mood`, unless a higher-severity mood is still inside its
    hold window — in which case keep emitting the held mood."""
    held: _MoodHold | None = getattr(request_app_state, "mood_hold", None)
    now = time.monotonic()
    if held is not None:
        elapsed = now - held.set_at
        hold_for = _HOLD_SECONDS.get(held.mood, 0.0)
        new_sev = _SEVERITY.get(new_mood, 0)
        held_sev = _SEVERITY.get(held.mood, 0)
        if held_sev > new_sev and elapsed < hold_for:
            # Step-down attempted too soon — keep the held mood.
            return held.mood
    # Either escalating, equal, or past the hold window: latch the new mood.
    request_app_state.mood_hold = _MoodHold(mood=new_mood, set_at=now)
    return new_mood

# Known observe-body fields and how they map to MoodSignals kwargs.
# Keys are what the surface sends; values are the MoodSignals field name.
_FIELD_MAP: dict[str, str] = {
    "trust_collapse": "trust_collapsed",
    "trust_delta": "trust_delta",
    "active_agent": "active_agent",
    "active_agent_count": "active_agent_count",
    "pulse_rate_above_baseline": "pulse_rate_above_baseline",
    "sustained_focus": "sustained_focus",
    "oracle_flagged": "oracle_pattern_flagged",
    "specter_auditing": "specter_auditing",
    "trust_sliding": "trust_sliding",
    "workspace_tone": "workspace_tone",
    "sustained_focus_minutes": "sustained_focus",  # alias for Sentry signal
    "is_late_hour": None,   # handled below — no direct MoodSignals field
    "resident_agents": None,  # handled below — informational, no direct field
    "active_module": "active_agent",  # alias
    "pulse_per_min": None,  # translates to pulse_rate_above_baseline
}

# Complete set of accepted surface field names
_KNOWN_FIELDS: frozenset[str] = frozenset(_FIELD_MAP)


def _get_engine(request: Request) -> MoodEngine:
    engine = getattr(request.app.state, "mood_engine", None)
    if engine is None:
        engine = MoodEngine()
        request.app.state.mood_engine = engine
    return engine


def _get_signals(request: Request) -> MoodSignals:
    signals = getattr(request.app.state, "mood_signals", None)
    if signals is None:
        signals = MoodSignals()
        request.app.state.mood_signals = signals
    return signals


class ObserveBody(BaseModel):
    """Observation payload sent by surfaces/kernel.

    All fields are optional — surfaces only set what they observe.
    extra="allow" so unknown keys come through and we can return 400
    rather than a pydantic 422 validation error.
    """

    model_config = ConfigDict(extra="allow")

    # Surface-facing field names (may differ from MoodSignals field names)
    pulse_per_min: float | None = None
    active_agents: int | None = None
    active_module: str | None = None
    resident_agents: list[str] | None = None
    oracle_flagged: bool | None = None
    trust_collapse: bool | None = None
    trust_delta: float | None = None
    active_agent: str | None = None
    active_agent_count: int | None = None
    pulse_rate_above_baseline: bool | None = None
    sustained_focus: bool | None = None
    sustained_focus_minutes: float | None = None
    specter_auditing: bool | None = None
    trust_sliding: bool | None = None
    workspace_tone: str | None = None
    is_late_hour: bool | None = None


def _apply_body_to_signals(body: ObserveBody, signals: MoodSignals) -> MoodSignals:
    """Return a new MoodSignals with body fields applied.

    Raises ValueError if any unknown (extra) fields are present.
    """
    # Check for extra (unknown) fields passed through pydantic's allow-extra
    extras = body.model_extra or {}
    if extras:
        unknown = ", ".join(sorted(extras))
        raise ValueError(f"Unknown observe field(s): {unknown}")

    # Build kwargs for MoodSignals replacement
    # We reconstruct from the current signals + the new observations
    import dataclasses
    current = dataclasses.asdict(signals)

    if body.trust_collapse is not None:
        current["trust_collapsed"] = body.trust_collapse
    if body.trust_delta is not None:
        current["trust_delta"] = body.trust_delta
    if body.active_agent is not None:
        current["active_agent"] = body.active_agent
    if body.active_module is not None:
        current["active_agent"] = body.active_module
    if body.active_agent_count is not None:
        current["active_agent_count"] = body.active_agent_count
    if body.active_agents is not None:
        current["active_agent_count"] = body.active_agents
    if body.pulse_rate_above_baseline is not None:
        current["pulse_rate_above_baseline"] = body.pulse_rate_above_baseline
    if body.pulse_per_min is not None:
        # translate raw pulse rate: above ~3/min = above baseline
        current["pulse_rate_above_baseline"] = body.pulse_per_min > 3.0
    if body.sustained_focus is not None:
        current["sustained_focus"] = body.sustained_focus
    if body.sustained_focus_minutes is not None:
        current["sustained_focus"] = body.sustained_focus_minutes >= 15.0
    if body.oracle_flagged is not None:
        current["oracle_pattern_flagged"] = body.oracle_flagged
    if body.specter_auditing is not None:
        current["specter_auditing"] = body.specter_auditing
    if body.trust_sliding is not None:
        current["trust_sliding"] = body.trust_sliding
    if body.workspace_tone is not None:
        current["workspace_tone"] = body.workspace_tone

    return MoodSignals(**current)


@router.get("/current")
async def current(request: Request) -> dict:
    """Return the current mood snapshot."""
    engine = _get_engine(request)
    signals = _get_signals(request)
    result = engine.evaluate(signals)
    raw_mood = result.mood.name.lower()
    mood_key = _apply_hold(request.app.state, raw_mood)
    return {
        "mood": mood_key,
        "tone": result.overlay.value if result.overlay is not None else None,
        "drift_seconds": result.spec.drift_seconds,
        "reason": result.spec.description,
    }


@router.websocket("/ws")
async def mood_ws(websocket: WebSocket):
    """WebSocket push stream: current mood every 2s."""
    await websocket.accept()
    try:
        while True:
            engine = _get_engine(websocket)
            snap = engine.evaluate(getattr(websocket.app.state, "mood_signals", MoodSignals()))
            raw_mood = snap.mood.name.lower()
            mood_key = _apply_hold(websocket.app.state, raw_mood)
            await websocket.send_json({
                "mood": mood_key,
                "tone": snap.overlay.value if snap.overlay is not None else None,
                "drift_seconds": snap.spec.drift_seconds,
                "reason": snap.spec.description,
            })
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return


@router.post("/observe")
async def observe(request: Request, body: ObserveBody) -> dict:
    """Push state observations into the engine and return the new mood."""
    engine = _get_engine(request)
    signals = _get_signals(request)
    try:
        new_signals = _apply_body_to_signals(body, signals)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Persist updated signals
    request.app.state.mood_signals = new_signals
    result = engine.evaluate(new_signals)
    raw_mood = result.mood.name.lower()
    mood_key = _apply_hold(request.app.state, raw_mood)
    return {"mood": mood_key, "reason": result.spec.description}

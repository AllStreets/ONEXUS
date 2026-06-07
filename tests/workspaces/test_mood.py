"""Tests for MoodEngine — 8-state ambient mood system."""
from __future__ import annotations

import pytest

from nexus.workspaces.mood import (
    Mood,
    MoodEngine,
    MoodResult,
    MoodSignals,
    TrustOverlay,
)


@pytest.fixture()
def engine() -> MoodEngine:
    return MoodEngine()


def _sig(**kwargs) -> MoodSignals:
    return MoodSignals(**kwargs)


# ── default mood ──────────────────────────────────────────────────────────────


def test_default_signals_give_calm_focus(engine):
    result = engine.evaluate(MoodSignals())
    assert result.mood is Mood.CALM_FOCUS


# ── alert (highest priority) ──────────────────────────────────────────────────


def test_trust_collapse_gives_alert(engine):
    result = engine.evaluate(_sig(trust_collapsed=True))
    assert result.mood is Mood.ALERT


def test_alert_overlay_is_collapse(engine):
    result = engine.evaluate(_sig(trust_collapsed=True))
    assert result.overlay is TrustOverlay.COLLAPSE


def test_alert_overrides_watchful(engine):
    result = engine.evaluate(_sig(trust_collapsed=True, oracle_pattern_flagged=True))
    assert result.mood is Mood.ALERT


# ── watchful ──────────────────────────────────────────────────────────────────


def test_oracle_pattern_gives_watchful(engine):
    result = engine.evaluate(_sig(oracle_pattern_flagged=True))
    assert result.mood is Mood.WATCHFUL


def test_specter_auditing_gives_watchful(engine):
    result = engine.evaluate(_sig(specter_auditing=True))
    assert result.mood is Mood.WATCHFUL


def test_trust_sliding_gives_watchful(engine):
    result = engine.evaluate(_sig(trust_sliding=True))
    assert result.mood is Mood.WATCHFUL


# ── routing ───────────────────────────────────────────────────────────────────


def test_high_pulse_multiple_agents_gives_routing(engine):
    result = engine.evaluate(_sig(pulse_rate_above_baseline=True, active_agent_count=3))
    assert result.mood is Mood.ROUTING


def test_high_pulse_single_agent_not_routing(engine):
    result = engine.evaluate(_sig(pulse_rate_above_baseline=True, active_agent_count=1))
    assert result.mood is not Mood.ROUTING


# ── creative ──────────────────────────────────────────────────────────────────


def test_magenta_tone_gives_creative(engine):
    result = engine.evaluate(_sig(workspace_tone="MAGENTA"))
    assert result.mood is Mood.CREATIVE


def test_comfyui_agent_gives_creative(engine):
    result = engine.evaluate(_sig(active_agent="comfyui"))
    assert result.mood is Mood.CREATIVE


# ── deliberating ──────────────────────────────────────────────────────────────


def test_council_agent_gives_deliberating(engine):
    result = engine.evaluate(_sig(active_agent="council"))
    assert result.mood is Mood.DELIBERATING


def test_specter_agent_gives_deliberating_without_audit(engine):
    # specter_auditing=False so watchful is skipped
    result = engine.evaluate(_sig(active_agent="specter", specter_auditing=False))
    assert result.mood is Mood.DELIBERATING


def test_legacy_agent_gives_deliberating(engine):
    result = engine.evaluate(_sig(active_agent="legacy"))
    assert result.mood is Mood.DELIBERATING


# ── reflective ────────────────────────────────────────────────────────────────


def test_consciousness_low_pulse_gives_reflective(engine):
    result = engine.evaluate(_sig(active_agent="consciousness", pulse_rate_above_baseline=False))
    assert result.mood is Mood.REFLECTIVE


# ── deep flow ─────────────────────────────────────────────────────────────────


def test_sustained_focus_gives_deep_flow(engine):
    result = engine.evaluate(_sig(sustained_focus=True))
    assert result.mood is Mood.DEEP_FLOW


# ── trust overlays ────────────────────────────────────────────────────────────


def test_large_trust_gain_gives_rising_overlay(engine):
    result = engine.evaluate(_sig(trust_delta=0.12))
    assert result.overlay is TrustOverlay.RISING


def test_large_trust_loss_gives_falling_overlay(engine):
    result = engine.evaluate(_sig(trust_delta=-0.022))
    assert result.overlay is TrustOverlay.FALLING


def test_small_trust_delta_gives_no_overlay(engine):
    result = engine.evaluate(_sig(trust_delta=0.005))
    assert result.overlay is None


def test_no_overlay_in_calm(engine):
    result = engine.evaluate(MoodSignals())
    assert result.overlay is None


# ── MoodSpec metadata ─────────────────────────────────────────────────────────


def test_all_eight_moods_have_specs(engine):
    specs = MoodEngine.all_specs()
    assert len(specs) == 8


def test_alert_has_fastest_drift(engine):
    alert_spec = MoodEngine.mood_spec(Mood.ALERT)
    calm_spec = MoodEngine.mood_spec(Mood.CALM_FOCUS)
    assert alert_spec.drift_seconds < calm_spec.drift_seconds


# ── to_dict ───────────────────────────────────────────────────────────────────


def test_result_to_dict(engine):
    result = engine.evaluate(_sig(trust_delta=0.12))
    d = result.to_dict()
    assert d["mood"] == "Calm Focus"
    assert d["overlay"] == "rising"
    assert "drift_seconds" in d
    assert "hue_family" in d


# ── tone gradients ────────────────────────────────────────────────────────────


def test_all_five_tones_have_gradients():
    for tone in ("INDIGO", "MAGENTA", "SAGE", "PLUM", "AMBER"):
        start, end = MoodEngine.tone_gradient(tone)
        assert start.startswith("#")
        assert end.startswith("#")

"""T4 — Tests for time-of-day bias on MoodResult."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from nexus.workspaces.mood import MoodEngine, MoodResult, MoodSignals, _tod_bias_for_hour


@pytest.fixture
def engine() -> MoodEngine:
    return MoodEngine()


# ---------------------------------------------------------------------------
# Unit tests for _tod_bias_for_hour helper
# ---------------------------------------------------------------------------

class TestTodBiasHelper:
    def test_morning_gold_06(self):
        assert _tod_bias_for_hour(6) == 0.5

    def test_morning_gold_09(self):
        assert _tod_bias_for_hour(9) == 0.5

    def test_morning_boundary_10_is_neutral(self):
        # 10 is the start of the midday window, not morning
        assert _tod_bias_for_hour(10) == 0.0

    def test_midday_neutral_12(self):
        assert _tod_bias_for_hour(12) == 0.0

    def test_midday_neutral_16(self):
        assert _tod_bias_for_hour(16) == 0.0

    def test_midday_boundary_17_is_evening(self):
        assert _tod_bias_for_hour(17) == 0.5

    def test_evening_violet_20(self):
        assert _tod_bias_for_hour(20) == 0.5

    def test_evening_boundary_22_is_night(self):
        assert _tod_bias_for_hour(22) == -0.5

    def test_night_desat_23(self):
        assert _tod_bias_for_hour(23) == -0.5

    def test_night_desat_00(self):
        assert _tod_bias_for_hour(0) == -0.5

    def test_night_desat_03(self):
        assert _tod_bias_for_hour(3) == -0.5

    def test_night_boundary_05_is_night(self):
        assert _tod_bias_for_hour(5) == -0.5

    def test_morning_boundary_06_enters_morning(self):
        assert _tod_bias_for_hour(6) == 0.5


# ---------------------------------------------------------------------------
# Tests for MoodResult carrying tod_bias
# ---------------------------------------------------------------------------

class TestMoodResultTodBias:
    def test_result_has_tod_bias_field(self, engine):
        result = engine.evaluate(MoodSignals())
        assert hasattr(result, "tod_bias")

    def test_tod_bias_is_float(self, engine):
        result = engine.evaluate(MoodSignals())
        assert isinstance(result.tod_bias, float)

    def test_morning_hour_gives_positive_bias(self, engine):
        with patch("nexus.workspaces.mood.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 8  # 08:xx — morning
            result = engine.evaluate(MoodSignals())
        assert result.tod_bias == 0.5

    def test_midday_hour_gives_zero_bias(self, engine):
        with patch("nexus.workspaces.mood.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 13  # 13:xx — midday
            result = engine.evaluate(MoodSignals())
        assert result.tod_bias == 0.0

    def test_evening_hour_gives_positive_bias(self, engine):
        with patch("nexus.workspaces.mood.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 19  # 19:xx — evening
            result = engine.evaluate(MoodSignals())
        assert result.tod_bias == 0.5

    def test_night_hour_gives_negative_bias(self, engine):
        with patch("nexus.workspaces.mood.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 2  # 02:xx — night
            result = engine.evaluate(MoodSignals())
        assert result.tod_bias == -0.5

    def test_signals_hour_utc_overrides_clock(self, engine):
        """When MoodSignals.hour_utc is set, it should override datetime.now()."""
        # Force midnight signals; verify we get night bias without mocking datetime
        result = engine.evaluate(MoodSignals(hour_utc=0))
        assert result.tod_bias == -0.5

    def test_signals_morning_hour_utc(self, engine):
        result = engine.evaluate(MoodSignals(hour_utc=7))
        assert result.tod_bias == 0.5

    def test_tod_bias_in_to_dict(self, engine):
        result = engine.evaluate(MoodSignals(hour_utc=14))
        d = result.to_dict()
        assert "tod_bias" in d
        assert d["tod_bias"] == 0.0

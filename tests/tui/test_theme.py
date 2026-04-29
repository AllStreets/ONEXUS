"""Tests for nexus.tui.theme -- trust color mapping and bar rendering."""
from __future__ import annotations

import pytest
from nexus.tui.theme import trust_color, trust_bar, trust_tier_name, NEXUS_THEME


class TestTrustColor:
    """Verify trust_color returns the correct style for each tier."""

    def test_skill_tier_zero(self):
        assert trust_color(0) == "nexus.trust.skill"

    def test_skill_tier_boundary(self):
        assert trust_color(24) == "nexus.trust.skill"

    def test_advisor_tier_lower(self):
        assert trust_color(25) == "nexus.trust.advisor"

    def test_advisor_tier_upper(self):
        assert trust_color(49) == "nexus.trust.advisor"

    def test_monitor_tier_lower(self):
        assert trust_color(50) == "nexus.trust.monitor"

    def test_monitor_tier_upper(self):
        assert trust_color(74) == "nexus.trust.monitor"

    def test_autonomous_tier_lower(self):
        assert trust_color(75) == "nexus.trust.autonomous"

    def test_autonomous_tier_upper(self):
        assert trust_color(99) == "nexus.trust.autonomous"

    def test_sovereign_tier(self):
        assert trust_color(100) == "nexus.trust.sovereign"


class TestTrustTierName:
    def test_skill(self):
        assert trust_tier_name(10) == "SKILL"

    def test_advisor(self):
        assert trust_tier_name(30) == "ADVISOR"

    def test_monitor(self):
        assert trust_tier_name(60) == "MONITOR"

    def test_autonomous(self):
        assert trust_tier_name(85) == "AUTONOMOUS"

    def test_sovereign(self):
        assert trust_tier_name(100) == "SOVEREIGN"


class TestTrustBar:
    """Verify trust_bar produces correct block-character strings."""

    FULL = "\u2588"
    SHADE = "\u2591"

    def test_zero_score(self):
        bar = trust_bar(0, width=10)
        assert bar == self.SHADE * 10

    def test_full_score(self):
        bar = trust_bar(100, width=10)
        assert bar == self.FULL * 10

    def test_half_score(self):
        bar = trust_bar(50, width=10)
        assert bar == self.FULL * 5 + self.SHADE * 5

    def test_eighty_score(self):
        bar = trust_bar(80, width=10)
        assert bar == self.FULL * 8 + self.SHADE * 2

    def test_custom_width(self):
        bar = trust_bar(50, width=20)
        assert len(bar) == 20
        assert bar == self.FULL * 10 + self.SHADE * 10

    def test_clamped_above_100(self):
        bar = trust_bar(150, width=10)
        assert bar == self.FULL * 10

    def test_clamped_below_0(self):
        bar = trust_bar(-10, width=10)
        assert bar == self.SHADE * 10

    def test_bar_length_always_matches_width(self):
        for score in range(0, 101, 7):
            for width in (5, 10, 15, 20):
                bar = trust_bar(score, width=width)
                assert len(bar) == width


class TestNexusTheme:
    """Verify the theme object is valid."""

    def test_theme_has_primary(self):
        assert "nexus.primary" in NEXUS_THEME.styles

    def test_theme_has_trust_styles(self):
        for tier in ("skill", "advisor", "monitor", "autonomous", "sovereign"):
            assert f"nexus.trust.{tier}" in NEXUS_THEME.styles

    def test_theme_has_surface_styles(self):
        assert "nexus.surface" in NEXUS_THEME.styles
        assert "nexus.border" in NEXUS_THEME.styles
        assert "nexus.text" in NEXUS_THEME.styles
        assert "nexus.text.dim" in NEXUS_THEME.styles

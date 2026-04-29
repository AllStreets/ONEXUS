"""Tests for the reputation system."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nexus.community.models import MarketplaceEntry
from nexus.community.reputation import ReputationSystem


@pytest.fixture
def tmp_reputation(tmp_path):
    return ReputationSystem(tmp_path / "reputation.json")


def _make_entry(**overrides) -> MarketplaceEntry:
    defaults = dict(
        name="test",
        author="tester",
        description="A test package",
        version="1.0.0",
        type="module",
        category="code",
    )
    defaults.update(overrides)
    return MarketplaceEntry(**defaults)


class TestPackageScore:
    def test_default_entry_gets_baseline_score(self, tmp_reputation):
        entry = _make_entry()
        score = tmp_reputation.calculate_package_score(entry)
        # No downloads, no rating, no trust -> moderate baseline
        assert 0 <= score <= 100

    def test_high_rating_increases_score(self, tmp_reputation):
        low = _make_entry(rating=1.0, rating_count=5)
        high = _make_entry(rating=5.0, rating_count=5)
        assert tmp_reputation.calculate_package_score(high) > tmp_reputation.calculate_package_score(low)

    def test_more_downloads_increases_score(self, tmp_reputation):
        few = _make_entry(downloads=1)
        many = _make_entry(downloads=10000)
        assert tmp_reputation.calculate_package_score(many) > tmp_reputation.calculate_package_score(few)

    def test_trust_score_factors_in(self, tmp_reputation):
        low_trust = _make_entry(type="agent", trust_score=10)
        high_trust = _make_entry(type="agent", trust_score=90)
        assert tmp_reputation.calculate_package_score(high_trust) > tmp_reputation.calculate_package_score(low_trust)

    def test_freshness_matters(self, tmp_reputation):
        recent = _make_entry(updated_at=datetime.now(timezone.utc).isoformat())
        old = _make_entry(updated_at="2020-01-01T00:00:00+00:00")
        assert tmp_reputation.calculate_package_score(recent) > tmp_reputation.calculate_package_score(old)

    def test_score_capped_at_100(self, tmp_reputation):
        entry = _make_entry(
            rating=5.0,
            rating_count=100,
            downloads=1_000_000,
            trust_score=100,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        assert tmp_reputation.calculate_package_score(entry) <= 100.0


class TestAuthorScore:
    def test_single_package(self, tmp_reputation):
        entry = _make_entry(rating=4.0, downloads=50, trust_score=60)
        score = tmp_reputation.calculate_author_score("tester", [entry])
        assert score > 0

    def test_multiple_packages_get_volume_bonus(self, tmp_reputation):
        entries = [_make_entry(name=f"pkg{i}", rating=4.0, downloads=50) for i in range(5)]
        multi_score = tmp_reputation.calculate_author_score("tester", entries)
        single_score = tmp_reputation.calculate_author_score("tester2", [entries[0]])
        assert multi_score > single_score

    def test_empty_packages(self, tmp_reputation):
        assert tmp_reputation.calculate_author_score("nobody", []) == 0.0

    def test_score_persisted(self, tmp_reputation):
        entry = _make_entry(rating=3.0)
        tmp_reputation.calculate_author_score("tester", [entry])
        assert tmp_reputation.data_path.exists()
        data = json.loads(tmp_reputation.data_path.read_text())
        assert "tester" in data["author_scores"]


class TestBadges:
    def test_verified_badge(self, tmp_reputation):
        entry = _make_entry(trust_score=10)
        assert "verified" in tmp_reputation.get_badges(entry)

    def test_no_verified_without_trust(self, tmp_reputation):
        entry = _make_entry(trust_score=None)
        assert "verified" not in tmp_reputation.get_badges(entry)

    def test_popular_badge(self, tmp_reputation):
        entry = _make_entry(downloads=100)
        assert "popular" in tmp_reputation.get_badges(entry)

    def test_not_popular_below_threshold(self, tmp_reputation):
        entry = _make_entry(downloads=99)
        assert "popular" not in tmp_reputation.get_badges(entry)

    def test_trusted_badge_agent_only(self, tmp_reputation):
        agent = _make_entry(type="agent", trust_score=80)
        module = _make_entry(type="module", trust_score=80)
        assert "trusted" in tmp_reputation.get_badges(agent)
        assert "trusted" not in tmp_reputation.get_badges(module)

    def test_top_rated_badge(self, tmp_reputation):
        entry = _make_entry(rating=4.5, rating_count=3)
        assert "top-rated" in tmp_reputation.get_badges(entry)

    def test_top_rated_needs_reviews(self, tmp_reputation):
        entry = _make_entry(rating=5.0, rating_count=0)
        assert "top-rated" not in tmp_reputation.get_badges(entry)

    def test_new_badge(self, tmp_reputation):
        entry = _make_entry(created_at=datetime.now(timezone.utc).isoformat())
        assert "new" in tmp_reputation.get_badges(entry)

    def test_not_new_after_30_days(self, tmp_reputation):
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        entry = _make_entry(created_at=old_date)
        assert "new" not in tmp_reputation.get_badges(entry)

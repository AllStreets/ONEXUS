"""Tests for the Marketplace class."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nexus.community.marketplace import Marketplace
from nexus.community.models import MarketplaceEntry


def _seed_registry(path: Path, modules: list[dict] | None = None) -> None:
    """Write a minimal registry.json for testing."""
    if modules is None:
        modules = [
            {
                "name": "alpha",
                "author": "dev1",
                "description": "Alpha module for testing",
                "version": "1.0.0",
                "type": "module",
                "category": "code",
                "keywords": ["testing", "alpha"],
                "license": "MIT",
                "created_at": "2026-03-01T00:00:00+00:00",
                "updated_at": "2026-04-01T00:00:00+00:00",
            },
            {
                "name": "beta",
                "author": "dev1",
                "description": "Beta agent for security",
                "version": "0.2.0",
                "type": "agent",
                "category": "infrastructure",
                "keywords": ["security", "beta"],
                "license": "Apache-2.0",
                "trust_score": 80,
                "created_at": "2026-02-01T00:00:00+00:00",
                "updated_at": "2026-04-10T00:00:00+00:00",
            },
            {
                "name": "gamma",
                "author": "dev2",
                "description": "Gamma data pipeline",
                "version": "0.5.0",
                "type": "agent",
                "category": "data",
                "keywords": ["pipeline", "data", "alpha"],
                "license": "MIT",
                "trust_score": 45,
                "created_at": "2026-01-15T00:00:00+00:00",
                "updated_at": "2026-03-20T00:00:00+00:00",
            },
        ]
    path.write_text(json.dumps({"modules": modules}))


@pytest.fixture
def marketplace(tmp_path) -> Marketplace:
    registry_path = tmp_path / "registry.json"
    _seed_registry(registry_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return Marketplace(registry_path, data_dir)


class TestBrowse:
    def test_browse_all(self, marketplace):
        entries = marketplace.browse()
        assert len(entries) == 3

    def test_browse_by_category(self, marketplace):
        entries = marketplace.browse(category="code")
        assert len(entries) == 1
        assert entries[0].name == "alpha"

    def test_browse_by_type(self, marketplace):
        entries = marketplace.browse(type_filter="agent")
        assert len(entries) == 2

    def test_browse_sort_by_trust(self, marketplace):
        entries = marketplace.browse(sort="trust")
        assert entries[0].name == "beta"  # trust 80

    def test_browse_sort_by_newest(self, marketplace):
        entries = marketplace.browse(sort="newest")
        # alpha has most recent created_at (2026-03-01 vs 2026-02-01)
        assert entries[0].name == "alpha"

    def test_browse_empty_category(self, marketplace):
        entries = marketplace.browse(category="business")
        assert len(entries) == 0


class TestGetDetails:
    def test_existing(self, marketplace):
        entry = marketplace.get_details("alpha")
        assert entry is not None
        assert entry.name == "alpha"
        assert entry.author == "dev1"

    def test_missing(self, marketplace):
        assert marketplace.get_details("nonexistent") is None


class TestInstallTracking:
    def test_record_install_increments(self, marketplace):
        marketplace.record_install("alpha")
        marketplace.record_install("alpha")
        entry = marketplace.get_details("alpha")
        assert entry.downloads == 2

    def test_record_install_persists(self, marketplace):
        marketplace.record_install("beta")
        # Reload stats
        marketplace._load_stats()
        entry = marketplace.get_details("beta")
        assert entry.downloads == 1

    def test_record_uninstall_tracked(self, marketplace):
        marketplace.record_install("alpha")
        marketplace.record_uninstall("alpha")
        history = marketplace._stats.get("install_history", [])
        actions = [h["action"] for h in history if h["name"] == "alpha"]
        assert "install" in actions
        assert "uninstall" in actions


class TestRating:
    def test_rate_valid(self, marketplace):
        marketplace.rate("alpha", 4, "Great module")
        entry = marketplace.get_details("alpha")
        assert entry.rating == 4.0
        assert entry.rating_count == 1

    def test_rate_multiple(self, marketplace):
        marketplace.rate("alpha", 5)
        marketplace.rate("alpha", 3)
        entry = marketplace.get_details("alpha")
        assert entry.rating == 4.0
        assert entry.rating_count == 2

    def test_rate_invalid_score(self, marketplace):
        with pytest.raises(ValueError):
            marketplace.rate("alpha", 6)

    def test_rate_zero_invalid(self, marketplace):
        with pytest.raises(ValueError):
            marketplace.rate("alpha", 0)

    def test_rate_nonexistent(self, marketplace):
        with pytest.raises(ValueError):
            marketplace.rate("does_not_exist", 3)


class TestTrending:
    def test_trending_with_recent_installs(self, marketplace):
        marketplace.record_install("gamma")
        marketplace.record_install("gamma")
        marketplace.record_install("alpha")
        trending = marketplace.get_trending(days=7)
        assert len(trending) >= 1
        assert trending[0].name == "gamma"

    def test_trending_empty_when_no_installs(self, marketplace):
        trending = marketplace.get_trending()
        assert len(trending) == 0


class TestRecommended:
    def test_recommendations_based_on_keywords(self, marketplace):
        # alpha and gamma share "alpha" keyword
        recs = marketplace.get_recommended(["alpha"])
        names = [r.name for r in recs]
        assert "gamma" in names  # shares "alpha" keyword

    def test_recommendations_exclude_installed(self, marketplace):
        recs = marketplace.get_recommended(["alpha"])
        names = [r.name for r in recs]
        assert "alpha" not in names

    def test_empty_installed_returns_top(self, marketplace):
        recs = marketplace.get_recommended([])
        assert len(recs) > 0


class TestSearchAdvanced:
    def test_search_by_query(self, marketplace):
        results = marketplace.search_advanced(query="security")
        assert len(results) == 1
        assert results[0].name == "beta"

    def test_search_by_category(self, marketplace):
        results = marketplace.search_advanced(category="data")
        assert len(results) == 1

    def test_search_by_type(self, marketplace):
        results = marketplace.search_advanced(type_filter="module")
        assert len(results) == 1

    def test_search_by_author(self, marketplace):
        results = marketplace.search_advanced(author="dev2")
        assert len(results) == 1
        assert results[0].name == "gamma"

    def test_search_min_rating(self, marketplace):
        marketplace.rate("alpha", 5)
        results = marketplace.search_advanced(min_rating=4.0)
        assert len(results) == 1
        assert results[0].name == "alpha"

    def test_search_combined_filters(self, marketplace):
        results = marketplace.search_advanced(query="alpha", category="code")
        assert len(results) == 1


class TestStats:
    def test_stats_counts(self, marketplace):
        stats = marketplace.get_stats()
        assert stats.total_packages == 3
        assert stats.total_agents == 2
        assert stats.total_modules == 1
        assert stats.total_authors == 2

    def test_stats_categories(self, marketplace):
        stats = marketplace.get_stats()
        assert stats.categories["code"] == 1
        assert stats.categories["data"] == 1
        assert stats.categories["infrastructure"] == 1

    def test_stats_downloads(self, marketplace):
        marketplace.record_install("alpha")
        marketplace.record_install("alpha")
        stats = marketplace.get_stats()
        assert stats.total_downloads == 2

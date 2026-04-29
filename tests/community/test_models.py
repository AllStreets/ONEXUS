"""Tests for marketplace data models."""
from __future__ import annotations

from nexus.community.models import MarketplaceEntry, MarketplaceStats


class TestMarketplaceEntry:
    def test_defaults(self):
        entry = MarketplaceEntry(
            name="test_mod",
            author="tester",
            description="A test module",
            version="1.0.0",
            type="module",
            category="code",
        )
        assert entry.downloads == 0
        assert entry.rating == 0.0
        assert entry.rating_count == 0
        assert entry.reviews == []
        assert entry.installed is False
        assert entry.trust_score is None
        assert entry.watch_events == []
        assert entry.coordination_targets == []

    def test_to_dict(self):
        entry = MarketplaceEntry(
            name="vex",
            author="nexus-core",
            description="Security scanner",
            version="0.1.0",
            type="agent",
            category="code",
            keywords=["security"],
            trust_score=47,
        )
        d = entry.to_dict()
        assert d["name"] == "vex"
        assert d["type"] == "agent"
        assert d["trust_score"] == 47
        assert d["keywords"] == ["security"]

    def test_from_dict(self):
        data = {
            "name": "flux",
            "author": "nexus-core",
            "description": "Data pipeline monitor",
            "version": "0.2.0",
            "type": "agent",
            "category": "data",
            "keywords": ["pipeline", "monitoring"],
            "trust_score": 50,
            "downloads": 42,
            "rating": 3.5,
            "rating_count": 4,
        }
        entry = MarketplaceEntry.from_dict(data)
        assert entry.name == "flux"
        assert entry.downloads == 42
        assert entry.rating == 3.5
        assert entry.trust_score == 50

    def test_from_dict_missing_fields(self):
        """Backward compatibility: minimal dict should work."""
        data = {"name": "old_module", "author": "someone", "description": "Legacy", "version": "0.0.1"}
        entry = MarketplaceEntry.from_dict(data)
        assert entry.type == "module"
        assert entry.category == ""
        assert entry.trust_score is None

    def test_roundtrip(self):
        entry = MarketplaceEntry(
            name="test",
            author="a",
            description="d",
            version="1.0.0",
            type="agent",
            category="infrastructure",
            keywords=["k1", "k2"],
            downloads=10,
            rating=4.0,
            trust_score=80,
        )
        restored = MarketplaceEntry.from_dict(entry.to_dict())
        assert restored.name == entry.name
        assert restored.downloads == entry.downloads
        assert restored.trust_score == entry.trust_score


class TestMarketplaceStats:
    def test_defaults(self):
        stats = MarketplaceStats()
        assert stats.total_packages == 0
        assert stats.categories == {}

    def test_to_dict(self):
        stats = MarketplaceStats(
            total_packages=25,
            total_modules=0,
            total_agents=25,
            total_downloads=500,
            total_authors=1,
            categories={"code": 7, "data": 5},
        )
        d = stats.to_dict()
        assert d["total_packages"] == 25
        assert d["categories"]["code"] == 7

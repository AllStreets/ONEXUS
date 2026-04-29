"""
Marketplace -- enhanced module/agent marketplace with reputation and discovery.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.community.models import MarketplaceEntry, MarketplaceStats
from nexus.community.registry import ModuleRegistry
from nexus.community.reputation import ReputationSystem


class Marketplace:
    """Enhanced module/agent marketplace with reputation and discovery."""

    def __init__(self, registry_path: Path, data_dir: Path):
        self.registry = ModuleRegistry(registry_path)
        self.data_dir = data_dir
        self.stats_path = data_dir / "marketplace_stats.json"
        self.reputation = ReputationSystem(data_dir / "reputation.json")
        self._stats: dict[str, Any] = {}
        self._load_stats()

    def _load_stats(self) -> None:
        if self.stats_path.exists():
            try:
                self._stats = json.loads(self.stats_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._stats = {"installs": {}, "ratings": {}, "install_history": []}
        else:
            self._stats = {"installs": {}, "ratings": {}, "install_history": []}

    def _save_stats(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.stats_path.write_text(json.dumps(self._stats, indent=2))

    def _entry_from_raw(self, raw: dict[str, Any]) -> MarketplaceEntry:
        """Convert a raw registry dict into a MarketplaceEntry with stats overlay."""
        name = raw.get("name", "")
        install_data = self._stats.get("installs", {}).get(name, {})
        rating_data = self._stats.get("ratings", {}).get(name, {})

        return MarketplaceEntry(
            name=name,
            author=raw.get("author", ""),
            description=raw.get("description", ""),
            version=raw.get("version", "0.0.0"),
            type=raw.get("type", "module"),
            category=raw.get("category", ""),
            keywords=raw.get("keywords", []),
            license=raw.get("license", "Apache-2.0"),
            downloads=install_data.get("count", raw.get("downloads", 0)),
            rating=rating_data.get("average", raw.get("rating", 0.0)),
            rating_count=rating_data.get("count", raw.get("rating_count", 0)),
            reviews=rating_data.get("reviews", raw.get("reviews", [])),
            installed=False,
            trust_score=raw.get("trust_score"),
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
            watch_events=raw.get("watch_events", []),
            coordination_targets=raw.get("coordination_targets", []),
        )

    def _all_entries(self) -> list[MarketplaceEntry]:
        """Get all registry entries as MarketplaceEntry objects."""
        return [self._entry_from_raw(m) for m in self.registry.list_all()]

    def browse(
        self,
        category: str | None = None,
        sort: str = "downloads",
        type_filter: str | None = None,
    ) -> list[MarketplaceEntry]:
        """Browse marketplace with filtering and sorting.

        category: code, data, business, content, infrastructure
        sort: downloads, rating, newest, trust
        type_filter: module, agent, or None for both
        """
        entries = self._all_entries()

        if category:
            entries = [e for e in entries if e.category.lower() == category.lower()]

        if type_filter:
            entries = [e for e in entries if e.type.lower() == type_filter.lower()]

        sort_keys = {
            "downloads": lambda e: e.downloads,
            "rating": lambda e: e.rating,
            "newest": lambda e: e.created_at or "",
            "trust": lambda e: (e.trust_score or 0),
        }
        key_fn = sort_keys.get(sort, sort_keys["downloads"])
        entries.sort(key=key_fn, reverse=True)

        return entries

    def get_details(self, name: str) -> MarketplaceEntry | None:
        """Get full details for a specific package."""
        raw = self.registry.get(name)
        if raw is None:
            return None
        return self._entry_from_raw(raw)

    def record_install(self, name: str) -> None:
        """Track an installation."""
        installs = self._stats.setdefault("installs", {})
        entry = installs.setdefault(name, {"count": 0})
        entry["count"] = entry.get("count", 0) + 1
        entry["last_installed"] = datetime.now(timezone.utc).isoformat()

        # Add to install history for trending
        history = self._stats.setdefault("install_history", [])
        history.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "install",
        })
        self._save_stats()

    def record_uninstall(self, name: str) -> None:
        """Track an uninstallation."""
        history = self._stats.setdefault("install_history", [])
        history.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "uninstall",
        })
        self._save_stats()

    def rate(self, name: str, score: int, review: str = "") -> None:
        """Rate a package (1-5 stars)."""
        if not 1 <= score <= 5:
            raise ValueError("Rating must be between 1 and 5")

        raw = self.registry.get(name)
        if raw is None:
            raise ValueError(f"Package '{name}' not found")

        ratings = self._stats.setdefault("ratings", {})
        pkg_ratings = ratings.setdefault(name, {"scores": [], "reviews": [], "average": 0.0, "count": 0})

        pkg_ratings["scores"].append(score)
        pkg_ratings["count"] = len(pkg_ratings["scores"])
        pkg_ratings["average"] = round(
            sum(pkg_ratings["scores"]) / len(pkg_ratings["scores"]), 1
        )

        if review:
            pkg_ratings["reviews"].append({
                "score": score,
                "review": review,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        self._save_stats()

    def get_trending(self, days: int = 7, limit: int = 10) -> list[MarketplaceEntry]:
        """Get trending packages based on recent installs."""
        cutoff = datetime.now(timezone.utc)
        history = self._stats.get("install_history", [])

        recent_counts: Counter[str] = Counter()
        for event in history:
            if event.get("action") != "install":
                continue
            try:
                ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                delta = (cutoff - ts).days
                if delta <= days:
                    recent_counts[event["name"]] += 1
            except (ValueError, KeyError):
                continue

        trending_names = [name for name, _ in recent_counts.most_common(limit)]
        entries = []
        for name in trending_names:
            entry = self.get_details(name)
            if entry:
                entries.append(entry)
        return entries

    def get_recommended(self, installed: list[str]) -> list[MarketplaceEntry]:
        """Get recommendations based on what's installed (keyword overlap)."""
        if not installed:
            return self.browse(sort="downloads")[:10]

        # Collect keywords from installed packages
        installed_keywords: set[str] = set()
        installed_set = set(installed)
        for name in installed:
            entry = self.get_details(name)
            if entry:
                installed_keywords.update(kw.lower() for kw in entry.keywords)

        if not installed_keywords:
            return self.browse(sort="downloads")[:10]

        # Score each non-installed package by keyword overlap
        all_entries = self._all_entries()
        scored: list[tuple[int, MarketplaceEntry]] = []
        for entry in all_entries:
            if entry.name in installed_set:
                continue
            overlap = sum(1 for kw in entry.keywords if kw.lower() in installed_keywords)
            if overlap > 0:
                scored.append((overlap, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:10]]

    def search_advanced(
        self,
        query: str = "",
        category: str | None = None,
        type_filter: str | None = None,
        min_rating: float = 0,
        author: str | None = None,
    ) -> list[MarketplaceEntry]:
        """Advanced search with multiple filters."""
        if query:
            raw_results = self.registry.search(query)
            entries = [self._entry_from_raw(r) for r in raw_results]
        else:
            entries = self._all_entries()

        if category:
            entries = [e for e in entries if e.category.lower() == category.lower()]

        if type_filter:
            entries = [e for e in entries if e.type.lower() == type_filter.lower()]

        if min_rating > 0:
            entries = [e for e in entries if e.rating >= min_rating]

        if author:
            entries = [e for e in entries if e.author.lower() == author.lower()]

        return entries

    def get_stats(self) -> MarketplaceStats:
        """Calculate and return aggregate marketplace stats."""
        entries = self._all_entries()
        categories: dict[str, int] = {}
        authors: set[str] = set()
        total_downloads = 0
        total_modules = 0
        total_agents = 0

        for entry in entries:
            cat = entry.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1
            authors.add(entry.author)
            total_downloads += entry.downloads
            if entry.type == "module":
                total_modules += 1
            elif entry.type == "agent":
                total_agents += 1

        return MarketplaceStats(
            total_packages=len(entries),
            total_modules=total_modules,
            total_agents=total_agents,
            total_downloads=total_downloads,
            total_authors=len(authors),
            categories=categories,
        )

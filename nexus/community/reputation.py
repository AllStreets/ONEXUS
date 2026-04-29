"""
ReputationSystem -- calculates trust scores and badges for marketplace packages.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.community.models import MarketplaceEntry


class ReputationSystem:
    """Tracks author and package reputation based on trust, ratings, and usage."""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.data_path.exists():
            try:
                return json.loads(self.data_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"author_scores": {}}

    def _save(self) -> None:
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(json.dumps(self._data, indent=2))

    def calculate_package_score(self, entry: MarketplaceEntry) -> float:
        """Calculate composite reputation score (0-100).

        Weighted formula:
        - 40% average rating (1-5 stars, normalized to 0-100)
        - 30% download count (logarithmic scale)
        - 20% trust score (agents only, 0-100; modules get 50 baseline)
        - 10% freshness (time since last update)
        """
        # Rating component: normalize 1-5 to 0-100
        if entry.rating > 0:
            rating_score = (entry.rating / 5.0) * 100.0
        else:
            rating_score = 50.0  # neutral default

        # Downloads component: log scale, cap at 100
        if entry.downloads > 0:
            download_score = min(100.0, math.log10(entry.downloads + 1) * 33.3)
        else:
            download_score = 0.0

        # Trust component
        if entry.trust_score is not None:
            trust_component = float(entry.trust_score)
        else:
            trust_component = 50.0

        # Freshness component
        freshness_score = self._calculate_freshness(entry.updated_at or entry.created_at)

        composite = (
            0.40 * rating_score
            + 0.30 * download_score
            + 0.20 * trust_component
            + 0.10 * freshness_score
        )
        return round(min(100.0, max(0.0, composite)), 1)

    def _calculate_freshness(self, date_str: str) -> float:
        """Return freshness score 0-100 based on recency."""
        if not date_str:
            return 50.0
        try:
            updated = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days_old = (now - updated).days
            if days_old <= 30:
                return 100.0
            elif days_old <= 90:
                return 80.0
            elif days_old <= 180:
                return 60.0
            elif days_old <= 365:
                return 40.0
            else:
                return 20.0
        except (ValueError, TypeError):
            return 50.0

    def calculate_author_score(self, author: str, packages: list[MarketplaceEntry]) -> float:
        """Calculate author reputation from aggregate package scores."""
        if not packages:
            return 0.0

        scores = [self.calculate_package_score(p) for p in packages]
        avg_score = sum(scores) / len(scores)

        # Bonus for having multiple well-rated packages
        volume_bonus = min(10.0, len(packages) * 1.5)

        result = round(min(100.0, avg_score + volume_bonus), 1)

        # Cache the score
        self._data["author_scores"][author] = result
        self._save()

        return result

    def get_badges(self, entry: MarketplaceEntry) -> list[str]:
        """Return earned badges for a package.

        Badges:
        - "verified" - passes all validation checks (trust_score > 0)
        - "popular" - 100+ downloads
        - "trusted" - agent with trust score 75+
        - "top-rated" - rating 4.5+
        - "new" - published in last 30 days
        """
        badges: list[str] = []

        # verified: has a trust score above zero (validated)
        if entry.trust_score is not None and entry.trust_score > 0:
            badges.append("verified")

        # popular: 100+ downloads
        if entry.downloads >= 100:
            badges.append("popular")

        # trusted: agent with high trust
        if entry.type == "agent" and entry.trust_score is not None and entry.trust_score >= 75:
            badges.append("trusted")

        # top-rated
        if entry.rating >= 4.5 and entry.rating_count >= 1:
            badges.append("top-rated")

        # new: created in last 30 days
        if entry.created_at:
            try:
                created = datetime.fromisoformat(entry.created_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if (now - created).days <= 30:
                    badges.append("new")
            except (ValueError, TypeError):
                pass

        return badges

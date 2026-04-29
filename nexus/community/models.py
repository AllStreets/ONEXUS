"""
Data models for the NEXUS marketplace.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketplaceEntry:
    """Represents a single package (module or agent) in the marketplace."""

    name: str
    author: str
    description: str
    version: str
    type: str  # "module" or "agent"
    category: str
    keywords: list[str] = field(default_factory=list)
    license: str = "Apache-2.0"
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    reviews: list[dict] = field(default_factory=list)
    installed: bool = False
    trust_score: int | None = None
    created_at: str = ""
    updated_at: str = ""

    # Agent-specific fields
    watch_events: list[str] = field(default_factory=list)
    coordination_targets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "version": self.version,
            "type": self.type,
            "category": self.category,
            "keywords": self.keywords,
            "license": self.license,
            "downloads": self.downloads,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "reviews": self.reviews,
            "installed": self.installed,
            "trust_score": self.trust_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "watch_events": self.watch_events,
            "coordination_targets": self.coordination_targets,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MarketplaceEntry:
        return cls(
            name=data.get("name", ""),
            author=data.get("author", ""),
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            type=data.get("type", "module"),
            category=data.get("category", ""),
            keywords=data.get("keywords", []),
            license=data.get("license", "Apache-2.0"),
            downloads=data.get("downloads", 0),
            rating=data.get("rating", 0.0),
            rating_count=data.get("rating_count", 0),
            reviews=data.get("reviews", []),
            installed=data.get("installed", False),
            trust_score=data.get("trust_score"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            watch_events=data.get("watch_events", []),
            coordination_targets=data.get("coordination_targets", []),
        )


@dataclass
class MarketplaceStats:
    """Aggregate statistics for the marketplace."""

    total_packages: int = 0
    total_modules: int = 0
    total_agents: int = 0
    total_downloads: int = 0
    total_authors: int = 0
    categories: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_packages": self.total_packages,
            "total_modules": self.total_modules,
            "total_agents": self.total_agents,
            "total_downloads": self.total_downloads,
            "total_authors": self.total_authors,
            "categories": self.categories,
        }

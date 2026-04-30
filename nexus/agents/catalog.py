"""Read the ONEXUS-Agents catalog from disk.

The catalog is a directory tree of JSON files:
    catalog/<category>/<agent-slug>.json

Each JSON file matches the AgentEntry schema defined here.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus.agents.catalog")


@dataclass
class AgentEntry:
    """A single agent from the ONEXUS-Agents catalog."""

    slug: str
    name: str
    tagline: str
    category: str
    tags: list[str]
    license: str
    runnable: bool
    adapter_ref: str | None
    composite_score: float
    rank_in_category: int
    source_github: str | None = None
    source_huggingface: str | None = None
    homepage: str | None = None
    stars: int | None = None
    downloads_30d: int | None = None
    trust_floor: float = 0.0

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AgentEntry:
        source = data.get("source", {})
        metrics = data.get("metrics", {})
        return cls(
            slug=data["slug"],
            name=data["name"],
            tagline=data.get("tagline", ""),
            category=data["category"],
            tags=data.get("tags", []),
            license=data.get("license", "Unknown"),
            runnable=data.get("runnable", False),
            adapter_ref=data.get("adapter_ref"),
            composite_score=data.get("composite_score", 0.0),
            rank_in_category=data.get("rank_in_category", 999),
            source_github=source.get("github"),
            source_huggingface=source.get("huggingface"),
            homepage=source.get("homepage"),
            stars=metrics.get("stars"),
            downloads_30d=metrics.get("downloads_30d"),
        )


@dataclass
class AdapterDescriptor:
    """MCP adapter descriptor for a runnable agent."""

    name: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, Any]
    capabilities: dict[str, list[str]]
    trust_floor: float
    default_tier: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AdapterDescriptor:
        return cls(
            name=data["name"],
            transport=data.get("transport", "stdio"),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            capabilities=data.get("capabilities", {}),
            trust_floor=data.get("trust_floor", 0.0),
            default_tier=data.get("default_tier", "OBSERVER"),
        )


class AgentCatalog:
    """Reads and queries the ONEXUS-Agents catalog directory."""

    def __init__(self, catalog_path: str | Path) -> None:
        self._root = Path(catalog_path)
        if not self._root.is_dir():
            raise FileNotFoundError(f"Catalog directory not found: {self._root}")
        # If pointed at the repo root, use the catalog/ subdirectory
        if (self._root / "catalog").is_dir():
            self._root = self._root / "catalog"
        self._entries: dict[str, AgentEntry] = {}
        self._adapters_root = self._root.parent / "adapters"
        self._load()

    def _load(self) -> None:
        """Scan the catalog directory and load all agent entries."""
        count = 0
        for cat_dir in sorted(self._root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            for json_file in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(json_file.read_text())
                    entry = AgentEntry.from_json(data)
                    self._entries[entry.slug] = entry
                    count += 1
                except Exception as exc:
                    logger.warning("Failed to load %s: %s", json_file, exc)
        logger.info("Loaded %d agents from catalog at %s", count, self._root)

    def reload(self) -> None:
        """Re-read the catalog from disk."""
        self._entries.clear()
        self._load()

    def list_agents(self, category: str | None = None, runnable_only: bool = False) -> list[AgentEntry]:
        """Return agents, optionally filtered by category and runnable status."""
        entries = list(self._entries.values())
        if category:
            entries = [e for e in entries if e.category == category]
        if runnable_only:
            entries = [e for e in entries if e.runnable]
        entries.sort(key=lambda e: e.composite_score, reverse=True)
        return entries

    def get_agent(self, slug: str) -> AgentEntry | None:
        return self._entries.get(slug)

    def search(self, query: str, limit: int = 20) -> list[AgentEntry]:
        """Simple keyword search across name, tagline, tags, and category."""
        q = query.lower()
        scored: list[tuple[float, AgentEntry]] = []
        for entry in self._entries.values():
            score = 0.0
            if q in entry.name.lower():
                score += 2.0
            if q in entry.tagline.lower():
                score += 1.0
            if q in entry.category:
                score += 1.5
            if any(q in t for t in entry.tags):
                score += 1.0
            if score > 0:
                scored.append((score + entry.composite_score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def categories(self) -> list[str]:
        """Return sorted list of all categories with at least one agent."""
        return sorted({e.category for e in self._entries.values()})

    def load_adapter(self, agent: AgentEntry) -> AdapterDescriptor | None:
        """Load the MCP adapter descriptor for a runnable agent."""
        if not agent.adapter_ref:
            return None
        adapter_path = self._root.parent / agent.adapter_ref
        if not adapter_path.exists():
            logger.warning("Adapter not found: %s", adapter_path)
            return None
        try:
            data = json.loads(adapter_path.read_text())
            return AdapterDescriptor.from_json(data)
        except Exception as exc:
            logger.warning("Failed to load adapter %s: %s", adapter_path, exc)
            return None

    @property
    def count(self) -> int:
        return len(self._entries)

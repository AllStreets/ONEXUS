"""
Marketplace API routes -- browse, search, rate, and discover packages.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from nexus.community.marketplace import Marketplace

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


def _get_marketplace(request: Request) -> Marketplace:
    """Lazily initialize and cache a Marketplace instance on app state."""
    if not hasattr(request.app.state, "marketplace"):
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        registry_path = project_root / "community" / "registry.json"
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        request.app.state.marketplace = Marketplace(registry_path, data_dir)
    return request.app.state.marketplace


# ---------- Pydantic response models ----------

class EntryResponse(BaseModel):
    name: str
    author: str
    description: str
    version: str
    type: str
    category: str
    keywords: list[str]
    license: str
    downloads: int
    rating: float
    rating_count: int
    trust_score: int | None
    created_at: str
    updated_at: str
    watch_events: list[str]
    coordination_targets: list[str]
    badges: list[str] = []


class BrowseResponse(BaseModel):
    packages: list[EntryResponse]
    count: int


class StatsResponse(BaseModel):
    total_packages: int
    total_modules: int
    total_agents: int
    total_downloads: int
    total_authors: int
    categories: dict[str, int]


class RateRequest(BaseModel):
    score: int
    review: str = ""


class RateResponse(BaseModel):
    success: bool
    message: str


# ---------- Helpers ----------

def _entry_to_response(mp: Marketplace, entry) -> EntryResponse:
    badges = mp.reputation.get_badges(entry)
    return EntryResponse(
        name=entry.name,
        author=entry.author,
        description=entry.description,
        version=entry.version,
        type=entry.type,
        category=entry.category,
        keywords=entry.keywords,
        license=entry.license,
        downloads=entry.downloads,
        rating=entry.rating,
        rating_count=entry.rating_count,
        trust_score=entry.trust_score,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        watch_events=entry.watch_events,
        coordination_targets=entry.coordination_targets,
        badges=badges,
    )


# ---------- Routes ----------

@router.get("/browse", response_model=BrowseResponse)
async def browse(
    request: Request,
    category: str | None = Query(None),
    sort: str = Query("downloads"),
    type: str | None = Query(None, alias="type"),
) -> BrowseResponse:
    """Browse marketplace with filtering and sorting."""
    mp = _get_marketplace(request)
    entries = mp.browse(category=category, sort=sort, type_filter=type)
    packages = [_entry_to_response(mp, e) for e in entries]
    return BrowseResponse(packages=packages, count=len(packages))


@router.get("/trending", response_model=BrowseResponse)
async def trending(
    request: Request,
    days: int = Query(7),
    limit: int = Query(10),
) -> BrowseResponse:
    """Get trending packages based on recent installs."""
    mp = _get_marketplace(request)
    entries = mp.get_trending(days=days, limit=limit)
    packages = [_entry_to_response(mp, e) for e in entries]
    return BrowseResponse(packages=packages, count=len(packages))


@router.get("/recommended", response_model=BrowseResponse)
async def recommended(
    request: Request,
    installed: str = Query("", description="Comma-separated list of installed package names"),
) -> BrowseResponse:
    """Get recommendations based on what is installed."""
    mp = _get_marketplace(request)
    installed_list = [s.strip() for s in installed.split(",") if s.strip()] if installed else []
    entries = mp.get_recommended(installed_list)
    packages = [_entry_to_response(mp, e) for e in entries]
    return BrowseResponse(packages=packages, count=len(packages))


@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    """Get aggregate marketplace statistics."""
    mp = _get_marketplace(request)
    s = mp.get_stats()
    return StatsResponse(**s.to_dict())


@router.get("/search", response_model=BrowseResponse)
async def search(
    request: Request,
    q: str = Query(""),
    category: str | None = Query(None),
    type: str | None = Query(None, alias="type"),
    min_rating: float = Query(0),
    author: str | None = Query(None),
) -> BrowseResponse:
    """Advanced search with multiple filters."""
    mp = _get_marketplace(request)
    entries = mp.search_advanced(
        query=q,
        category=category,
        type_filter=type,
        min_rating=min_rating,
        author=author,
    )
    packages = [_entry_to_response(mp, e) for e in entries]
    return BrowseResponse(packages=packages, count=len(packages))


@router.get("/{name}", response_model=EntryResponse)
async def get_details(name: str, request: Request) -> EntryResponse:
    """Get full details for a specific package."""
    mp = _get_marketplace(request)
    entry = mp.get_details(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Package '{name}' not found")
    return _entry_to_response(mp, entry)


@router.post("/{name}/rate", response_model=RateResponse)
async def rate_package(name: str, body: RateRequest, request: Request) -> RateResponse:
    """Rate a package (1-5 stars)."""
    mp = _get_marketplace(request)
    try:
        mp.rate(name, body.score, body.review)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RateResponse(success=True, message=f"Rated '{name}' with {body.score} stars")

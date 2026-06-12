"""
Agent catalog — browse, search, and launch ONEXUS-Agents through MCP adapters.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.agents.launcher import AgentLauncher, AgentLaunchError

logger = logging.getLogger("nexus.api.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Response models ────────────────────────────────────────────────────────

class AgentSummary(BaseModel):
    slug: str
    name: str
    tagline: str
    category: str
    tags: list[str]
    license: str
    runnable: bool
    composite_score: float
    rank_in_category: int
    stars: int | None = None
    source_github: str | None = None
    trust_floor: float = 0.0


class AgentDetail(AgentSummary):
    adapter_ref: str | None = None
    source_huggingface: str | None = None
    homepage: str | None = None
    downloads_30d: int | None = None
    adapter: dict[str, Any] | None = None


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]
    total: int
    categories: list[str] = []


class RunningAgentInfo(BaseModel):
    slug: str
    name: str
    category: str
    pid: int | None = None
    tools: list[str] = []
    trust_floor: float = 0.0
    status: str = "running"


class LaunchResponse(BaseModel):
    slug: str
    status: str
    message: str
    tools: list[str] = []
    pid: int | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_catalog(request: Request):
    catalog = getattr(request.app.state, "agent_catalog", None)
    if catalog is None:
        raise HTTPException(status_code=503, detail="Agent catalog not loaded")
    return catalog


def _get_launcher(request: Request) -> AgentLauncher:
    launcher = getattr(request.app.state, "agent_launcher", None)
    if launcher is None:
        raise HTTPException(status_code=503, detail="Agent launcher not initialized")
    return launcher


def _entry_to_summary(e) -> AgentSummary:
    return AgentSummary(
        slug=e.slug,
        name=e.name,
        tagline=e.tagline,
        category=e.category,
        tags=e.tags,
        license=e.license,
        runnable=e.runnable,
        composite_score=e.composite_score,
        rank_in_category=e.rank_in_category,
        stars=e.stars,
        source_github=e.source_github,
        trust_floor=e.trust_floor,
    )


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    category: str | None = None,
    runnable_only: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    catalog = _get_catalog(request)
    entries = catalog.list_agents(category=category, runnable_only=runnable_only)
    total = len(entries)
    page = entries[offset:offset + limit]
    return AgentListResponse(
        agents=[_entry_to_summary(e) for e in page],
        total=total,
        categories=catalog.categories(),
    )


@router.get("/categories")
async def list_categories(request: Request) -> dict[str, Any]:
    catalog = _get_catalog(request)
    cats = catalog.categories()
    counts = {}
    for cat in cats:
        counts[cat] = len(catalog.list_agents(category=cat))
    return {"categories": cats, "counts": counts}


@router.get("/search", response_model=AgentListResponse)
async def search_agents(
    request: Request,
    q: str = "",
    limit: int = 20,
):
    catalog = _get_catalog(request)
    if not q.strip():
        all_matches = catalog.list_agents()
    else:
        # Search scans the WHOLE catalog; a high cap returns every match so we
        # can report the true total, then page to `limit` for display.
        all_matches = catalog.search(q.strip(), limit=1_000_000)
    total = len(all_matches)
    page = all_matches[:limit]
    return AgentListResponse(
        agents=[_entry_to_summary(e) for e in page],
        total=total,
        categories=catalog.categories(),
    )


@router.get("/running")
async def list_running(request: Request) -> list[RunningAgentInfo]:
    launcher = _get_launcher(request)
    return [
        RunningAgentInfo(
            slug=a.slug, name=a.name, category=a.category,
            pid=a.process.pid, tools=a.tools,
            trust_floor=a.trust_floor, status="running",
        )
        for a in launcher.list_running()
    ]


@router.get("/{slug}")
async def get_agent(request: Request, slug: str) -> AgentDetail:
    catalog = _get_catalog(request)
    entry = catalog.get_agent(slug)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")

    adapter_data = None
    if entry.runnable:
        adapter = catalog.load_adapter(entry)
        if adapter:
            adapter_data = {
                "name": adapter.name,
                "transport": adapter.transport,
                "command": adapter.command,
                "args": adapter.args,
                "env": {k: v for k, v in adapter.env.items()},
                "capabilities": adapter.capabilities,
                "trust_floor": adapter.trust_floor,
                "default_tier": adapter.default_tier,
            }

    return AgentDetail(
        slug=entry.slug,
        name=entry.name,
        tagline=entry.tagline,
        category=entry.category,
        tags=entry.tags,
        license=entry.license,
        runnable=entry.runnable,
        composite_score=entry.composite_score,
        rank_in_category=entry.rank_in_category,
        stars=entry.stars,
        source_github=entry.source_github,
        trust_floor=entry.trust_floor,
        adapter_ref=entry.adapter_ref,
        source_huggingface=entry.source_huggingface,
        homepage=entry.homepage,
        downloads_30d=entry.downloads_30d,
        adapter=adapter_data,
    )


@router.post("/{slug}/launch", response_model=LaunchResponse)
async def launch_agent(request: Request, slug: str) -> LaunchResponse:
    launcher = _get_launcher(request)
    if launcher.is_running(slug):
        agent = launcher.get(slug)
        return LaunchResponse(
            slug=slug, status="already_running",
            message=f"{slug} is already running (PID {agent.process.pid})",
            tools=agent.tools, pid=agent.process.pid,
        )
    try:
        agent = launcher.launch(slug)
    except AgentLaunchError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return LaunchResponse(
        slug=slug, status="launched",
        message=f"{agent.name} launched (PID {agent.process.pid})",
        tools=agent.tools, pid=agent.process.pid,
    )


@router.post("/{slug}/stop")
async def stop_agent(request: Request, slug: str) -> dict[str, str]:
    launcher = _get_launcher(request)
    try:
        agent = launcher.stop(slug)
    except AgentLaunchError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return {"slug": slug, "status": "stopped", "message": f"{agent.name} stopped"}

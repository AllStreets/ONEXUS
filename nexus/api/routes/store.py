"""Agent store: browse catalog agents that have a verified recipe, install them as
confined MCP servers, and remove them.

Key values sent to install go to the store's 0600 secrets file and nowhere else: no
response, log line or ledger entry contains them.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nexus.store.installer import InstallError

router = APIRouter(prefix="/api/store", tags=["store"])


class InstallBody(BaseModel):
    hosts: list[str] = Field(default_factory=list, max_length=50)
    env: dict[str, str] = Field(default_factory=dict)


class HostsBody(BaseModel):
    hosts: list[str] = Field(default_factory=list, max_length=50)


def _store(request: Request):
    installer = getattr(request.app.state, "store_installer", None)
    if installer is None:
        raise HTTPException(503, "The agent store needs the ONEXUS-Agents catalog alongside ONEXUS.")
    return installer


def _card(recipe: dict, entry, record) -> dict[str, Any]:
    v = recipe.get("verified") or {}
    inst = recipe.get("install") or {}
    return {
        "slug": recipe["slug"],
        "name": entry.name if entry else recipe["slug"],
        "tagline": entry.tagline if entry else "",
        "category": entry.category if entry else "",
        "stars": entry.stars if entry else None,
        "license": recipe.get("license", "Unknown"),
        "kind": inst.get("kind"),
        "tools": v.get("tools") or [],
        "needs_keys": [e["name"] for e in recipe.get("env") or [] if e.get("required")],
        "prebuilt": bool(recipe.get("prebuilt")),
        "installed": record is not None,
    }


@router.get("/agents")
def list_agents(request: Request, q: str = "", category: str = "") -> dict[str, Any]:
    inst = _store(request)
    catalog = request.app.state.agent_catalog
    out = []
    needle = q.strip().lower()
    for r in inst.recipes.installable():
        entry = catalog.get_agent(r["slug"]) if catalog else None
        card = _card(r, entry, inst.state.get(r["slug"]))
        if category and card["category"] != category:
            continue
        if needle and needle not in " ".join([card["name"], card["tagline"], " ".join(card["tools"])]).lower():
            continue
        out.append(card)
    out.sort(key=lambda c: (not c["installed"], -(c["stars"] or 0), c["name"].lower()))
    return {"agents": out, "total": len(out), "summary": inst.recipes.summary()}


@router.get("/agents/{slug}")
def agent_detail(request: Request, slug: str) -> dict[str, Any]:
    inst = _store(request)
    recipe = inst.recipes.get(slug)
    if not recipe:
        raise HTTPException(404, f"'{slug}' has no recipe")
    catalog = request.app.state.agent_catalog
    entry = catalog.get_agent(slug) if catalog else None
    record = inst.state.get(slug)
    v = recipe.get("verified") or {}
    return {
        **_card(recipe, entry, record),
        "installable": bool(v.get("ok")) and slug in {r["slug"] for r in inst.recipes.installable()},
        "source": recipe.get("source"),
        "derived_from": recipe.get("derived_from"),
        "install": recipe.get("install"),
        "command": recipe.get("command"),
        "env": recipe.get("env") or [],
        "hosts": recipe.get("hosts") or {"proposed": [], "evidence": {}},
        "verified": v,
        "homepage": getattr(entry, "homepage", None),
        "repo": getattr(entry, "source_github", None),
        "record": None if record is None else {
            "hosts": record.hosts, "installed_at": record.installed_at, "image": record.image,
            "keys_given": [k for k in record.env_names if k in inst.state.secrets_for(slug)],
        },
    }


@router.post("/agents/{slug}/install", status_code=202)
def install(request: Request, slug: str, body: InstallBody) -> dict[str, Any]:
    inst = _store(request)
    try:
        job = inst.start(slug, body.hosts, body.env)
    except InstallError as exc:
        raise HTTPException(400, str(exc)) from None
    return job.public()


@router.get("/jobs/{job_id}")
def job_status(request: Request, job_id: str) -> dict[str, Any]:
    job = _store(request).job(job_id)
    if not job:
        raise HTTPException(404, "no such install")
    return job.public()


@router.put("/agents/{slug}/hosts")
def set_hosts(request: Request, slug: str, body: HostsBody) -> dict[str, Any]:
    inst = _store(request)
    try:
        inst.validate_hosts(body.hosts)
    except InstallError as exc:
        raise HTTPException(400, str(exc)) from None
    rec = inst.state.set_hosts(slug, [h.lower() for h in body.hosts])
    if not rec:
        raise HTTPException(404, f"'{slug}' isn't installed")
    return {"slug": slug, "hosts": rec.hosts}


@router.delete("/agents/{slug}")
def uninstall(request: Request, slug: str) -> dict[str, Any]:
    inst = _store(request)
    launcher = getattr(request.app.state, "agent_launcher", None)
    if launcher is not None and launcher.is_running(slug):
        launcher.stop(slug)
    if not inst.uninstall(slug):
        raise HTTPException(404, f"'{slug}' isn't installed")
    return {"slug": slug, "removed": True}

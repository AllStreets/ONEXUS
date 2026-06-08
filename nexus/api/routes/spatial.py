from __future__ import annotations
from fastapi import APIRouter, Request
from typing import Any

router = APIRouter(prefix="/api/spatial", tags=["spatial"])


def _kernel(request: Request):
    return getattr(request.app.state, "kernel", None)


@router.get("/agents")
async def list_all_agents(request: Request) -> dict:
    """Return all known agents, system + catalog, unified."""
    kernel = _kernel(request)
    agents: list[dict[str, Any]] = []
    if kernel is None:
        return {"agents": agents}

    aegis = kernel.aegis

    # 1. System (built-in) agents — those whose manifest is registered with Aegis
    seen: set[str] = set()
    manifests = getattr(aegis, "_manifests", {})
    for slug, manifest in manifests.items():
        seen.add(slug)
        agents.append({
            "slug": slug,
            "name": manifest.name,
            "tagline": manifest.tagline,
            "category": manifest.category,
            "version": manifest.version,
            "system": True,
            "trust": aegis.get_trust(slug),
            "tier": aegis.get_tier(slug),
            "identity": {
                "kind": manifest.identity.mark.kind,
                "gradient": list(manifest.identity.mark.gradient),
            },
        })

    # 2. Installed catalog agents (Phase 4 installer)
    try:
        from nexus.agents.installer import installed_slugs, load_installed_manifest
        from nexus.config import NexusConfig
        cfg = NexusConfig()
        for slug in installed_slugs(cfg.data_dir):
            if slug in seen:
                continue
            m = load_installed_manifest(slug, cfg.data_dir)
            if m is None:
                continue
            agents.append({
                "slug": slug,
                "name": m.name,
                "tagline": m.tagline,
                "category": m.category,
                "version": m.version,
                "system": False,
                "trust": aegis.get_trust(slug),
                "tier": aegis.get_tier(slug),
                "identity": {
                    "kind": m.identity.mark.kind,
                    "gradient": list(m.identity.mark.gradient),
                },
            })
    except Exception:
        pass

    return {"agents": agents, "total": len(agents)}

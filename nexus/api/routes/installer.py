"""REST endpoint for the agent install flow."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.agents.installer import plan_from_manifest_dict, install_from_plan
from nexus.config import NexusConfig


router = APIRouter(prefix="/api/agents", tags=["agents"])


class InstallRequest(BaseModel):
    manifest: dict
    confirm: bool = False


@router.post("/install")
async def install(request: Request, body: InstallRequest) -> dict:
    try:
        plan = plan_from_manifest_dict(body.manifest)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid manifest: {exc}")

    plan_payload = {
        "slug": plan.slug,
        "name": plan.name,
        "version": plan.version,
        "publisher": plan.publisher,
        "license": plan.license,
        "tagline": plan.tagline,
        "groups": [
            {"permission_class": g.permission_class, "capabilities": g.capabilities}
            for g in plan.groups
        ],
        "has_privileged": plan.has_privileged,
    }

    if not body.confirm:
        return {"plan": plan_payload, "installed": False}

    cfg = NexusConfig()
    install_from_plan(plan, cfg.data_dir)
    return {"plan": plan_payload, "installed": True}

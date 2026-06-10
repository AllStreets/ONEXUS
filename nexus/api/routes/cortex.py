"""Cortex launcher — multi-agent dispatch from a single prompt.

Unlike ``POST /api/messages`` (which lets Cortex auto-select ONE module),
this endpoint lets the user (or the launcher UI) fan a single prompt to
multiple agents at once, or pick the top-N candidates that Cortex would
have considered.

Endpoints:

  POST /api/cortex/launch
      { message, workspace_id?, agents?: list[str], top_k?: int }

      - If ``agents`` is provided → dispatch to exactly that set.
      - Else if ``top_k`` is provided → take Cortex's top-K candidate
        modules from its intent classifier and run them all.
      - Else → fall back to single-agent routing (same path as
        /api/messages, but returned in the multi-run envelope).

      Each run executes in parallel via asyncio.gather. Aegis is
      consulted per-agent — denied agents return as a non-fatal
      ``{"success": false, "error": "denied"}`` row.

  GET /api/cortex/candidates?message=...
      Returns the top-5 scored intents Cortex would consider for the
      message, so the launcher UI can pre-tick "good guess" agents.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from nexus.kernel.aegis import PermissionDenied


router = APIRouter(prefix="/api/cortex", tags=["cortex"])


def _get_kernel(request: Request):
    return request.app.state.kernel


class LaunchBody(BaseModel):
    message: str = Field(..., min_length=1)
    workspace_id: str | None = None
    agents: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)


async def _run_one(cortex, module_name: str, message: str) -> dict[str, Any]:
    """Run a single agent. Mirrors the safety steps in cortex.process()
    so multi-launch follows the same Aegis discipline as single routing."""
    module = cortex._modules.get(module_name)
    if module is None:
        return {
            "module": module_name,
            "success": False,
            "error": f"module {module_name!r} not registered",
            "response": "",
            "elapsed_ms": 0,
        }
    # Aegis: handle capability
    try:
        cortex._aegis.check(module_name, "handle")
    except PermissionDenied:
        cortex._chronicle.log("cortex", "permission_denied", {
            "module": module_name, "via": "multi_launch",
            "message_preview": message[:100],
        })
        return {
            "module": module_name,
            "success": False,
            "error": "permission_denied",
            "response": "",
            "elapsed_ms": 0,
        }
    # Aegis: network if module requires it
    if getattr(module, "requires_network", False) and not cortex._aegis.is_network_allowed(module_name):
        return {
            "module": module_name,
            "success": False,
            "error": "network_required_but_not_allowed",
            "response": "",
            "elapsed_ms": 0,
        }

    context = cortex._build_context()
    start = time.perf_counter()
    try:
        response = await module.handle(message, context)
        elapsed = int((time.perf_counter() - start) * 1000)
        cortex._chronicle.log("cortex", "multi_run", {
            "module": module_name,
            "elapsed_ms": elapsed,
            "response_preview": (response or "")[:160],
        })
        return {
            "module": module_name,
            "success": True,
            "error": None,
            "response": response or "",
            "elapsed_ms": elapsed,
        }
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        cortex._chronicle.log("cortex", "multi_run_error", {
            "module": module_name, "error": str(exc),
        })
        cortex._aegis.record_outcome(module_name, False)
        return {
            "module": module_name,
            "success": False,
            "error": str(exc),
            "response": "",
            "elapsed_ms": elapsed,
        }


def _resolve_targets(cortex, body: LaunchBody) -> list[str]:
    """Pick which agents to fan to. Honors explicit lists first, then
    classifier top-K, then single-agent fallback."""
    if body.agents:
        # Dedupe + filter to actually-registered modules. Garbage slugs
        # come back as denied/missing rows from _run_one so the user can
        # see why.
        seen: list[str] = []
        for slug in body.agents:
            slug = (slug or "").strip().lower()
            if slug and slug not in seen:
                seen.append(slug)
        return seen
    if body.top_k:
        _, scored = cortex._select_module(body.message)
        out: list[str] = []
        for s in scored:
            if s.module and s.module not in out:
                out.append(s.module)
            if len(out) >= body.top_k:
                break
        return out
    # Fallback: single agent (same path as /api/messages, just multiplexed).
    target, _ = cortex._select_module(body.message)
    return [target] if target else []


@router.post("/launch")
async def launch(body: LaunchBody, request: Request) -> dict:
    kernel = _get_kernel(request)
    cortex = kernel.cortex

    targets = _resolve_targets(cortex, body)
    if not targets:
        raise HTTPException(status_code=400, detail="no agents matched and none provided")

    kernel.chronicle.log("cortex", "multi_launch_start", {
        "agents": targets,
        "workspace_id": body.workspace_id,
        "message_preview": body.message[:140],
        "mode": "explicit" if body.agents else ("top_k" if body.top_k else "single"),
    })

    runs = await asyncio.gather(*(_run_one(cortex, slug, body.message) for slug in targets))

    succeeded = sum(1 for r in runs if r["success"])

    kernel.chronicle.log("cortex", "multi_launch_done", {
        "agents": targets,
        "succeeded": succeeded,
        "failed": len(runs) - succeeded,
    })

    return {
        "targets": targets,
        "runs": runs,
        "succeeded": succeeded,
        "failed": len(runs) - succeeded,
    }


@router.get("/candidates")
async def candidates(
    request: Request,
    message: str = Query(..., min_length=1),
) -> dict:
    """Top-5 candidate agents Cortex would weigh for this prompt.

    Used by the launcher UI to pre-suggest "smart picks" before the user
    decides whether to fan out to multiple agents.
    """
    kernel = _get_kernel(request)
    cortex = kernel.cortex
    target, scored = cortex._select_module(message)
    top = []
    seen: set[str] = set()
    for s in scored:
        if not s.module or s.module in seen:
            continue
        seen.add(s.module)
        top.append({
            "module": s.module,
            "intent": s.name,
            "score": round(float(s.score), 3),
        })
        if len(top) >= 5:
            break
    # Always include the registered module list so the picker has every
    # available option even if classification scored zero for them.
    all_modules = list(cortex._modules.keys())
    return {
        "primary": target,
        "top": top,
        "all_modules": all_modules,
    }

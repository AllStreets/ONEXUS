from __future__ import annotations

import os
import sqlite3

from fastapi import APIRouter, Request

from nexus import __version__
from nexus.api.models import (
    HealthCheckResponse,
    SystemConfigResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/api/system", tags=["system"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(request: Request) -> SystemStatusResponse:
    """System status overview."""
    kernel = _get_kernel(request)
    cfg = kernel.config
    return SystemStatusResponse(
        version=__version__,
        data_dir=str(cfg.data_dir),
        db_exists=os.path.exists(str(cfg.db_path)),
        model=cfg.model_name,
        llm_port=cfg.llm_port,
        modules_loaded=len(kernel.cortex.list_modules()) + 5 + (  # +5 kernel components
            len(getattr(request.app.state, 'agent_catalog', None).list_agents(runnable_only=True))
            if getattr(request.app.state, 'agent_catalog', None) else 0
        ),
        default_provider=cfg.default_provider,
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(request: Request) -> HealthCheckResponse:
    """Health check: DB accessibility and LLM connectivity."""
    kernel = _get_kernel(request)

    # Check DB
    db_ok = False
    try:
        conn = sqlite3.connect(str(kernel.config.db_path), timeout=2.0)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    # Check LLM availability — any registered provider healthy = LLM available
    llm_ok: bool | None = None
    try:
        router = kernel.provider_router
        if router is not None:
            health_map = await router.health()
            llm_ok = any(health_map.values()) if health_map else False
        else:
            llm_ok = False
    except Exception:
        llm_ok = False

    overall = "healthy" if db_ok else "degraded"
    return HealthCheckResponse(status=overall, db_accessible=db_ok, llm_available=llm_ok)


@router.get("/db")
async def database_info(request: Request):
    """Database statistics and table info."""
    kernel = _get_kernel(request)
    db_path = str(kernel.config.db_path)
    info = {"path": db_path, "tables": {}, "size_bytes": 0}

    try:
        info["size_bytes"] = os.path.getsize(db_path)
    except OSError:
        pass

    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for t in tables:
            name = t["name"]
            try:
                count = conn.execute(f"SELECT COUNT(*) as c FROM [{name}]").fetchone()["c"]
                info["tables"][name] = count
            except Exception:
                info["tables"][name] = -1
        conn.close()
    except Exception as e:
        info["error"] = str(e)

    return info


@router.get("/config", response_model=SystemConfigResponse)
async def system_config(request: Request) -> SystemConfigResponse:
    """Return current configuration (sanitized, no secrets)."""
    kernel = _get_kernel(request)
    cfg = kernel.config
    return SystemConfigResponse(
        data_dir=str(cfg.data_dir),
        model_name=cfg.model_name,
        llm_port=cfg.llm_port,
        log_level=cfg.log_level,
        default_provider=cfg.default_provider,
        openai_configured=bool(cfg.openai_api_key),
        anthropic_configured=bool(cfg.anthropic_api_key),
        telegram_configured=bool(cfg.telegram_token),
        discord_configured=bool(cfg.discord_token),
    )

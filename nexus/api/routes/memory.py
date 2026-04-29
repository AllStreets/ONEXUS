from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request

from nexus.api.models import (
    MemoryEpisodicResponse,
    MemoryEraseResponse,
    MemorySemanticResponse,
    MemoryWorkingResponse,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("/working", response_model=MemoryWorkingResponse)
async def get_working_memory(request: Request) -> MemoryWorkingResponse:
    """Query working memory (current session key-value store)."""
    kernel = _get_kernel(request)
    return MemoryWorkingResponse(entries=dict(kernel.engram.working._store))


@router.get("/episodic", response_model=MemoryEpisodicResponse)
async def search_episodic_memory(
    request: Request,
    query: str | None = Query(default=None, description="FTS search query"),
    limit: int = Query(default=10, ge=1, le=500),
) -> MemoryEpisodicResponse:
    """Search episodic memory. If no query, returns recent entries."""
    kernel = _get_kernel(request)
    try:
        if query:
            results = kernel.engram.episodic.recall(query, limit=limit)
        else:
            results = kernel.engram.episodic.recall_recent(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Memory query failed: {exc}")
    return MemoryEpisodicResponse(results=results, count=len(results))


@router.get("/semantic", response_model=MemorySemanticResponse)
async def search_semantic_memory(
    request: Request,
    query: str = Query(..., min_length=1, description="Semantic search query"),
    category: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=100),
) -> MemorySemanticResponse:
    """Search semantic memory by vector similarity."""
    kernel = _get_kernel(request)
    try:
        results = kernel.engram.semantic.search(query, category=category, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {exc}")
    return MemorySemanticResponse(results=results, count=len(results))


@router.delete("", response_model=MemoryEraseResponse)
async def erase_memory(request: Request) -> MemoryEraseResponse:
    """Erase all memory (GDPR Article 17 -- right to erasure)."""
    kernel = _get_kernel(request)
    db_path = str(kernel.config.db_path)
    try:
        # Clear working memory
        kernel.engram.working.clear()

        # Remove the database file
        if os.path.exists(db_path):
            os.remove(db_path)

        # Re-initialize databases
        kernel.engram.init_db()
        kernel.chronicle.init_db()
        kernel.aegis.init_db()

        return MemoryEraseResponse(success=True, message="All memory erased.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erase failed: {exc}")

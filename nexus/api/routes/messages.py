from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from nexus.api.models import MessageRequest, MessageResponse, FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.post("", response_model=MessageResponse)
async def send_message(body: MessageRequest, request: Request) -> MessageResponse:
    """Send a message through Cortex and return the response.

    The message + the agent's reply are also persisted to the workspace's
    Engram episodic memory (if a workspace_id is provided), and the routing
    decision is logged to Chronicle scoped to that workspace. This is what
    keeps the conversation surface honest — every exchange leaves a trace
    in the kernel state, not just in browser memory.
    """
    kernel = _get_kernel(request)

    # 1. Route + process — exercises the full Cortex pipeline (pattern,
    #    semantic, structure, context, optional LLM fallback).
    try:
        response = await kernel.cortex.process(body.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {exc}")

    module_name, _ = kernel.cortex._select_module(body.message)

    # 2. Persist the exchange in Engram (workspace-scoped when possible).
    memory_id = None
    engram = kernel.engram
    if body.workspace_id:
        mgr = getattr(request.app.state, "workspace_manager", None)
        if mgr is not None:
            try:
                cfg = mgr.get(body.workspace_id)
            except Exception:
                cfg = None
            if cfg is not None and getattr(cfg, "roots", None):
                from pathlib import Path
                try:
                    engram = kernel.engram.partition(Path(cfg.roots[0]))
                except Exception:
                    pass
    try:
        memory_id = engram.episodic.store(
            f"USER: {body.message}\nAGENT[{module_name or 'unknown'}]: {response}",
            source=f"messages:{module_name or 'unknown'}",
        )
    except Exception:
        pass

    # 3. Log to chronicle with workspace scope so the cockpit's permission /
    #    activity feeds can filter by workspace.
    try:
        kernel.chronicle.log("messages", "exchange", {
            "workspace_id": body.workspace_id,
            "module": module_name,
            "message_preview": body.message[:140],
            "response_length": len(response),
            "memory_id": memory_id,
        })
    except Exception:
        pass

    # 4. Nudge mood signals — sending a message implies the user is engaging,
    #    which raises engram_busy_ratio and pulse activity.
    try:
        signals = getattr(request.app.state, "mood_signals", None)
        if signals is not None:
            # Increment engram_busy_ratio modestly, capped at 1.0.
            signals.engram_busy_ratio = min(1.0, (signals.engram_busy_ratio or 0.0) + 0.04)
            request.app.state.mood_signals = signals
    except Exception:
        pass

    return MessageResponse(
        response=response,
        module=module_name or None,
        workspace_id=body.workspace_id,
        memory_id=memory_id,
    )


@router.post("/stream")
async def stream_message(body: MessageRequest, request: Request) -> StreamingResponse:
    """Send a message and stream the response via Server-Sent Events."""
    kernel = _get_kernel(request)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            response = await kernel.cortex.process(body.message)
            module, _ = kernel.cortex._select_module(body.message)

            # Stream the response in chunks for SSE
            chunk_size = 80
            for i in range(0, len(response), chunk_size):
                chunk = response[i : i + chunk_size]
                data = json.dumps({"type": "chunk", "content": chunk, "module": module})
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.01)

            done_data = json.dumps({"type": "done", "module": module})
            yield f"data: {done_data}\n\n"
        except Exception as exc:
            error_data = json.dumps({"type": "error", "detail": str(exc)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(body: FeedbackRequest, request: Request) -> FeedbackResponse:
    """Submit trust feedback for a module response. Accepted = +0.12, rejected = -0.22."""
    kernel = _get_kernel(request)
    new_trust = kernel.aegis.record_outcome(body.module, body.accepted)
    delta = 0.12 if body.accepted else -0.22
    kernel.chronicle.log("cortex", "user_feedback", {
        "module": body.module,
        "accepted": body.accepted,
        "new_trust": new_trust,
        "delta": delta,
    })
    return FeedbackResponse(
        module=body.module,
        accepted=body.accepted,
        new_trust=new_trust,
        delta=delta,
    )

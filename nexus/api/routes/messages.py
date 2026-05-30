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
    """Send a message through Cortex and return the response."""
    kernel = _get_kernel(request)
    try:
        response = await kernel.cortex.process(body.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {exc}")

    # Determine which module handled it
    module_name, _ = kernel.cortex._select_module(body.message)
    return MessageResponse(response=response, module=module_name or None)


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

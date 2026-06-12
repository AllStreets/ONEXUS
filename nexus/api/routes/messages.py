from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from nexus.api.models import MessageRequest, MessageResponse, FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api/messages", tags=["messages"])

_STREAM_CHUNK = 80  # chars per SSE frame in the chunked fallback


def _get_kernel(request: Request):
    return request.app.state.kernel


# ── shared exchange pipeline ─────────────────────────────────────────────────
# Both the sync endpoint and the streaming endpoint MUST leave the same trace
# in the kernel: the exchange in Engram (workspace-partitioned when possible),
# a chronicle entry scoped to the workspace, and the mood nudge. Keep this in
# one place so the two endpoints can never drift apart.

def _workspace_engram(kernel, request: Request, workspace_id: str | None):
    """Return the Engram to persist into — partitioned to the workspace's
    first root when one is declared, the kernel-global Engram otherwise."""
    engram = kernel.engram
    if workspace_id:
        mgr = getattr(request.app.state, "workspace_manager", None)
        if mgr is not None:
            try:
                cfg = mgr.get(workspace_id)
            except Exception:
                cfg = None
            if cfg is not None and getattr(cfg, "roots", None):
                from pathlib import Path
                try:
                    engram = kernel.engram.partition(Path(cfg.roots[0]))
                except Exception:
                    pass
    return engram


def _persist_exchange(
    kernel, request: Request, body: MessageRequest,
    module_name: str | None, response: str,
) -> str | None:
    """Persist one user/agent exchange + log + nudge mood. Returns memory_id."""
    # 1. Engram (workspace-scoped when possible).
    memory_id = None
    engram = _workspace_engram(kernel, request, body.workspace_id)
    try:
        memory_id = engram.episodic.store(
            f"USER: {body.message}\nAGENT[{module_name or 'unknown'}]: {response}",
            source=f"messages:{module_name or 'unknown'}",
        )
    except Exception:
        pass

    # 2. Chronicle with workspace scope so the cockpit's permission /
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

    # 3. Mood signals — sending a message implies the user is engaging,
    #    which raises engram_busy_ratio and pulse activity.
    try:
        signals = getattr(request.app.state, "mood_signals", None)
        if signals is not None:
            signals.engram_busy_ratio = min(1.0, (signals.engram_busy_ratio or 0.0) + 0.04)
            request.app.state.mood_signals = signals
    except Exception:
        pass

    return memory_id


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

    # 2-4. Shared exchange pipeline (Engram + Chronicle + mood).
    memory_id = _persist_exchange(kernel, request, body, module_name, response)

    return MessageResponse(
        response=response,
        module=module_name or None,
        workspace_id=body.workspace_id,
        memory_id=memory_id,
    )


def _stream_persona(kernel, request: Request, module_name: str | None) -> str:
    """System prompt for the provider-streamed reply: the routed module's
    curated persona (same map the Cortex launcher uses)."""
    from nexus.api.routes.cortex import _AGENT_PERSONAS
    slug = module_name or "oracle"
    return _AGENT_PERSONAS.get(
        slug,
        f"You are {slug}, an agent in the ONEXUS operating system. "
        f"Respond helpfully and concisely to the user's request.",
    )


@router.post("/stream")
async def stream_message(body: MessageRequest, request: Request) -> StreamingResponse:
    """Send a message and stream the response via Server-Sent Events.

    Two delivery modes, one persistence pipeline:

    - When a healthy streaming-capable provider is registered, tokens are
      streamed straight from the provider as they are generated (the reply
      is the LLM answering as the Cortex-routed module).
    - Otherwise (no provider, provider unhealthy, or stream failure before
      the first token) we fall back to the full Cortex pipeline and chunk
      the complete module response into SSE frames — same content as
      ``POST /api/messages``.

    Either way the exchange lands in Engram + Chronicle + mood through the
    same `_persist_exchange` helper the sync endpoint uses, and the terminal
    frame carries the module + memory_id.
    """
    kernel = _get_kernel(request)

    async def event_stream() -> AsyncGenerator[str, None]:
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        try:
            module, _ = kernel.cortex._select_module(body.message)

            parts: list[str] = []
            streamed = False
            router_ = getattr(kernel, "provider_router", None)
            if router_ is not None and hasattr(router_, "infer_stream"):
                try:
                    persona = _stream_persona(kernel, request, module)
                    messages = [
                        {"role": "system", "content": persona},
                        {"role": "user", "content": body.message},
                    ]
                    agen = router_.infer_stream(messages=messages, max_tokens=1024, temperature=0.7)
                    async for token in agen:
                        if not token:
                            continue
                        parts.append(token)
                        yield sse({"type": "chunk", "content": token, "module": module})
                    streamed = bool(parts)
                except Exception:
                    # Provider unavailable / stream failed mid-flight. If we
                    # already sent tokens, keep them; otherwise fall back to
                    # the chunked pipeline below.
                    streamed = bool(parts)

            if streamed:
                response = "".join(parts)
            else:
                # Chunked fallback — the full canonical Cortex pipeline
                # (module handlers, Aegis gates, cortex-side chronicle +
                # engram effects), identical to POST /api/messages.
                response = await kernel.cortex.process(body.message)
                module, _ = kernel.cortex._select_module(body.message)
                for i in range(0, len(response), _STREAM_CHUNK):
                    chunk = response[i : i + _STREAM_CHUNK]
                    yield sse({"type": "chunk", "content": chunk, "module": module})
                    await asyncio.sleep(0.01)

            memory_id = _persist_exchange(kernel, request, body, module, response)
            yield sse({"type": "done", "module": module, "memory_id": memory_id,
                       "streamed": streamed})
        except Exception as exc:
            yield sse({"type": "error", "detail": str(exc)})

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

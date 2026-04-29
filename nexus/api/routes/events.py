from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from nexus.api.models import PublishEventRequest, PublishEventResponse, TopicListResponse
from nexus.kernel.pulse import Message, Priority

router = APIRouter(prefix="/api/events", tags=["events"])


def _get_kernel(request: Request):
    return request.app.state.kernel


class ConnectionManager:
    """Manages active WebSocket connections for Pulse event broadcasting."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Shared connection manager instance
_manager = ConnectionManager()

# Track topics that have had messages published
_seen_topics: set[str] = set()


@router.websocket("/ws")
async def websocket_events(ws: WebSocket) -> None:
    """WebSocket endpoint that broadcasts all Pulse events to connected clients."""
    kernel = ws.app.state.kernel
    await _manager.connect(ws)

    # Subscribe to all Pulse topics so we can forward events
    async def _relay(msg: Message) -> None:
        _seen_topics.add(msg.topic)
        await _manager.broadcast({
            "topic": msg.topic,
            "source": msg.source,
            "payload": msg.payload,
            "msg_id": msg.msg_id,
            "priority": int(msg.priority),
        })

    sub_id = kernel.pulse.subscribe("*", _relay)

    try:
        # Keep the connection alive; process incoming pings/messages
        while True:
            try:
                data = await ws.receive_text()
                # Clients can send ping/keepalive; we just ignore it
            except WebSocketDisconnect:
                break
    finally:
        kernel.pulse.unsubscribe(sub_id)
        _manager.disconnect(ws)


@router.get("/topics", response_model=TopicListResponse)
async def list_topics(request: Request) -> TopicListResponse:
    """List topics that have had events published during this session."""
    return TopicListResponse(topics=sorted(_seen_topics))


@router.post("/publish", response_model=PublishEventResponse)
async def publish_event(body: PublishEventRequest, request: Request) -> PublishEventResponse:
    """Publish an event to Pulse."""
    kernel = _get_kernel(request)
    msg = Message(
        topic=body.topic,
        source=body.source,
        payload=body.payload,
    )
    _seen_topics.add(body.topic)
    await kernel.pulse.publish(msg)
    return PublishEventResponse(success=True, topic=body.topic)

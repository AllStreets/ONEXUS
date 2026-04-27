"""
Pulse — the Nexus message bus.
Async in-process pub/sub with priority queuing and wildcard topics.
"""
import asyncio
import fnmatch
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Awaitable


class Priority(IntEnum):
    EMERGENCY = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class Message:
    topic: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


_Handler = Callable[[Message], Awaitable[None]]


class Pulse:
    def __init__(self):
        self._subs: dict[str, tuple[str, _Handler]] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, int, Message]] = asyncio.PriorityQueue()
        self._seq = 0
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, pattern: str, handler: _Handler) -> str:
        sub_id = uuid.uuid4().hex[:8]
        self._subs[sub_id] = (pattern, handler)
        self._ensure_running()
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        self._subs.pop(sub_id, None)

    async def publish(self, msg: Message) -> None:
        self._seq += 1
        await self._queue.put((msg.priority, self._seq, msg))
        self._ensure_running()

    def _ensure_running(self):
        if not self._running:
            self._running = True
            self._task = asyncio.ensure_future(self._process())

    async def _process(self):
        while True:
            try:
                _, _, msg = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if self._queue.empty():
                    self._running = False
                    return
                continue
            for _, (pattern, handler) in list(self._subs.items()):
                if fnmatch.fnmatch(msg.topic, pattern):
                    try:
                        await handler(msg)
                    except Exception:
                        pass

    async def drain(self):
        while not self._queue.empty():
            await asyncio.sleep(0.01)

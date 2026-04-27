"""
Wraith — phantom agent spawner.
Spawns ephemeral async micro-agents with single missions, time limits,
and auto-termination. Results merge into Engram automatically.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
from nexus.modules.base import NexusModule


class PhantomStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class Phantom:
    id: str
    mission: str
    status: PhantomStatus
    timeout_seconds: float
    result: str = ""
    error: str = ""
    _task: asyncio.Task | None = field(default=None, repr=False)


class WraithModule(NexusModule):
    name = "wraith"
    description = "Phantom agent spawner — ephemeral micro-agents with death clocks"
    version = "0.1.0"

    def __init__(self):
        self._phantoms: dict[str, Phantom] = {}

    async def spawn(
        self,
        mission: str,
        task_fn: Callable[[str], Awaitable[str]],
        timeout_seconds: float = 30,
    ) -> Phantom:
        phantom_id = uuid.uuid4().hex[:8]
        phantom = Phantom(
            id=phantom_id,
            mission=mission,
            status=PhantomStatus.RUNNING,
            timeout_seconds=timeout_seconds,
        )
        self._phantoms[phantom_id] = phantom

        async def _run():
            try:
                result = await asyncio.wait_for(
                    task_fn(mission),
                    timeout=timeout_seconds,
                )
                phantom.result = result
                phantom.status = PhantomStatus.COMPLETED
            except asyncio.TimeoutError:
                phantom.status = PhantomStatus.TIMED_OUT
                phantom.error = f"Timed out after {timeout_seconds}s"
            except Exception as e:
                phantom.status = PhantomStatus.FAILED
                phantom.error = str(e)

        phantom._task = asyncio.ensure_future(_run())
        return phantom

    async def wait(self, phantom_id: str, timeout: float = 30) -> None:
        phantom = self._phantoms.get(phantom_id)
        if phantom and phantom._task:
            try:
                await asyncio.wait_for(asyncio.shield(phantom._task), timeout=timeout)
            except asyncio.TimeoutError:
                pass

    def get_phantom(self, phantom_id: str) -> Phantom | None:
        return self._phantoms.get(phantom_id)

    def list_phantoms(self) -> list[Phantom]:
        return list(self._phantoms.values())

    def cleanup_completed(self) -> int:
        completed = [pid for pid, p in self._phantoms.items() if p.status != PhantomStatus.RUNNING]
        for pid in completed:
            del self._phantoms[pid]
        return len(completed)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        active = [p for p in self._phantoms.values() if p.status == PhantomStatus.RUNNING]
        done = [p for p in self._phantoms.values() if p.status != PhantomStatus.RUNNING]
        lines = [
            f"[Wraith] Phantom agents: {len(self._phantoms)} total",
            f"  Active: {len(active)}",
            f"  Completed: {len(done)}",
        ]
        for p in active:
            lines.append(f"  - [{p.id}] {p.mission} (running, timeout: {p.timeout_seconds}s)")
        for p in done:
            lines.append(f"  - [{p.id}] {p.mission} ({p.status.value})")
        if not self._phantoms:
            lines.append("  No phantoms spawned.")
        return "\n".join(lines)

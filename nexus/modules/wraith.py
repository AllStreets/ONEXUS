"""
Wraith — phantom agent spawner.
Spawns ephemeral async micro-agents with single missions, time limits,
and auto-termination. Results merge into Engram automatically.
"""
import re
import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional
from nexus.modules.base import NexusModule


class PhantomStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class Phantom:
    id: str
    mission: str
    status: PhantomStatus
    timeout_seconds: float
    result: str = ""
    error: str = ""
    _task: asyncio.Task | None = field(default=None, repr=False)


# Trust-tiered death clocks (seconds). Wraith's own tier governs how long
# spawned phantoms may run before forced termination.
_TIER_TIMEOUTS = {
    "OBSERVER": 15.0,
    "ADVISOR": 30.0,
    "MONITOR": 120.0,
    "EXECUTOR": 600.0,
    "AUTONOMOUS": 1800.0,
}

_DURATION_RE = re.compile(
    r"\bfor\s+(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b",
    re.IGNORECASE,
)


def _parse_duration(text: str) -> tuple[Optional[float], str]:
    """Extract a 'for N <unit>' clause. Returns (seconds_or_None, cleaned_text)."""
    m = _DURATION_RE.search(text)
    if not m:
        return None, text
    n = float(m.group(1))
    unit = m.group(2).lower()[0]
    if unit == "s":
        secs = n
    elif unit == "m":
        secs = n * 60
    elif unit == "h":
        secs = n * 3600
    else:
        secs = n
    cleaned = (text[:m.start()] + text[m.end():]).strip()
    return secs, cleaned


class WraithModule(NexusModule):
    name = "wraith"
    description = "Phantom agent spawner — ephemeral micro-agents with death clocks"
    version = "0.1.0"

    def __init__(self):
        self._phantoms: dict[str, Phantom] = {}

    def _default_timeout(self, aegis: Any) -> float:
        if aegis is None:
            return _TIER_TIMEOUTS["ADVISOR"]
        try:
            tier = aegis.get_tier(self.name)
        except Exception:
            return _TIER_TIMEOUTS["ADVISOR"]
        return _TIER_TIMEOUTS.get(tier, _TIER_TIMEOUTS["ADVISOR"])

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
            except asyncio.CancelledError:
                phantom.status = PhantomStatus.CANCELLED
                phantom.error = "Cancelled"
                raise
            except Exception as e:
                phantom.status = PhantomStatus.FAILED
                phantom.error = str(e)

        phantom._task = asyncio.ensure_future(_run())
        return phantom

    async def wait(self, phantom_id: str, timeout: float = 30) -> None:
        phantom = self._phantoms.get(phantom_id)
        if not phantom or not phantom._task:
            return
        try:
            await asyncio.wait_for(asyncio.shield(phantom._task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        # Give the task a final tick to run its except/finally and update status
        if not phantom._task.done():
            try:
                await asyncio.wait_for(asyncio.shield(phantom._task), timeout=0.1)
            except (asyncio.TimeoutError, asyncio.CancelledError):
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

    def kill(self, phantom_id: str) -> bool:
        p = self._phantoms.get(phantom_id)
        if not p or not p._task or p._task.done():
            return False
        p._task.cancel()
        # Mark status synchronously so callers see CANCELLED immediately;
        # the _run except branch may not run if cancel races completion.
        p.status = PhantomStatus.CANCELLED
        if not p.error:
            p.error = "Cancelled"
        return True

    # -- command parsing ---------------------------------------------------

    def _parse_command(self, message: str) -> tuple[str, str]:
        """Returns (verb, remainder). Verb is one of: spawn, results, kill, list, status."""
        text = message.strip()
        low = text.lower()
        for prefix in ("wraith ", "phantom ", "phantoms "):
            if low.startswith(prefix):
                text = text[len(prefix):].strip()
                low = text.lower()
                break

        verbs = {
            "spawn": "spawn",
            "results": "results",
            "result": "results",
            "kill": "kill",
            "cancel": "kill",
            "list": "list",
            "status": "list",
        }
        for raw, verb in verbs.items():
            if low == raw:
                return verb, ""
            if low.startswith(raw + " "):
                return verb, text[len(raw) + 1:].strip()
        return "list", text

    def _status_summary(self) -> str:
        active = [p for p in self._phantoms.values() if p.status == PhantomStatus.RUNNING]
        done = [p for p in self._phantoms.values() if p.status != PhantomStatus.RUNNING]
        lines = [
            f"[Wraith] Phantom agents: {len(self._phantoms)} total",
            f"  Active: {len(active)}",
            f"  Completed: {len(done)}",
        ]
        for p in active:
            lines.append(f"  - [{p.id}] {p.mission} (running, timeout: {p.timeout_seconds:.0f}s)")
        for p in done:
            tail = f" — {p.error}" if p.error else ""
            lines.append(f"  - [{p.id}] {p.mission} ({p.status.value}){tail}")
        if not self._phantoms:
            lines.append("  No phantoms spawned.")
        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        verb, rest = self._parse_command(message)

        if verb == "list":
            return self._status_summary()

        if verb == "results":
            pid = rest.split()[0] if rest else ""
            p = self._phantoms.get(pid)
            if not p:
                return f"[Wraith] No phantom with id '{pid}'."
            if p.status == PhantomStatus.RUNNING:
                return (
                    f"[Wraith] Phantom {p.id} still running ({p.mission}).\n"
                    f"  Death clock: {p.timeout_seconds:.0f}s"
                )
            if p.status == PhantomStatus.COMPLETED:
                return (
                    f"[Wraith] Phantom {p.id} — completed.\n"
                    f"  Mission: {p.mission}\n"
                    f"  Result:\n{p.result}"
                )
            return (
                f"[Wraith] Phantom {p.id} — {p.status.value}.\n"
                f"  Mission: {p.mission}\n"
                f"  Error: {p.error}"
            )

        if verb == "kill":
            pid = rest.split()[0] if rest else ""
            if self.kill(pid):
                return f"[Wraith] Killed phantom {pid}."
            return f"[Wraith] No active phantom with id '{pid}'."

        if verb == "spawn":
            mission = rest.strip()
            if not mission:
                return "[Wraith] Usage: spawn <mission> [for <N> <s|m|h>]"

            override_secs, cleaned_mission = _parse_duration(mission)
            if cleaned_mission:
                mission = cleaned_mission

            aegis = context.get("aegis")
            timeout = override_secs if override_secs is not None else self._default_timeout(aegis)

            # Default executor: route mission back through cortex.
            # Overridable via direct call to spawn() — room for future
            # direct-agent dispatch without changing the command surface.
            cortex = context.get("cortex")
            if cortex is None:
                return "[Wraith] No cortex available for phantom dispatch."

            async def _route(m: str) -> str:
                return await cortex.process(m)

            phantom = await self.spawn(mission, _route, timeout_seconds=timeout)

            tier = "ADVISOR"
            if aegis is not None:
                try:
                    tier = aegis.get_tier(self.name)
                except Exception:
                    pass

            return (
                f"[Wraith] Phantom {phantom.id} spawned.\n"
                f"  Mission: {phantom.mission}\n"
                f"  Death clock: {timeout:.0f}s ({tier} tier)\n"
                f"  Check progress: phantom results {phantom.id}"
            )

        return self._status_summary()

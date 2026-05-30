# tests/modules/test_wraith.py
import asyncio
import pytest
from nexus.modules.wraith import WraithModule, Phantom, PhantomStatus


@pytest.fixture
def wraith():
    return WraithModule()


def test_wraith_attrs(wraith):
    assert wraith.name == "wraith"
    assert wraith.version == "0.1.0"


@pytest.mark.asyncio
async def test_spawn_phantom(wraith):
    async def research_task(mission: str) -> str:
        return f"Found info about: {mission}"

    phantom = await wraith.spawn(
        mission="Research Acme Corp before meeting",
        task_fn=research_task,
        timeout_seconds=5,
    )
    assert isinstance(phantom, Phantom)
    assert phantom.mission == "Research Acme Corp before meeting"
    assert phantom.status == PhantomStatus.RUNNING


@pytest.mark.asyncio
async def test_phantom_completes(wraith):
    async def quick_task(mission: str) -> str:
        return f"Done: {mission}"

    phantom = await wraith.spawn("quick job", quick_task, timeout_seconds=5)
    await wraith.wait(phantom.id, timeout=3)
    updated = wraith.get_phantom(phantom.id)
    assert updated.status == PhantomStatus.COMPLETED
    assert "Done" in updated.result


@pytest.mark.asyncio
async def test_phantom_timeout(wraith):
    async def slow_task(mission: str) -> str:
        await asyncio.sleep(10)
        return "never"

    phantom = await wraith.spawn("slow job", slow_task, timeout_seconds=0.1)
    await wraith.wait(phantom.id, timeout=1)
    updated = wraith.get_phantom(phantom.id)
    assert updated.status in (PhantomStatus.TIMED_OUT, PhantomStatus.FAILED)


@pytest.mark.asyncio
async def test_list_phantoms(wraith):
    async def task(m: str) -> str:
        return m

    await wraith.spawn("job1", task, timeout_seconds=5)
    await wraith.spawn("job2", task, timeout_seconds=5)
    phantoms = wraith.list_phantoms()
    assert len(phantoms) == 2


@pytest.mark.asyncio
async def test_phantom_auto_cleanup(wraith):
    async def task(m: str) -> str:
        return m

    phantom = await wraith.spawn("temp", task, timeout_seconds=5)
    await wraith.wait(phantom.id, timeout=2)
    wraith.cleanup_completed()
    assert len(wraith.list_phantoms()) == 0


@pytest.mark.asyncio
async def test_wraith_handle(wraith):
    result = await wraith.handle("status", {"llm": None})
    assert "wraith" in result.lower() or "phantom" in result.lower()


class _FakeAegis:
    def __init__(self, tier="ADVISOR"):
        self._tier = tier

    def get_tier(self, _name):
        return self._tier


class _FakeCortex:
    def __init__(self, response="routed"):
        self.calls = []
        self.response = response

    async def process(self, message):
        self.calls.append(message)
        return self.response


@pytest.mark.asyncio
async def test_handle_spawn_routes_through_cortex(wraith):
    cortex = _FakeCortex(response="cortex says hi")
    ctx = {"cortex": cortex, "aegis": _FakeAegis("MONITOR"), "llm": None}

    out = await wraith.handle("spawn research acme corp", ctx)
    assert "Phantom" in out and "spawned" in out
    assert "MONITOR" in out and "120" in out  # MONITOR -> 120s

    phantoms = wraith.list_phantoms()
    assert len(phantoms) == 1
    pid = phantoms[0].id

    await wraith.wait(pid, timeout=2)
    assert cortex.calls == ["research acme corp"]

    result = await wraith.handle(f"results {pid}", ctx)
    assert "completed" in result and "cortex says hi" in result


@pytest.mark.asyncio
async def test_handle_spawn_with_duration_override(wraith):
    cortex = _FakeCortex(response="ok")
    ctx = {"cortex": cortex, "aegis": _FakeAegis("ADVISOR"), "llm": None}

    out = await wraith.handle("spawn analyze logs for 5 minutes", ctx)
    assert "300" in out  # 5 min == 300s overrides ADVISOR default 30s

    phantom = wraith.list_phantoms()[0]
    assert phantom.mission == "analyze logs"
    assert phantom.timeout_seconds == 300


@pytest.mark.asyncio
async def test_handle_kill(wraith):
    async def slow(_m):
        await asyncio.sleep(10)
        return "x"

    phantom = await wraith.spawn("slow", slow, timeout_seconds=5)
    out = await wraith.handle(f"kill {phantom.id}", {"llm": None})
    assert "Killed" in out
    await wraith.wait(phantom.id, timeout=1)
    assert wraith.get_phantom(phantom.id).status == PhantomStatus.CANCELLED


@pytest.mark.asyncio
async def test_handle_results_unknown_id(wraith):
    out = await wraith.handle("results deadbeef", {"llm": None})
    assert "No phantom" in out

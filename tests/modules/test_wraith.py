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

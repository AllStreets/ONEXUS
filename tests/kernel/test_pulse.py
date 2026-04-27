import asyncio
import pytest
from nexus.kernel.pulse import Pulse, Message, Priority


@pytest.fixture
def pulse():
    return Pulse()


@pytest.mark.asyncio
async def test_publish_and_subscribe(pulse):
    received = []
    async def handler(msg: Message):
        received.append(msg)
    pulse.subscribe("test.topic", handler)
    await pulse.publish(Message(topic="test.topic", source="test_module", payload={"key": "value"}))
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].payload == {"key": "value"}


@pytest.mark.asyncio
async def test_priority_ordering(pulse):
    received = []
    async def handler(msg: Message):
        received.append(msg.payload["order"])
    pulse.subscribe("ordered", handler)
    await pulse.publish(Message(topic="ordered", source="test", payload={"order": 2}, priority=Priority.NORMAL))
    await pulse.publish(Message(topic="ordered", source="test", payload={"order": 1}, priority=Priority.EMERGENCY))
    await asyncio.sleep(0.05)
    assert received[0] == 1


@pytest.mark.asyncio
async def test_unsubscribe(pulse):
    received = []
    async def handler(msg: Message):
        received.append(msg)
    sub_id = pulse.subscribe("unsub.topic", handler)
    pulse.unsubscribe(sub_id)
    await pulse.publish(Message(topic="unsub.topic", source="test", payload={}))
    await asyncio.sleep(0.05)
    assert len(received) == 0


@pytest.mark.asyncio
async def test_wildcard_subscribe(pulse):
    received = []
    async def handler(msg: Message):
        received.append(msg.topic)
    pulse.subscribe("module.*", handler)
    await pulse.publish(Message(topic="module.oracle", source="test", payload={}))
    await pulse.publish(Message(topic="module.sentry", source="test", payload={}))
    await pulse.publish(Message(topic="other.topic", source="test", payload={}))
    await asyncio.sleep(0.05)
    assert received == ["module.oracle", "module.sentry"]

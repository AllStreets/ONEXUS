import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.messaging.manager import BridgeManager
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message


class FakeBridge(MessageBridge):
    name = "fake"

    def __init__(self):
        self._started = False
        self._stopped = False
        self._callback = None
        self._sent: list[tuple[str, str]] = []
        self._allowed_chat_ids = {"test-chat"}

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._stopped = True

    async def send(self, chat_id: str, text: str) -> None:
        self._sent.append((chat_id, text))

    async def on_message(self, callback) -> None:
        self._callback = callback


@pytest.fixture
def pulse():
    return Pulse()


@pytest.fixture
def mock_cortex():
    cortex = MagicMock()
    cortex.process = AsyncMock(return_value="nexus says hello")
    return cortex


@pytest.fixture
def manager(pulse, mock_cortex):
    return BridgeManager(pulse=pulse, cortex_process=mock_cortex.process)


def test_manager_register_bridge(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    assert "fake" in manager._bridges


@pytest.mark.asyncio
async def test_manager_start_starts_all_bridges(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()
    assert bridge._started is True


@pytest.mark.asyncio
async def test_manager_stop_stops_all_bridges(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()
    await manager.stop()
    assert bridge._stopped is True


@pytest.mark.asyncio
async def test_manager_routes_inbound_to_cortex(manager, mock_cortex):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    assert bridge._callback is not None
    response = await bridge._callback("chat123", "hello nexus", "fake")
    mock_cortex.process.assert_called_once_with("hello nexus")
    assert response == "nexus says hello"


@pytest.mark.asyncio
async def test_manager_subscribes_to_notify_events(manager, pulse):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.dream_loop",
        source="dream_loop",
        payload={"text": "I found a pattern!"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert bridge._sent[0][1] == "I found a pattern!"


@pytest.mark.asyncio
async def test_manager_notify_sends_to_all_bridges(manager, pulse):
    bridge1 = FakeBridge()
    bridge1.name = "fake1"
    bridge2 = FakeBridge()
    bridge2.name = "fake2"
    manager.register(bridge1)
    manager.register(bridge2)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.test",
        source="test",
        payload={"text": "broadcast"},
    ))
    await pulse.drain()

    assert len(bridge1._sent) == 1
    assert len(bridge2._sent) == 1


@pytest.mark.asyncio
async def test_manager_no_bridges_is_fine(manager):
    """Manager with no bridges should start and stop without errors."""
    await manager.start()
    await manager.stop()


@pytest.mark.asyncio
async def test_manager_notify_without_text_uses_topic(manager, pulse):
    """Notify events without a 'text' key should use the topic as fallback."""
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.alert",
        source="test",
        payload={"severity": "high"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert "notify.alert" in bridge._sent[0][1]

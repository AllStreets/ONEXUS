# tests/messaging/test_bridge.py
import pytest
from nexus.messaging.bridge import MessageBridge

def test_bridge_is_abstract():
    with pytest.raises(TypeError):
        MessageBridge()

def test_bridge_subclass_must_implement_start():
    with pytest.raises(TypeError):
        class Bad(MessageBridge):
            name = "bad"
            async def stop(self) -> None: pass
            async def send(self, chat_id: str, text: str) -> None: pass
            async def on_message(self, callback) -> None: pass
        Bad()

def test_bridge_subclass_must_implement_send():
    with pytest.raises(TypeError):
        class Bad(MessageBridge):
            name = "bad"
            async def start(self) -> None: pass
            async def stop(self) -> None: pass
            async def on_message(self, callback) -> None: pass
        Bad()

@pytest.mark.asyncio
async def test_valid_bridge_subclass():
    class StubBridge(MessageBridge):
        name = "stub"
        async def start(self) -> None: pass
        async def stop(self) -> None: pass
        async def send(self, chat_id: str, text: str) -> None: pass
        async def on_message(self, callback) -> None:
            self._callback = callback

    bridge = StubBridge()
    assert bridge.name == "stub"
    await bridge.start()
    await bridge.stop()
    await bridge.send("123", "hello")

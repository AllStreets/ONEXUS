# tests/test_batch7a_integration.py
"""
Batch 7a integration tests — multi-provider inference and messaging bridges.
Tests the full flow from config through router to LLMClient, and
BridgeManager inbound/outbound with Pulse.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.config import NexusConfig
from nexus.inference.llm import LLMClient
from nexus.inference.router import ProviderRouter
from nexus.inference.local import LocalProvider
from nexus.inference.provider import InferenceProvider
from nexus.messaging.manager import BridgeManager
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.modules.general import GeneralModule


# --- Multi-Provider Integration ---

@pytest.mark.asyncio
async def test_llm_client_with_multi_provider_router():
    """LLMClient with a router containing multiple providers routes correctly."""
    class StubProvider(InferenceProvider):
        name = "stub"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "stub says hi"
        async def health(self):
            return True

    router = ProviderRouter(default="stub")
    router.register(StubProvider())
    client = LLMClient(router=router)

    result = await client.chat(system="System.", user="Hello")
    assert result == "stub says hi"


@pytest.mark.asyncio
async def test_llm_client_backward_compat_with_local():
    """LLMClient created with just base_url still works."""
    client = LLMClient(base_url="http://localhost:8384")
    assert "local" in client._router.list_providers()


@pytest.mark.asyncio
async def test_router_provider_fallback():
    """When requested provider is unhealthy, falls back to default."""
    class HealthyProvider(InferenceProvider):
        name = "healthy"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "healthy response"
        async def health(self):
            return True

    class UnhealthyProvider(InferenceProvider):
        name = "sick"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "never seen"
        async def health(self):
            return False

    router = ProviderRouter(default="healthy")
    router.register(HealthyProvider())
    router.register(UnhealthyProvider())

    result = await router.infer([{"role": "user", "content": "hi"}], provider="sick")
    assert result == "healthy response"


# --- Messaging Integration ---

class InMemoryBridge(MessageBridge):
    name = "memory"

    def __init__(self):
        self._callback = None
        self._sent: list[tuple[str, str]] = []
        self._started = False
        self._allowed_chat_ids = {"test-chat"}

    async def start(self):
        self._started = True
    async def stop(self):
        self._started = False
    async def send(self, chat_id, text):
        self._sent.append((chat_id, text))
    async def on_message(self, callback):
        self._callback = callback


@pytest.mark.asyncio
async def test_bridge_manager_routes_inbound_through_cortex(tmp_config, mock_llm_response):
    """Inbound bridge message -> Cortex -> module -> response."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)
    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)
    cortex.set_llm(mock_llm_response("nexus response"))

    bridge = InMemoryBridge()
    manager = BridgeManager(pulse=pulse, cortex_process=cortex.process)
    manager.register(bridge)
    await manager.start()

    response = await bridge._callback("test-chat", "hello", "memory")
    assert "nexus response" in response
    await manager.stop()


@pytest.mark.asyncio
async def test_bridge_manager_forwards_notify_events():
    """Pulse notify.* events are forwarded to all bridges."""
    pulse = Pulse()
    cortex_process = AsyncMock(return_value="ok")

    bridge = InMemoryBridge()
    manager = BridgeManager(pulse=pulse, cortex_process=cortex_process)
    manager.register(bridge)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.dream_loop",
        source="dream_loop",
        payload={"text": "Found a pattern in your emails"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert "Found a pattern" in bridge._sent[0][1]
    await manager.stop()


@pytest.mark.asyncio
async def test_config_reads_provider_settings(tmp_path, monkeypatch):
    """NexusConfig reads all provider and messaging settings from env."""
    monkeypatch.setenv("NEXUS_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("NEXUS_OPENAI_KEY", "sk-test")
    monkeypatch.setenv("NEXUS_ANTHROPIC_KEY", "ant-test")
    monkeypatch.setenv("NEXUS_TELEGRAM_TOKEN", "tg-token")
    monkeypatch.setenv("NEXUS_TELEGRAM_CHAT_IDS", "111,222")
    monkeypatch.setenv("NEXUS_DISCORD_TOKEN", "dc-token")
    monkeypatch.setenv("NEXUS_DISCORD_CHANNEL_IDS", "aaa")

    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")

    assert cfg.default_provider == "openai"
    assert cfg.openai_api_key == "sk-test"
    assert cfg.anthropic_api_key == "ant-test"
    assert cfg.telegram_token == "tg-token"
    assert cfg.telegram_chat_ids == ["111", "222"]
    assert cfg.discord_token == "dc-token"
    assert cfg.discord_channel_ids == ["aaa"]

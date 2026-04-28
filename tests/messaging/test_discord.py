# tests/messaging/test_discord.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.messaging.discord_bridge import DiscordBridge
from nexus.messaging.bridge import MessageBridge

def test_discord_bridge_is_message_bridge():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    assert isinstance(bridge, MessageBridge)

def test_discord_bridge_name():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    assert bridge.name == "discord"

def test_discord_bridge_stores_config():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123", "456"])
    assert bridge._token == "fake-token"
    assert bridge._allowed_channel_ids == {"123", "456"}

@pytest.mark.asyncio
async def test_discord_bridge_on_message_registers_callback():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    assert bridge._callback is callback

@pytest.mark.asyncio
async def test_discord_bridge_ignores_unauthorized_channel():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    mock_message = MagicMock()
    mock_message.channel.id = 999
    mock_message.content = "hello"
    mock_message.author.bot = False
    await bridge._handle_message(mock_message)
    callback.assert_not_called()

@pytest.mark.asyncio
async def test_discord_bridge_ignores_bot_messages():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = "hello"
    mock_message.author.bot = True
    await bridge._handle_message(mock_message)
    callback.assert_not_called()

@pytest.mark.asyncio
async def test_discord_bridge_processes_authorized_channel():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="nexus response")
    await bridge.on_message(callback)
    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = "hello nexus"
    mock_message.author.bot = False
    mock_message.channel.send = AsyncMock()
    await bridge._handle_message(mock_message)
    callback.assert_called_once_with("123", "hello nexus", "discord")
    mock_message.channel.send.assert_called_once_with("nexus response")

@pytest.mark.asyncio
async def test_discord_bridge_send():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bridge._client = MagicMock()
    bridge._client.get_channel = MagicMock(return_value=mock_channel)
    await bridge.send("123", "outbound message")
    mock_channel.send.assert_called_once_with("outbound message")

@pytest.mark.asyncio
async def test_discord_bridge_ignores_empty_messages():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock()
    await bridge.on_message(callback)
    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = ""
    mock_message.author.bot = False
    await bridge._handle_message(mock_message)
    callback.assert_not_called()

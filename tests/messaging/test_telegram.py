# tests/messaging/test_telegram.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.messaging.telegram import TelegramBridge
from nexus.messaging.bridge import MessageBridge

def test_telegram_bridge_is_message_bridge():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    assert isinstance(bridge, MessageBridge)

def test_telegram_bridge_name():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    assert bridge.name == "telegram"

def test_telegram_bridge_stores_config():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123", "456"])
    assert bridge._token == "fake-token"
    assert bridge._allowed_chat_ids == {"123", "456"}

@pytest.mark.asyncio
async def test_telegram_bridge_on_message_registers_callback():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    assert bridge._callback is callback

@pytest.mark.asyncio
async def test_telegram_bridge_ignores_unauthorized_chat():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    mock_update = MagicMock()
    mock_update.message.chat_id = 999
    mock_update.message.text = "hello"
    mock_context = MagicMock()
    await bridge._handle_message(mock_update, mock_context)
    callback.assert_not_called()

@pytest.mark.asyncio
async def test_telegram_bridge_processes_authorized_chat():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="nexus response")
    await bridge.on_message(callback)
    mock_update = MagicMock()
    mock_update.message.chat_id = 123
    mock_update.message.text = "hello nexus"
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()
    await bridge._handle_message(mock_update, mock_context)
    callback.assert_called_once_with("123", "hello nexus", "telegram")
    mock_context.bot.send_message.assert_called_once_with(chat_id=123, text="nexus response")

@pytest.mark.asyncio
async def test_telegram_bridge_send():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    bridge._app = MagicMock()
    bridge._app.bot.send_message = AsyncMock()
    await bridge.send("123", "outbound message")
    bridge._app.bot.send_message.assert_called_once_with(chat_id=123, text="outbound message")

@pytest.mark.asyncio
async def test_telegram_bridge_ignores_empty_messages():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock()
    await bridge.on_message(callback)
    mock_update = MagicMock()
    mock_update.message.chat_id = 123
    mock_update.message.text = None
    mock_context = MagicMock()
    await bridge._handle_message(mock_update, mock_context)
    callback.assert_not_called()

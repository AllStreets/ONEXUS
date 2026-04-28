# nexus/messaging/telegram.py
"""
TelegramBridge — two-way Telegram messaging for NEXUS.
Uses python-telegram-bot. Only processes messages from allowed chat IDs.
"""
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from nexus.messaging.bridge import MessageBridge, MessageCallback


class TelegramBridge(MessageBridge):
    name = "telegram"

    def __init__(self, token: str, allowed_chat_ids: list[str]):
        self._token = token
        self._allowed_chat_ids = set(allowed_chat_ids)
        self._callback: MessageCallback | None = None
        self._app: Application | None = None

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, chat_id: str, text: str) -> None:
        if self._app:
            await self._app.bot.send_message(chat_id=int(chat_id), text=text)

    async def on_message(self, callback: MessageCallback) -> None:
        self._callback = callback

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        chat_id = str(update.message.chat_id)
        if chat_id not in self._allowed_chat_ids:
            return
        if self._callback:
            response = await self._callback(chat_id, update.message.text, "telegram")
            await context.bot.send_message(chat_id=update.message.chat_id, text=response)

# nexus/messaging/discord_bridge.py
"""
DiscordBridge — two-way Discord messaging for NEXUS.
Uses discord.py. Only processes messages from allowed channel IDs.
Ignores bot messages to prevent feedback loops.
"""
import asyncio
import discord
from nexus.messaging.bridge import MessageBridge, MessageCallback


class DiscordBridge(MessageBridge):
    name = "discord"

    def __init__(self, token: str, allowed_channel_ids: list[str]):
        self._token = token
        self._allowed_channel_ids = set(allowed_channel_ids)
        self._callback: MessageCallback | None = None
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

    async def start(self) -> None:
        asyncio.create_task(self._client.start(self._token))

    async def stop(self) -> None:
        await self._client.close()

    async def send(self, chat_id: str, text: str) -> None:
        channel = self._client.get_channel(int(chat_id))
        if channel:
            await channel.send(text)

    async def on_message(self, callback: MessageCallback) -> None:
        self._callback = callback

    async def _handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.content:
            return
        channel_id = str(message.channel.id)
        if channel_id not in self._allowed_channel_ids:
            return
        if self._callback:
            response = await self._callback(channel_id, message.content, "discord")
            await message.channel.send(response)

"""
BridgeManager — lifecycle manager for messaging bridges.
Routes inbound messages to Cortex, subscribes to Pulse notify.* events for outbound.
"""
from typing import Callable, Awaitable
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message


class BridgeManager:
    def __init__(
        self,
        pulse: Pulse,
        cortex_process: Callable[[str], Awaitable[str]],
    ):
        self._pulse = pulse
        self._cortex_process = cortex_process
        self._bridges: dict[str, MessageBridge] = {}
        self._pulse_sub_id: str | None = None

    def register(self, bridge: MessageBridge) -> None:
        self._bridges[bridge.name] = bridge

    async def start(self) -> None:
        """Start all bridges and subscribe to notify events."""
        for bridge in self._bridges.values():
            await bridge.on_message(self._handle_inbound)
            await bridge.start()

        self._pulse_sub_id = self._pulse.subscribe("notify.*", self._handle_notify)

    async def stop(self) -> None:
        """Stop all bridges and unsubscribe from Pulse."""
        if self._pulse_sub_id:
            self._pulse.unsubscribe(self._pulse_sub_id)

        for bridge in self._bridges.values():
            await bridge.stop()

    async def _handle_inbound(self, chat_id: str, text: str, source: str) -> str:
        """Route an inbound message from any bridge through Cortex."""
        return await self._cortex_process(text)

    async def _handle_notify(self, msg: Message) -> None:
        """Forward a Pulse notify event to all active bridges."""
        text = msg.payload.get("text", f"[{msg.topic}] {msg.payload}")
        for bridge in self._bridges.values():
            # Send to all known chat IDs for this bridge
            for chat_id in getattr(bridge, "_allowed_chat_ids", set()) | getattr(bridge, "_allowed_channel_ids", set()):
                await bridge.send(chat_id, text)

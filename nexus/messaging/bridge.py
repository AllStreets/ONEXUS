# nexus/messaging/bridge.py
"""
MessageBridge — abstract base class for messaging platform integrations.
Each bridge handles connection, sending, and receiving for one platform.
"""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

MessageCallback = Callable[[str, str, str], Awaitable[str]]

class MessageBridge(ABC):
    name: str

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send(self, chat_id: str, text: str) -> None:
        ...

    @abstractmethod
    async def on_message(self, callback: MessageCallback) -> None:
        ...

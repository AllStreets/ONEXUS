"""
InferenceProvider — abstract base class for all LLM inference backends.
Every provider normalizes to OpenAI-style messages format.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ProviderUnavailable(Exception):
    """Raised when no inference provider is reachable."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Provider '{provider}' is unavailable")


class InferenceProvider(ABC):
    name: str

    @abstractmethod
    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Send messages in OpenAI format and return the completion text."""
        ...

    async def infer_stream(
        self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Yield the completion text incrementally.

        Default implementation for providers without native streaming:
        run the blocking ``infer`` and yield the complete response once.
        Streaming-capable providers override this with real token streams.
        """
        yield await self.infer(messages, max_tokens=max_tokens, temperature=temperature)

    @abstractmethod
    async def health(self) -> bool:
        """Return True if this provider is reachable and ready."""
        ...

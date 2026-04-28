"""
InferenceProvider — abstract base class for all LLM inference backends.
Every provider normalizes to OpenAI-style messages format.
"""
from abc import ABC, abstractmethod


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

    @abstractmethod
    async def health(self) -> bool:
        """Return True if this provider is reachable and ready."""
        ...

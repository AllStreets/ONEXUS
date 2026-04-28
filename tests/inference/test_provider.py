import pytest
from nexus.inference.provider import InferenceProvider


def test_provider_is_abstract():
    """InferenceProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        InferenceProvider()


def test_provider_subclass_must_implement_infer():
    """Subclass without infer() raises TypeError."""
    with pytest.raises(TypeError):
        class BadProvider(InferenceProvider):
            name = "bad"
            async def health(self) -> bool:
                return True
        BadProvider()


def test_provider_subclass_must_implement_health():
    """Subclass without health() raises TypeError."""
    with pytest.raises(TypeError):
        class BadProvider(InferenceProvider):
            name = "bad"
            async def infer(self, messages, max_tokens=1024, temperature=0.7):
                return "ok"
        BadProvider()


@pytest.mark.asyncio
async def test_valid_provider_subclass():
    """A complete subclass can be instantiated and called."""
    class StubProvider(InferenceProvider):
        name = "stub"
        async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
            return "stub response"
        async def health(self) -> bool:
            return True

    provider = StubProvider()
    assert provider.name == "stub"
    result = await provider.infer([{"role": "user", "content": "hello"}])
    assert result == "stub response"
    assert await provider.health() is True

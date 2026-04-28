import pytest
from unittest.mock import AsyncMock
from nexus.inference.router import ProviderRouter
from nexus.inference.provider import InferenceProvider, ProviderUnavailable


class FakeProvider(InferenceProvider):
    name = "fake"

    def __init__(self, response: str = "fake response", healthy: bool = True):
        self._response = response
        self._healthy = healthy

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        return self._response

    async def health(self) -> bool:
        return self._healthy


def test_router_register_provider():
    router = ProviderRouter(default="fake")
    provider = FakeProvider()
    router.register(provider)
    assert "fake" in router.providers


def test_router_list_providers():
    router = ProviderRouter(default="fake")
    router.register(FakeProvider())
    assert router.list_providers() == ["fake"]


@pytest.mark.asyncio
async def test_router_infer_uses_default():
    router = ProviderRouter(default="fake")
    router.register(FakeProvider(response="default answer"))
    result = await router.infer([{"role": "user", "content": "hi"}])
    assert result == "default answer"


@pytest.mark.asyncio
async def test_router_infer_with_specific_provider():
    router = ProviderRouter(default="fake")
    router.register(FakeProvider(response="default"))

    other = FakeProvider(response="other answer")
    other.name = "other"
    router.register(other)

    result = await router.infer([{"role": "user", "content": "hi"}], provider="other")
    assert result == "other answer"


@pytest.mark.asyncio
async def test_router_fallback_to_default_on_unhealthy():
    router = ProviderRouter(default="healthy")

    healthy = FakeProvider(response="healthy answer", healthy=True)
    healthy.name = "healthy"
    router.register(healthy)

    unhealthy = FakeProvider(response="never seen", healthy=False)
    unhealthy.name = "broken"
    router.register(unhealthy)

    result = await router.infer([{"role": "user", "content": "hi"}], provider="broken")
    assert result == "healthy answer"


@pytest.mark.asyncio
async def test_router_raises_when_all_unhealthy():
    router = ProviderRouter(default="broken")

    broken = FakeProvider(response="never", healthy=False)
    broken.name = "broken"
    router.register(broken)

    with pytest.raises(ProviderUnavailable):
        await router.infer([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_router_raises_for_unknown_provider():
    router = ProviderRouter(default="fake")
    router.register(FakeProvider())

    with pytest.raises(ProviderUnavailable):
        await router.infer([{"role": "user", "content": "hi"}], provider="nonexistent")


@pytest.mark.asyncio
async def test_router_health_aggregates():
    router = ProviderRouter(default="a")

    a = FakeProvider(healthy=True)
    a.name = "a"
    router.register(a)

    b = FakeProvider(healthy=False)
    b.name = "b"
    router.register(b)

    health = await router.health()
    assert health == {"a": True, "b": False}


@pytest.mark.asyncio
async def test_router_passes_params():
    mock_provider = AsyncMock(spec=InferenceProvider)
    mock_provider.name = "mock"
    mock_provider.health = AsyncMock(return_value=True)
    mock_provider.infer = AsyncMock(return_value="ok")

    router = ProviderRouter(default="mock")
    router.register(mock_provider)

    await router.infer([{"role": "user", "content": "hi"}], max_tokens=256, temperature=0.3)
    mock_provider.infer.assert_called_once_with(
        [{"role": "user", "content": "hi"}],
        max_tokens=256,
        temperature=0.3,
    )

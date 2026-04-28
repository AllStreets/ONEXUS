import pytest
from nexus.modules.base import NexusModule


def test_module_has_required_attrs():
    """All modules must declare name, description, and version."""
    class TestMod(NexusModule):
        name = "test"
        description = "A test module"
        version = "0.1.0"

        async def handle(self, message: str, context: dict) -> str:
            return "ok"

    mod = TestMod()
    assert mod.name == "test"
    assert mod.description == "A test module"


def test_module_requires_network_defaults_false():
    class LocalMod(NexusModule):
        name = "local"
        description = "A local module"
        version = "0.1.0"

        async def handle(self, message: str, context: dict) -> str:
            return "ok"

    mod = LocalMod()
    assert mod.requires_network is False


def test_module_without_name_raises():
    with pytest.raises(TypeError):
        class BadMod(NexusModule):
            pass
        BadMod()


@pytest.mark.asyncio
async def test_module_handle():
    class EchoMod(NexusModule):
        name = "echo"
        description = "Echoes input"
        version = "0.1.0"

        async def handle(self, message: str, context: dict) -> str:
            return f"Echo: {message}"

    mod = EchoMod()
    result = await mod.handle("hello", {})
    assert result == "Echo: hello"


# ---------- GeneralModule tests ----------

from nexus.modules.general import GeneralModule


@pytest.fixture
def general():
    return GeneralModule()


@pytest.mark.asyncio
async def test_general_module_responds(general):
    result = await general.handle("hello", {"llm": None})
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_general_module_uses_llm(general, mock_llm_response):
    fake_llm = mock_llm_response("The answer is 42.")
    result = await general.handle("What is the meaning of life?", {"llm": fake_llm})
    assert "42" in result


@pytest.mark.asyncio
async def test_general_module_fallback_without_llm(general):
    result = await general.handle("test", {"llm": None})
    assert isinstance(result, str)

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

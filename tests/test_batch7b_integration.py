# tests/test_batch7b_integration.py
"""
Batch 7b integration tests — community ecosystem and differentiation modules.
Tests module routing through Cortex, Pulse event flows, and community installer.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.config import NexusConfig
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.modules.dream_loop import DreamLoopModule
from nexus.modules.adversarial import AdversarialModule
from nexus.modules.tripwire import TripwireModule
from nexus.modules.provenance import ProvenanceModule
from nexus.modules.sandbox import SandboxModule
from nexus.modules.symbiosis import SymbiosisModule
from nexus.modules.consciousness import ConsciousnessModule
from nexus.modules.emergence import EmergenceModule
from nexus.modules.ethical_prism import EthicalPrismModule
from nexus.community.validator import ModuleValidator
from nexus.community.installer import ModuleInstaller


@pytest.fixture
def full_kernel(tmp_config, mock_llm_response):
    """Create a kernel with all 9 new modules registered."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)

    modules = [
        DreamLoopModule(), AdversarialModule(), TripwireModule(),
        ProvenanceModule(), SandboxModule(), SymbiosisModule(),
        ConsciousnessModule(), EmergenceModule(), EthicalPrismModule(),
    ]
    for mod in modules:
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    cortex.set_llm(mock_llm_response("mock analysis result"))
    return cortex, engram, chronicle


@pytest.mark.asyncio
async def test_cortex_routes_to_dream_loop(full_kernel):
    cortex, engram, _ = full_kernel
    # Store memories with real content so FTS MATCH can find them
    engram.episodic.store("User asked about weather patterns", source="test")
    engram.episodic.store("User discussed project deadlines", source="test")
    response = await cortex.process("show me my dreams and insights")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_adversarial(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("red team the system and stress test")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_ethical_prism(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("analyze this ethically and morally")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_consciousness(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("how are you doing, show journal")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_cortex_routes_to_sandbox(full_kernel):
    cortex, _, _ = full_kernel
    response = await cortex.process("what if I simulate this hypothetical")
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_all_new_modules_have_required_attrs():
    modules = [
        DreamLoopModule(), AdversarialModule(), TripwireModule(),
        ProvenanceModule(), SandboxModule(), SymbiosisModule(),
        ConsciousnessModule(), EmergenceModule(), EthicalPrismModule(),
    ]
    for mod in modules:
        assert mod.name, f"{mod.__class__.__name__} missing name"
        assert mod.description, f"{mod.__class__.__name__} missing description"
        assert mod.version, f"{mod.__class__.__name__} missing version"


def test_community_validator_and_installer_work_together(tmp_path):
    """End-to-end: validate a module, install it, verify installation."""
    mod_dir = tmp_path / "community" / "modules" / "testuser" / "hello"
    mod_dir.mkdir(parents=True)

    (mod_dir / "manifest.json").write_text(json.dumps({
        "name": "hello",
        "author": "testuser",
        "description": "Says hello to the user.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["hello", "greet"],
        "license": "MIT",
    }))

    (mod_dir / "module.py").write_text('''
from nexus.modules.base import NexusModule
from typing import Any

class HelloModule(NexusModule):
    name = "hello"
    description = "Says hello to the user."
    version = "1.0.0"
    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "Hello!"
''')

    test_dir = mod_dir / "tests"
    test_dir.mkdir()
    (test_dir / "test_hello.py").write_text('''
def test_name():
    assert True
def test_desc():
    assert True
def test_ver():
    assert True
def test_handle():
    assert True
''')
    (mod_dir / "README.md").write_text("# Hello Module")

    # Validate
    validator = ModuleValidator()
    result = validator.validate(mod_dir)
    assert result.valid is True

    # Install
    install_dir = tmp_path / "installed"
    install_dir.mkdir()
    installer = ModuleInstaller(
        community_root=tmp_path / "community",
        install_dir=install_dir,
    )
    install_result = installer.install("testuser/hello")
    assert install_result.success is True
    assert install_result.keywords == ["hello", "greet"]
    assert (install_dir / "hello" / "module.py").exists()

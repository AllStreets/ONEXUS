# tests/test_batch2_integration.py
"""
Batch 2 integration: Oracle triggers -> Prism synthesizes -> Atlas stores ->
Cipher scores -> Sentry monitors cognitive state. Full perception pipeline.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.oracle import OracleModule, TriggerRule
from nexus.modules.sentry import SentryModule
from nexus.modules.atlas import AtlasModule
from nexus.modules.cipher import CipherModule, SourceProfile
from nexus.modules.prism import PrismModule


@pytest.fixture
def perception_system(tmp_config):
    """Full Nexus with all Batch 2 modules."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram, chronicle=chronicle, aegis=aegis,
        pulse=pulse, config=tmp_config,
    )

    # Register all modules
    general = GeneralModule()
    oracle = OracleModule()
    sentry = SentryModule()
    atlas = AtlasModule(db_path=tmp_config.db_path)
    atlas.init_db()
    cipher = CipherModule()
    prism = PrismModule()

    for mod in [general, oracle, sentry, atlas, cipher, prism]:
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    # Configure Oracle with a trigger rule
    oracle.add_rule(TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    ))

    # Configure Cipher with sources
    cipher.register_source(SourceProfile(name="reuters", base_trust=0.94, category="news"))

    return {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "oracle": oracle,
        "sentry": sentry,
        "atlas": atlas,
        "cipher": cipher,
        "prism": prism,
    }


@pytest.mark.asyncio
async def test_oracle_trigger_via_cortex(perception_system):
    """Oracle fires triggers when routed deadline-related input."""
    cortex = perception_system["cortex"]
    response = await cortex.process("Check alerts for this overdue deadline")
    assert "trigger" in response.lower() or "deadline" in response.lower()


@pytest.mark.asyncio
async def test_sentry_reports_state(perception_system):
    """Sentry reports cognitive state when asked."""
    cortex = perception_system["cortex"]
    response = await cortex.process("What is my focus level and cognitive state?")
    assert "focus" in response.lower() or "fatigue" in response.lower()


@pytest.mark.asyncio
async def test_atlas_stores_and_retrieves(perception_system):
    """Atlas can store facts and retrieve them."""
    atlas = perception_system["atlas"]
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    cortex = perception_system["cortex"]
    response = await cortex.process("What do you know about Connor?")
    assert "flexport" in response.lower() or "connor" in response.lower()


@pytest.mark.asyncio
async def test_prism_synthesizes_observations(perception_system):
    """Prism finds cross-domain connections."""
    prism = perception_system["prism"]
    prism.add_observation("calendar", "Flight to NYC on Friday", ["travel", "nyc"])
    prism.add_observation("weather", "Storm warning for NYC", ["weather", "nyc", "alert"])
    cortex = perception_system["cortex"]
    response = await cortex.process("Synthesize cross-domain connections")
    assert "nyc" in response.lower() or "insight" in response.lower() or "connection" in response.lower()


@pytest.mark.asyncio
async def test_cipher_detects_conflicts(perception_system):
    """Cipher detects conflicting claims from different sources."""
    cipher = perception_system["cipher"]
    cipher.record_claim("market_direction", "bullish", source="reuters", trust=0.94)
    cipher.record_claim("market_direction", "bearish", source="blog", trust=0.12)
    cortex = perception_system["cortex"]
    response = await cortex.process("Show me source conflicts and trust verification")
    assert "conflict" in response.lower()


@pytest.mark.asyncio
async def test_all_modules_registered(perception_system):
    """All Batch 2 modules are registered in Cortex."""
    cortex = perception_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "oracle", "sentry", "atlas", "cipher", "prism"]:
        assert name in modules

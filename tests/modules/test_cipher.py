# tests/modules/test_cipher.py
import pytest
from nexus.modules.cipher import CipherModule, SourceProfile
from nexus.kernel.pulse import Pulse, Message


@pytest.fixture
def cipher():
    c = CipherModule()
    c.register_source(SourceProfile(name="reuters", base_trust=0.94, category="news"))
    c.register_source(SourceProfile(name="linkedin", base_trust=0.61, category="social"))
    c.register_source(SourceProfile(name="anonymous_blog", base_trust=0.12, category="blog"))
    return c


def test_cipher_attrs(cipher):
    assert cipher.name == "cipher"
    assert cipher.version == "0.1.0"


def test_register_source(cipher):
    sources = cipher.list_sources()
    assert len(sources) == 3
    assert any(s.name == "reuters" for s in sources)


def test_score_information_known_source(cipher):
    result = cipher.score("Oil prices surge 5%", source="reuters")
    assert result["trust_score"] == 0.94
    assert result["source"] == "reuters"


def test_score_information_unknown_source(cipher):
    result = cipher.score("Some random claim", source="unknown_blog")
    assert result["trust_score"] < 0.2  # Default low trust


def test_detect_conflict(cipher):
    cipher.record_claim("oil_price_direction", "rising", source="reuters", trust=0.94)
    cipher.record_claim("oil_price_direction", "falling", source="anonymous_blog", trust=0.12)
    conflicts = cipher.get_conflicts()
    assert len(conflicts) >= 1
    assert conflicts[0]["claim_id"] == "oil_price_direction"


def test_no_conflict_same_value(cipher):
    cipher.record_claim("weather_today", "sunny", source="reuters", trust=0.94)
    cipher.record_claim("weather_today", "sunny", source="linkedin", trust=0.61)
    conflicts = cipher.get_conflicts()
    assert len(conflicts) == 0


def test_provenance_chain(cipher):
    cipher.record_claim("fact_1", "value_a", source="reuters", trust=0.94)
    chain = cipher.get_provenance("fact_1")
    assert len(chain) >= 1
    assert chain[0]["source"] == "reuters"
    assert chain[0]["trust"] == 0.94


@pytest.mark.asyncio
async def test_cipher_handle(cipher):
    cipher.record_claim("test_claim", "value", source="reuters", trust=0.94)
    result = await cipher.handle("What do you know about test_claim?", {"llm": None})
    assert "reuters" in result.lower() or "0.94" in result


@pytest.mark.asyncio
async def test_cipher_handle_with_conflict(cipher):
    cipher.record_claim("disputed", "yes", source="reuters", trust=0.94)
    cipher.record_claim("disputed", "no", source="anonymous_blog", trust=0.12)
    result = await cipher.handle("conflicts", {"llm": None})
    assert "conflict" in result.lower()


@pytest.mark.asyncio
async def test_cipher_on_load_subscribes():
    c = CipherModule()
    pulse = Pulse()
    await c.on_load({"pulse": pulse})
    assert c._sub_id is not None


@pytest.mark.asyncio
async def test_cipher_auto_registers_source():
    c = CipherModule()
    msg = Message(
        topic="cortex.response",
        source="cortex",
        payload={"module": "oracle", "message": "scan alerts", "response": "No threats detected"},
    )
    await c._on_response(msg)
    sources = c.list_sources()
    assert any(s.name == "oracle" for s in sources)


@pytest.mark.asyncio
async def test_cipher_auto_records_claim():
    c = CipherModule()
    msg = Message(
        topic="cortex.response",
        source="cortex",
        payload={"module": "oracle", "message": "scan", "response": "All clear"},
    )
    await c._on_response(msg)
    # Should have one claim
    assert len(c._claims) == 1


@pytest.mark.asyncio
async def test_cipher_ignores_own_responses():
    c = CipherModule()
    msg = Message(
        topic="cortex.response",
        source="cortex",
        payload={"module": "cipher", "message": "test", "response": "test"},
    )
    await c._on_response(msg)
    assert len(c._claims) == 0

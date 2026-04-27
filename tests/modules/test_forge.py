# tests/modules/test_forge.py
import pytest
from nexus.modules.forge import ForgeModule, NegotiationConfig, NegotiationState, Offer


@pytest.fixture
def forge():
    return ForgeModule()


def test_forge_attrs(forge):
    assert forge.name == "forge"
    assert forge.version == "0.1.0"


def test_create_negotiation(forge):
    config = NegotiationConfig(
        domain="freelance_rate",
        floor=100,
        ceiling=200,
        target=150,
        max_rounds=5,
        concession_limit=0.2,
    )
    neg_id = forge.create_negotiation(config)
    assert isinstance(neg_id, str)
    state = forge.get_state(neg_id)
    assert state.status == "active"


def test_make_offer(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    offer = forge.make_offer(neg_id)
    assert isinstance(offer, Offer)
    assert 100 <= offer.amount <= 200


def test_receive_counter(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    response = forge.receive_counter(neg_id, 120)
    assert response in ("accept", "counter", "escalate")


def test_accept_above_floor(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    # Counter at target or above should accept
    response = forge.receive_counter(neg_id, 160)
    assert response == "accept"


def test_escalate_below_floor(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    response = forge.receive_counter(neg_id, 50)
    assert response == "escalate"


def test_max_rounds_reached(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 2, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 110)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 110)
    state = forge.get_state(neg_id)
    assert state.status in ("escalated", "active")


def test_negotiation_history(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 130)
    history = forge.get_history(neg_id)
    assert len(history) >= 2


@pytest.mark.asyncio
async def test_forge_handle(forge):
    result = await forge.handle("Start negotiation for freelance rate $100-$200", {"llm": None})
    assert "negotiation" in result.lower() or "offer" in result.lower()


@pytest.mark.asyncio
async def test_forge_handle_status(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    forge.create_negotiation(config)
    result = await forge.handle("Show active negotiations", {"llm": None})
    assert "active" in result.lower() or "rate" in result.lower()

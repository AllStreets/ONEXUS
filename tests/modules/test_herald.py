# tests/modules/test_herald.py
import pytest
from nexus.modules.herald import HeraldModule, ExternalAgent, A2AMessage


@pytest.fixture
def herald():
    return HeraldModule()


def test_herald_attrs(herald):
    assert herald.name == "herald"
    assert herald.version == "0.1.0"


def test_register_agent(herald):
    agent = herald.register_agent(
        agent_id="agent-alice-001",
        name="Alice's Nexus",
        endpoint="https://alice.nexus.local:8400",
        trust_grant=50,
    )
    assert isinstance(agent, ExternalAgent)
    assert agent.name == "Alice's Nexus"


def test_list_agents(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.register_agent("a2", "Agent B", "http://b:8400", 30)
    agents = herald.list_agents()
    assert len(agents) == 2


def test_revoke_agent(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.revoke_agent("a1")
    assert len(herald.list_agents()) == 0


def test_send_message(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    msg = herald.compose_message(
        to_agent="a1",
        content="Schedule meeting for Thursday",
        msg_type="request",
    )
    assert isinstance(msg, A2AMessage)
    assert msg.to_agent == "a1"
    assert msg.content == "Schedule meeting for Thursday"


def test_send_to_unknown_agent_fails(herald):
    with pytest.raises(KeyError):
        herald.compose_message("unknown", "hello", "request")


def test_message_history(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.compose_message("a1", "msg1", "request")
    herald.compose_message("a1", "msg2", "response")
    history = herald.message_history("a1")
    assert len(history) == 2


def test_agent_reputation(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.record_interaction_outcome("a1", success=True)
    herald.record_interaction_outcome("a1", success=True)
    herald.record_interaction_outcome("a1", success=False)
    agent = herald.get_agent("a1")
    assert agent.reputation > 0.5


@pytest.mark.asyncio
async def test_herald_handle(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    result = await herald.handle("Show connected agents", {"llm": None})
    assert "agent a" in result.lower() or "a1" in result.lower()


@pytest.mark.asyncio
async def test_herald_handle_empty(herald):
    result = await herald.handle("agents", {"llm": None})
    assert "no external" in result.lower() or "no agent" in result.lower()


def test_herald_requires_network(herald):
    assert herald.requires_network is True


def test_herald_outbound_logged_to_chronicle(herald, tmp_config):
    from nexus.kernel.chronicle import Chronicle
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    context = {"chronicle": chronicle}
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.compose_message("a1", "hello", "request", context=context)
    events = chronicle.query(source="herald", action="outbound_data")
    assert len(events) == 1
    assert "Agent A" in events[0]["payload"]["summary"]

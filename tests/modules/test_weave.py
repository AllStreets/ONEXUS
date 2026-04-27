# tests/modules/test_weave.py
import pytest
from nexus.modules.weave import WeaveModule, Contact, RelationshipHealth


@pytest.fixture
def weave():
    return WeaveModule()


def test_weave_attrs(weave):
    assert weave.name == "weave"
    assert weave.version == "0.1.0"


def test_add_contact(weave):
    contact = weave.add_contact(
        name="Alice Chen",
        tags=["engineering", "frontend"],
    )
    assert isinstance(contact, Contact)
    assert contact.name == "Alice Chen"


def test_record_interaction(weave):
    c = weave.add_contact("Bob Smith", ["sales"])
    weave.record_interaction(c.id, "email", "Discussed Q3 targets")
    contact = weave.get_contact(c.id)
    assert contact.interaction_count == 1


def test_relationship_health_active(weave):
    c = weave.add_contact("Carol", ["team"])
    weave.record_interaction(c.id, "meeting", "Weekly sync")
    weave.record_interaction(c.id, "slack", "Quick question")
    weave.record_interaction(c.id, "email", "Project update")
    health = weave.get_health(c.id)
    assert health == RelationshipHealth.ACTIVE


def test_relationship_health_new(weave):
    c = weave.add_contact("Dan", ["vendor"])
    health = weave.get_health(c.id)
    assert health == RelationshipHealth.NEW


def test_find_connections(weave):
    c1 = weave.add_contact("Alice", ["engineering", "frontend"])
    c2 = weave.add_contact("Bob", ["engineering", "backend"])
    c3 = weave.add_contact("Carol", ["sales"])
    connections = weave.find_connections("engineering")
    assert len(connections) == 2


def test_reconnection_suggestions(weave):
    c = weave.add_contact("Old Friend", ["personal"])
    # No interactions = stale relationship
    suggestions = weave.reconnection_suggestions()
    assert len(suggestions) >= 1
    assert suggestions[0].name == "Old Friend"


def test_add_connection_between_contacts(weave):
    c1 = weave.add_contact("Alice", ["eng"])
    c2 = weave.add_contact("Bob", ["eng"])
    weave.add_link(c1.id, c2.id, "colleagues")
    links = weave.get_links(c1.id)
    assert len(links) == 1
    assert links[0]["contact_id"] == c2.id


@pytest.mark.asyncio
async def test_weave_handle(weave):
    weave.add_contact("Alice", ["team"])
    result = await weave.handle("Show my network", {"llm": None})
    assert "alice" in result.lower() or "contact" in result.lower()


@pytest.mark.asyncio
async def test_weave_handle_empty(weave):
    result = await weave.handle("network", {"llm": None})
    assert "no contacts" in result.lower() or "empty" in result.lower()

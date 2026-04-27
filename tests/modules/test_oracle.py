# tests/modules/test_oracle.py
import pytest
from nexus.modules.oracle import OracleModule, TriggerRule


@pytest.fixture
def oracle():
    return OracleModule()


def test_oracle_attrs(oracle):
    assert oracle.name == "oracle"
    assert oracle.version == "0.1.0"


def test_add_trigger_rule(oracle):
    rule = TriggerRule(
        name="meeting_overload",
        keywords=["meeting", "calendar", "schedule"],
        threshold=0.5,
        description="Fires when calendar density is high",
    )
    oracle.add_rule(rule)
    assert len(oracle.list_rules()) == 1
    assert oracle.list_rules()[0].name == "meeting_overload"


def test_evaluate_triggers_match(oracle):
    rule = TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    )
    oracle.add_rule(rule)
    fired = oracle.evaluate("The project deadline is tomorrow and two tasks are overdue")
    assert len(fired) == 1
    assert fired[0]["rule"] == "deadline_alert"
    assert fired[0]["score"] > 0.3


def test_evaluate_triggers_no_match(oracle):
    rule = TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    )
    oracle.add_rule(rule)
    fired = oracle.evaluate("The weather is nice today")
    assert len(fired) == 0


@pytest.mark.asyncio
async def test_oracle_handle(oracle):
    rule = TriggerRule(
        name="finance_alert",
        keywords=["budget", "expense", "cost", "revenue"],
        threshold=0.3,
        description="Fires on financial input",
    )
    oracle.add_rule(rule)
    result = await oracle.handle("The Q3 budget shows a 15% cost overrun", {"llm": None})
    assert "finance_alert" in result.lower() or "trigger" in result.lower()


@pytest.mark.asyncio
async def test_oracle_handle_no_triggers(oracle):
    result = await oracle.handle("hello", {"llm": None})
    assert "no triggers" in result.lower() or "no active" in result.lower()

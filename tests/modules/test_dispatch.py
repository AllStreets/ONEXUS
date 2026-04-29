# tests/modules/test_dispatch.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.dispatch import DispatchModule, Notification, RoutingRule


@pytest.fixture
def dispatch():
    return DispatchModule()


def test_dispatch_attrs(dispatch):
    assert dispatch.name == "dispatch"
    assert dispatch.version == "0.1.0"


def test_detect_priority_critical(dispatch):
    assert dispatch.detect_priority("CRITICAL: server is down") == "critical"
    assert dispatch.detect_priority("Production outage detected") == "critical"


def test_detect_priority_high(dispatch):
    assert dispatch.detect_priority("Urgent: deploy needed") == "high"
    assert dispatch.detect_priority("Alert: disk space warning") == "high"


def test_detect_priority_low(dispatch):
    assert dispatch.detect_priority("FYI: new docs published") == "low"


def test_detect_priority_normal(dispatch):
    assert dispatch.detect_priority("Please review the PR") == "normal"


def test_detect_channel(dispatch):
    assert dispatch.detect_channel("Send an email notification") == "email"
    assert dispatch.detect_channel("Post to slack channel") == "slack"
    assert dispatch.detect_channel("Send SMS alert") == "sms"
    assert dispatch.detect_channel("Fire a webhook") == "webhook"


def test_detect_channel_default(dispatch):
    assert dispatch.detect_channel("notify the team") == "slack"


def test_extract_recipients_emails(dispatch):
    text = "Send to alice@example.com and bob@company.org"
    recipients = dispatch.extract_recipients(text)
    assert "alice@example.com" in recipients
    assert "bob@company.org" in recipients


def test_extract_recipients_mentions(dispatch):
    text = "Notify @alice and @bob about this"
    recipients = dispatch.extract_recipients(text)
    assert "@alice" in recipients
    assert "@bob" in recipients


def test_route_matches_rules(dispatch):
    routes = dispatch.route("urgent alert: server down")
    assert len(routes) >= 1
    channels = [r["channel"] for r in routes]
    assert "slack" in channels  # alert rule


def test_route_no_match(dispatch):
    routes = dispatch.route("hello there")
    assert len(routes) == 0


def test_add_rule(dispatch):
    dispatch.add_rule("custom", "pizza", "sms", "high")
    rules = dispatch.list_rules()
    assert any(r.name == "custom" for r in rules)
    routes = dispatch.route("order pizza now")
    assert any(r["rule"] == "custom" for r in routes)


def test_create_notification(dispatch):
    n = dispatch.create_notification("Critical alert: server down", "email", "critical", "ops@co.com")
    assert n.channel == "email"
    assert n.priority == "critical"
    assert n.recipient == "ops@co.com"
    assert len(dispatch._sent) == 1


@pytest.mark.asyncio
async def test_handle_returns_routing(dispatch):
    context = {"llm": None, "engram": None}
    result = await dispatch.handle(
        "Send urgent email alert to alice@example.com about the outage",
        context,
    )
    assert "[Dispatch]" in result
    assert "Channel:" in result
    assert "Priority:" in result


@pytest.mark.asyncio
async def test_handle_with_llm(dispatch):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Subject: Server Outage\nBody: Immediate attention required."
    context = {"llm": mock_llm, "engram": None}
    result = await dispatch.handle("Send alert about server issues", context)
    assert "[Dispatch]" in result
    mock_llm.complete.assert_called_once()

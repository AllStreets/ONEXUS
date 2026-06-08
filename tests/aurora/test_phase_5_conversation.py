"""Tests for the Conversational surface route."""


def test_messages_endpoint_returns_response(client):
    """POST /api/messages should return a response from cortex (even if it routes to default fallback)."""
    r = client.post("/api/messages", json={"message": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert "response" in body


def test_aurora_app_js_contains_conversation_route(client):
    """The Aurora app.js must include the #/conversation/ route handler."""
    r = client.get("/aurora/static/app.js")
    assert r.status_code == 200
    assert "#/conversation/" in r.text
    assert "renderConversation" in r.text

"""T6 — WebSocket push stream endpoints accept connections and send JSON."""
import json
import pytest


class TestMoodWebSocket:
    def test_mood_ws_accepts_connection(self, client):
        """WS /api/mood/ws connects and sends at least one JSON message."""
        with client.websocket_connect("/api/mood/ws") as ws:
            data = ws.receive_json()
        assert "mood" in data

    def test_mood_ws_message_has_required_keys(self, client):
        with client.websocket_connect("/api/mood/ws") as ws:
            data = ws.receive_json()
        assert "mood" in data
        assert "drift_seconds" in data

    def test_mood_ws_mood_is_lowercase_string(self, client):
        with client.websocket_connect("/api/mood/ws") as ws:
            data = ws.receive_json()
        assert isinstance(data["mood"], str)
        # mood should be snake_case, no uppercase
        assert data["mood"] == data["mood"].lower()


class TestPermissionsWebSocket:
    def test_permissions_ws_accepts_connection(self, client):
        """WS /api/permissions/ws connects and sends at least one JSON message."""
        with client.websocket_connect("/api/permissions/ws") as ws:
            data = ws.receive_json()
        assert "pending" in data

    def test_permissions_ws_pending_is_list(self, client):
        with client.websocket_connect("/api/permissions/ws") as ws:
            data = ws.receive_json()
        assert isinstance(data["pending"], list)

    def test_permissions_ws_empty_queue(self, client):
        """With no pending tickets the pending list is empty."""
        with client.websocket_connect("/api/permissions/ws") as ws:
            data = ws.receive_json()
        assert data["pending"] == []

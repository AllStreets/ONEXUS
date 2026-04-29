"""Tests for federation protocol."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.federation.models import (
    FederationRequest,
    FederationResponse,
    PeerCapabilities,
    PeerInfo,
)
from nexus.federation.peer import PeerRegistry
from nexus.federation.protocol import FederationProtocol
from nexus.federation.security import FederationSecurity


@pytest.fixture
def chronicle():
    mock = MagicMock()
    mock.log = MagicMock()
    return mock


@pytest.fixture
def cortex():
    mock = MagicMock()
    mock.process = AsyncMock(return_value="[Nexus] Mock response")
    mock.list_modules = MagicMock(return_value=["general", "oracle"])
    mock._select_module = MagicMock(return_value="general")
    return mock


@pytest.fixture
def registry(tmp_path):
    return PeerRegistry(data_path=tmp_path / "federation")


@pytest.fixture
def security(chronicle):
    return FederationSecurity(
        instance_id="nexus-local-test",
        chronicle=chronicle,
        shared_secret="test-secret",
    )


@pytest.fixture
def protocol(registry, security, cortex, chronicle):
    return FederationProtocol(
        instance_id="nexus-local-test",
        instance_name="test-instance",
        version="0.1.0",
        registry=registry,
        security=security,
        cortex=cortex,
        chronicle=chronicle,
        enabled=True,
    )


@pytest.fixture
def disabled_protocol(registry, security, cortex, chronicle):
    return FederationProtocol(
        instance_id="nexus-local-test",
        instance_name="test-instance",
        version="0.1.0",
        registry=registry,
        security=security,
        cortex=cortex,
        chronicle=chronicle,
        enabled=False,
    )


@pytest.fixture
def sample_peer():
    return PeerInfo(
        peer_id="nexus-remote-001",
        url="http://localhost:8381",
        version="0.1.0",
        instance_name="remote-test",
    )


class TestHandshake:
    @pytest.mark.asyncio
    async def test_handle_handshake(self, protocol):
        payload = {
            "peer_id": "nexus-remote",
            "instance_name": "remote",
            "version": "0.1.0",
            "url": "http://localhost:8381",
        }
        result = await protocol.handle_handshake(payload)
        assert result["peer_id"] == "nexus-local-test"
        assert result["instance_name"] == "test-instance"
        assert result["version"] == "0.1.0"

        # Peer should be registered
        peer = protocol.registry.get_peer("nexus-remote")
        assert peer is not None
        assert peer.status == "connected"

    @pytest.mark.asyncio
    async def test_handle_handshake_missing_peer_id(self, protocol):
        with pytest.raises(ValueError, match="missing peer_id"):
            await protocol.handle_handshake({"instance_name": "test"})

    @pytest.mark.asyncio
    async def test_handshake_disabled(self, disabled_protocol):
        with pytest.raises(RuntimeError, match="not enabled"):
            await disabled_protocol.handle_handshake({"peer_id": "test"})

    @pytest.mark.asyncio
    async def test_handshake_outbound(self, protocol):
        """Test outbound handshake with mocked HTTP."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "peer_id": "nexus-remote",
            "instance_name": "remote",
            "version": "0.1.0",
        })

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            peer = await protocol.handshake("http://localhost:8381")
            assert peer.peer_id == "nexus-remote"
            assert peer.status == "connected"
            assert protocol.registry.get_peer("nexus-remote") is not None


class TestCapabilities:
    def test_get_local_capabilities(self, protocol):
        caps = protocol.get_local_capabilities()
        assert caps["peer_id"] == "nexus-local-test"
        assert "general" in caps["modules"]
        assert "oracle" in caps["modules"]
        assert caps["total_modules"] == 2
        assert caps["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_exchange_capabilities(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "peer_id": "nexus-remote-001",
            "modules": ["general", "herald"],
            "agents": [],
            "categories": [],
            "total_modules": 2,
            "version": "0.1.0",
        })

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            caps = await protocol.exchange_capabilities(sample_peer)
            assert caps.peer_id == "nexus-remote-001"
            assert "herald" in caps.modules
            assert caps.total_modules == 2


class TestRouting:
    @pytest.mark.asyncio
    async def test_handle_incoming_known_peer(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        request = FederationRequest(
            request_id="req-001",
            source_peer="nexus-remote-001",
            message="What modules do you have?",
        )

        response = await protocol.handle_incoming(request)
        assert response.success is True
        assert response.handled_by == "general"
        assert response.response == "[Nexus] Mock response"

    @pytest.mark.asyncio
    async def test_handle_incoming_unknown_peer(self, protocol):
        request = FederationRequest(
            request_id="req-002",
            source_peer="nexus-unknown",
            message="Hello",
        )
        response = await protocol.handle_incoming(request)
        assert response.success is False
        assert "handshake required" in response.response.lower()

    @pytest.mark.asyncio
    async def test_handle_incoming_disabled(self, disabled_protocol):
        request = FederationRequest(
            request_id="req-003",
            source_peer="nexus-remote",
            message="Hello",
        )
        response = await disabled_protocol.handle_incoming(request)
        assert response.success is False
        assert "not enabled" in response.response.lower()

    @pytest.mark.asyncio
    async def test_handle_incoming_rate_limited(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        # Exhaust rate limit
        for _ in range(30):
            protocol.security.check_rate_limit("nexus-remote-001", max_per_minute=30)

        request = FederationRequest(
            request_id="req-004",
            source_peer="nexus-remote-001",
            message="Flood",
        )
        response = await protocol.handle_incoming(request)
        assert response.success is False
        assert "rate limit" in response.response.lower()

    @pytest.mark.asyncio
    async def test_handle_incoming_with_valid_signature(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        request = FederationRequest(
            request_id="req-005",
            source_peer="nexus-remote-001",
            message="Signed message",
        )
        request.signature = protocol.security.sign_request(request)

        response = await protocol.handle_incoming(request)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_handle_incoming_with_invalid_signature(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        request = FederationRequest(
            request_id="req-006",
            source_peer="nexus-remote-001",
            message="Bad sig",
            signature="definitely-not-valid",
        )

        response = await protocol.handle_incoming(request)
        assert response.success is False
        assert "invalid signature" in response.response.lower()

    @pytest.mark.asyncio
    async def test_handle_incoming_cortex_error(self, protocol, sample_peer, cortex):
        protocol.registry.add_peer(sample_peer)
        cortex.process = AsyncMock(side_effect=RuntimeError("Module crashed"))

        request = FederationRequest(
            request_id="req-007",
            source_peer="nexus-remote-001",
            message="Crash me",
        )
        response = await protocol.handle_incoming(request)
        assert response.success is False
        assert "error" in response.response.lower()

    @pytest.mark.asyncio
    async def test_route_to_peer(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "request_id": "req-008",
            "source_peer": "nexus-remote-001",
            "response": "Remote response",
            "handled_by": "general",
            "success": True,
        })

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await protocol.route_to_peer("nexus-remote-001", "Hello remote")
            assert result == "Remote response"

    @pytest.mark.asyncio
    async def test_route_to_unknown_peer(self, protocol):
        with pytest.raises(ValueError, match="Unknown peer"):
            await protocol.route_to_peer("nonexistent", "Hello")

    @pytest.mark.asyncio
    async def test_route_to_disconnected_peer(self, protocol, sample_peer):
        sample_peer.status = "disconnected"
        protocol.registry.add_peer(sample_peer)
        with pytest.raises(ValueError, match="disconnected"):
            await protocol.route_to_peer("nexus-remote-001", "Hello")


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_handle_heartbeat_known_peer(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)
        result = await protocol.handle_heartbeat({"peer_id": "nexus-remote-001"})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_handle_heartbeat_unknown_peer(self, protocol):
        result = await protocol.handle_heartbeat({"peer_id": "nexus-unknown"})
        assert result["status"] == "unknown_peer"

    @pytest.mark.asyncio
    async def test_send_heartbeat_success(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await protocol.send_heartbeat("nexus-remote-001")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_heartbeat_failure(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await protocol.send_heartbeat("nexus-remote-001")
            assert result is False
            peer = protocol.registry.get_peer("nexus-remote-001")
            assert peer.status == "stale"


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_peer(self, protocol, sample_peer):
        protocol.registry.add_peer(sample_peer)

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await protocol.disconnect_peer("nexus-remote-001")
            peer = protocol.registry.get_peer("nexus-remote-001")
            assert peer.status == "disconnected"

    @pytest.mark.asyncio
    async def test_disconnect_unknown(self, protocol):
        # Should not raise
        await protocol.disconnect_peer("nonexistent")

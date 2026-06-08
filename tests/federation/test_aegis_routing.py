"""
Tests that FederationProtocol and PeerDiscovery route through
KernelHttpClient when one is provided (Phase 6 T7).

These tests use a minimal AsyncMock as the http_client so they can
verify the new path without needing a real Aegis DB or real HTTP server.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from nexus.federation.discovery import PeerDiscovery
from nexus.federation.models import PeerInfo
from nexus.federation.peer import PeerRegistry
from nexus.federation.protocol import FederationProtocol
from nexus.federation.security import FederationSecurity


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chronicle():
    m = MagicMock()
    m.log = MagicMock()
    return m


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
def cortex():
    m = MagicMock()
    m.process = AsyncMock(return_value="[Nexus] response")
    m.list_modules = MagicMock(return_value=["general"])
    m._select_module = MagicMock(return_value="general")
    return m


@pytest.fixture
def sample_peer():
    return PeerInfo(
        peer_id="nexus-remote-001",
        url="http://localhost:8381",
        version="0.1.0",
        instance_name="remote-test",
    )


def _make_http_client(method: str, return_json: dict) -> MagicMock:
    """Build a minimal fake KernelHttpClient-like object."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=return_json)

    client = MagicMock()
    # Make get/post awaitable
    setattr(client, method, AsyncMock(return_value=resp))
    return client


# ---------------------------------------------------------------------------
# PeerDiscovery — http_client path
# ---------------------------------------------------------------------------

class TestPeerDiscoveryHttpClient:
    @pytest.mark.asyncio
    async def test_discover_manual_uses_http_client(self, registry, security, chronicle):
        """discover_manual() uses http_client.get() when provided."""
        http_client = _make_http_client("get", {
            "version": "0.1.0",
            "peer_id": "nexus-remote-001",
            "instance_name": "remote",
        })

        discovery = PeerDiscovery(
            registry=registry,
            security=security,
            chronicle=chronicle,
            instance_id="nexus-local-test",
            http_client=http_client,
        )

        peer = await discovery.discover_manual("http://localhost:8381")

        assert peer is not None
        assert peer.peer_id == "nexus-remote-001"
        # Verify our http_client.get was called (not httpx.AsyncClient)
        http_client.get.assert_called_once()
        call_url = http_client.get.call_args[0][0]
        assert "/api/system/status" in call_url

    @pytest.mark.asyncio
    async def test_heartbeat_all_uses_http_client(
        self, registry, security, chronicle, sample_peer
    ):
        """heartbeat_all() uses http_client.post() when provided."""
        registry.add_peer(sample_peer)

        http_client = _make_http_client("post", {})

        discovery = PeerDiscovery(
            registry=registry,
            security=security,
            chronicle=chronicle,
            instance_id="nexus-local-test",
            http_client=http_client,
        )

        results = await discovery.heartbeat_all()

        assert results.get("nexus-remote-001") is True
        http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_manual_fallback_without_http_client(
        self, registry, security, chronicle
    ):
        """Without http_client, discover_manual falls back to httpx.AsyncClient."""
        from unittest.mock import patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "version": "0.1.0",
            "peer_id": "nexus-remote-fallback",
            "instance_name": "remote",
        })

        discovery = PeerDiscovery(
            registry=registry,
            security=security,
            chronicle=chronicle,
            instance_id="nexus-local-test",
            # http_client intentionally omitted — should fall back to httpx
        )

        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            peer = await discovery.discover_manual("http://localhost:8381")

        assert peer is not None
        assert peer.peer_id == "nexus-remote-fallback"
        mock_cls.assert_called_once()  # proves httpx.AsyncClient was used


# ---------------------------------------------------------------------------
# FederationProtocol — http_client path
# ---------------------------------------------------------------------------

class TestFederationProtocolHttpClient:
    @pytest.mark.asyncio
    async def test_handshake_uses_http_client(
        self, registry, security, cortex, chronicle
    ):
        """handshake() uses http_client.post() when provided."""
        http_client = _make_http_client("post", {
            "peer_id": "nexus-remote-001",
            "instance_name": "remote",
            "version": "0.1.0",
            "trust_level": 10,
        })

        protocol = FederationProtocol(
            instance_id="nexus-local-test",
            instance_name="test-instance",
            version="0.1.0",
            registry=registry,
            security=security,
            cortex=cortex,
            chronicle=chronicle,
            enabled=True,
            http_client=http_client,
        )

        peer = await protocol.handshake("http://localhost:8381")

        assert peer.peer_id == "nexus-remote-001"
        assert peer.status == "connected"
        http_client.post.assert_called_once()
        call_url = http_client.post.call_args[0][0]
        assert "/api/federation/handshake" in call_url

    @pytest.mark.asyncio
    async def test_route_to_peer_uses_http_client(
        self, registry, security, cortex, chronicle, sample_peer
    ):
        """route_to_peer() uses http_client.post() when provided."""
        registry.add_peer(sample_peer)

        http_client = _make_http_client("post", {
            "request_id": "req-001",
            "source_peer": "nexus-remote-001",
            "response": "Remote response via aegis",
            "handled_by": "general",
            "success": True,
        })

        protocol = FederationProtocol(
            instance_id="nexus-local-test",
            instance_name="test-instance",
            version="0.1.0",
            registry=registry,
            security=security,
            cortex=cortex,
            chronicle=chronicle,
            enabled=True,
            http_client=http_client,
        )

        result = await protocol.route_to_peer("nexus-remote-001", "Hello via aegis")

        assert result == "Remote response via aegis"
        http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_heartbeat_uses_http_client(
        self, registry, security, cortex, chronicle, sample_peer
    ):
        """send_heartbeat() uses http_client.post() when provided."""
        registry.add_peer(sample_peer)

        http_client = _make_http_client("post", {})

        protocol = FederationProtocol(
            instance_id="nexus-local-test",
            instance_name="test-instance",
            version="0.1.0",
            registry=registry,
            security=security,
            cortex=cortex,
            chronicle=chronicle,
            enabled=True,
            http_client=http_client,
        )

        result = await protocol.send_heartbeat("nexus-remote-001")

        assert result is True
        http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_without_http_client(
        self, registry, security, cortex, chronicle, sample_peer
    ):
        """Without http_client, protocol falls back to httpx.AsyncClient."""
        from unittest.mock import patch

        registry.add_peer(sample_peer)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "request_id": "req-fallback",
            "source_peer": "nexus-remote-001",
            "response": "Fallback response",
            "handled_by": "general",
            "success": True,
        })

        protocol = FederationProtocol(
            instance_id="nexus-local-test",
            instance_name="test-instance",
            version="0.1.0",
            registry=registry,
            security=security,
            cortex=cortex,
            chronicle=chronicle,
            enabled=True,
            # http_client intentionally omitted
        )

        with patch("nexus.federation.protocol.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await protocol.route_to_peer(
                "nexus-remote-001", "Hello fallback"
            )

        assert result == "Fallback response"
        mock_cls.assert_called_once()

"""Tests for peer discovery."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.federation.discovery import PeerDiscovery
from nexus.federation.models import PeerInfo
from nexus.federation.peer import PeerRegistry
from nexus.federation.security import FederationSecurity


@pytest.fixture
def chronicle():
    mock = MagicMock()
    mock.log = MagicMock()
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
def discovery(registry, security, chronicle):
    return PeerDiscovery(
        registry=registry,
        security=security,
        chronicle=chronicle,
        instance_id="nexus-local-test",
    )


class TestManualDiscovery:
    @pytest.mark.asyncio
    async def test_discover_valid_nexus(self, discovery):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "version": "0.1.0",
            "peer_id": "nexus-remote-001",
            "instance_name": "remote-peer",
        })

        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            peer = await discovery.discover_manual("http://localhost:8381")
            assert peer is not None
            assert peer.peer_id == "nexus-remote-001"
            assert peer.version == "0.1.0"

            # Should be in registry
            assert discovery.registry.get_peer("nexus-remote-001") is not None

    @pytest.mark.asyncio
    async def test_discover_non_nexus(self, discovery):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"status": "ok"})  # No "version"

        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            peer = await discovery.discover_manual("http://localhost:9999")
            assert peer is None

    @pytest.mark.asyncio
    async def test_discover_connection_error(self, discovery):
        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            peer = await discovery.discover_manual("http://localhost:9999")
            assert peer is None

    @pytest.mark.asyncio
    async def test_discover_self_skipped(self, discovery):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "version": "0.1.0",
            "peer_id": "nexus-local-test",  # Same as our instance ID
            "instance_name": "self",
        })

        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            peer = await discovery.discover_manual("http://localhost:8380")
            assert peer is None


class TestHeartbeatAll:
    @pytest.mark.asyncio
    async def test_heartbeat_all_mixed(self, discovery, registry):
        peer1 = PeerInfo(
            peer_id="nexus-001", url="http://localhost:8381",
            version="0.1.0", instance_name="peer1",
        )
        peer2 = PeerInfo(
            peer_id="nexus-002", url="http://localhost:8382",
            version="0.1.0", instance_name="peer2",
        )
        registry.add_peer(peer1)
        registry.add_peer(peer2)

        def _make_response(status_code):
            r = MagicMock()
            r.status_code = status_code
            return r

        call_count = 0

        async def _mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "8381" in url:
                return _make_response(200)
            else:
                raise Exception("Connection refused")

        with patch("nexus.federation.discovery.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = _mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            results = await discovery.heartbeat_all()
            assert results["nexus-001"] is True
            assert results["nexus-002"] is False

    @pytest.mark.asyncio
    async def test_heartbeat_skips_disconnected(self, discovery, registry):
        peer = PeerInfo(
            peer_id="nexus-disc", url="http://localhost:8381",
            version="0.1.0", instance_name="disconnected",
            status="disconnected",
        )
        registry.add_peer(peer)

        results = await discovery.heartbeat_all()
        assert results["nexus-disc"] is False


class TestCleanupStale:
    @pytest.mark.asyncio
    async def test_cleanup_stale(self, discovery, registry):
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        peer = PeerInfo(
            peer_id="nexus-stale", url="http://localhost:8381",
            version="0.1.0", instance_name="stale",
            last_seen=old_time, status="connected",
        )
        registry.add_peer(peer)

        removed = await discovery.cleanup_stale(timeout=300)
        assert "nexus-stale" in removed
        assert registry.get_peer("nexus-stale").status == "disconnected"

    @pytest.mark.asyncio
    async def test_cleanup_keeps_fresh(self, discovery, registry):
        peer = PeerInfo(
            peer_id="nexus-fresh", url="http://localhost:8381",
            version="0.1.0", instance_name="fresh",
        )
        registry.add_peer(peer)

        removed = await discovery.cleanup_stale(timeout=300)
        assert removed == []
        assert registry.get_peer("nexus-fresh").status == "connected"

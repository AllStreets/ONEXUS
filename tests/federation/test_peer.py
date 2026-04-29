"""Tests for peer registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest

from nexus.federation.models import PeerCapabilities, PeerInfo
from nexus.federation.peer import PeerRegistry


@pytest.fixture
def registry(tmp_path):
    return PeerRegistry(data_path=tmp_path / "federation")


@pytest.fixture
def sample_peer():
    return PeerInfo(
        peer_id="nexus-test-001",
        url="http://localhost:8381",
        version="0.1.0",
        instance_name="test-peer",
    )


@pytest.fixture
def sample_peer_2():
    return PeerInfo(
        peer_id="nexus-test-002",
        url="http://localhost:8382",
        version="0.1.0",
        instance_name="test-peer-2",
    )


class TestPeerRegistryCRUD:
    def test_add_and_get(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        result = registry.get_peer("nexus-test-001")
        assert result is not None
        assert result.peer_id == "nexus-test-001"
        assert result.url == "http://localhost:8381"

    def test_get_nonexistent(self, registry):
        assert registry.get_peer("nonexistent") is None

    def test_remove_peer(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        registry.remove_peer("nexus-test-001")
        assert registry.get_peer("nexus-test-001") is None

    def test_remove_nonexistent(self, registry):
        # Should not raise
        registry.remove_peer("nonexistent")

    def test_list_peers(self, registry, sample_peer, sample_peer_2):
        registry.add_peer(sample_peer)
        registry.add_peer(sample_peer_2)
        peers = registry.list_peers()
        assert len(peers) == 2
        ids = {p.peer_id for p in peers}
        assert ids == {"nexus-test-001", "nexus-test-002"}

    def test_list_empty(self, registry):
        assert registry.list_peers() == []


class TestFindCapability:
    def test_find_by_module(self, registry, sample_peer, sample_peer_2):
        registry.add_peer(sample_peer)
        registry.add_peer(sample_peer_2)

        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-001",
            modules=["general", "oracle"],
            total_modules=2,
        ))
        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-002",
            modules=["general", "herald"],
            total_modules=2,
        ))

        results = registry.find_capability("oracle")
        assert len(results) == 1
        assert results[0].peer_id == "nexus-test-001"

    def test_find_shared_module(self, registry, sample_peer, sample_peer_2):
        registry.add_peer(sample_peer)
        registry.add_peer(sample_peer_2)

        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-001", modules=["general"], total_modules=1,
        ))
        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-002", modules=["general"], total_modules=1,
        ))

        results = registry.find_capability("general")
        assert len(results) == 2

    def test_find_nonexistent_module(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-001", modules=["general"], total_modules=1,
        ))
        assert registry.find_capability("nonexistent") == []

    def test_find_skips_disconnected(self, registry, sample_peer):
        sample_peer.status = "disconnected"
        registry.add_peer(sample_peer)
        registry.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-001", modules=["general"], total_modules=1,
        ))
        assert registry.find_capability("general") == []


class TestHeartbeatAndStale:
    def test_update_heartbeat(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        old_seen = sample_peer.last_seen
        registry.update_heartbeat("nexus-test-001")
        peer = registry.get_peer("nexus-test-001")
        assert peer.status == "connected"
        # last_seen should be updated (or at least not earlier)
        assert peer.last_seen >= old_seen

    def test_stale_detection(self, registry):
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        peer = PeerInfo(
            peer_id="nexus-stale",
            url="http://localhost:9999",
            version="0.1.0",
            instance_name="stale-peer",
            last_seen=old_time,
            status="connected",
        )
        registry.add_peer(peer)
        stale = registry.get_stale_peers(timeout_seconds=300)
        assert len(stale) == 1
        assert stale[0].peer_id == "nexus-stale"

    def test_stale_skips_disconnected(self, registry):
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        peer = PeerInfo(
            peer_id="nexus-disc",
            url="http://localhost:9999",
            version="0.1.0",
            instance_name="disc-peer",
            last_seen=old_time,
            status="disconnected",
        )
        registry.add_peer(peer)
        stale = registry.get_stale_peers(timeout_seconds=300)
        assert len(stale) == 0

    def test_not_stale_if_recent(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        stale = registry.get_stale_peers(timeout_seconds=300)
        assert len(stale) == 0

    def test_mark_stale(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        registry.mark_stale("nexus-test-001")
        assert registry.get_peer("nexus-test-001").status == "stale"

    def test_mark_disconnected(self, registry, sample_peer):
        registry.add_peer(sample_peer)
        registry.mark_disconnected("nexus-test-001")
        assert registry.get_peer("nexus-test-001").status == "disconnected"


class TestSaveLoad:
    def test_save_and_load(self, tmp_path, sample_peer):
        reg1 = PeerRegistry(data_path=tmp_path / "fed1")
        reg1.add_peer(sample_peer)
        reg1.set_capabilities(PeerCapabilities(
            peer_id="nexus-test-001",
            modules=["general", "oracle"],
            total_modules=2,
            version="0.1.0",
        ))
        reg1.save()

        reg2 = PeerRegistry(data_path=tmp_path / "fed1")
        reg2.load()
        assert len(reg2.list_peers()) == 1
        peer = reg2.get_peer("nexus-test-001")
        assert peer is not None
        assert peer.instance_name == "test-peer"

        caps = reg2.get_capabilities("nexus-test-001")
        assert caps is not None
        assert "oracle" in caps.modules

    def test_load_empty(self, tmp_path):
        reg = PeerRegistry(data_path=tmp_path / "fed_empty")
        reg.load()
        assert reg.list_peers() == []

    def test_load_corrupt_file(self, tmp_path):
        reg_path = tmp_path / "fed_corrupt"
        reg_path.mkdir(parents=True, exist_ok=True)
        (reg_path / "federation_peers.json").write_text("not json")
        reg = PeerRegistry(data_path=reg_path)
        reg.load()
        assert reg.list_peers() == []

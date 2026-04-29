"""Tests for federation data models."""
from __future__ import annotations

from nexus.federation.models import (
    FederationMessage,
    FederationRequest,
    FederationResponse,
    PeerCapabilities,
    PeerInfo,
)


class TestPeerInfo:
    def test_creation_defaults(self):
        peer = PeerInfo(
            peer_id="nexus-abc123",
            url="http://localhost:8381",
            version="0.1.0",
            instance_name="test-instance",
        )
        assert peer.peer_id == "nexus-abc123"
        assert peer.url == "http://localhost:8381"
        assert peer.status == "connected"
        assert peer.trust_level == 10
        assert peer.first_seen != ""
        assert peer.last_seen != ""

    def test_to_dict_roundtrip(self):
        peer = PeerInfo(
            peer_id="nexus-abc123",
            url="http://localhost:8381",
            version="0.1.0",
            instance_name="test-instance",
            status="stale",
            trust_level=50,
        )
        data = peer.to_dict()
        restored = PeerInfo.from_dict(data)
        assert restored.peer_id == peer.peer_id
        assert restored.url == peer.url
        assert restored.version == peer.version
        assert restored.status == peer.status
        assert restored.trust_level == peer.trust_level

    def test_from_dict_with_defaults(self):
        data = {
            "peer_id": "nexus-xyz",
            "url": "http://example.com",
            "version": "1.0.0",
            "instance_name": "remote",
        }
        peer = PeerInfo.from_dict(data)
        assert peer.status == "connected"
        assert peer.trust_level == 10


class TestPeerCapabilities:
    def test_creation(self):
        caps = PeerCapabilities(
            peer_id="nexus-abc",
            modules=["general", "oracle", "herald"],
            agents=["research-agent"],
            categories=["analysis"],
            total_modules=3,
            version="0.1.0",
        )
        assert len(caps.modules) == 3
        assert caps.total_modules == 3

    def test_roundtrip(self):
        caps = PeerCapabilities(
            peer_id="nexus-abc",
            modules=["general"],
            total_modules=1,
            version="0.1.0",
        )
        data = caps.to_dict()
        restored = PeerCapabilities.from_dict(data)
        assert restored.peer_id == caps.peer_id
        assert restored.modules == caps.modules
        assert restored.total_modules == caps.total_modules


class TestFederationRequest:
    def test_creation(self):
        req = FederationRequest(
            request_id="req-001",
            source_peer="nexus-abc",
            message="What time is it?",
        )
        assert req.request_id == "req-001"
        assert req.target_module is None
        assert req.signature == ""
        assert req.timestamp != ""

    def test_roundtrip(self):
        req = FederationRequest(
            request_id="req-002",
            source_peer="nexus-abc",
            message="Hello",
            target_module="general",
            signature="abc123",
        )
        data = req.to_dict()
        restored = FederationRequest.from_dict(data)
        assert restored.request_id == req.request_id
        assert restored.source_peer == req.source_peer
        assert restored.message == req.message
        assert restored.target_module == req.target_module
        assert restored.signature == req.signature


class TestFederationResponse:
    def test_creation(self):
        resp = FederationResponse(
            request_id="req-001",
            source_peer="nexus-xyz",
            response="It is 3pm",
            handled_by="general",
            success=True,
        )
        assert resp.success is True
        assert resp.handled_by == "general"

    def test_roundtrip(self):
        resp = FederationResponse(
            request_id="req-001",
            source_peer="nexus-xyz",
            response="Error occurred",
            handled_by="federation",
            success=False,
        )
        data = resp.to_dict()
        restored = FederationResponse.from_dict(data)
        assert restored.success is False
        assert restored.handled_by == "federation"


class TestFederationMessage:
    def test_creation(self):
        msg = FederationMessage(
            type="federation.handshake",
            peer_id="nexus-abc",
            payload={"version": "0.1.0"},
        )
        assert msg.type == "federation.handshake"
        assert msg.payload["version"] == "0.1.0"

    def test_roundtrip(self):
        msg = FederationMessage(
            type="federation.heartbeat",
            peer_id="nexus-abc",
            payload={},
        )
        data = msg.to_dict()
        restored = FederationMessage.from_dict(data)
        assert restored.type == msg.type
        assert restored.peer_id == msg.peer_id

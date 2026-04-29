"""Tests for federation security."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from nexus.federation.models import FederationRequest, PeerInfo
from nexus.federation.security import FederationSecurity


@pytest.fixture
def chronicle():
    mock = MagicMock()
    mock.log = MagicMock()
    return mock


@pytest.fixture
def security(chronicle):
    return FederationSecurity(
        instance_id="nexus-test-local",
        chronicle=chronicle,
        shared_secret="test-secret-key",
    )


@pytest.fixture
def sample_request():
    return FederationRequest(
        request_id="req-001",
        source_peer="nexus-remote",
        message="Hello from remote",
        timestamp="2025-01-01T00:00:00+00:00",
    )


@pytest.fixture
def sample_peer():
    return PeerInfo(
        peer_id="nexus-remote",
        url="http://localhost:8381",
        version="0.1.0",
        instance_name="remote-peer",
    )


class TestInstanceId:
    def test_generate_unique(self):
        id1 = FederationSecurity.generate_instance_id()
        id2 = FederationSecurity.generate_instance_id()
        assert id1 != id2
        assert id1.startswith("nexus-")
        assert len(id1) == 22  # "nexus-" + 16 hex chars


class TestSigning:
    def test_sign_produces_hex(self, security, sample_request):
        sig = security.sign_request(sample_request)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex digest

    def test_sign_deterministic(self, security, sample_request):
        sig1 = security.sign_request(sample_request)
        sig2 = security.sign_request(sample_request)
        assert sig1 == sig2

    def test_sign_changes_with_message(self, security):
        req1 = FederationRequest(
            request_id="req-001", source_peer="nexus-remote",
            message="Hello", timestamp="2025-01-01T00:00:00+00:00",
        )
        req2 = FederationRequest(
            request_id="req-001", source_peer="nexus-remote",
            message="Goodbye", timestamp="2025-01-01T00:00:00+00:00",
        )
        assert security.sign_request(req1) != security.sign_request(req2)


class TestVerification:
    def test_verify_valid_signature(self, security, sample_request, sample_peer):
        sig = security.sign_request(sample_request)
        assert security.verify_request(sample_request, sig, sample_peer) is True

    def test_verify_invalid_signature(self, security, sample_request, sample_peer):
        assert security.verify_request(sample_request, "bad-signature", sample_peer) is False

    def test_verify_tampered_message(self, security, sample_request, sample_peer):
        sig = security.sign_request(sample_request)
        sample_request.message = "Tampered message"
        assert security.verify_request(sample_request, sig, sample_peer) is False

    def test_different_secrets_fail(self, chronicle, sample_request, sample_peer):
        sec1 = FederationSecurity("id1", chronicle, shared_secret="secret-a")
        sec2 = FederationSecurity("id2", chronicle, shared_secret="secret-b")
        sig = sec1.sign_request(sample_request)
        assert sec2.verify_request(sample_request, sig, sample_peer) is False


class TestRateLimiting:
    def test_allows_under_limit(self, security):
        for _ in range(5):
            assert security.check_rate_limit("nexus-remote", max_per_minute=10) is True

    def test_blocks_over_limit(self, security):
        peer_id = "nexus-flood"
        limit = 5
        for _ in range(limit):
            assert security.check_rate_limit(peer_id, max_per_minute=limit) is True
        # Next request should be blocked
        assert security.check_rate_limit(peer_id, max_per_minute=limit) is False

    def test_different_peers_independent(self, security):
        limit = 3
        for _ in range(limit):
            security.check_rate_limit("peer-a", max_per_minute=limit)
        assert security.check_rate_limit("peer-a", max_per_minute=limit) is False
        # peer-b should still be allowed
        assert security.check_rate_limit("peer-b", max_per_minute=limit) is True


class TestLogging:
    def test_log_federation_event(self, security, chronicle):
        security.log_federation_event("test_event", "nexus-remote", {"key": "value"})
        chronicle.log.assert_called_once()
        args = chronicle.log.call_args
        assert args[0][0] == "federation"
        assert args[0][1] == "test_event"
        assert args[0][2]["peer_id"] == "nexus-remote"
        assert args[0][2]["key"] == "value"

    def test_log_with_no_chronicle(self):
        sec = FederationSecurity("test-id", chronicle=None, shared_secret="secret")
        # Should not raise
        sec.log_federation_event("test", "peer", {})

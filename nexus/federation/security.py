"""
Federation security -- request signing, verification, and rate limiting.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from nexus.federation.models import FederationRequest, PeerInfo


class FederationSecurity:
    """Security layer for federation -- request signing, verification, rate limiting."""

    def __init__(self, instance_id: str, chronicle: Any, shared_secret: str = ""):
        self.instance_id = instance_id
        self.chronicle = chronicle
        self._shared_secret = shared_secret or self._derive_default_secret(instance_id)
        self._request_counts: dict[str, list[float]] = {}

    @staticmethod
    def generate_instance_id() -> str:
        """Generate a unique instance identifier (UUID-based)."""
        return f"nexus-{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _derive_default_secret(instance_id: str) -> str:
        """Derive a default shared secret from the instance ID.

        In production, users should configure an explicit shared secret.
        This default exists so federation works out of the box between
        instances that know each other's IDs.
        """
        return hashlib.sha256(f"nexus-federation-{instance_id}".encode()).hexdigest()

    def sign_request(self, request: FederationRequest) -> str:
        """Create an HMAC signature for a request using shared secret."""
        payload = f"{request.request_id}:{request.source_peer}:{request.message}:{request.timestamp}"
        return hmac.new(
            self._shared_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_request(self, request: FederationRequest, signature: str,
                       peer: PeerInfo) -> bool:
        """Verify a request signature from a known peer.

        Rebuilds the expected signature and compares using constant-time comparison.
        """
        payload = f"{request.request_id}:{request.source_peer}:{request.message}:{request.timestamp}"
        expected = hmac.new(
            self._shared_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def check_rate_limit(self, peer_id: str, max_per_minute: int = 30) -> bool:
        """Check if a peer has exceeded rate limits.

        Returns True if the request is allowed, False if rate-limited.
        """
        now = time.monotonic()
        window = 60.0

        if peer_id not in self._request_counts:
            self._request_counts[peer_id] = []

        # Prune old entries outside the window
        self._request_counts[peer_id] = [
            t for t in self._request_counts[peer_id]
            if now - t < window
        ]

        if len(self._request_counts[peer_id]) >= max_per_minute:
            self.log_federation_event("rate_limited", peer_id, {
                "count": len(self._request_counts[peer_id]),
                "max": max_per_minute,
            })
            return False

        self._request_counts[peer_id].append(now)
        return True

    def log_federation_event(self, event_type: str, peer_id: str, data: dict) -> None:
        """Log all federation activity to Chronicle for audit."""
        if self.chronicle:
            self.chronicle.log("federation", event_type, {
                "instance_id": self.instance_id,
                "peer_id": peer_id,
                **data,
            })

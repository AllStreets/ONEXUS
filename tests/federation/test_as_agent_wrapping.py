"""
T3 — Verify that federation call sites wrap _http calls in as_agent("federation"),
which makes KernelHttpClient route through aegis.network().

Strategy: build a KernelHttpClient backed by a mock Aegis whose .network()
records every call.  Register a federation manifest so check_capability passes.
Then invoke PeerDiscovery.discover_manual() and confirm aegis.network() fired.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from nexus.context import current_agent_slug
from nexus.federation.discovery import PeerDiscovery
from nexus.federation.peer import PeerRegistry
from nexus.federation.security import FederationSecurity
from nexus.inference.kernel_http_client import KernelHttpClient


# ---------------------------------------------------------------------------
# Fixtures
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
        instance_id="nexus-t3-test",
        chronicle=chronicle,
        shared_secret="t3-secret",
    )


def _make_mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


# ---------------------------------------------------------------------------
# Test: as_agent("federation") context is set when _http.get is called
# ---------------------------------------------------------------------------

class TestAsAgentWrapping:
    @pytest.mark.asyncio
    async def test_discover_manual_calls_aegis_network(self, registry, security, chronicle):
        """
        PeerDiscovery.discover_manual() must fire aegis.network() because
        the call is now wrapped in as_agent("federation").

        We build a real KernelHttpClient with a spy on aegis.network().
        The spy records the agent_slug that was active at call time.
        """
        captured_slugs: list[str | None] = []

        async def fake_network(agent_slug, url, *, method="GET", **kwargs):
            # Record what agent slug was active + what aegis.network received
            captured_slugs.append(agent_slug)
            return _make_mock_response({
                "version": "0.1.0",
                "peer_id": "nexus-remote-t3",
                "instance_name": "remote-t3",
            })

        mock_aegis = MagicMock()
        mock_aegis.network = AsyncMock(side_effect=fake_network)

        http_client = KernelHttpClient(aegis=mock_aegis)

        discovery = PeerDiscovery(
            registry=registry,
            security=security,
            chronicle=chronicle,
            instance_id="nexus-t3-test",
            http_client=http_client,
        )

        peer = await discovery.discover_manual("http://localhost:8381")

        assert peer is not None
        assert peer.peer_id == "nexus-remote-t3"
        # aegis.network must have been called
        assert mock_aegis.network.called, "aegis.network() was not called"
        # The slug passed to aegis.network must be "federation"
        assert captured_slugs, "no agent slug was captured"
        assert captured_slugs[0] == "federation", (
            f"expected agent slug 'federation', got {captured_slugs[0]!r}"
        )

    @pytest.mark.asyncio
    async def test_without_as_agent_context_slug_is_none(self):
        """
        Baseline: outside any as_agent() context, current_agent_slug() is None.
        This confirms the context manager is what sets the slug.
        """
        assert current_agent_slug() is None

    @pytest.mark.asyncio
    async def test_as_agent_sets_federation_slug_during_call(self, registry, security, chronicle):
        """
        Verify the context variable is set to 'federation' inside the http call
        by checking the slug at the moment aegis.network is invoked.
        """
        slug_at_call_time: list[str | None] = []

        async def recording_network(agent_slug, url, *, method="GET", **kwargs):
            # Record the context variable directly (not just the arg)
            slug_at_call_time.append(current_agent_slug())
            return _make_mock_response({
                "version": "0.1.0",
                "peer_id": "nexus-ctx-check",
                "instance_name": "ctx-remote",
            })

        mock_aegis = MagicMock()
        mock_aegis.network = AsyncMock(side_effect=recording_network)

        http_client = KernelHttpClient(aegis=mock_aegis)

        discovery = PeerDiscovery(
            registry=registry,
            security=security,
            chronicle=chronicle,
            instance_id="nexus-t3-test",
            http_client=http_client,
        )

        await discovery.discover_manual("http://localhost:8382")

        assert slug_at_call_time, "network was never called"
        assert slug_at_call_time[0] == "federation", (
            f"context var was {slug_at_call_time[0]!r}, expected 'federation'"
        )

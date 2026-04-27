# tests/modules/test_collective.py
import pytest
from nexus.modules.collective import (
    CollectiveModule,
    FederatedConfig,
    PeerNode,
    ModelUpdate,
    AggregationResult,
)


@pytest.fixture
def collective():
    return CollectiveModule()


def test_collective_attrs(collective):
    assert collective.name == "collective"
    assert collective.version == "0.1.0"


def test_create_config(collective):
    config = FederatedConfig(
        model_id="sentiment-v1",
        min_peers=3,
        rounds=5,
        noise_scale=1.0,
        contribution_enabled=False,
    )
    assert config.noise_scale == 1.0
    assert config.contribution_enabled is False


def test_register_peer(collective):
    peer = PeerNode(peer_id="peer-001", endpoint="localhost:9001", reputation=0.5)
    collective.register_peer(peer)
    assert len(collective.list_peers()) == 1


def test_register_duplicate_peer(collective):
    peer = PeerNode(peer_id="peer-001", endpoint="localhost:9001", reputation=0.5)
    collective.register_peer(peer)
    collective.register_peer(peer)
    assert len(collective.list_peers()) == 1


def test_remove_peer(collective):
    peer = PeerNode(peer_id="peer-001", endpoint="localhost:9001", reputation=0.5)
    collective.register_peer(peer)
    collective.remove_peer("peer-001")
    assert len(collective.list_peers()) == 0


def test_create_model_update(collective):
    update = collective.create_update(
        model_id="sentiment-v1",
        weights={"layer1": [0.1, 0.2, 0.3], "layer2": [0.4, 0.5]},
    )
    assert isinstance(update, ModelUpdate)
    assert update.model_id == "sentiment-v1"
    assert len(update.noised_weights) > 0


def test_differential_privacy_adds_noise(collective):
    collective.noise_scale = 1.0
    update1 = collective.create_update("m1", {"l1": [1.0, 2.0, 3.0]})
    update2 = collective.create_update("m1", {"l1": [1.0, 2.0, 3.0]})
    w1 = update1.noised_weights["l1"]
    w2 = update2.noised_weights["l1"]
    assert w1 != w2


def test_aggregate_updates(collective):
    updates = [
        ModelUpdate(model_id="m1", noised_weights={"l1": [1.0, 2.0]}, peer_id="p1", round_num=1),
        ModelUpdate(model_id="m1", noised_weights={"l1": [3.0, 4.0]}, peer_id="p2", round_num=1),
    ]
    result = collective.aggregate(updates)
    assert isinstance(result, AggregationResult)
    assert len(result.averaged_weights["l1"]) == 2
    assert abs(result.averaged_weights["l1"][0] - 2.0) < 0.01
    assert abs(result.averaged_weights["l1"][1] - 3.0) < 0.01


def test_contribution_disabled_by_default(collective):
    assert collective.is_contributing() is False


def test_enable_contribution(collective):
    collective.set_contributing(True)
    assert collective.is_contributing() is True
    collective.set_contributing(False)
    assert collective.is_contributing() is False


@pytest.mark.asyncio
async def test_collective_handle(collective):
    result = await collective.handle("Show federated learning status", {"llm": None})
    assert "collective" in result.lower() or "federated" in result.lower() or "peer" in result.lower()


@pytest.mark.asyncio
async def test_collective_handle_peers(collective):
    peer = PeerNode(peer_id="peer-001", endpoint="localhost:9001", reputation=0.5)
    collective.register_peer(peer)
    result = await collective.handle("List connected peers", {"llm": None})
    assert "peer-001" in result or "1" in result

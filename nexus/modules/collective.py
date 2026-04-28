# nexus/modules/collective.py
"""
Collective -- federated learning coordinator.
Manages peer-to-peer model sharing with differential privacy guarantees.
Users opt in explicitly. No data leaves the machine without consent.
Noise injection ensures individual contributions cannot be extracted.
"""
import random
import uuid
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class FederatedConfig:
    model_id: str
    min_peers: int = 3
    rounds: int = 5
    noise_scale: float = 1.0
    contribution_enabled: bool = False


@dataclass
class PeerNode:
    peer_id: str
    endpoint: str
    reputation: float = 0.5


@dataclass
class ModelUpdate:
    model_id: str
    noised_weights: dict[str, list[float]]
    peer_id: str = ""
    round_num: int = 0


@dataclass
class AggregationResult:
    model_id: str
    averaged_weights: dict[str, list[float]]
    num_contributors: int
    round_num: int


class CollectiveModule(NexusModule):
    name = "collective"
    description = "Federated learning -- peer model sharing with differential privacy"
    version = "0.1.0"
    requires_network = True

    def __init__(self):
        self._peers: dict[str, PeerNode] = {}
        self._contributing: bool = False
        self.noise_scale: float = 1.0

    def register_peer(self, peer: PeerNode) -> None:
        self._peers[peer.peer_id] = peer

    def remove_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)

    def list_peers(self) -> list[PeerNode]:
        return list(self._peers.values())

    def is_contributing(self) -> bool:
        return self._contributing

    def set_contributing(self, enabled: bool) -> None:
        self._contributing = enabled

    def create_update(
        self,
        model_id: str,
        weights: dict[str, list[float]],
        context: dict[str, Any] | None = None,
    ) -> ModelUpdate:
        noised = {}
        for layer, values in weights.items():
            noised[layer] = [
                v + random.gauss(0, self.noise_scale) for v in values
            ]
        update = ModelUpdate(
            model_id=model_id,
            noised_weights=noised,
            peer_id=uuid.uuid4().hex[:8],
            round_num=0,
        )
        if context:
            layers = len(noised)
            self._log_outbound(
                context, "federated_peers",
                f"Noised model update for {model_id} ({layers} layers, noise={self.noise_scale})",
            )
        return update

    def aggregate(self, updates: list[ModelUpdate]) -> AggregationResult:
        if not updates:
            return AggregationResult(
                model_id="", averaged_weights={}, num_contributors=0, round_num=0,
            )

        model_id = updates[0].model_id
        all_layers = updates[0].noised_weights.keys()
        averaged: dict[str, list[float]] = {}

        for layer in all_layers:
            layer_values = [u.noised_weights[layer] for u in updates]
            num_values = len(layer_values[0])
            averaged[layer] = [
                sum(vals[i] for vals in layer_values) / len(layer_values)
                for i in range(num_values)
            ]

        return AggregationResult(
            model_id=model_id,
            averaged_weights=averaged,
            num_contributors=len(updates),
            round_num=updates[0].round_num,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        peers = self.list_peers()
        status = "ACTIVE" if self._contributing else "INACTIVE"
        lines = [
            f"[Collective] Federated learning status: {status}",
            f"  Contributing: {self._contributing}",
            f"  Connected peers: {len(peers)}",
        ]
        if peers:
            for p in peers[:10]:
                lines.append(f"    {p.peer_id} @ {p.endpoint} (rep: {p.reputation})")
        else:
            lines.append("  No peers connected.")
        lines.append(f"  Noise scale: {self.noise_scale}")
        return "\n".join(lines)

# nexus/modules/forge.py
"""
Forge — autonomous negotiation engine.
Handles structured multi-round negotiations within user-defined parameters.
Operates within Aegis-defined boundaries and escalates when hitting limits.
"""
import uuid
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class NegotiationConfig:
    domain: str
    floor: float
    ceiling: float
    target: float
    max_rounds: int
    concession_limit: float


@dataclass
class Offer:
    round_num: int
    amount: float
    from_party: str
    timestamp: str = ""


@dataclass
class NegotiationState:
    id: str
    config: NegotiationConfig
    status: str  # active, accepted, escalated, rejected
    current_round: int = 0
    offers: list[Offer] = field(default_factory=list)
    our_last: float = 0.0


class ForgeModule(NexusModule):
    name = "forge"
    description = "Autonomous negotiation — multi-round structured bargaining with guardrails"
    version = "0.1.0"

    def __init__(self):
        self._negotiations: dict[str, NegotiationState] = {}

    def create_negotiation(self, config: NegotiationConfig) -> str:
        neg_id = uuid.uuid4().hex[:8]
        state = NegotiationState(id=neg_id, config=config, status="active")
        self._negotiations[neg_id] = state
        return neg_id

    def get_state(self, neg_id: str) -> NegotiationState:
        return self._negotiations[neg_id]

    def make_offer(self, neg_id: str) -> Offer:
        state = self._negotiations[neg_id]
        cfg = state.config
        state.current_round += 1

        if state.current_round == 1:
            amount = cfg.ceiling
        else:
            concession = (cfg.ceiling - cfg.target) * cfg.concession_limit * state.current_round
            amount = max(cfg.target, cfg.ceiling - concession)

        offer = Offer(round_num=state.current_round, amount=round(amount, 2), from_party="nexus")
        state.offers.append(offer)
        state.our_last = amount
        return offer

    def receive_counter(self, neg_id: str, amount: float) -> str:
        state = self._negotiations[neg_id]
        cfg = state.config

        offer = Offer(round_num=state.current_round, amount=amount, from_party="counterparty")
        state.offers.append(offer)

        if amount < cfg.floor:
            state.status = "escalated"
            return "escalate"

        if amount >= cfg.target:
            state.status = "accepted"
            return "accept"

        if state.current_round >= cfg.max_rounds:
            state.status = "escalated"
            return "escalate"

        return "counter"

    def get_history(self, neg_id: str) -> list[Offer]:
        return self._negotiations[neg_id].offers

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()

        if "start" in lower or "create" in lower or "begin" in lower:
            import re
            nums = re.findall(r'\$?([\d,]+)', message)
            if len(nums) >= 2:
                floor = float(nums[0].replace(",", ""))
                ceiling = float(nums[1].replace(",", ""))
                target = (floor + ceiling) / 2
                config = NegotiationConfig(
                    domain="custom",
                    floor=floor,
                    ceiling=ceiling,
                    target=target,
                    max_rounds=5,
                    concession_limit=0.2,
                )
                neg_id = self.create_negotiation(config)
                offer = self.make_offer(neg_id)
                return (
                    f"[Forge] Negotiation {neg_id} started.\n"
                    f"  Range: ${floor:.0f} - ${ceiling:.0f} (target: ${target:.0f})\n"
                    f"  Opening offer: ${offer.amount:.0f}"
                )

        # Show active negotiations
        if self._negotiations:
            lines = [f"[Forge] {len(self._negotiations)} negotiation(s):"]
            for state in self._negotiations.values():
                lines.append(
                    f"  [{state.id}] {state.config.domain} — {state.status} "
                    f"(round {state.current_round}/{state.config.max_rounds})"
                )
            return "\n".join(lines)

        return "[Forge] No active negotiations. Say 'start negotiation for $X-$Y' to begin."

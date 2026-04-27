"""
Herald — agent-to-agent communication handler.
Manages discovery, authentication, and message exchange with external agents.
Maintains reputation scores based on interaction outcomes.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class ExternalAgent:
    agent_id: str
    name: str
    endpoint: str
    trust_grant: int
    reputation: float = 0.5
    _successes: int = field(default=0, repr=False)
    _failures: int = field(default=0, repr=False)


@dataclass
class A2AMessage:
    id: str
    from_agent: str
    to_agent: str
    content: str
    msg_type: str
    timestamp: str


class HeraldModule(NexusModule):
    name = "herald"
    description = "Agent-to-agent communication — discovery, auth, and message exchange"
    version = "0.1.0"

    def __init__(self):
        self._agents: dict[str, ExternalAgent] = {}
        self._messages: list[A2AMessage] = []

    def register_agent(
        self,
        agent_id: str,
        name: str,
        endpoint: str,
        trust_grant: int,
    ) -> ExternalAgent:
        agent = ExternalAgent(
            agent_id=agent_id,
            name=name,
            endpoint=endpoint,
            trust_grant=trust_grant,
        )
        self._agents[agent_id] = agent
        return agent

    def revoke_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> ExternalAgent | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[ExternalAgent]:
        return list(self._agents.values())

    def compose_message(
        self,
        to_agent: str,
        content: str,
        msg_type: str,
    ) -> A2AMessage:
        if to_agent not in self._agents:
            raise KeyError(f"Unknown agent: {to_agent}")
        msg = A2AMessage(
            id=uuid.uuid4().hex[:10],
            from_agent="nexus-local",
            to_agent=to_agent,
            content=content,
            msg_type=msg_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._messages.append(msg)
        return msg

    def message_history(self, agent_id: str) -> list[A2AMessage]:
        return [m for m in self._messages if m.to_agent == agent_id or m.from_agent == agent_id]

    def record_interaction_outcome(self, agent_id: str, success: bool) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            return
        if success:
            agent._successes += 1
        else:
            agent._failures += 1
        total = agent._successes + agent._failures
        agent.reputation = round(agent._successes / total, 3) if total > 0 else 0.5

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._agents:
            return "[Herald] No external agents connected."
        lines = [f"[Herald] {len(self._agents)} connected agent(s):"]
        for agent in self._agents.values():
            lines.append(
                f"  - {agent.name} ({agent.agent_id})"
                f" | trust: {agent.trust_grant} | reputation: {agent.reputation}"
            )
        return "\n".join(lines)

"""
Cipher — trust-scored information.
Every piece of information gets a provenance chain and computed trust score.
When sources conflict, Cipher surfaces the conflict explicitly.
"""
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule

_DEFAULT_UNKNOWN_TRUST = 0.15


@dataclass
class SourceProfile:
    name: str
    base_trust: float
    category: str


@dataclass
class Claim:
    claim_id: str
    value: str
    source: str
    trust: float


class CipherModule(NexusModule):
    name = "cipher"
    description = "Trust-scored information with provenance chains and conflict detection"
    version = "0.1.0"

    def __init__(self):
        self._sources: dict[str, SourceProfile] = {}
        self._claims: dict[str, list[Claim]] = {}

    def register_source(self, profile: SourceProfile) -> None:
        self._sources[profile.name] = profile

    def list_sources(self) -> list[SourceProfile]:
        return list(self._sources.values())

    def score(self, information: str, source: str) -> dict[str, Any]:
        """Score a piece of information based on its source."""
        profile = self._sources.get(source)
        trust = profile.base_trust if profile else _DEFAULT_UNKNOWN_TRUST
        return {
            "information": information,
            "source": source,
            "trust_score": trust,
            "category": profile.category if profile else "unknown",
        }

    def record_claim(self, claim_id: str, value: str, source: str, trust: float) -> None:
        """Record a claim with its source and trust score."""
        claim = Claim(claim_id=claim_id, value=value, source=source, trust=trust)
        self._claims.setdefault(claim_id, []).append(claim)

    def get_conflicts(self) -> list[dict[str, Any]]:
        """Find claims where different sources report different values."""
        conflicts = []
        for claim_id, claims in self._claims.items():
            values = {c.value for c in claims}
            if len(values) > 1:
                conflicts.append({
                    "claim_id": claim_id,
                    "positions": [
                        {"value": c.value, "source": c.source, "trust": c.trust}
                        for c in sorted(claims, key=lambda x: x.trust, reverse=True)
                    ],
                })
        return conflicts

    def get_provenance(self, claim_id: str) -> list[dict[str, Any]]:
        """Get the provenance chain for a claim."""
        claims = self._claims.get(claim_id, [])
        return [
            {"source": c.source, "value": c.value, "trust": c.trust}
            for c in sorted(claims, key=lambda x: x.trust, reverse=True)
        ]

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()
        if "conflict" in lower:
            conflicts = self.get_conflicts()
            if not conflicts:
                return "[Cipher] No conflicting claims detected."
            lines = ["[Cipher] Detected conflicts:"]
            for c in conflicts:
                lines.append(f"  Claim: {c['claim_id']}")
                for p in c["positions"]:
                    lines.append(f"    - {p['source']} says '{p['value']}' (trust: {p['trust']})")
            return "\n".join(lines)
        # Check if asking about a specific claim
        for claim_id in self._claims:
            if claim_id.lower() in lower:
                chain = self.get_provenance(claim_id)
                lines = [f"[Cipher] Provenance for '{claim_id}':"]
                for entry in chain:
                    lines.append(f"  - {entry['source']}: '{entry['value']}' (trust: {entry['trust']})")
                return "\n".join(lines)
        # Default: show source registry
        if not self._sources:
            return "[Cipher] No sources registered."
        lines = ["[Cipher] Registered sources:"]
        for s in sorted(self._sources.values(), key=lambda x: x.base_trust, reverse=True):
            lines.append(f"  - {s.name}: {s.base_trust} ({s.category})")
        return "\n".join(lines)

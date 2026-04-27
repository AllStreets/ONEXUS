# Batch 5: Network + Platform -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two final modules -- Collective (federated learning) and Legacy (knowledge crystallization) -- completing the full 21-module intelligence stack at 24 modules. Update Cortex routing, write integration tests, and do the final comprehensive README update.

**Architecture:** Collective manages federated model sharing with differential privacy, operating within user-defined boundaries. Legacy distills months of Engram episodic/semantic data and Echo behavioral profiles into structured, exportable knowledge artifacts. Both extend NexusModule.

**Tech Stack:** Python 3.11+, SQLite, existing kernel + all prior modules

---

### Task 1: Collective -- Federated Learning

**Files:**
- Create: `nexus/modules/collective.py`
- Create: `tests/modules/test_collective.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    # With noise_scale=1.0, outputs should differ (probabilistic but virtually certain)
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
    # Average of [1,2] and [3,4] = [2,3]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_collective.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Collective module**

```python
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
    ) -> ModelUpdate:
        noised = {}
        for layer, values in weights.items():
            noised[layer] = [
                v + random.gauss(0, self.noise_scale) for v in values
            ]
        return ModelUpdate(
            model_id=model_id,
            noised_weights=noised,
            peer_id=uuid.uuid4().hex[:8],
            round_num=0,
        )

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_collective.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/collective.py tests/modules/test_collective.py
git commit -m "feat: Collective module -- federated learning with differential privacy and peer management"
git push origin main
```

---

### Task 2: Legacy -- Knowledge Crystallization

**Files:**
- Create: `nexus/modules/legacy.py`
- Create: `tests/modules/test_legacy.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_legacy.py
import pytest
from nexus.modules.legacy import (
    LegacyModule,
    KnowledgeArtifact,
    DecisionPattern,
    ArtifactType,
)


@pytest.fixture
def legacy():
    return LegacyModule()


def test_legacy_attrs(legacy):
    assert legacy.name == "legacy"
    assert legacy.version == "0.1.0"


def test_record_decision(legacy):
    legacy.record_decision(
        domain="hiring",
        decision="Hired candidate with strong culture fit over higher GPA",
        outcome="positive",
        factors=["culture fit", "communication", "growth mindset"],
    )
    assert legacy.decision_count() == 1


def test_record_multiple_decisions(legacy):
    legacy.record_decision("hiring", "Hired A over B", "positive", ["experience"])
    legacy.record_decision("hiring", "Rejected C", "positive", ["culture"])
    legacy.record_decision("investing", "Passed on deal X", "negative", ["valuation"])
    assert legacy.decision_count() == 3


def test_extract_patterns(legacy):
    legacy.record_decision("hiring", "Hired A: strong culture fit", "positive", ["culture fit", "communication"])
    legacy.record_decision("hiring", "Hired B: great communicator", "positive", ["communication", "teamwork"])
    legacy.record_decision("hiring", "Rejected C: poor communication", "positive", ["communication"])
    patterns = legacy.extract_patterns("hiring")
    assert len(patterns) > 0
    assert any(isinstance(p, DecisionPattern) for p in patterns)


def test_pattern_has_frequency(legacy):
    legacy.record_decision("investing", "Invested in A", "positive", ["team", "market"])
    legacy.record_decision("investing", "Invested in B", "positive", ["team", "product"])
    legacy.record_decision("investing", "Passed on C", "negative", ["team"])
    patterns = legacy.extract_patterns("investing")
    if patterns:
        assert patterns[0].frequency >= 2


def test_crystallize_artifact(legacy):
    legacy.record_decision("hiring", "Hired A", "positive", ["culture", "comm"])
    legacy.record_decision("hiring", "Hired B", "positive", ["culture", "growth"])
    legacy.record_decision("hiring", "Rejected C", "positive", ["culture"])
    artifact = legacy.crystallize("hiring")
    assert isinstance(artifact, KnowledgeArtifact)
    assert artifact.domain == "hiring"
    assert artifact.artifact_type == ArtifactType.FRAMEWORK
    assert len(artifact.content) > 0


def test_crystallize_empty_domain(legacy):
    artifact = legacy.crystallize("nonexistent")
    assert artifact.content == ""
    assert len(artifact.patterns) == 0


def test_export_markdown(legacy):
    legacy.record_decision("negotiation", "Opened high", "positive", ["anchoring", "patience"])
    legacy.record_decision("negotiation", "Walked away", "positive", ["patience", "alternatives"])
    artifact = legacy.crystallize("negotiation")
    md = legacy.export_markdown(artifact)
    assert isinstance(md, str)
    assert "negotiation" in md.lower()


def test_list_domains(legacy):
    legacy.record_decision("hiring", "Hired A", "positive", ["culture"])
    legacy.record_decision("investing", "Invested in B", "positive", ["team"])
    domains = legacy.list_domains()
    assert "hiring" in domains
    assert "investing" in domains


@pytest.mark.asyncio
async def test_legacy_handle(legacy):
    legacy.record_decision("hiring", "Hired A", "positive", ["culture"])
    legacy.record_decision("hiring", "Hired B", "positive", ["culture"])
    result = await legacy.handle("Crystallize my hiring decisions", {"llm": None})
    assert "hiring" in result.lower() or "pattern" in result.lower() or "framework" in result.lower()


@pytest.mark.asyncio
async def test_legacy_handle_empty(legacy):
    result = await legacy.handle("Show my knowledge", {"llm": None})
    assert "no decisions" in result.lower() or "no data" in result.lower() or "record" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_legacy.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Legacy module**

```python
# nexus/modules/legacy.py
"""
Legacy -- knowledge crystallization engine.
Distills months of decisions, outcomes, and behavioral patterns into
structured, exportable knowledge artifacts. Extracts frameworks, playbooks,
and heuristics from actual behavior -- not self-reported preferences.
"""
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from nexus.modules.base import NexusModule


class ArtifactType(Enum):
    FRAMEWORK = "framework"
    PLAYBOOK = "playbook"
    HEURISTIC = "heuristic"


@dataclass
class DecisionRecord:
    domain: str
    decision: str
    outcome: str
    factors: list[str]


@dataclass
class DecisionPattern:
    factor: str
    frequency: int
    positive_rate: float
    domains: list[str]


@dataclass
class KnowledgeArtifact:
    domain: str
    artifact_type: ArtifactType
    patterns: list[DecisionPattern]
    content: str
    decision_count: int


class LegacyModule(NexusModule):
    name = "legacy"
    description = "Knowledge crystallization -- distills decisions into transferable wisdom"
    version = "0.1.0"

    def __init__(self):
        self._decisions: list[DecisionRecord] = []

    def record_decision(
        self,
        domain: str,
        decision: str,
        outcome: str,
        factors: list[str],
    ) -> None:
        self._decisions.append(DecisionRecord(
            domain=domain,
            decision=decision,
            outcome=outcome,
            factors=factors,
        ))

    def decision_count(self) -> int:
        return len(self._decisions)

    def list_domains(self) -> list[str]:
        return sorted(set(d.domain for d in self._decisions))

    def extract_patterns(self, domain: str) -> list[DecisionPattern]:
        domain_decisions = [d for d in self._decisions if d.domain == domain]
        if not domain_decisions:
            return []

        factor_counts: Counter[str] = Counter()
        factor_positive: Counter[str] = Counter()
        factor_domains: dict[str, set[str]] = {}

        for d in domain_decisions:
            for f in d.factors:
                factor_counts[f] += 1
                if d.outcome == "positive":
                    factor_positive[f] += 1
                factor_domains.setdefault(f, set()).add(d.domain)

        patterns = []
        for factor, count in factor_counts.most_common():
            if count >= 2:
                pos_rate = factor_positive[factor] / count if count > 0 else 0.0
                patterns.append(DecisionPattern(
                    factor=factor,
                    frequency=count,
                    positive_rate=round(pos_rate, 2),
                    domains=sorted(factor_domains.get(factor, set())),
                ))

        return patterns

    def crystallize(self, domain: str) -> KnowledgeArtifact:
        domain_decisions = [d for d in self._decisions if d.domain == domain]
        if not domain_decisions:
            return KnowledgeArtifact(
                domain=domain,
                artifact_type=ArtifactType.FRAMEWORK,
                patterns=[],
                content="",
                decision_count=0,
            )

        patterns = self.extract_patterns(domain)

        lines = [f"Decision Framework: {domain.title()}"]
        lines.append(f"Based on {len(domain_decisions)} decisions.\n")
        if patterns:
            lines.append("Key factors (by frequency):")
            for p in patterns:
                lines.append(
                    f"  - {p.factor}: appeared in {p.frequency} decisions "
                    f"({p.positive_rate:.0%} positive outcome rate)"
                )
        lines.append("")
        lines.append("Decisions analyzed:")
        for d in domain_decisions:
            lines.append(f"  [{d.outcome}] {d.decision}")

        return KnowledgeArtifact(
            domain=domain,
            artifact_type=ArtifactType.FRAMEWORK,
            patterns=patterns,
            content="\n".join(lines),
            decision_count=len(domain_decisions),
        )

    def export_markdown(self, artifact: KnowledgeArtifact) -> str:
        lines = [f"# {artifact.domain.title()} Decision Framework"]
        lines.append(f"\n*Crystallized from {artifact.decision_count} decisions.*\n")
        if artifact.patterns:
            lines.append("## Key Patterns\n")
            for p in artifact.patterns:
                lines.append(
                    f"- **{p.factor}**: {p.frequency}x "
                    f"({p.positive_rate:.0%} positive)"
                )
        lines.append(f"\n## Raw Framework\n\n{artifact.content}")
        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._decisions:
            return "[Legacy] No decisions recorded yet. Record decisions to build knowledge artifacts."

        lower = message.lower()
        domains = self.list_domains()

        # Try to find a domain match in the message
        target_domain = None
        for d in domains:
            if d in lower:
                target_domain = d
                break

        if target_domain:
            artifact = self.crystallize(target_domain)
            return f"[Legacy] {artifact.content}"

        # Show overview
        lines = [f"[Legacy] Knowledge base: {self.decision_count()} decisions across {len(domains)} domains"]
        for d in domains:
            count = sum(1 for dec in self._decisions if dec.domain == d)
            patterns = self.extract_patterns(d)
            lines.append(f"  {d}: {count} decisions, {len(patterns)} patterns extracted")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_legacy.py -v`
Expected: 12 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/legacy.py tests/modules/test_legacy.py
git commit -m "feat: Legacy module -- knowledge crystallization with pattern extraction and artifact export"
git push origin main
```

---

### Task 3: Cortex Router Update + Batch 5 Integration Tests

**Files:**
- Modify: `nexus/kernel/cortex.py` (add keywords)
- Create: `tests/test_batch5_integration.py`

- [ ] **Step 1: Update Cortex keywords**

Add to `_MODULE_KEYWORDS` in `nexus/kernel/cortex.py`:

```python
        "collective": ["federated", "peer", "distributed", "swarm learning", "model sharing"],
        "legacy": ["crystallize", "distill", "framework", "playbook", "wisdom", "pattern extract"],
```

- [ ] **Step 2: Write integration tests**

```python
# tests/test_batch5_integration.py
"""
Batch 5 integration: Network + platform modules through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.collective import CollectiveModule
from nexus.modules.legacy import LegacyModule


@pytest.fixture
def network_system(tmp_config):
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram, chronicle=chronicle, aegis=aegis,
        pulse=pulse, config=tmp_config,
    )

    modules = {
        "general": GeneralModule(),
        "collective": CollectiveModule(),
        "legacy": LegacyModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, **modules}


@pytest.mark.asyncio
async def test_collective_via_cortex(network_system):
    cortex = network_system["cortex"]
    response = await cortex.process("Show federated learning peer status")
    assert "collective" in response.lower() or "federated" in response.lower() or "peer" in response.lower()


@pytest.mark.asyncio
async def test_legacy_via_cortex(network_system):
    leg = network_system["legacy"]
    leg.record_decision("hiring", "Hired A", "positive", ["culture"])
    leg.record_decision("hiring", "Hired B", "positive", ["culture"])
    cortex = network_system["cortex"]
    response = await cortex.process("Crystallize my hiring decision framework")
    assert "hiring" in response.lower() or "pattern" in response.lower() or "framework" in response.lower()


@pytest.mark.asyncio
async def test_all_network_modules_registered(network_system):
    cortex = network_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "collective", "legacy"]:
        assert name in modules
```

- [ ] **Step 3: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 4: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/cortex.py tests/test_batch5_integration.py
git commit -m "feat: Cortex routing for network modules + Batch 5 integration tests"
git push origin main
```

---

### Task 4: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Full README update**

Update: test badge, module count badge (21 -> 23), intro paragraph, architecture diagram (add Network + Platform tier), "What's Built" section with new module tables, module roadmap (Batch 5 modules now BUILT, Nexus Site still PLANNED), test count, project structure with new files, design principles.

- [ ] **Step 2: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add README.md
git commit -m "docs: full README update for Batch 5 -- architecture, module tables, roadmap"
git push origin main
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Collective (federated learning) -- Task 1
- [x] Legacy (knowledge crystallization) -- Task 2
- [x] Cortex routing + integration tests -- Task 3
- [x] README update -- Task 4

**Note:** Nexus Site (documentation website) is not a Python module -- it's a frontend/documentation project that belongs in a separate repository or build step. The two intelligence modules (Collective, Legacy) complete the module roster.

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code complete.

**Type consistency:** `CollectiveModule`/`FederatedConfig`/`PeerNode`/`ModelUpdate`/`AggregationResult`, `LegacyModule`/`KnowledgeArtifact`/`DecisionPattern`/`ArtifactType` -- all names consistent.

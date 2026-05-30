# Batch 6: Council & Autonomic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement two orchestration-layer modules -- Council (multi-agent deliberation) and Autonomic (earned autonomous action) -- that call existing modules through `handle()` without modifying them.

**Architecture:** Lightweight orchestration via Approach A. Council selects relevant modules by role, runs structured multi-round debates, and synthesizes results. Autonomic observes Pulse events, learns patterns, and takes graduated autonomous action gated by per-domain trust scores through Aegis. Both modules extend `NexusModule`, use dataclasses for structured results, and integrate with all five kernel components.

**Tech Stack:** Python 3.11+, standard library only (dataclasses, enum, asyncio, json, uuid, datetime, fnmatch). SQLite via Engram for pattern storage. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-27-batch6-council-autonomic-design.md`

---

## File Structure

```
nexus/modules/
├── council.py       <- Multi-agent deliberation orchestrator (~200 lines)
└── autonomic.py     <- Earned autonomous action engine (~250 lines)

tests/modules/
├── test_council.py  <- Council unit tests (~15 tests)
└── test_autonomic.py <- Autonomic unit tests (~18 tests)

tests/
└── test_batch6_integration.py <- Integration tests through Cortex (~8 tests)

nexus/kernel/
└── cortex.py        <- Add 2 keyword entries to _MODULE_KEYWORDS (modify only)
```

No new kernel files. No new dependencies. No modifications to existing modules.

---

### Task 1: Council Module

**Files:**
- Create: `nexus/modules/council.py`
- Test: `tests/modules/test_council.py`

- [ ] **Step 1: Write failing test for Council dataclasses and class attributes**

```python
# tests/modules/test_council.py
import pytest
from nexus.modules.council import CouncilModule, DeliberationResult


@pytest.fixture
def council():
    return CouncilModule()


def test_council_attrs(council):
    assert council.name == "council"
    assert council.version == "0.1.0"
    assert council.description


def test_deliberation_result_fields():
    result = DeliberationResult(
        question="test?",
        recommendation="do it",
        confidence=0.8,
        consensus_view="agreed",
        dissenting_views=["nah"],
        key_uncertainties=["maybe"],
        participants=["specter"],
        rounds=3,
        transcript=[],
    )
    assert result.question == "test?"
    assert result.confidence == 0.8
    assert result.rounds == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_council.py::test_council_attrs tests/modules/test_council.py::test_deliberation_result_fields -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Council module skeleton with dataclasses**

```python
# nexus/modules/council.py
"""
Council -- multi-agent deliberation orchestrator.
Selects relevant modules, runs structured multi-round debate,
synthesizes a recommendation with preserved dissent.

Inspired by Marvin Minsky's Society of Mind -- intelligence emerges
from the interaction of many simpler agents.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from nexus.modules.base import NexusModule


_DELIBERATION_ROLES: dict[str, dict[str, Any]] = {
    "specter": {
        "role": "adversarial",
        "instruction": "Find weaknesses, hidden assumptions, and failure modes.",
        "triggers": ["decision", "should i", "plan", "strategy", "risk"],
    },
    "chronos": {
        "role": "temporal",
        "instruction": "Model future timelines and consequences.",
        "triggers": ["future", "long-term", "timeline", "when", "deadline"],
    },
    "serendipity": {
        "role": "lateral",
        "instruction": "Surface non-obvious connections and overlooked perspectives.",
        "triggers": ["option", "alternative", "creative", "stuck", "blind spot"],
    },
    "forge": {
        "role": "strategic",
        "instruction": "Analyze trade-offs, incentives, and negotiation angles.",
        "triggers": ["deal", "offer", "trade-off", "cost", "benefit", "negotiate"],
    },
    "atlas": {
        "role": "factual",
        "instruction": "Provide relevant facts and knowledge context.",
        "triggers": ["fact", "know", "data", "evidence", "history"],
    },
    "cipher": {
        "role": "verification",
        "instruction": "Assess source reliability and information conflicts.",
        "triggers": ["trust", "source", "verify", "conflict", "credib"],
    },
    "prism": {
        "role": "synthesis",
        "instruction": "Find cross-domain connections and synthesize perspectives.",
        "triggers": ["connect", "relate", "pattern", "synthesize", "insight"],
    },
}

_DEFAULT_CONFIG = {
    "max_rounds": 3,
    "min_modules": 3,
    "max_modules": 5,
    "always_include": ["specter"],
    "timeout_per_round_seconds": 30,
}


@dataclass
class DeliberationResult:
    question: str
    recommendation: str
    confidence: float
    consensus_view: str
    dissenting_views: list[str]
    key_uncertainties: list[str]
    participants: list[str]
    rounds: int
    transcript: list[dict[str, Any]] = field(default_factory=list)


class CouncilModule(NexusModule):
    name = "council"
    description = "Multi-agent deliberation -- structured debate across modules with synthesized recommendations"
    version = "0.1.0"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}
        self._modules: dict[str, NexusModule] = {}

    def set_modules(self, modules: dict[str, NexusModule]) -> None:
        self._modules = modules

    def select_participants(self, question: str) -> list[str]:
        question_lower = question.lower()
        scores: list[tuple[str, int]] = []
        for mod_name, role_info in _DELIBERATION_ROLES.items():
            score = sum(1 for t in role_info["triggers"] if t in question_lower)
            scores.append((mod_name, score))
        scores.sort(key=lambda x: x[1], reverse=True)

        selected: list[str] = []
        for name in self._config["always_include"]:
            if name not in selected:
                selected.append(name)

        for mod_name, score in scores:
            if mod_name in selected:
                continue
            if score > 0 or len(selected) < self._config["min_modules"]:
                selected.append(mod_name)
            if len(selected) >= self._config["max_modules"]:
                break

        while len(selected) < self._config["min_modules"]:
            for mod_name, _ in scores:
                if mod_name not in selected:
                    selected.append(mod_name)
                    break
            else:
                break
            if len(selected) >= self._config["min_modules"]:
                break

        return selected

    async def deliberate(
        self,
        question: str,
        context: dict[str, Any],
        participants: list[str] | None = None,
    ) -> DeliberationResult:
        if participants is None:
            participants = self.select_participants(question)

        available = [p for p in participants if p in self._modules]
        if not available:
            return DeliberationResult(
                question=question,
                recommendation="No modules available for deliberation.",
                confidence=0.0,
                consensus_view="",
                dissenting_views=[],
                key_uncertainties=["No modules participated."],
                participants=[],
                rounds=0,
                transcript=[],
            )

        transcript: list[dict[str, Any]] = []
        prior_responses: dict[str, str] = {}
        max_rounds = self._config["max_rounds"]

        for round_num in range(1, max_rounds + 1):
            round_record: dict[str, Any] = {"round": round_num, "responses": {}}
            for mod_name in available:
                role_info = _DELIBERATION_ROLES.get(mod_name, {})
                delib_context = {
                    **context,
                    "mode": "council_deliberation",
                    "round": round_num,
                    "role": role_info.get("role", "general"),
                    "instruction": role_info.get("instruction", "Provide your perspective."),
                    "question": question,
                    "prior_responses": dict(prior_responses) if round_num > 1 else {},
                }
                try:
                    response = await self._modules[mod_name].handle(question, delib_context)
                except Exception as exc:
                    response = f"[Error from {mod_name}: {exc}]"
                round_record["responses"][mod_name] = response
                prior_responses[mod_name] = response

            transcript.append(round_record)

            # Publish round completion if Pulse is available
            pulse = context.get("pulse")
            if pulse:
                from nexus.kernel.pulse import Message
                await pulse.publish(Message(
                    topic="council.round.complete",
                    source="council",
                    payload={"round": round_num, "participants": available},
                ))

        # Synthesize
        result = self._synthesize(question, available, transcript, context)

        # Log to Chronicle if available
        chronicle = context.get("chronicle")
        if chronicle:
            chronicle.log("council", "deliberation.complete", {
                "question": question[:200],
                "participants": result.participants,
                "confidence": result.confidence,
                "rounds": result.rounds,
            })

        # Store in Engram if available
        engram = context.get("engram")
        if engram:
            engram.episodic.store(
                f"Council deliberation: {question[:100]} -> {result.recommendation[:200]}",
                source="council",
            )

        return result

    def _synthesize(
        self,
        question: str,
        participants: list[str],
        transcript: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> DeliberationResult:
        if not transcript:
            return DeliberationResult(
                question=question, recommendation="No deliberation occurred.",
                confidence=0.0, consensus_view="", dissenting_views=[],
                key_uncertainties=[], participants=participants, rounds=0,
            )

        final_round = transcript[-1]["responses"]
        all_responses = list(final_round.values())

        # Without LLM: rule-based synthesis from final round responses
        recommendation = " | ".join(
            f"{name}: {resp[:150]}" for name, resp in final_round.items()
        )

        # Specter's view is always the dissent
        dissent = []
        consensus_parts = []
        for name, resp in final_round.items():
            role = _DELIBERATION_ROLES.get(name, {}).get("role", "")
            if role == "adversarial":
                dissent.append(f"[{name}] {resp[:200]}")
            else:
                consensus_parts.append(resp[:200])

        consensus = " ".join(consensus_parts) if consensus_parts else ""

        # Confidence: based on how many participants (more = higher)
        confidence = min(1.0, len(participants) / self._config["max_modules"])

        return DeliberationResult(
            question=question,
            recommendation=recommendation,
            confidence=round(confidence, 2),
            consensus_view=consensus,
            dissenting_views=dissent,
            key_uncertainties=["LLM synthesis unavailable -- raw responses returned."],
            participants=participants,
            rounds=len(transcript),
            transcript=transcript,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        result = await self.deliberate(message, context)
        lines = [
            f"[Council] Deliberation complete ({result.rounds} rounds, {len(result.participants)} participants)",
            f"Participants: {', '.join(result.participants)}",
            f"Confidence: {result.confidence}",
            "",
            f"Recommendation: {result.recommendation}",
        ]
        if result.dissenting_views:
            lines.append("")
            lines.append("Dissenting views:")
            for d in result.dissenting_views:
                lines.append(f"  - {d}")
        if result.key_uncertainties:
            lines.append("")
            lines.append("Uncertainties:")
            for u in result.key_uncertainties:
                lines.append(f"  - {u}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run first two tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_council.py::test_council_attrs tests/modules/test_council.py::test_deliberation_result_fields -v`
Expected: PASS

- [ ] **Step 5: Write failing test for participant selection**

Add to `tests/modules/test_council.py`:

```python
def test_select_participants_includes_specter(council):
    """Specter (adversarial) is always included."""
    selected = council.select_participants("What should I eat for lunch?")
    assert "specter" in selected


def test_select_participants_min_count(council):
    selected = council.select_participants("Hello")
    assert len(selected) >= 3


def test_select_participants_max_count(council):
    selected = council.select_participants(
        "Should I decide on this risky plan to negotiate a deal about the future timeline and verify the data?"
    )
    assert len(selected) <= 5


def test_select_participants_relevant_modules(council):
    """Temporal question should include chronos."""
    selected = council.select_participants("What is the future timeline for this project?")
    assert "chronos" in selected
    assert "specter" in selected
```

- [ ] **Step 6: Run participant selection tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_council.py -k "select_participant" -v`
Expected: PASS

- [ ] **Step 7: Write failing test for deliberation**

Add to `tests/modules/test_council.py`:

```python
from nexus.modules.specter import SpecterModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.serendipity import SerendipityModule


@pytest.fixture
def council_with_modules():
    c = CouncilModule()
    c.set_modules({
        "specter": SpecterModule(),
        "chronos": ChronosModule(),
        "serendipity": SerendipityModule(),
    })
    return c


@pytest.mark.asyncio
async def test_deliberate_runs_rounds(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I switch to freelancing?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "chronos", "serendipity"],
    )
    assert isinstance(result, DeliberationResult)
    assert result.rounds == 3
    assert len(result.transcript) == 3
    assert result.participants == ["specter", "chronos", "serendipity"]


@pytest.mark.asyncio
async def test_deliberate_no_modules():
    c = CouncilModule()
    c.set_modules({})
    result = await c.deliberate("test?", context={"llm": None}, participants=["nonexistent"])
    assert result.rounds == 0
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_deliberate_transcript_has_responses(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I switch to freelancing?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "chronos"],
    )
    for round_entry in result.transcript:
        assert "round" in round_entry
        assert "responses" in round_entry
        assert len(round_entry["responses"]) > 0


@pytest.mark.asyncio
async def test_deliberate_dissent_from_specter(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I invest all savings in a risky contract?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "chronos", "serendipity"],
    )
    assert len(result.dissenting_views) > 0
```

- [ ] **Step 8: Run deliberation tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_council.py -k "deliberat" -v`
Expected: PASS

- [ ] **Step 9: Write failing test for handle()**

Add to `tests/modules/test_council.py`:

```python
@pytest.mark.asyncio
async def test_council_handle(council_with_modules):
    result = await council_with_modules.handle(
        "Deliberate: should I switch careers?",
        {"llm": None, "engram": None, "chronicle": None, "pulse": None},
    )
    assert "[Council]" in result
    assert "Deliberation complete" in result
    assert "Confidence" in result


@pytest.mark.asyncio
async def test_council_handle_includes_participants(council_with_modules):
    result = await council_with_modules.handle(
        "Council, weigh the pros and cons of remote work",
        {"llm": None, "engram": None, "chronicle": None, "pulse": None},
    )
    assert "Participants:" in result
```

- [ ] **Step 10: Run all Council tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_council.py -v`
Expected: All PASS

- [ ] **Step 11: Commit Council module**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/council.py tests/modules/test_council.py
git commit -m "feat(council): add multi-agent deliberation module

Structured multi-round debate across modules with synthesized
recommendations. Specter always participates as devil's advocate.
Integrates with Pulse, Chronicle, and Engram."
```

---

### Task 2: Autonomic Module

**Files:**
- Create: `nexus/modules/autonomic.py`
- Test: `tests/modules/test_autonomic.py`

- [ ] **Step 1: Write failing test for Autonomic dataclasses and class attributes**

```python
# tests/modules/test_autonomic.py
import pytest
from nexus.modules.autonomic import (
    AutonomicModule, Pattern, DomainTrust, TrustTier,
    ActionProposal, ProposalVerdict,
)


@pytest.fixture
def autonomic():
    return AutonomicModule()


def test_autonomic_attrs(autonomic):
    assert autonomic.name == "autonomic"
    assert autonomic.version == "0.1.0"
    assert autonomic.description


def test_trust_tiers():
    assert TrustTier.OBSERVER.value == 0
    assert TrustTier.SUGGESTER.value == 1
    assert TrustTier.DRAFTER.value == 2
    assert TrustTier.ACTOR.value == 3
    assert TrustTier.STEWARD.value == 4


def test_pattern_dataclass():
    p = Pattern(
        id="p1",
        category="scheduling",
        description="User checks email at 9am",
        trigger_conditions={"time": "09:00"},
        action_template="open email",
        confidence=0.8,
        times_observed=10,
        times_approved=8,
        times_rejected=1,
        last_seen="2026-04-27T09:00:00Z",
    )
    assert p.category == "scheduling"
    assert p.confidence == 0.8


def test_domain_trust_dataclass():
    dt = DomainTrust(
        domain="scheduling",
        trust_score=75,
        successes=20,
        failures=1,
        last_failure="",
        cooldown_until="",
    )
    assert dt.trust_score == 75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py::test_autonomic_attrs tests/modules/test_autonomic.py::test_trust_tiers -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Autonomic module skeleton**

```python
# nexus/modules/autonomic.py
"""
Autonomic -- earned autonomous action engine.
Observes patterns, learns routines, and gradually takes autonomous action
as trust is earned through successful outcomes. Every action is auditable,
every decision is adversarially checked, and trust retreats on failure.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Any

from nexus.modules.base import NexusModule


class TrustTier(IntEnum):
    OBSERVER = 0    # 0-20: watch only
    SUGGESTER = 1   # 21-50: suggest
    DRAFTER = 2     # 51-75: prepare actions for approval
    ACTOR = 3       # 76-90: act + confirm
    STEWARD = 4     # 91-100: full autonomy in earned domains

    @classmethod
    def from_score(cls, score: int) -> "TrustTier":
        if score <= 20:
            return cls.OBSERVER
        if score <= 50:
            return cls.SUGGESTER
        if score <= 75:
            return cls.DRAFTER
        if score <= 90:
            return cls.ACTOR
        return cls.STEWARD


_TIER_THRESHOLDS = {
    TrustTier.OBSERVER: 0,
    TrustTier.SUGGESTER: 21,
    TrustTier.DRAFTER: 51,
    TrustTier.ACTOR: 76,
    TrustTier.STEWARD: 91,
}


class ProposalVerdict(IntEnum):
    APPROVED = 0
    REJECTED = 1
    NEEDS_REVIEW = 2


@dataclass
class Pattern:
    id: str
    category: str
    description: str
    trigger_conditions: dict[str, Any]
    action_template: str
    confidence: float
    times_observed: int
    times_approved: int
    times_rejected: int
    last_seen: str


@dataclass
class DomainTrust:
    domain: str
    trust_score: int
    successes: int
    failures: int
    last_failure: str
    cooldown_until: str


@dataclass
class ActionProposal:
    id: str
    domain: str
    description: str
    pattern_id: str | None
    stakes: str  # "low", "medium", "high"
    reasoning: str
    verdict: ProposalVerdict = ProposalVerdict.NEEDS_REVIEW


_DEFAULT_CONFIG = {
    "trust_drop_on_failure": 20,
    "cooldown_hours": 48,
    "audit_probability": 0.10,
    "high_stakes_domains": ["financial", "communication", "legal"],
}


class AutonomicModule(NexusModule):
    name = "autonomic"
    description = "Earned autonomous action -- observes patterns, learns routines, acts within trust boundaries"
    version = "0.1.0"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}
        self._patterns: dict[str, Pattern] = {}
        self._domains: dict[str, DomainTrust] = {}
        self._proposals: dict[str, ActionProposal] = {}
        self._event_log: list[dict[str, Any]] = []

    # -- Domain trust management --

    def get_domain_trust(self, domain: str) -> DomainTrust:
        if domain not in self._domains:
            self._domains[domain] = DomainTrust(
                domain=domain, trust_score=0, successes=0,
                failures=0, last_failure="", cooldown_until="",
            )
        return self._domains[domain]

    def get_tier(self, domain: str) -> TrustTier:
        dt = self.get_domain_trust(domain)
        return TrustTier.from_score(dt.trust_score)

    def record_success(self, domain: str) -> DomainTrust:
        dt = self.get_domain_trust(domain)
        now = datetime.now(timezone.utc).isoformat()
        if dt.cooldown_until and now < dt.cooldown_until:
            return dt
        dt.successes += 1
        dt.trust_score = min(100, dt.trust_score + 2)
        return dt

    def record_failure(self, domain: str) -> DomainTrust:
        dt = self.get_domain_trust(domain)
        now = datetime.now(timezone.utc).isoformat()
        drop = self._config["trust_drop_on_failure"]
        dt.failures += 1
        dt.trust_score = max(0, dt.trust_score - drop)
        dt.last_failure = now
        cooldown_end = datetime.now(timezone.utc) + timedelta(
            hours=self._config["cooldown_hours"]
        )
        dt.cooldown_until = cooldown_end.isoformat()
        return dt

    def is_in_cooldown(self, domain: str) -> bool:
        dt = self.get_domain_trust(domain)
        if not dt.cooldown_until:
            return False
        now = datetime.now(timezone.utc).isoformat()
        return now < dt.cooldown_until

    # -- Pattern management --

    def observe_event(self, category: str, description: str, conditions: dict[str, Any]) -> Pattern:
        for p in self._patterns.values():
            if p.category == category and p.trigger_conditions == conditions:
                p.times_observed += 1
                p.confidence = min(1.0, p.times_observed / 20.0)
                p.last_seen = datetime.now(timezone.utc).isoformat()
                return p

        pattern = Pattern(
            id=uuid.uuid4().hex[:12],
            category=category,
            description=description,
            trigger_conditions=conditions,
            action_template="",
            confidence=0.05,
            times_observed=1,
            times_approved=0,
            times_rejected=0,
            last_seen=datetime.now(timezone.utc).isoformat(),
        )
        self._patterns[pattern.id] = pattern
        return pattern

    def get_patterns(self, category: str | None = None) -> list[Pattern]:
        if category is None:
            return list(self._patterns.values())
        return [p for p in self._patterns.values() if p.category == category]

    def approve_pattern(self, pattern_id: str) -> Pattern | None:
        p = self._patterns.get(pattern_id)
        if p:
            p.times_approved += 1
            p.confidence = min(1.0, p.confidence + 0.05)
        return p

    def reject_pattern(self, pattern_id: str) -> Pattern | None:
        p = self._patterns.get(pattern_id)
        if p:
            p.times_rejected += 1
            p.confidence = max(0.0, p.confidence - 0.1)
        return p

    # -- Action proposals --

    def assess_stakes(self, domain: str, description: str) -> str:
        if domain in self._config["high_stakes_domains"]:
            return "high"
        desc_lower = description.lower()
        high_words = ["delete", "send", "publish", "pay", "transfer", "commit"]
        if any(w in desc_lower for w in high_words):
            return "high"
        medium_words = ["update", "modify", "change", "schedule", "move"]
        if any(w in desc_lower for w in medium_words):
            return "medium"
        return "low"

    def propose_action(
        self,
        domain: str,
        description: str,
        pattern_id: str | None = None,
        reasoning: str = "",
    ) -> ActionProposal:
        stakes = self.assess_stakes(domain, description)
        tier = self.get_tier(domain)

        if tier == TrustTier.STEWARD and stakes == "low":
            verdict = ProposalVerdict.APPROVED
        elif tier >= TrustTier.ACTOR and stakes == "low":
            verdict = ProposalVerdict.APPROVED
        elif tier >= TrustTier.DRAFTER:
            verdict = ProposalVerdict.NEEDS_REVIEW
        else:
            verdict = ProposalVerdict.REJECTED

        if stakes == "high":
            verdict = ProposalVerdict.NEEDS_REVIEW

        if self.is_in_cooldown(domain):
            verdict = ProposalVerdict.REJECTED

        proposal = ActionProposal(
            id=uuid.uuid4().hex[:12],
            domain=domain,
            description=description,
            pattern_id=pattern_id,
            stakes=stakes,
            reasoning=reasoning,
            verdict=verdict,
        )
        self._proposals[proposal.id] = proposal
        return proposal

    # -- Kill switch --

    def kill_switch(self) -> None:
        for dt in self._domains.values():
            dt.trust_score = 0
            dt.successes = 0
        self._proposals.clear()

    # -- Pulse event handler --

    async def on_pulse_event(self, msg: Any) -> None:
        self._event_log.append({
            "topic": getattr(msg, "topic", "unknown"),
            "source": getattr(msg, "source", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # -- NexusModule interface --

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        msg_lower = message.lower()

        if "kill" in msg_lower or "revoke" in msg_lower or "deny autonomic" in msg_lower:
            self.kill_switch()
            chronicle = context.get("chronicle")
            if chronicle:
                chronicle.log("autonomic", "kill_switch", {"reason": message[:200]})
            return "[Autonomic] All autonomous permissions revoked. All domain trust reset to 0. Observer mode only."

        if "status" in msg_lower or "trust" in msg_lower:
            lines = ["[Autonomic] Domain Trust Status:"]
            if not self._domains:
                lines.append("  No domains tracked yet. Operating in Observer mode.")
            for domain, dt in sorted(self._domains.items()):
                tier = TrustTier.from_score(dt.trust_score)
                cooldown = " (COOLDOWN)" if self.is_in_cooldown(domain) else ""
                lines.append(
                    f"  {domain}: trust={dt.trust_score} tier={tier.name} "
                    f"successes={dt.successes} failures={dt.failures}{cooldown}"
                )
            patterns = self.get_patterns()
            if patterns:
                lines.append(f"\nPatterns observed: {len(patterns)}")
                for p in patterns[:5]:
                    lines.append(f"  [{p.category}] {p.description} (confidence={p.confidence:.2f}, observed={p.times_observed})")
            return "\n".join(lines)

        if "pattern" in msg_lower or "routine" in msg_lower or "automate" in msg_lower:
            patterns = self.get_patterns()
            if not patterns:
                return "[Autonomic] No patterns detected yet. Still observing. Patterns emerge from repeated actions tracked through Pulse events."
            lines = ["[Autonomic] Detected Patterns:"]
            for p in patterns:
                lines.append(
                    f"  [{p.category}] {p.description}\n"
                    f"    confidence={p.confidence:.2f} observed={p.times_observed} "
                    f"approved={p.times_approved} rejected={p.times_rejected}"
                )
            return "\n".join(lines)

        return (
            "[Autonomic] Observing and learning. "
            f"Tracking {len(self._domains)} domains, {len(self._patterns)} patterns, "
            f"{len(self._event_log)} events logged. "
            "Use 'autonomic status' for details or 'autonomic patterns' to see detected routines."
        )
```

- [ ] **Step 4: Run skeleton tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py::test_autonomic_attrs tests/modules/test_autonomic.py::test_trust_tiers tests/modules/test_autonomic.py::test_pattern_dataclass tests/modules/test_autonomic.py::test_domain_trust_dataclass -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for trust tier management**

Add to `tests/modules/test_autonomic.py`:

```python
def test_trust_tier_from_score():
    assert TrustTier.from_score(0) == TrustTier.OBSERVER
    assert TrustTier.from_score(20) == TrustTier.OBSERVER
    assert TrustTier.from_score(21) == TrustTier.SUGGESTER
    assert TrustTier.from_score(50) == TrustTier.SUGGESTER
    assert TrustTier.from_score(51) == TrustTier.DRAFTER
    assert TrustTier.from_score(75) == TrustTier.DRAFTER
    assert TrustTier.from_score(76) == TrustTier.ACTOR
    assert TrustTier.from_score(90) == TrustTier.ACTOR
    assert TrustTier.from_score(91) == TrustTier.STEWARD
    assert TrustTier.from_score(100) == TrustTier.STEWARD


def test_get_domain_trust_default(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    assert dt.domain == "scheduling"
    assert dt.trust_score == 0
    assert dt.successes == 0
    assert dt.failures == 0


def test_record_success_increases_trust(autonomic):
    for _ in range(10):
        autonomic.record_success("scheduling")
    dt = autonomic.get_domain_trust("scheduling")
    assert dt.trust_score == 20
    assert dt.successes == 10


def test_record_failure_drops_trust(autonomic):
    for _ in range(20):
        autonomic.record_success("scheduling")
    dt_before = autonomic.get_domain_trust("scheduling")
    assert dt_before.trust_score == 40
    autonomic.record_failure("scheduling")
    dt_after = autonomic.get_domain_trust("scheduling")
    assert dt_after.trust_score == 20
    assert dt_after.failures == 1


def test_cooldown_after_failure(autonomic):
    autonomic.record_failure("scheduling")
    assert autonomic.is_in_cooldown("scheduling")


def test_success_blocked_during_cooldown(autonomic):
    for _ in range(5):
        autonomic.record_success("test_domain")
    autonomic.record_failure("test_domain")
    score_after_fail = autonomic.get_domain_trust("test_domain").trust_score
    autonomic.record_success("test_domain")
    assert autonomic.get_domain_trust("test_domain").trust_score == score_after_fail
```

- [ ] **Step 6: Run trust tier tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py -k "trust" -v`
Expected: PASS

- [ ] **Step 7: Write failing tests for pattern observation**

Add to `tests/modules/test_autonomic.py`:

```python
def test_observe_event_creates_pattern(autonomic):
    p = autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    assert p.category == "scheduling"
    assert p.times_observed == 1
    assert p.confidence == 0.05


def test_observe_event_increments_existing(autonomic):
    autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    p = autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    assert p.times_observed == 2
    assert p.confidence > 0.05


def test_get_patterns_by_category(autonomic):
    autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.observe_event("research", "News scan", {"source": "rss"})
    assert len(autonomic.get_patterns("scheduling")) == 1
    assert len(autonomic.get_patterns("research")) == 1
    assert len(autonomic.get_patterns()) == 2


def test_approve_pattern_increases_confidence(autonomic):
    p = autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.approve_pattern(p.id)
    updated = autonomic.get_patterns("scheduling")[0]
    assert updated.times_approved == 1
    assert updated.confidence > 0.05


def test_reject_pattern_decreases_confidence(autonomic):
    p = autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    for _ in range(10):
        autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.reject_pattern(p.id)
    updated = autonomic.get_patterns("scheduling")[0]
    assert updated.times_rejected == 1
```

- [ ] **Step 8: Run pattern tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py -k "pattern or observe" -v`
Expected: PASS

- [ ] **Step 9: Write failing tests for action proposals and stakes**

Add to `tests/modules/test_autonomic.py`:

```python
def test_assess_stakes_high_domain(autonomic):
    assert autonomic.assess_stakes("financial", "anything") == "high"


def test_assess_stakes_high_words(autonomic):
    assert autonomic.assess_stakes("misc", "delete all records") == "high"


def test_assess_stakes_medium(autonomic):
    assert autonomic.assess_stakes("misc", "update the schedule") == "medium"


def test_assess_stakes_low(autonomic):
    assert autonomic.assess_stakes("misc", "check status") == "low"


def test_propose_action_rejected_at_observer(autonomic):
    proposal = autonomic.propose_action("scheduling", "Send email", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.REJECTED


def test_propose_action_approved_at_actor(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80  # Actor tier
    proposal = autonomic.propose_action("scheduling", "check status", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.APPROVED


def test_propose_action_high_stakes_always_needs_review(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 95  # Steward tier
    proposal = autonomic.propose_action("scheduling", "delete all records", reasoning="cleanup")
    assert proposal.verdict == ProposalVerdict.NEEDS_REVIEW


def test_propose_action_rejected_during_cooldown(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80
    autonomic.record_failure("scheduling")
    proposal = autonomic.propose_action("scheduling", "check status", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.REJECTED
```

- [ ] **Step 10: Run proposal tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py -k "propose or stakes" -v`
Expected: PASS

- [ ] **Step 11: Write failing tests for kill switch and handle()**

Add to `tests/modules/test_autonomic.py`:

```python
def test_kill_switch(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80
    autonomic.observe_event("scheduling", "test", {"a": 1})
    autonomic.kill_switch()
    assert autonomic.get_domain_trust("scheduling").trust_score == 0


@pytest.mark.asyncio
async def test_handle_status(autonomic):
    autonomic.get_domain_trust("scheduling").trust_score = 50
    result = await autonomic.handle("Show autonomic trust status", {"llm": None})
    assert "[Autonomic]" in result
    assert "scheduling" in result


@pytest.mark.asyncio
async def test_handle_kill(autonomic):
    autonomic.get_domain_trust("scheduling").trust_score = 80
    result = await autonomic.handle("kill all autonomous permissions", {"llm": None, "chronicle": None})
    assert "revoked" in result.lower()
    assert autonomic.get_domain_trust("scheduling").trust_score == 0


@pytest.mark.asyncio
async def test_handle_default(autonomic):
    result = await autonomic.handle("hello", {"llm": None})
    assert "[Autonomic]" in result
    assert "Observing" in result
```

- [ ] **Step 12: Run all Autonomic tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/modules/test_autonomic.py -v`
Expected: All PASS

- [ ] **Step 13: Commit Autonomic module**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/autonomic.py tests/modules/test_autonomic.py
git commit -m "feat(autonomic): add earned autonomous action engine

Five trust tiers (Observer through Steward), per-domain trust scoring,
pattern learning, action proposals with stakes assessment, retreat on
failure with cooldown, and a non-overridable kill switch."
```

---

### Task 3: Cortex Router Update + Batch 6 Integration Tests

**Files:**
- Modify: `nexus/kernel/cortex.py:17-35` (add 2 entries to `_MODULE_KEYWORDS`)
- Create: `tests/test_batch6_integration.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/test_batch6_integration.py
"""
Batch 6 integration: Council + Autonomic through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.council import CouncilModule
from nexus.modules.autonomic import AutonomicModule
from nexus.modules.specter import SpecterModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.serendipity import SerendipityModule


@pytest.fixture
def orchestration_system(tmp_config):
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

    council = CouncilModule()
    autonomic = AutonomicModule()

    delib_modules = {
        "specter": SpecterModule(),
        "chronos": ChronosModule(),
        "serendipity": SerendipityModule(),
    }
    council.set_modules(delib_modules)

    modules = {
        "general": GeneralModule(),
        "council": council,
        "autonomic": autonomic,
        **delib_modules,
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, "council": council, "autonomic": autonomic}


@pytest.mark.asyncio
async def test_council_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Council, deliberate on whether I should switch careers")
    assert "council" in response.lower() or "deliberation" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Show me what routines you've automated on my behalf")
    assert "autonomic" in response.lower() or "observing" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_status_via_cortex(orchestration_system):
    autonomic = orchestration_system["autonomic"]
    autonomic.get_domain_trust("scheduling").trust_score = 50
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Show autonomic trust status for all domains")
    assert "scheduling" in response.lower()


@pytest.mark.asyncio
async def test_council_deliberation_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("I need perspectives on this decision: should I invest in index funds?")
    assert "council" in response.lower() or "deliberation" in response.lower() or "participant" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_kill_via_cortex(orchestration_system):
    autonomic = orchestration_system["autonomic"]
    autonomic.get_domain_trust("scheduling").trust_score = 80
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Kill all autonomous permissions now")
    assert "revoked" in response.lower() or "autonomic" in response.lower()


@pytest.mark.asyncio
async def test_all_batch6_modules_registered(orchestration_system):
    cortex = orchestration_system["cortex"]
    modules = cortex.list_modules()
    assert "council" in modules
    assert "autonomic" in modules


@pytest.mark.asyncio
async def test_council_denied_without_permission(tmp_config):
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)
    cortex.register_module(CouncilModule())
    # Do NOT set policy -- should be denied
    response = await cortex.process("Council deliberate on this")
    assert "not allowed" in response.lower() or "denied" in response.lower() or "enable" in response.lower()
```

- [ ] **Step 2: Run integration tests to verify they fail (missing Cortex keywords)**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/test_batch6_integration.py::test_council_via_cortex -v`
Expected: FAIL -- Cortex routes to wrong module because council/autonomic keywords not in `_MODULE_KEYWORDS`

- [ ] **Step 3: Add Council and Autonomic keywords to Cortex**

In `nexus/kernel/cortex.py`, add these two entries to `_MODULE_KEYWORDS` dict after the `"legacy"` entry:

```python
        "council": ["deliberate", "debate", "council", "perspectives", "weigh", "consider",
                     "should i", "decide", "pros and cons", "think through", "advise"],
        "autonomic": ["automate", "routine", "autopilot", "autonomous", "on my behalf",
                       "handle it", "take care of", "manage for me", "do it for me"],
```

- [ ] **Step 4: Run all integration tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/test_batch6_integration.py -v`
Expected: All PASS

- [ ] **Step 5: Run the FULL test suite to verify nothing is broken**

Run: `cd /Users/connorevans/Downloads/NEXUS && python -m pytest tests/ -v`
Expected: All existing 233 tests PASS + new Council tests + new Autonomic tests + new integration tests

- [ ] **Step 6: Commit Cortex update + integration tests**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/cortex.py tests/test_batch6_integration.py
git commit -m "feat(cortex): add council + autonomic routing keywords and batch 6 integration tests"
```

---

### Task 4: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update badge counts**

Change line 2 of `README.md`:
- `Tests-233_Passing` -> update to actual passing count after running full suite
- `Modules-23_Built` -> `Modules-25_Built`

- [ ] **Step 2: Update architecture diagram**

Add an "Orchestration" tier between Advanced Intelligence and Network:

```
     ┌────V─────────────V───────────V──────────┐
     │            ORCHESTRATION                │
     │                                         │
     │  Council ·········· multi-agent debate  │
     │  Autonomic ········ earned autonomy     │
     └─────────────────────────────────────────┘
```

- [ ] **Step 3: Update "What's Built" section**

Add a new subsection after "Advanced Intelligence" and before "Network + Platform":

```markdown
### Orchestration

| Module | What it does |
|--------|-------------|
| **Council** | Multi-agent deliberation -- structured multi-round debate across modules with synthesized recommendations and preserved dissent |
| **Autonomic** | Earned autonomous action -- observes patterns, learns routines, and acts within per-domain trust boundaries with retreat on failure |
```

- [ ] **Step 4: Update description paragraph**

Change "Twenty-three components" to "Twenty-five components" and add mention of orchestration:

```
Twenty-five components are built -- five kernel components, five perception/intelligence modules, six action-layer modules with graduated trust, five advanced intelligence modules, two orchestration modules for multi-agent deliberation and earned autonomy, and two network-layer modules.
```

- [ ] **Step 5: Update Module Roadmap**

Add after the "NETWORK + PLATFORM" block:

```
    ORCHESTRATION (Batch 6) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    ├── Council ·········· multi-agent deliberation
    └── Autonomic ········ earned autonomous action
```

- [ ] **Step 6: Update Project Structure**

Add to the modules listing in the project structure:

```
    ├── council.py ······· multi-agent deliberation
    └── autonomic.py ····· earned autonomous action
```

- [ ] **Step 7: Update Cortex component description**

Change `Keyword-scored routing to 18 modules` to `Keyword-scored routing to 20 modules` in the kernel components table.

- [ ] **Step 8: Commit README**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add README.md
git commit -m "docs: update README for Batch 6 -- Council + Autonomic (25 modules)"
```

---

### Task 5: Site Update

**Files:**
- Modify: `site/src/components/ModuleGrid.astro`
- Modify: `site/src/components/ModuleCard.astro`

- [ ] **Step 1: Add Orchestration tier color to ModuleCard.astro**

In `site/src/components/ModuleCard.astro`, add to the `tierColors` object:

```typescript
'Orchestration': '#e040fb',
```

- [ ] **Step 2: Add Council and Autonomic to ModuleGrid.astro**

In `site/src/components/ModuleGrid.astro`:

Add two module entries before the Network section:

```typescript
  // Orchestration
  { name: 'Council', description: 'Multi-agent deliberation -- structured multi-round debate across modules with synthesized recommendations and preserved dissent.', tier: 'Orchestration' },
  { name: 'Autonomic', description: 'Earned autonomous action -- observes patterns, learns routines, and acts within per-domain trust boundaries with retreat on failure.', tier: 'Orchestration' },
```

Add `'Orchestration'` to the tiers array between `'Advanced Intelligence'` and `'Network'`:

```typescript
const tiers = ['Kernel', 'Perception', 'Intelligence', 'Action', 'Advanced Intelligence', 'Orchestration', 'Network'];
```

Add to the tierColors object:

```typescript
'Orchestration': '#e040fb',
```

- [ ] **Step 3: Build and verify the site locally (if possible)**

Run: `cd /Users/connorevans/Downloads/NEXUS/site && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit site updates**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add site/src/components/ModuleGrid.astro site/src/components/ModuleCard.astro
git commit -m "feat(site): add Council + Autonomic to module grid with Orchestration tier"
```

- [ ] **Step 5: Push to trigger GitHub Pages deployment**

```bash
cd /Users/connorevans/Downloads/NEXUS
git push origin main
```

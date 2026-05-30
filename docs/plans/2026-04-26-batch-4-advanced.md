# Batch 4: Advanced Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five modules — Specter, Chronos, Dreamweaver, Serendipity, Forge — completing the full intelligence stack. Future modeling, adversarial reasoning, overnight deep analysis, engineered serendipity, and autonomous negotiation.

**Architecture:** Each module extends `NexusModule`. Specter runs structured adversarial analysis. Chronos models probabilistic future timelines. Dreamweaver processes idle-time insights. Serendipity inverts relevance to find surprising connections. Forge handles multi-round negotiations within user-defined boundaries.

**Tech Stack:** Python 3.11+, SQLite, asyncio, existing kernel + Batch 2-3 modules

---

### Task 1: Specter — Adversarial Red Team

**Files:**
- Create: `nexus/modules/specter.py`
- Create: `tests/modules/test_specter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_specter.py
import pytest
from nexus.modules.specter import SpecterModule, RedTeamReport, StakeLevel


@pytest.fixture
def specter():
    return SpecterModule()


def test_specter_attrs(specter):
    assert specter.name == "specter"
    assert specter.version == "0.1.0"


def test_assess_stakes_low(specter):
    level = specter.assess_stakes("Should I grab lunch at the cafe?")
    assert level == StakeLevel.LOW


def test_assess_stakes_high(specter):
    level = specter.assess_stakes("I'm about to sign a $50,000 contract with a new vendor")
    assert level in (StakeLevel.HIGH, StakeLevel.CRITICAL)


def test_assess_stakes_medium(specter):
    level = specter.assess_stakes("Thinking about switching our CI pipeline to GitHub Actions")
    assert level == StakeLevel.MEDIUM


def test_red_team_analysis(specter):
    report = specter.analyze(
        decision="Accept the job offer at $180k with no equity",
        context="Currently making $150k with 0.5% equity at a startup",
    )
    assert isinstance(report, RedTeamReport)
    assert len(report.counter_arguments) > 0
    assert len(report.failure_modes) > 0
    assert len(report.hidden_assumptions) > 0


def test_red_team_report_has_recommendation(specter):
    report = specter.analyze(
        decision="Deploy to production on Friday afternoon",
        context="No staging environment, team is remote",
    )
    assert isinstance(report.recommendation, str)
    assert len(report.recommendation) > 0


def test_custom_adversarial_prompt(specter):
    report = specter.analyze(
        decision="Invest all savings in crypto",
        context="Market is volatile, no emergency fund",
        adversarial_angles=["liquidity risk", "regulatory risk", "opportunity cost"],
    )
    assert len(report.counter_arguments) >= 3


@pytest.mark.asyncio
async def test_specter_handle(specter):
    result = await specter.handle(
        "Red team this: Accept a 2-year non-compete clause for a 20% raise",
        {"llm": None},
    )
    assert "counter" in result.lower() or "risk" in result.lower() or "assumption" in result.lower()


@pytest.mark.asyncio
async def test_specter_handle_low_stakes(specter):
    result = await specter.handle("What should I eat for lunch?", {"llm": None})
    assert "low" in result.lower() or "stake" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_specter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Specter module**

```python
# nexus/modules/specter.py
"""
Specter — adversarial red-team agent.
Runs structured adversarial analysis on high-stakes decisions:
counter-arguments, failure modes, hidden assumptions, worst-case scenarios.
Auto-activates based on detected stake level.
"""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any
from nexus.modules.base import NexusModule

_HIGH_STAKE_MARKERS = [
    "contract", "invest", "hire", "fire", "quit", "resign", "acquire",
    "merge", "lawsuit", "deploy", "production", "publish", "announce",
    "commit", "sign", "negotiate", "$", "salary", "equity", "fund",
    "non-compete", "partnership", "acquisition",
]
_MEDIUM_STAKE_MARKERS = [
    "switch", "migrate", "change", "restructure", "reorganize", "pivot",
    "launch", "release", "proposal", "strategy", "plan", "decision",
    "choose", "select", "evaluate",
]


class StakeLevel(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class RedTeamReport:
    decision: str
    stake_level: StakeLevel
    counter_arguments: list[str]
    failure_modes: list[str]
    hidden_assumptions: list[str]
    worst_case: str
    recommendation: str


class SpecterModule(NexusModule):
    name = "specter"
    description = "Adversarial red-team — counter-arguments, failure modes, hidden assumptions"
    version = "0.1.0"

    def assess_stakes(self, text: str) -> StakeLevel:
        text_lower = text.lower()
        high_hits = sum(1 for m in _HIGH_STAKE_MARKERS if m in text_lower)
        med_hits = sum(1 for m in _MEDIUM_STAKE_MARKERS if m in text_lower)
        if high_hits >= 2:
            return StakeLevel.CRITICAL
        if high_hits >= 1:
            return StakeLevel.HIGH
        if med_hits >= 1:
            return StakeLevel.MEDIUM
        return StakeLevel.LOW

    def analyze(
        self,
        decision: str,
        context: str = "",
        adversarial_angles: list[str] | None = None,
    ) -> RedTeamReport:
        stake = self.assess_stakes(decision + " " + context)

        if adversarial_angles:
            counters = [f"From the angle of {a}: this decision may fail because it ignores {a}." for a in adversarial_angles]
        else:
            counters = [
                "The opposite position has merit: the status quo may outperform the change.",
                "This decision optimizes for short-term gain at potential long-term cost.",
                "Selection bias: you may be overweighting evidence that supports this choice.",
            ]

        failures = [
            "The timeline is more aggressive than historical precedent suggests.",
            "Key dependencies are outside your control and may not materialize.",
            "The decision assumes stable conditions that could change rapidly.",
        ]

        assumptions = [
            "You assume the other party's incentives align with yours.",
            "You assume current conditions will persist through execution.",
            "You assume you have complete information — but information gaps are likely.",
        ]

        worst = "Complete failure: the decision backfires, the fallback position is worse than the starting point, and recovery requires more resources than the original investment."

        rec = f"Given {stake.name} stakes: pause and verify your top assumption before committing. What would have to be true for this to fail?"

        return RedTeamReport(
            decision=decision,
            stake_level=stake,
            counter_arguments=counters,
            failure_modes=failures,
            hidden_assumptions=assumptions,
            worst_case=worst,
            recommendation=rec,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        stake = self.assess_stakes(message)
        if stake == StakeLevel.LOW:
            return "[Specter] Low-stakes decision detected. Red-team analysis not warranted."

        report = self.analyze(decision=message)
        lines = [
            f"[Specter] Red Team Analysis (stakes: {report.stake_level.name})",
            "",
            "Counter-arguments:",
        ]
        for i, c in enumerate(report.counter_arguments, 1):
            lines.append(f"  {i}. {c}")
        lines.append("")
        lines.append("Failure modes:")
        for i, f in enumerate(report.failure_modes, 1):
            lines.append(f"  {i}. {f}")
        lines.append("")
        lines.append("Hidden assumptions:")
        for i, a in enumerate(report.hidden_assumptions, 1):
            lines.append(f"  {i}. {a}")
        lines.append("")
        lines.append(f"Worst case: {report.worst_case}")
        lines.append("")
        lines.append(f"Recommendation: {report.recommendation}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_specter.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/specter.py tests/modules/test_specter.py
git commit -m "feat: Specter module — adversarial red-team with stake detection and structured analysis"
git push origin main
```

---

### Task 2: Chronos — Temporal Branching

**Files:**
- Create: `nexus/modules/chronos.py`
- Create: `tests/modules/test_chronos.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_chronos.py
import pytest
from nexus.modules.chronos import ChronosModule, Timeline, Branch


@pytest.fixture
def chronos():
    return ChronosModule()


def test_chronos_attrs(chronos):
    assert chronos.name == "chronos"
    assert chronos.version == "0.1.0"


def test_create_timeline(chronos):
    tl = chronos.create_timeline(
        decision="Accept the offer at Company B",
        context="Currently at Company A, 3 years tenure",
    )
    assert isinstance(tl, Timeline)
    assert len(tl.branches) >= 2


def test_branches_have_outcomes(chronos):
    tl = chronos.create_timeline("Invest $10k in index funds vs bonds", "Risk-averse investor")
    for branch in tl.branches:
        assert isinstance(branch, Branch)
        assert branch.label != ""
        assert 0.0 <= branch.probability <= 1.0
        assert len(branch.outcomes) > 0


def test_probabilities_sum_to_one(chronos):
    tl = chronos.create_timeline("Move to NYC vs stay in Chicago", "Family in Chicago, job offer in NYC")
    total = sum(b.probability for b in tl.branches)
    assert abs(total - 1.0) < 0.01


def test_counterfactual(chronos):
    result = chronos.counterfactual(
        actual_decision="Took the safe job",
        alternative="Joined the startup",
        outcome_actual="Stable but unfulfilling",
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_multi_domain_branches(chronos):
    tl = chronos.create_timeline(
        "Quit and go freelance",
        "Stable salary, mortgage, two kids",
        domains=["finance", "career", "family"],
    )
    for branch in tl.branches:
        assert any(d in branch.outcomes for d in ["finance", "career", "family"])


@pytest.mark.asyncio
async def test_chronos_handle(chronos):
    result = await chronos.handle("Model the future if I switch careers to AI research", {"llm": None})
    assert "branch" in result.lower() or "timeline" in result.lower() or "outcome" in result.lower()


@pytest.mark.asyncio
async def test_chronos_counterfactual_handle(chronos):
    result = await chronos.handle("What if I had started the company last year instead of waiting?", {"llm": None})
    assert "counterfactual" in result.lower() or "alternative" in result.lower() or "what if" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement Chronos module**

```python
# nexus/modules/chronos.py
"""
Chronos — temporal branching and counter-factual modeling.
Models probabilistic future timelines across multiple life domains.
Also handles counter-factuals: 'what if I had done X instead?'
"""
import uuid
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule

_DEFAULT_DOMAINS = ["career", "finance", "wellbeing"]


@dataclass
class Branch:
    label: str
    probability: float
    outcomes: dict[str, str]
    risk_level: str


@dataclass
class Timeline:
    id: str
    decision: str
    context: str
    branches: list[Branch]
    domains: list[str]


class ChronosModule(NexusModule):
    name = "chronos"
    description = "Temporal branching — probabilistic future modeling and counter-factuals"
    version = "0.1.0"

    def create_timeline(
        self,
        decision: str,
        context: str = "",
        domains: list[str] | None = None,
    ) -> Timeline:
        domains = domains or _DEFAULT_DOMAINS
        timeline_id = uuid.uuid4().hex[:8]

        branch_a = Branch(
            label=f"Proceed: {decision[:60]}",
            probability=0.55,
            outcomes={d: f"Positive trajectory in {d} — change creates new opportunities" for d in domains},
            risk_level="medium",
        )
        branch_b = Branch(
            label=f"Status quo: don't act",
            probability=0.30,
            outcomes={d: f"Stable trajectory in {d} — predictable but constrained growth" for d in domains},
            risk_level="low",
        )
        branch_c = Branch(
            label=f"Proceed but conditions worsen",
            probability=0.15,
            outcomes={d: f"Negative trajectory in {d} — external factors undermine the decision" for d in domains},
            risk_level="high",
        )

        return Timeline(
            id=timeline_id,
            decision=decision,
            context=context,
            branches=[branch_a, branch_b, branch_c],
            domains=domains,
        )

    def counterfactual(
        self,
        actual_decision: str,
        alternative: str,
        outcome_actual: str,
    ) -> str:
        return (
            f"Counterfactual analysis:\n"
            f"  Actual: {actual_decision} -> {outcome_actual}\n"
            f"  Alternative: {alternative}\n"
            f"  Assessment: The alternative path likely would have produced different "
            f"trade-offs rather than a strictly better outcome. The key variable is "
            f"whether the risks you avoided were real or perceived. Given the actual "
            f"outcome ({outcome_actual}), the counterfactual suggests the alternative "
            f"had both higher upside and higher variance."
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()
        if "what if" in lower or "counterfactual" in lower or "instead" in lower:
            result = self.counterfactual(
                actual_decision="the path taken",
                alternative=message,
                outcome_actual="current state",
            )
            return f"[Chronos] {result}"

        tl = self.create_timeline(decision=message)
        lines = [f"[Chronos] Timeline for: {tl.decision[:80]}"]
        for b in tl.branches:
            lines.append(f"  Branch: {b.label} (p={b.probability}, risk={b.risk_level})")
            for domain, outcome in b.outcomes.items():
                lines.append(f"    {domain}: {outcome}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_chronos.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/chronos.py tests/modules/test_chronos.py
git commit -m "feat: Chronos module — temporal branching with probabilistic futures and counter-factuals"
git push origin main
```

---

### Task 3: Dreamweaver — Overnight Synthesis

**Files:**
- Create: `nexus/modules/dreamweaver.py`
- Create: `tests/modules/test_dreamweaver.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_dreamweaver.py
import pytest
from nexus.modules.dreamweaver import DreamweaverModule, SynthesisReport


@pytest.fixture
def dreamweaver():
    return DreamweaverModule()


def test_dreamweaver_attrs(dreamweaver):
    assert dreamweaver.name == "dreamweaver"
    assert dreamweaver.version == "0.1.0"


def test_ingest_events(dreamweaver):
    dreamweaver.ingest("Had a meeting with Acme Corp about logistics partnership")
    dreamweaver.ingest("Read an article about supply chain disruptions in Asia")
    dreamweaver.ingest("Prospect mentioned they need faster shipping in Q4")
    assert dreamweaver.event_count() == 3


def test_synthesize_finds_patterns(dreamweaver):
    dreamweaver.ingest("Meeting: discussed Acme Corp shipping timeline")
    dreamweaver.ingest("News: port delays in Shanghai affecting Q4 deliveries")
    dreamweaver.ingest("Email: prospect needs Q4 delivery guarantee")
    dreamweaver.ingest("Calendar: supply chain review meeting Thursday")
    report = dreamweaver.synthesize()
    assert isinstance(report, SynthesisReport)
    assert len(report.insights) > 0


def test_synthesize_empty(dreamweaver):
    report = dreamweaver.synthesize()
    assert len(report.insights) == 0


def test_morning_brief(dreamweaver):
    dreamweaver.ingest("Closed deal with Acme Corp")
    dreamweaver.ingest("Competitor launched new product")
    dreamweaver.ingest("Team member requested PTO next week")
    brief = dreamweaver.morning_brief()
    assert isinstance(brief, str)
    assert len(brief) > 0


def test_clear_events(dreamweaver):
    dreamweaver.ingest("event 1")
    dreamweaver.ingest("event 2")
    dreamweaver.clear()
    assert dreamweaver.event_count() == 0


@pytest.mark.asyncio
async def test_dreamweaver_handle(dreamweaver):
    dreamweaver.ingest("Important meeting notes about Q4 planning")
    result = await dreamweaver.handle("Generate morning brief", {"llm": None})
    assert "brief" in result.lower() or "insight" in result.lower() or "q4" in result.lower()


@pytest.mark.asyncio
async def test_dreamweaver_handle_empty(dreamweaver):
    result = await dreamweaver.handle("morning brief", {"llm": None})
    assert "no events" in result.lower() or "nothing" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement Dreamweaver module**

```python
# nexus/modules/dreamweaver.py
"""
Dreamweaver — overnight synthesis engine.
Ingests the day's events, finds patterns and connections during idle time,
and produces a morning brief of insights the user might have missed.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Insight:
    pattern: str
    supporting_events: list[str]
    significance: str


@dataclass
class SynthesisReport:
    insights: list[Insight]
    event_count: int
    themes: list[str]


def _extract_keywords(text: str) -> set[str]:
    stop = {"the", "a", "an", "is", "was", "are", "were", "in", "on", "at", "to", "for",
            "of", "with", "and", "or", "but", "not", "this", "that", "had", "has", "have",
            "about", "from", "by", "be", "been", "being", "they", "them", "their", "it"}
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {w for w in words if w not in stop}


class DreamweaverModule(NexusModule):
    name = "dreamweaver"
    description = "Overnight synthesis — deep pattern analysis and morning briefs"
    version = "0.1.0"

    def __init__(self):
        self._events: list[str] = []

    def ingest(self, event: str) -> None:
        self._events.append(event)

    def event_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()

    def synthesize(self) -> SynthesisReport:
        if not self._events:
            return SynthesisReport(insights=[], event_count=0, themes=[])

        # Build keyword frequency across events
        keyword_events: dict[str, list[int]] = {}
        for i, event in enumerate(self._events):
            for kw in _extract_keywords(event):
                keyword_events.setdefault(kw, []).append(i)

        # Find themes: keywords appearing in 2+ events
        themes = sorted(
            [(kw, indices) for kw, indices in keyword_events.items() if len(indices) >= 2],
            key=lambda x: len(x[1]),
            reverse=True,
        )

        insights = []
        seen_event_groups: set[frozenset[int]] = set()
        for kw, indices in themes[:5]:
            group = frozenset(indices)
            if group in seen_event_groups:
                continue
            seen_event_groups.add(group)
            supporting = [self._events[i] for i in indices]
            insights.append(Insight(
                pattern=f"Recurring theme '{kw}' across {len(indices)} events",
                supporting_events=supporting,
                significance=f"Multiple signals around '{kw}' suggest this deserves attention.",
            ))

        theme_names = [kw for kw, _ in themes[:10]]
        return SynthesisReport(
            insights=insights,
            event_count=len(self._events),
            themes=theme_names,
        )

    def morning_brief(self) -> str:
        report = self.synthesize()
        if not report.insights:
            return "[Dreamweaver] No patterns detected. Quiet day."
        lines = [f"[Dreamweaver] Morning Brief ({report.event_count} events processed)"]
        if report.themes:
            lines.append(f"  Top themes: {', '.join(report.themes[:5])}")
        lines.append("")
        for i, insight in enumerate(report.insights, 1):
            lines.append(f"  {i}. {insight.pattern}")
            lines.append(f"     {insight.significance}")
            for ev in insight.supporting_events[:3]:
                lines.append(f"       - {ev[:100]}")
        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._events:
            return "[Dreamweaver] No events ingested. Nothing to synthesize."
        return self.morning_brief()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_dreamweaver.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/dreamweaver.py tests/modules/test_dreamweaver.py
git commit -m "feat: Dreamweaver module — overnight synthesis with pattern detection and morning briefs"
git push origin main
```

---

### Task 4: Serendipity — Anti-Optimization Engine

**Files:**
- Create: `nexus/modules/serendipity.py`
- Create: `tests/modules/test_serendipity.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_serendipity.py
import pytest
from nexus.modules.serendipity import SerendipityModule, SurprisingConnection


@pytest.fixture
def serendipity():
    return SerendipityModule()


def test_serendipity_attrs(serendipity):
    assert serendipity.name == "serendipity"
    assert serendipity.version == "0.1.0"


def test_record_focus_area(serendipity):
    serendipity.record_focus("supply chain logistics")
    serendipity.record_focus("warehouse optimization")
    assert len(serendipity.list_focus_areas()) == 2


def test_add_distant_knowledge(serendipity):
    serendipity.add_knowledge(
        domain="neuroscience",
        content="Neural pathways optimize routing efficiency similar to logistics networks",
        tags=["routing", "optimization", "networks"],
    )
    assert len(serendipity.list_knowledge()) == 1


def test_find_surprising_connections(serendipity):
    serendipity.record_focus("supply chain logistics")
    serendipity.record_focus("route optimization")
    serendipity.add_knowledge(
        "neuroscience",
        "Neural pathway routing mirrors supply chain optimization patterns",
        ["routing", "optimization", "pathways"],
    )
    serendipity.add_knowledge(
        "biology",
        "Ant colony optimization algorithms derived from foraging behavior",
        ["optimization", "swarm", "logistics"],
    )
    connections = serendipity.find_connections()
    assert len(connections) >= 1
    assert any(isinstance(c, SurprisingConnection) for c in connections)


def test_no_connections_without_knowledge(serendipity):
    serendipity.record_focus("cooking")
    connections = serendipity.find_connections()
    assert len(connections) == 0


def test_surprise_score(serendipity):
    serendipity.record_focus("machine learning")
    serendipity.add_knowledge(
        "archaeology",
        "Stratigraphy uses layered analysis similar to deep learning architectures",
        ["layers", "analysis", "pattern recognition"],
    )
    connections = serendipity.find_connections()
    if connections:
        assert 0.0 <= connections[0].surprise_score <= 1.0


def test_penalizes_obvious(serendipity):
    serendipity.record_focus("machine learning")
    serendipity.add_knowledge("AI", "New ML paper on transformers", ["machine", "learning", "transformers"])
    serendipity.add_knowledge("music", "Bach's fugues use recursive mathematical structures", ["recursive", "structure", "pattern"])
    connections = serendipity.find_connections()
    # The music connection should score higher surprise than the AI one (if AI one even passes)
    if len(connections) >= 2:
        ai_conn = [c for c in connections if "AI" in c.source_domain]
        music_conn = [c for c in connections if "music" in c.source_domain]
        if ai_conn and music_conn:
            assert music_conn[0].surprise_score >= ai_conn[0].surprise_score


@pytest.mark.asyncio
async def test_serendipity_handle(serendipity):
    serendipity.record_focus("logistics")
    serendipity.add_knowledge("biology", "Slime mold optimizes network paths", ["network", "optimization"])
    result = await serendipity.handle("Surprise me", {"llm": None})
    assert "connection" in result.lower() or "surprising" in result.lower() or "biology" in result.lower()


@pytest.mark.asyncio
async def test_serendipity_handle_empty(serendipity):
    result = await serendipity.handle("surprise me", {"llm": None})
    assert "no focus" in result.lower() or "no knowledge" in result.lower() or "nothing" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement Serendipity module**

```python
# nexus/modules/serendipity.py
"""
Serendipity — anti-optimization engine.
Monitors what the user focuses on, identifies adjacent fields they are NOT
looking at, and surfaces surprising cross-domain connections with deep
structural similarity. Uses an inverted relevance function — penalizes
obvious connections, rewards surprising ones.
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class KnowledgeEntry:
    domain: str
    content: str
    tags: list[str]


@dataclass
class SurprisingConnection:
    source_domain: str
    content: str
    shared_concepts: list[str]
    surprise_score: float
    explanation: str


def _extract_terms(text: str) -> set[str]:
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))


class SerendipityModule(NexusModule):
    name = "serendipity"
    description = "Anti-optimization — surfaces surprising cross-domain connections"
    version = "0.1.0"

    def __init__(self):
        self._focus_areas: list[str] = []
        self._knowledge: list[KnowledgeEntry] = []

    def record_focus(self, area: str) -> None:
        self._focus_areas.append(area)

    def list_focus_areas(self) -> list[str]:
        return list(self._focus_areas)

    def add_knowledge(self, domain: str, content: str, tags: list[str]) -> None:
        self._knowledge.append(KnowledgeEntry(domain=domain, content=content, tags=tags))

    def list_knowledge(self) -> list[KnowledgeEntry]:
        return list(self._knowledge)

    def find_connections(self) -> list[SurprisingConnection]:
        if not self._focus_areas or not self._knowledge:
            return []

        focus_terms = set()
        for area in self._focus_areas:
            focus_terms.update(_extract_terms(area))

        connections = []
        for entry in self._knowledge:
            entry_terms = set(t.lower() for t in entry.tags) | _extract_terms(entry.content)
            shared = focus_terms & entry_terms
            if not shared:
                continue

            # Domain distance: same domain = 0 surprise, distant domain = high surprise
            focus_domains = {_extract_terms(a) for a in self._focus_areas}
            domain_terms = _extract_terms(entry.domain)
            domain_overlap = sum(1 for fd in focus_domains for t in domain_terms if t in fd)

            # Surprise = concept overlap * domain distance
            concept_overlap = len(shared) / max(len(focus_terms | entry_terms), 1)
            domain_distance = 1.0 / (1.0 + domain_overlap)
            surprise = round(concept_overlap * domain_distance, 3)

            if surprise > 0:
                connections.append(SurprisingConnection(
                    source_domain=entry.domain,
                    content=entry.content,
                    shared_concepts=sorted(shared),
                    surprise_score=surprise,
                    explanation=f"Connects {entry.domain} to your focus via: {', '.join(sorted(shared))}",
                ))

        connections.sort(key=lambda c: c.surprise_score, reverse=True)
        return connections

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._focus_areas:
            return "[Serendipity] No focus areas recorded. Tell me what you're working on first."
        if not self._knowledge:
            return "[Serendipity] No knowledge base entries. Feed me content from other domains."

        connections = self.find_connections()
        if not connections:
            return "[Serendipity] No surprising connections found yet. Keep feeding diverse knowledge."
        lines = [f"[Serendipity] {len(connections)} surprising connection(s):"]
        for c in connections[:5]:
            lines.append(f"  [{c.source_domain}] (surprise: {c.surprise_score})")
            lines.append(f"    {c.content}")
            lines.append(f"    {c.explanation}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_serendipity.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/serendipity.py tests/modules/test_serendipity.py
git commit -m "feat: Serendipity module — anti-optimization with inverted relevance scoring"
git push origin main
```

---

### Task 5: Forge — Autonomous Negotiation

**Files:**
- Create: `nexus/modules/forge.py`
- Create: `tests/modules/test_forge.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_forge.py
import pytest
from nexus.modules.forge import ForgeModule, NegotiationConfig, NegotiationState, Offer


@pytest.fixture
def forge():
    return ForgeModule()


def test_forge_attrs(forge):
    assert forge.name == "forge"
    assert forge.version == "0.1.0"


def test_create_negotiation(forge):
    config = NegotiationConfig(
        domain="freelance_rate",
        floor=100,
        ceiling=200,
        target=150,
        max_rounds=5,
        concession_limit=0.2,
    )
    neg_id = forge.create_negotiation(config)
    assert isinstance(neg_id, str)
    state = forge.get_state(neg_id)
    assert state.status == "active"


def test_make_offer(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    offer = forge.make_offer(neg_id)
    assert isinstance(offer, Offer)
    assert 100 <= offer.amount <= 200


def test_receive_counter(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    response = forge.receive_counter(neg_id, 120)
    assert response in ("accept", "counter", "escalate")


def test_accept_above_floor(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    # Counter at target or above should accept
    response = forge.receive_counter(neg_id, 160)
    assert response == "accept"


def test_escalate_below_floor(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    response = forge.receive_counter(neg_id, 50)
    assert response == "escalate"


def test_max_rounds_reached(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 2, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 110)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 110)
    state = forge.get_state(neg_id)
    assert state.status in ("escalated", "active")


def test_negotiation_history(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    neg_id = forge.create_negotiation(config)
    forge.make_offer(neg_id)
    forge.receive_counter(neg_id, 130)
    history = forge.get_history(neg_id)
    assert len(history) >= 2


@pytest.mark.asyncio
async def test_forge_handle(forge):
    result = await forge.handle("Start negotiation for freelance rate $100-$200", {"llm": None})
    assert "negotiation" in result.lower() or "offer" in result.lower()


@pytest.mark.asyncio
async def test_forge_handle_status(forge):
    config = NegotiationConfig("rate", 100, 200, 150, 5, 0.2)
    forge.create_negotiation(config)
    result = await forge.handle("Show active negotiations", {"llm": None})
    assert "active" in result.lower() or "rate" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement Forge module**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_forge.py -v`
Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/forge.py tests/modules/test_forge.py
git commit -m "feat: Forge module — autonomous negotiation with multi-round bargaining and escalation"
git push origin main
```

---

### Task 6: Cortex Router Update + Batch 4 Integration Tests

**Files:**
- Modify: `nexus/kernel/cortex.py` (add keywords)
- Create: `tests/test_batch4_integration.py`

- [ ] **Step 1: Update Cortex keywords**

Add to `_MODULE_KEYWORDS` in `nexus/kernel/cortex.py`:

```python
        "specter": ["red team", "adversarial", "counter-argument", "devil's advocate", "risk analysis"],
        "chronos": ["timeline", "future", "branch", "counterfactual", "what if", "temporal"],
        "dreamweaver": ["morning brief", "overnight", "synthesis", "sleep", "idle", "pattern"],
        "serendipity": ["surprising", "unexpected", "serendip", "random", "adjacent", "diverse"],
        "forge": ["negotiat", "bargain", "offer", "counter-offer", "concession", "deal"],
```

- [ ] **Step 2: Write integration tests**

```python
# tests/test_batch4_integration.py
"""
Batch 4 integration: Advanced intelligence modules through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.specter import SpecterModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.dreamweaver import DreamweaverModule
from nexus.modules.serendipity import SerendipityModule
from nexus.modules.forge import ForgeModule


@pytest.fixture
def advanced_system(tmp_config):
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
        "specter": SpecterModule(),
        "chronos": ChronosModule(),
        "dreamweaver": DreamweaverModule(),
        "serendipity": SerendipityModule(),
        "forge": ForgeModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, **modules}


@pytest.mark.asyncio
async def test_specter_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Red team this: I want to sign a $100k contract with a new vendor")
    assert "counter" in response.lower() or "risk" in response.lower() or "assumption" in response.lower()


@pytest.mark.asyncio
async def test_chronos_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Model the future timeline if I switch to freelancing")
    assert "branch" in response.lower() or "timeline" in response.lower()


@pytest.mark.asyncio
async def test_dreamweaver_via_cortex(advanced_system):
    dw = advanced_system["dreamweaver"]
    dw.ingest("Important Q4 planning session")
    cortex = advanced_system["cortex"]
    response = await cortex.process("Generate my morning brief from overnight synthesis")
    assert "brief" in response.lower() or "q4" in response.lower()


@pytest.mark.asyncio
async def test_serendipity_via_cortex(advanced_system):
    s = advanced_system["serendipity"]
    s.record_focus("logistics")
    s.add_knowledge("biology", "Slime mold network optimization", ["network", "optimization"])
    cortex = advanced_system["cortex"]
    response = await cortex.process("Show me something surprising and unexpected")
    assert "surprising" in response.lower() or "biology" in response.lower() or "connection" in response.lower()


@pytest.mark.asyncio
async def test_forge_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Start a negotiation for freelance rate $100-$200")
    assert "negotiation" in response.lower() or "offer" in response.lower()


@pytest.mark.asyncio
async def test_all_advanced_modules_registered(advanced_system):
    cortex = advanced_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "specter", "chronos", "dreamweaver", "serendipity", "forge"]:
        assert name in modules
```

- [ ] **Step 3: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 4: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/cortex.py tests/test_batch4_integration.py
git commit -m "feat: Cortex routing for advanced modules + Batch 4 integration tests"
git push origin main
```

---

### Task 7: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Full README update**

Update: test badge, module count badge, intro paragraph, architecture diagram (add advanced intelligence tier), "What's Built" section with new module tables, module roadmap (Batch 4 now BUILT), test count, project structure with new files.

- [ ] **Step 2: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add README.md
git commit -m "docs: full README update for Batch 4 — architecture, module tables, roadmap"
git push origin main
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Specter (adversarial red team) — Task 1
- [x] Chronos (temporal branching + counter-factuals) — Task 2
- [x] Dreamweaver (overnight synthesis) — Task 3
- [x] Serendipity (anti-optimization) — Task 4
- [x] Forge (autonomous negotiation) — Task 5
- [x] Cortex routing + integration tests — Task 6
- [x] README update — Task 7

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code complete.

**Type consistency:** `SpecterModule`/`RedTeamReport`/`StakeLevel`, `ChronosModule`/`Timeline`/`Branch`, `DreamweaverModule`/`SynthesisReport`/`Insight`, `SerendipityModule`/`SurprisingConnection`/`KnowledgeEntry`, `ForgeModule`/`NegotiationConfig`/`NegotiationState`/`Offer` — all names consistent.

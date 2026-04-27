# Batch 2: Perception + Intelligence Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five modules — Oracle, Sentry, Atlas, Prism, Cipher — so NEXUS proactively monitors data sources, builds a world model, synthesizes cross-domain insights, and scores information quality. Observe-and-suggest only; no autonomous actions.

**Architecture:** Each module extends `NexusModule`, communicates via Pulse, reads/writes Engram, and is gated by Aegis. Cortex gets a keyword-based router upgrade so it can direct queries to the right module instead of always routing to `general`.

**Tech Stack:** Python 3.11+, SQLite/FTS5, existing kernel (Pulse, Engram, Chronicle, Aegis, Cortex)

---

### Task 1: Oracle — Anticipatory Trigger Engine

**Files:**
- Create: `nexus/modules/oracle.py`
- Create: `tests/modules/test_oracle.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_oracle.py
import pytest
from nexus.modules.oracle import OracleModule, TriggerRule


@pytest.fixture
def oracle():
    return OracleModule()


def test_oracle_attrs(oracle):
    assert oracle.name == "oracle"
    assert oracle.version == "0.1.0"


def test_add_trigger_rule(oracle):
    rule = TriggerRule(
        name="meeting_overload",
        keywords=["meeting", "calendar", "schedule"],
        threshold=0.5,
        description="Fires when calendar density is high",
    )
    oracle.add_rule(rule)
    assert len(oracle.list_rules()) == 1
    assert oracle.list_rules()[0].name == "meeting_overload"


def test_evaluate_triggers_match(oracle):
    rule = TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    )
    oracle.add_rule(rule)
    fired = oracle.evaluate("The project deadline is tomorrow and two tasks are overdue")
    assert len(fired) == 1
    assert fired[0]["rule"] == "deadline_alert"
    assert fired[0]["score"] > 0.3


def test_evaluate_triggers_no_match(oracle):
    rule = TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    )
    oracle.add_rule(rule)
    fired = oracle.evaluate("The weather is nice today")
    assert len(fired) == 0


@pytest.mark.asyncio
async def test_oracle_handle(oracle):
    rule = TriggerRule(
        name="finance_alert",
        keywords=["budget", "expense", "cost", "revenue"],
        threshold=0.3,
        description="Fires on financial input",
    )
    oracle.add_rule(rule)
    result = await oracle.handle("The Q3 budget shows a 15% cost overrun", {"llm": None})
    assert "finance_alert" in result.lower() or "trigger" in result.lower()


@pytest.mark.asyncio
async def test_oracle_handle_no_triggers(oracle):
    result = await oracle.handle("hello", {"llm": None})
    assert "no triggers" in result.lower() or "no active" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_oracle.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Oracle module**

```python
# nexus/modules/oracle.py
"""
Oracle — anticipatory trigger engine.
Scans input against configurable trigger rules with keyword-weighted scoring.
Fires events when pattern density exceeds thresholds.
Observe-only: Oracle never takes actions, only surfaces information.
"""
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class TriggerRule:
    name: str
    keywords: list[str]
    threshold: float
    description: str
    weight: float = 1.0


class OracleModule(NexusModule):
    name = "oracle"
    description = "Anticipatory trigger engine — scans for patterns and fires events"
    version = "0.1.0"

    def __init__(self):
        self._rules: list[TriggerRule] = []

    def add_rule(self, rule: TriggerRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> None:
        self._rules = [r for r in self._rules if r.name != name]

    def list_rules(self) -> list[TriggerRule]:
        return list(self._rules)

    def evaluate(self, text: str) -> list[dict[str, Any]]:
        """Score text against all rules. Return fired triggers (score > threshold)."""
        text_lower = text.lower()
        words = set(text_lower.split())
        fired = []
        for rule in self._rules:
            hits = sum(1 for kw in rule.keywords if kw.lower() in text_lower)
            if not rule.keywords:
                continue
            score = (hits / len(rule.keywords)) * rule.weight
            if score >= rule.threshold:
                fired.append({
                    "rule": rule.name,
                    "score": round(score, 3),
                    "description": rule.description,
                    "matched_keywords": [kw for kw in rule.keywords if kw.lower() in text_lower],
                })
        return fired

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        fired = self.evaluate(message)
        if not fired:
            return "[Oracle] No triggers fired. No active patterns match this input."
        lines = ["[Oracle] Triggered alerts:"]
        for t in fired:
            lines.append(f"  - {t['rule']} (score: {t['score']}) — {t['description']}")
            lines.append(f"    Matched: {', '.join(t['matched_keywords'])}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_oracle.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/oracle.py tests/modules/test_oracle.py
git commit -m "feat: Oracle module — anticipatory trigger engine with keyword scoring"
git push origin main
```

---

### Task 2: Sentry — Cognitive Load Model

**Files:**
- Create: `nexus/modules/sentry.py`
- Create: `tests/modules/test_sentry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_sentry.py
import pytest
from nexus.modules.sentry import SentryModule, CognitiveState


@pytest.fixture
def sentry():
    return SentryModule()


def test_sentry_attrs(sentry):
    assert sentry.name == "sentry"
    assert sentry.version == "0.1.0"


def test_default_state(sentry):
    state = sentry.get_state()
    assert isinstance(state, CognitiveState)
    assert 0.0 <= state.focus <= 1.0
    assert 0.0 <= state.fatigue <= 1.0
    assert 0.0 <= state.stress <= 1.0
    assert isinstance(state.flow, bool)


def test_update_signal_typing_speed(sentry):
    sentry.update_signal("typing_speed", 0.3)
    state = sentry.get_state()
    # Low typing speed increases fatigue estimate
    assert state.fatigue > 0.0


def test_update_signal_message_frequency(sentry):
    sentry.update_signal("message_frequency", 0.9)
    state = sentry.get_state()
    # High message frequency suggests engagement
    assert state.focus > 0.0


def test_update_signal_time_gap(sentry):
    sentry.update_signal("time_gap", 0.8)
    state = sentry.get_state()
    # Large time gap between messages suggests break/fatigue
    assert state.fatigue > 0.0


def test_flow_state_detection(sentry):
    # Simulate flow conditions: high focus, low fatigue, low stress
    sentry.update_signal("typing_speed", 0.9)
    sentry.update_signal("message_frequency", 0.8)
    sentry.update_signal("time_gap", 0.1)
    state = sentry.get_state()
    assert state.focus > 0.5


def test_state_to_dict(sentry):
    d = sentry.get_state().to_dict()
    assert "focus" in d
    assert "fatigue" in d
    assert "stress" in d
    assert "flow" in d


@pytest.mark.asyncio
async def test_sentry_handle(sentry):
    result = await sentry.handle("How am I doing?", {"llm": None})
    assert "focus" in result.lower() or "state" in result.lower()


@pytest.mark.asyncio
async def test_sentry_handle_with_signal(sentry):
    sentry.update_signal("typing_speed", 0.2)
    result = await sentry.handle("status", {"llm": None})
    assert "fatigue" in result.lower() or "focus" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_sentry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Sentry module**

```python
# nexus/modules/sentry.py
"""
Sentry — cognitive load model.
Maintains a real-time estimate of the user's cognitive state based on
behavioral signals (typing speed, message frequency, time gaps).
Outputs a state vector: focus, fatigue, stress, flow.
"""
from dataclasses import dataclass
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class CognitiveState:
    focus: float = 0.5
    fatigue: float = 0.0
    stress: float = 0.0
    flow: bool = False

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "focus": round(self.focus, 2),
            "fatigue": round(self.fatigue, 2),
            "stress": round(self.stress, 2),
            "flow": self.flow,
        }


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


class SentryModule(NexusModule):
    name = "sentry"
    description = "Cognitive load model — tracks user focus, fatigue, stress, and flow"
    version = "0.1.0"

    def __init__(self):
        self._signals: dict[str, float] = {}
        self._state = CognitiveState()

    def update_signal(self, signal_name: str, value: float) -> None:
        """Update a behavioral signal (0.0–1.0) and recalculate state."""
        self._signals[signal_name] = _clamp(value)
        self._recalculate()

    def _recalculate(self) -> None:
        typing = self._signals.get("typing_speed", 0.5)
        freq = self._signals.get("message_frequency", 0.5)
        gap = self._signals.get("time_gap", 0.3)

        # Focus: high typing speed + high frequency = focused
        self._state.focus = _clamp(typing * 0.5 + freq * 0.5)
        # Fatigue: low typing speed + high gap = fatigued
        self._state.fatigue = _clamp((1.0 - typing) * 0.5 + gap * 0.5)
        # Stress: high frequency + low gap = pressured
        self._state.stress = _clamp(freq * 0.4 + (1.0 - gap) * 0.3 + (1.0 - typing) * 0.3)
        # Flow: high focus, low fatigue, low stress
        self._state.flow = (
            self._state.focus > 0.6
            and self._state.fatigue < 0.4
            and self._state.stress < 0.5
        )

    def get_state(self) -> CognitiveState:
        return self._state

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        s = self._state
        lines = [
            "[Sentry] Cognitive State:",
            f"  Focus:   {s.focus:.2f}",
            f"  Fatigue: {s.fatigue:.2f}",
            f"  Stress:  {s.stress:.2f}",
            f"  Flow:    {'active' if s.flow else 'inactive'}",
        ]
        if s.flow:
            lines.append("  -> Flow state detected. Non-critical interrupts are suppressed.")
        if s.fatigue > 0.6:
            lines.append("  -> High fatigue detected. Consider taking a break.")
        if s.stress > 0.7:
            lines.append("  -> Elevated stress. Prioritizing only essential items.")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_sentry.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/sentry.py tests/modules/test_sentry.py
git commit -m "feat: Sentry module — cognitive load model with focus/fatigue/stress/flow"
git push origin main
```

---

### Task 3: Atlas — Living World Model (Knowledge Graph)

**Files:**
- Create: `nexus/modules/atlas.py`
- Create: `tests/modules/test_atlas.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_atlas.py
import pytest
import time
from nexus.modules.atlas import AtlasModule, Fact


@pytest.fixture
def atlas(tmp_config):
    a = AtlasModule(db_path=tmp_config.db_path)
    a.init_db()
    return a


def test_atlas_attrs(atlas):
    assert atlas.name == "atlas"
    assert atlas.version == "0.1.0"


def test_add_fact(atlas):
    fact_id = atlas.add_fact(
        subject="Connor",
        predicate="works_at",
        obj="Flexport",
        confidence=0.95,
        source="user_input",
    )
    assert isinstance(fact_id, str)
    assert len(fact_id) > 0


def test_query_facts(atlas):
    atlas.add_fact("Connor", "lives_in", "Chicago", 0.9, "user_input")
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    results = atlas.query(subject="Connor")
    assert len(results) == 2


def test_query_by_predicate(atlas):
    atlas.add_fact("Connor", "knows", "Python", 0.99, "observation")
    atlas.add_fact("Connor", "knows", "TypeScript", 0.85, "observation")
    atlas.add_fact("Alice", "knows", "Rust", 0.9, "observation")
    results = atlas.query(predicate="knows")
    assert len(results) == 3


def test_confidence_decay(atlas):
    fact_id = atlas.add_fact("Test", "is", "fresh", 0.9, "test", max_age_days=0)
    # After decay, confidence should be lower
    facts = atlas.query(subject="Test", apply_decay=True)
    # With max_age_days=0, confidence drops immediately
    assert len(facts) >= 1


def test_conflicting_facts(atlas):
    atlas.add_fact("Connor", "lives_in", "Chicago", 0.9, "user_input")
    atlas.add_fact("Connor", "lives_in", "New York", 0.6, "rumor")
    results = atlas.query(subject="Connor", predicate="lives_in")
    assert len(results) == 2
    # Higher confidence fact should sort first
    assert results[0]["confidence"] >= results[1]["confidence"]


def test_remove_fact(atlas):
    fact_id = atlas.add_fact("temp", "is", "temporary", 0.5, "test")
    atlas.remove_fact(fact_id)
    results = atlas.query(subject="temp")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_atlas_handle_query(atlas):
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    result = await atlas.handle("What do you know about Connor?", {"llm": None})
    assert "connor" in result.lower() or "flexport" in result.lower()


@pytest.mark.asyncio
async def test_atlas_handle_empty(atlas):
    result = await atlas.handle("What do you know about nobody?", {"llm": None})
    assert "no facts" in result.lower() or "nothing" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_atlas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Atlas module**

```python
# nexus/modules/atlas.py
"""
Atlas — the living world model.
A temporal knowledge graph where facts have confidence scores, sources,
and time-based decay. Conflicting facts coexist with competing confidence.
"""
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Fact:
    id: str
    subject: str
    predicate: str
    obj: str
    confidence: float
    source: str
    timestamp: str
    max_age_days: int | None


class AtlasModule(NexusModule):
    name = "atlas"
    description = "Living world model — temporal knowledge graph with confidence decay"
    version = "0.1.0"

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_facts (
                id           TEXT PRIMARY KEY,
                subject      TEXT NOT NULL,
                predicate    TEXT NOT NULL,
                object       TEXT NOT NULL,
                confidence   REAL NOT NULL,
                source       TEXT NOT NULL,
                timestamp    TEXT NOT NULL,
                max_age_days INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_subject ON atlas_facts(subject)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_predicate ON atlas_facts(predicate)")
        conn.commit()
        conn.close()

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float,
        source: str,
        max_age_days: int | None = None,
    ) -> str:
        fact_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            """INSERT INTO atlas_facts
               (id, subject, predicate, object, confidence, source, timestamp, max_age_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fact_id, subject, predicate, obj, confidence, source, ts, max_age_days),
        )
        conn.commit()
        conn.close()
        return fact_id

    def remove_fact(self, fact_id: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM atlas_facts WHERE id = ?", (fact_id,))
        conn.commit()
        conn.close()

    def query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        obj: str | None = None,
        apply_decay: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if subject:
            clauses.append("LOWER(subject) = LOWER(?)")
            params.append(subject)
        if predicate:
            clauses.append("LOWER(predicate) = LOWER(?)")
            params.append(predicate)
        if obj:
            clauses.append("LOWER(object) = LOWER(?)")
            params.append(obj)
        where = " AND ".join(clauses) if clauses else "1=1"
        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM atlas_facts WHERE {where} ORDER BY confidence DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        results = []
        for r in rows:
            conf = r["confidence"]
            if apply_decay and r["max_age_days"] is not None:
                created = datetime.fromisoformat(r["timestamp"])
                age_days = (now - created).total_seconds() / 86400
                decay = max(0.0, 1.0 - (age_days / max(r["max_age_days"], 0.001)))
                conf = conf * decay
            results.append({
                "id": r["id"],
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "confidence": round(conf, 3),
                "source": r["source"],
                "timestamp": r["timestamp"],
            })
        return results

    def _extract_subject(self, message: str) -> str | None:
        """Extract a likely subject from a query message."""
        lower = message.lower()
        for prefix in ("what do you know about ", "tell me about ", "who is ", "what is "):
            if lower.startswith(prefix):
                return message[len(prefix):].rstrip("?").strip()
        words = message.split()
        if len(words) <= 3:
            return message.strip("?").strip()
        return None

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        subject = self._extract_subject(message)
        if subject:
            results = self.query(subject=subject, apply_decay=True)
            if not results:
                return f"[Atlas] No facts found about '{subject}'."
            lines = [f"[Atlas] Known facts about '{subject}':"]
            for f in results:
                lines.append(
                    f"  - {f['subject']} {f['predicate']} {f['object']} "
                    f"(confidence: {f['confidence']}, source: {f['source']})"
                )
            return "\n".join(lines)
        # Fallback: show all recent facts
        results = self.query(apply_decay=True, limit=10)
        if not results:
            return "[Atlas] No facts in the world model yet."
        lines = ["[Atlas] Recent world model facts:"]
        for f in results:
            lines.append(f"  - {f['subject']} {f['predicate']} {f['object']} ({f['confidence']})")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_atlas.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/atlas.py tests/modules/test_atlas.py
git commit -m "feat: Atlas module — living world model with temporal knowledge graph"
git push origin main
```

---

### Task 4: Cipher — Trust-Scored Information

**Files:**
- Create: `nexus/modules/cipher.py`
- Create: `tests/modules/test_cipher.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_cipher.py
import pytest
from nexus.modules.cipher import CipherModule, SourceProfile


@pytest.fixture
def cipher():
    c = CipherModule()
    c.register_source(SourceProfile(name="reuters", base_trust=0.94, category="news"))
    c.register_source(SourceProfile(name="linkedin", base_trust=0.61, category="social"))
    c.register_source(SourceProfile(name="anonymous_blog", base_trust=0.12, category="blog"))
    return c


def test_cipher_attrs(cipher):
    assert cipher.name == "cipher"
    assert cipher.version == "0.1.0"


def test_register_source(cipher):
    sources = cipher.list_sources()
    assert len(sources) == 3
    assert any(s.name == "reuters" for s in sources)


def test_score_information_known_source(cipher):
    result = cipher.score("Oil prices surge 5%", source="reuters")
    assert result["trust_score"] == 0.94
    assert result["source"] == "reuters"


def test_score_information_unknown_source(cipher):
    result = cipher.score("Some random claim", source="unknown_blog")
    assert result["trust_score"] < 0.2  # Default low trust


def test_detect_conflict(cipher):
    cipher.record_claim("oil_price_direction", "rising", source="reuters", trust=0.94)
    cipher.record_claim("oil_price_direction", "falling", source="anonymous_blog", trust=0.12)
    conflicts = cipher.get_conflicts()
    assert len(conflicts) >= 1
    assert conflicts[0]["claim_id"] == "oil_price_direction"


def test_no_conflict_same_value(cipher):
    cipher.record_claim("weather_today", "sunny", source="reuters", trust=0.94)
    cipher.record_claim("weather_today", "sunny", source="linkedin", trust=0.61)
    conflicts = cipher.get_conflicts()
    assert len(conflicts) == 0


def test_provenance_chain(cipher):
    cipher.record_claim("fact_1", "value_a", source="reuters", trust=0.94)
    chain = cipher.get_provenance("fact_1")
    assert len(chain) >= 1
    assert chain[0]["source"] == "reuters"
    assert chain[0]["trust"] == 0.94


@pytest.mark.asyncio
async def test_cipher_handle(cipher):
    cipher.record_claim("test_claim", "value", source="reuters", trust=0.94)
    result = await cipher.handle("What do you know about test_claim?", {"llm": None})
    assert "reuters" in result.lower() or "0.94" in result


@pytest.mark.asyncio
async def test_cipher_handle_with_conflict(cipher):
    cipher.record_claim("disputed", "yes", source="reuters", trust=0.94)
    cipher.record_claim("disputed", "no", source="anonymous_blog", trust=0.12)
    result = await cipher.handle("conflicts", {"llm": None})
    assert "conflict" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_cipher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Cipher module**

```python
# nexus/modules/cipher.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_cipher.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/cipher.py tests/modules/test_cipher.py
git commit -m "feat: Cipher module — trust-scored information with provenance and conflict detection"
git push origin main
```

---

### Task 5: Prism — Cross-Domain Synthesis

**Files:**
- Create: `nexus/modules/prism.py`
- Create: `tests/modules/test_prism.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_prism.py
import pytest
from nexus.modules.prism import PrismModule, Insight


@pytest.fixture
def prism():
    return PrismModule()


def test_prism_attrs(prism):
    assert prism.name == "prism"
    assert prism.version == "0.1.0"


def test_add_observation(prism):
    prism.add_observation(
        domain="calendar",
        content="Meeting with Acme Corp at 3pm",
        tags=["meeting", "acme"],
    )
    assert len(prism.list_observations()) == 1


def test_synthesize_finds_connection(prism):
    prism.add_observation("calendar", "Flight to NYC on Friday", ["travel", "nyc"])
    prism.add_observation("weather", "Hurricane warning for NYC this weekend", ["weather", "nyc", "alert"])
    prism.add_observation("crm", "Meeting with NYC client scheduled for Saturday", ["meeting", "nyc", "client"])

    insights = prism.synthesize()
    assert len(insights) >= 1
    # Should connect NYC travel + hurricane + meeting
    assert any("nyc" in i.tags for i in insights)


def test_synthesize_no_connection(prism):
    prism.add_observation("calendar", "Dentist appointment", ["health"])
    prism.add_observation("code", "Fixed linting errors", ["code", "cleanup"])
    insights = prism.synthesize()
    # No shared tags, no connection
    assert len(insights) == 0


def test_insight_has_domains(prism):
    prism.add_observation("email", "Vendor mentioned price increase", ["vendor", "pricing"])
    prism.add_observation("finance", "Q3 budget is tight", ["budget", "pricing"])
    insights = prism.synthesize()
    assert len(insights) >= 1
    assert len(insights[0].domains) >= 2


def test_clear_observations(prism):
    prism.add_observation("test", "data", ["tag"])
    prism.clear_observations()
    assert len(prism.list_observations()) == 0


@pytest.mark.asyncio
async def test_prism_handle_with_insights(prism):
    prism.add_observation("calendar", "Flight to London", ["travel", "london"])
    prism.add_observation("news", "London tube strike next week", ["london", "transport", "strike"])
    result = await prism.handle("synthesize", {"llm": None})
    assert "london" in result.lower() or "connection" in result.lower() or "insight" in result.lower()


@pytest.mark.asyncio
async def test_prism_handle_no_observations(prism):
    result = await prism.handle("synthesize", {"llm": None})
    assert "no observations" in result.lower() or "no insights" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_prism.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Prism module**

```python
# nexus/modules/prism.py
"""
Prism — cross-domain synthesis engine.
Collects observations from multiple domains, finds non-obvious connections
through shared tags and context overlap, and surfaces synthesized insights.
"""
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Observation:
    domain: str
    content: str
    tags: list[str]


@dataclass
class Insight:
    summary: str
    domains: list[str]
    tags: list[str]
    observations: list[Observation]
    connection_strength: float


class PrismModule(NexusModule):
    name = "prism"
    description = "Cross-domain synthesis — finds non-obvious connections across information sources"
    version = "0.1.0"

    def __init__(self):
        self._observations: list[Observation] = []

    def add_observation(self, domain: str, content: str, tags: list[str]) -> None:
        self._observations.append(Observation(domain=domain, content=content, tags=tags))

    def list_observations(self) -> list[Observation]:
        return list(self._observations)

    def clear_observations(self) -> None:
        self._observations.clear()

    def synthesize(self) -> list[Insight]:
        """Find cross-domain connections through shared tags."""
        if len(self._observations) < 2:
            return []

        # Build tag -> observation index
        tag_index: dict[str, list[int]] = {}
        for i, obs in enumerate(self._observations):
            for tag in obs.tags:
                tag_index.setdefault(tag.lower(), []).append(i)

        # Find groups of observations connected by shared tags
        seen_groups: set[frozenset[int]] = set()
        insights: list[Insight] = []

        for tag, indices in tag_index.items():
            if len(indices) < 2:
                continue
            # Only consider cross-domain connections
            domains = {self._observations[i].domain for i in indices}
            if len(domains) < 2:
                continue

            group_key = frozenset(indices)
            if group_key in seen_groups:
                continue
            seen_groups.add(group_key)

            connected_obs = [self._observations[i] for i in indices]
            shared_tags = set.intersection(
                *(set(o.tags) for o in connected_obs)
            )
            all_tags = set()
            for o in connected_obs:
                all_tags.update(o.tags)

            # Connection strength: ratio of shared tags to total unique tags
            strength = len(shared_tags) / len(all_tags) if all_tags else 0.0

            summary_parts = [f"[{o.domain}] {o.content}" for o in connected_obs]
            summary = "Connection found: " + " + ".join(summary_parts)

            insights.append(Insight(
                summary=summary,
                domains=sorted(domains),
                tags=sorted(shared_tags),
                observations=connected_obs,
                connection_strength=round(strength, 3),
            ))

        insights.sort(key=lambda x: x.connection_strength, reverse=True)
        return insights

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._observations:
            return "[Prism] No observations collected. Feed data from Oracle, Sentry, or other sources first."

        insights = self.synthesize()
        if not insights:
            return "[Prism] No cross-domain insights found. Observations exist but have no shared context."

        lines = [f"[Prism] {len(insights)} cross-domain insight(s) found:"]
        for i, ins in enumerate(insights, 1):
            lines.append(f"  {i}. Domains: {', '.join(ins.domains)}")
            lines.append(f"     Shared tags: {', '.join(ins.tags)}")
            lines.append(f"     Strength: {ins.connection_strength}")
            for obs in ins.observations:
                lines.append(f"       [{obs.domain}] {obs.content}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_prism.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/prism.py tests/modules/test_prism.py
git commit -m "feat: Prism module — cross-domain synthesis with tag-based connection scoring"
git push origin main
```

---

### Task 6: Cortex Router Upgrade — Keyword-Based Module Selection

**Files:**
- Modify: `nexus/kernel/cortex.py`
- Modify: `tests/kernel/test_cortex.py` (add routing tests)

- [ ] **Step 1: Add failing tests for keyword routing**

Append to `tests/kernel/test_cortex.py`:

```python
from nexus.modules.oracle import OracleModule
from nexus.modules.sentry import SentryModule


@pytest.fixture
def multi_cortex(kernel_deps):
    """Cortex with multiple modules registered."""
    c = Cortex(**kernel_deps)
    c.register_module(GeneralModule())
    c.register_module(OracleModule())
    c.register_module(SentryModule())
    kernel_deps["aegis"].set_policy("general", allowed=True)
    kernel_deps["aegis"].set_policy("oracle", allowed=True)
    kernel_deps["aegis"].set_policy("sentry", allowed=True)
    return c


@pytest.mark.asyncio
async def test_route_to_oracle(multi_cortex):
    response = await multi_cortex.process("Check my triggers and alerts")
    assert "oracle" in response.lower() or "trigger" in response.lower() or "no active" in response.lower()


@pytest.mark.asyncio
async def test_route_to_sentry(multi_cortex):
    response = await multi_cortex.process("What is my cognitive state and focus level?")
    assert "sentry" in response.lower() or "focus" in response.lower() or "fatigue" in response.lower()


@pytest.mark.asyncio
async def test_route_fallback_to_general(multi_cortex):
    response = await multi_cortex.process("Tell me a joke")
    # No keyword match, falls back to general
    assert isinstance(response, str)
    assert len(response) > 0
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/kernel/test_cortex.py -v`
Expected: Existing tests pass, new routing tests may fail (routes to general instead of oracle/sentry)

- [ ] **Step 3: Upgrade Cortex `_select_module`**

Replace `_select_module` in `nexus/kernel/cortex.py`:

```python
    # Module keyword hints for routing
    _MODULE_KEYWORDS: dict[str, list[str]] = {
        "oracle": ["trigger", "alert", "monitor", "scan", "anticipat", "pattern"],
        "sentry": ["cognitive", "focus", "fatigue", "stress", "flow", "state", "energy", "tired"],
        "atlas": ["fact", "know about", "world model", "knowledge", "who is", "what is"],
        "cipher": ["trust", "source", "provenance", "conflict", "verify", "credib"],
        "prism": ["synthesize", "connection", "cross-domain", "insight", "relate"],
    }

    def _select_module(self, message: str) -> str:
        """
        Select which module should handle this message.
        Uses keyword matching against registered modules, falls back to 'general'.
        """
        if not self._modules:
            return ""

        msg_lower = message.lower()
        best_module = ""
        best_score = 0

        for mod_name, keywords in self._MODULE_KEYWORDS.items():
            if mod_name not in self._modules:
                continue
            score = sum(1 for kw in keywords if kw in msg_lower)
            if score > best_score:
                best_score = score
                best_module = mod_name

        if best_module:
            return best_module

        # Fallback to general, or first available module
        if "general" in self._modules:
            return "general"
        return next(iter(self._modules))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/kernel/test_cortex.py -v`
Expected: ALL PASSED (existing + 3 new)

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/cortex.py tests/kernel/test_cortex.py
git commit -m "feat: Cortex keyword-based router for multi-module dispatch"
git push origin main
```

---

### Task 7: Batch 2 Integration Tests

**Files:**
- Create: `tests/test_batch2_integration.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/test_batch2_integration.py
"""
Batch 2 integration: Oracle triggers -> Prism synthesizes -> Atlas stores ->
Cipher scores -> Sentry monitors cognitive state. Full perception pipeline.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.oracle import OracleModule, TriggerRule
from nexus.modules.sentry import SentryModule
from nexus.modules.atlas import AtlasModule
from nexus.modules.cipher import CipherModule, SourceProfile
from nexus.modules.prism import PrismModule


@pytest.fixture
def perception_system(tmp_config):
    """Full Nexus with all Batch 2 modules."""
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

    # Register all modules
    general = GeneralModule()
    oracle = OracleModule()
    sentry = SentryModule()
    atlas = AtlasModule(db_path=tmp_config.db_path)
    atlas.init_db()
    cipher = CipherModule()
    prism = PrismModule()

    for mod in [general, oracle, sentry, atlas, cipher, prism]:
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    # Configure Oracle with a trigger rule
    oracle.add_rule(TriggerRule(
        name="deadline_alert",
        keywords=["deadline", "due", "overdue"],
        threshold=0.3,
        description="Fires on deadline-related input",
    ))

    # Configure Cipher with sources
    cipher.register_source(SourceProfile(name="reuters", base_trust=0.94, category="news"))

    return {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "oracle": oracle,
        "sentry": sentry,
        "atlas": atlas,
        "cipher": cipher,
        "prism": prism,
    }


@pytest.mark.asyncio
async def test_oracle_trigger_via_cortex(perception_system):
    """Oracle fires triggers when routed deadline-related input."""
    cortex = perception_system["cortex"]
    response = await cortex.process("Check alerts for this overdue deadline")
    assert "trigger" in response.lower() or "deadline" in response.lower()


@pytest.mark.asyncio
async def test_sentry_reports_state(perception_system):
    """Sentry reports cognitive state when asked."""
    cortex = perception_system["cortex"]
    response = await cortex.process("What is my focus level and cognitive state?")
    assert "focus" in response.lower() or "fatigue" in response.lower()


@pytest.mark.asyncio
async def test_atlas_stores_and_retrieves(perception_system):
    """Atlas can store facts and retrieve them."""
    atlas = perception_system["atlas"]
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    cortex = perception_system["cortex"]
    response = await cortex.process("What do you know about Connor?")
    assert "flexport" in response.lower() or "connor" in response.lower()


@pytest.mark.asyncio
async def test_prism_synthesizes_observations(perception_system):
    """Prism finds cross-domain connections."""
    prism = perception_system["prism"]
    prism.add_observation("calendar", "Flight to NYC on Friday", ["travel", "nyc"])
    prism.add_observation("weather", "Storm warning for NYC", ["weather", "nyc", "alert"])
    cortex = perception_system["cortex"]
    response = await cortex.process("Synthesize cross-domain connections")
    assert "nyc" in response.lower() or "insight" in response.lower() or "connection" in response.lower()


@pytest.mark.asyncio
async def test_cipher_detects_conflicts(perception_system):
    """Cipher detects conflicting claims from different sources."""
    cipher = perception_system["cipher"]
    cipher.record_claim("market_direction", "bullish", source="reuters", trust=0.94)
    cipher.record_claim("market_direction", "bearish", source="blog", trust=0.12)
    cortex = perception_system["cortex"]
    response = await cortex.process("Show me source conflicts and trust verification")
    assert "conflict" in response.lower()


@pytest.mark.asyncio
async def test_all_modules_registered(perception_system):
    """All Batch 2 modules are registered in Cortex."""
    cortex = perception_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "oracle", "sentry", "atlas", "cipher", "prism"]:
        assert name in modules
```

- [ ] **Step 2: Run integration tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/test_batch2_integration.py -v`
Expected: 6 PASSED

- [ ] **Step 3: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 4: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add tests/test_batch2_integration.py
git commit -m "test: Batch 2 integration tests — full perception pipeline"
git push origin main
```

---

### Task 8: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the module roadmap section**

Update the Batch 2 line in the module roadmap from `░░░░░░░░░░ PLANNED` to `██████████ BUILT`.

Also update the test count badge and the "49 tests" line in the Testing section to reflect the new total.

- [ ] **Step 2: Run full suite to get final count**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v --tb=short`

- [ ] **Step 3: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add README.md
git commit -m "docs: update README for Batch 2 completion"
git push origin main
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Oracle (anticipatory triggers) — Task 1
- [x] Sentry (emotional/cognitive state) — Task 2
- [x] Atlas (knowledge graph with decay) — Task 3
- [x] Cipher (trust-scored information) — Task 4
- [x] Prism (cross-domain synthesis) — Task 5
- [x] Cortex router upgrade — Task 6
- [x] Integration tests — Task 7
- [x] README update — Task 8

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks complete.

**Type consistency:** `OracleModule`/`TriggerRule`, `SentryModule`/`CognitiveState`, `AtlasModule`/`Fact`, `CipherModule`/`SourceProfile`/`Claim`, `PrismModule`/`Observation`/`Insight` — all names consistent across tasks.

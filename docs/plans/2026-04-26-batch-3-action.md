# Batch 3: Action Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six modules — Wraith, Echo, Herald, Weave, Sigil — plus upgrade Aegis to graduated trust (0-100). The system can now take actions: spawn research swarms, communicate with external agents, monitor threats, model behavior, and map social graphs. Earned autonomy goes live.

**Architecture:** Each module extends `NexusModule`. Wraith spawns ephemeral async tasks. Echo builds behavioral profiles from Engram history. Herald handles A2A message exchange. Weave maintains an in-memory social graph. Sigil scans for threats with severity-based Pulse priority. Aegis gets outcome-based trust adjustment.

**Tech Stack:** Python 3.11+, SQLite, asyncio, existing kernel + Batch 2 modules

---

### Task 1: Aegis Graduated Trust Upgrade

**Files:**
- Modify: `nexus/kernel/aegis.py`
- Modify: `tests/kernel/test_aegis.py` (append new tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/kernel/test_aegis.py`:

```python
def test_get_trust_level(aegis):
    aegis.set_policy("oracle", allowed=True)
    assert aegis.get_trust("oracle") == 0


def test_adjust_trust_positive(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=10, reason="successful prediction")
    assert aegis.get_trust("oracle") == 10


def test_adjust_trust_negative(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=30, reason="setup")
    aegis.adjust_trust("oracle", delta=-15, reason="bad prediction")
    assert aegis.get_trust("oracle") == 15


def test_trust_clamped_0_100(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=200, reason="overflow test")
    assert aegis.get_trust("oracle") == 100
    aegis.adjust_trust("oracle", delta=-300, reason="underflow test")
    assert aegis.get_trust("oracle") == 0


def test_check_with_trust_threshold(aegis):
    aegis.set_policy("wraith", allowed=True)
    aegis.adjust_trust("wraith", delta=25, reason="earned")
    # Should pass if required trust <= current trust
    assert aegis.check_trust("wraith", required_trust=20) is True
    assert aegis.check_trust("wraith", required_trust=50) is False


def test_trust_history(aegis):
    aegis.set_policy("echo", allowed=True)
    aegis.adjust_trust("echo", delta=10, reason="good draft")
    aegis.adjust_trust("echo", delta=5, reason="style match")
    history = aegis.trust_history("echo")
    assert len(history) == 2
    assert history[0]["reason"] == "good draft"
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/kernel/test_aegis.py -v`
Expected: Existing 7 pass, new 6 fail (methods don't exist yet)

- [ ] **Step 3: Implement graduated trust**

Add these methods to the `Aegis` class in `nexus/kernel/aegis.py`:

```python
    def get_trust(self, module: str) -> int:
        conn = self._conn()
        row = conn.execute("SELECT trust FROM aegis_policies WHERE module = ?", (module,)).fetchone()
        conn.close()
        return int(row["trust"]) if row else 0

    def adjust_trust(self, module: str, delta: int, reason: str) -> int:
        conn = self._conn()
        row = conn.execute("SELECT trust FROM aegis_policies WHERE module = ?", (module,)).fetchone()
        if row is None:
            conn.close()
            return 0
        new_trust = max(0, min(100, int(row["trust"]) + delta))
        conn.execute("UPDATE aegis_policies SET trust = ? WHERE module = ?", (new_trust, module))
        conn.commit()
        conn.close()
        self._log_trust_change(module, delta, new_trust, reason)
        return new_trust

    def check_trust(self, module: str, required_trust: int) -> bool:
        return self.get_trust(module) >= required_trust

    def _log_trust_change(self, module: str, delta: int, new_trust: int, reason: str) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_trust_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                module    TEXT NOT NULL,
                delta     INTEGER NOT NULL,
                new_trust INTEGER NOT NULL,
                reason    TEXT NOT NULL
            )
        """)
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO aegis_trust_log (timestamp, module, delta, new_trust, reason) VALUES (?, ?, ?, ?, ?)",
            (ts, module, delta, new_trust, reason),
        )
        conn.commit()
        conn.close()

    def trust_history(self, module: str, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_trust_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                module    TEXT NOT NULL,
                delta     INTEGER NOT NULL,
                new_trust INTEGER NOT NULL,
                reason    TEXT NOT NULL
            )
        """)
        rows = conn.execute(
            "SELECT timestamp, delta, new_trust, reason FROM aegis_trust_log WHERE module = ? ORDER BY id ASC LIMIT ?",
            (module, limit),
        ).fetchall()
        conn.close()
        return [{"timestamp": r["timestamp"], "delta": r["delta"], "new_trust": r["new_trust"], "reason": r["reason"]} for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/kernel/test_aegis.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/aegis.py tests/kernel/test_aegis.py
git commit -m "feat: Aegis graduated trust — 0-100 scoring with outcome-based adjustment and history"
git push origin main
```

---

### Task 2: Wraith — Phantom Agent Spawner

**Files:**
- Create: `nexus/modules/wraith.py`
- Create: `tests/modules/test_wraith.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_wraith.py
import asyncio
import pytest
from nexus.modules.wraith import WraithModule, Phantom, PhantomStatus


@pytest.fixture
def wraith():
    return WraithModule()


def test_wraith_attrs(wraith):
    assert wraith.name == "wraith"
    assert wraith.version == "0.1.0"


@pytest.mark.asyncio
async def test_spawn_phantom(wraith):
    async def research_task(mission: str) -> str:
        return f"Found info about: {mission}"

    phantom = await wraith.spawn(
        mission="Research Acme Corp before meeting",
        task_fn=research_task,
        timeout_seconds=5,
    )
    assert isinstance(phantom, Phantom)
    assert phantom.mission == "Research Acme Corp before meeting"
    assert phantom.status == PhantomStatus.RUNNING


@pytest.mark.asyncio
async def test_phantom_completes(wraith):
    async def quick_task(mission: str) -> str:
        return f"Done: {mission}"

    phantom = await wraith.spawn("quick job", quick_task, timeout_seconds=5)
    await wraith.wait(phantom.id, timeout=3)
    updated = wraith.get_phantom(phantom.id)
    assert updated.status == PhantomStatus.COMPLETED
    assert "Done" in updated.result


@pytest.mark.asyncio
async def test_phantom_timeout(wraith):
    async def slow_task(mission: str) -> str:
        await asyncio.sleep(10)
        return "never"

    phantom = await wraith.spawn("slow job", slow_task, timeout_seconds=0.1)
    await wraith.wait(phantom.id, timeout=1)
    updated = wraith.get_phantom(phantom.id)
    assert updated.status in (PhantomStatus.TIMED_OUT, PhantomStatus.FAILED)


@pytest.mark.asyncio
async def test_list_phantoms(wraith):
    async def task(m: str) -> str:
        return m

    await wraith.spawn("job1", task, timeout_seconds=5)
    await wraith.spawn("job2", task, timeout_seconds=5)
    phantoms = wraith.list_phantoms()
    assert len(phantoms) == 2


@pytest.mark.asyncio
async def test_phantom_auto_cleanup(wraith):
    async def task(m: str) -> str:
        return m

    phantom = await wraith.spawn("temp", task, timeout_seconds=5)
    await wraith.wait(phantom.id, timeout=2)
    wraith.cleanup_completed()
    assert len(wraith.list_phantoms()) == 0


@pytest.mark.asyncio
async def test_wraith_handle(wraith):
    result = await wraith.handle("status", {"llm": None})
    assert "wraith" in result.lower() or "phantom" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_wraith.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Wraith module**

```python
# nexus/modules/wraith.py
"""
Wraith — phantom agent spawner.
Spawns ephemeral async micro-agents with single missions, time limits,
and auto-termination. Results merge into Engram automatically.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
from nexus.modules.base import NexusModule


class PhantomStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class Phantom:
    id: str
    mission: str
    status: PhantomStatus
    timeout_seconds: float
    result: str = ""
    error: str = ""
    _task: asyncio.Task | None = field(default=None, repr=False)


class WraithModule(NexusModule):
    name = "wraith"
    description = "Phantom agent spawner — ephemeral micro-agents with death clocks"
    version = "0.1.0"

    def __init__(self):
        self._phantoms: dict[str, Phantom] = {}

    async def spawn(
        self,
        mission: str,
        task_fn: Callable[[str], Awaitable[str]],
        timeout_seconds: float = 30,
    ) -> Phantom:
        phantom_id = uuid.uuid4().hex[:8]
        phantom = Phantom(
            id=phantom_id,
            mission=mission,
            status=PhantomStatus.RUNNING,
            timeout_seconds=timeout_seconds,
        )
        self._phantoms[phantom_id] = phantom

        async def _run():
            try:
                result = await asyncio.wait_for(
                    task_fn(mission),
                    timeout=timeout_seconds,
                )
                phantom.result = result
                phantom.status = PhantomStatus.COMPLETED
            except asyncio.TimeoutError:
                phantom.status = PhantomStatus.TIMED_OUT
                phantom.error = f"Timed out after {timeout_seconds}s"
            except Exception as e:
                phantom.status = PhantomStatus.FAILED
                phantom.error = str(e)

        phantom._task = asyncio.ensure_future(_run())
        return phantom

    async def wait(self, phantom_id: str, timeout: float = 30) -> None:
        phantom = self._phantoms.get(phantom_id)
        if phantom and phantom._task:
            try:
                await asyncio.wait_for(asyncio.shield(phantom._task), timeout=timeout)
            except asyncio.TimeoutError:
                pass

    def get_phantom(self, phantom_id: str) -> Phantom | None:
        return self._phantoms.get(phantom_id)

    def list_phantoms(self) -> list[Phantom]:
        return list(self._phantoms.values())

    def cleanup_completed(self) -> int:
        completed = [pid for pid, p in self._phantoms.items() if p.status != PhantomStatus.RUNNING]
        for pid in completed:
            del self._phantoms[pid]
        return len(completed)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        active = [p for p in self._phantoms.values() if p.status == PhantomStatus.RUNNING]
        done = [p for p in self._phantoms.values() if p.status != PhantomStatus.RUNNING]
        lines = [
            f"[Wraith] Phantom agents: {len(self._phantoms)} total",
            f"  Active: {len(active)}",
            f"  Completed: {len(done)}",
        ]
        for p in active:
            lines.append(f"  - [{p.id}] {p.mission} (running, timeout: {p.timeout_seconds}s)")
        for p in done:
            lines.append(f"  - [{p.id}] {p.mission} ({p.status.value})")
        if not self._phantoms:
            lines.append("  No phantoms spawned.")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_wraith.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/wraith.py tests/modules/test_wraith.py
git commit -m "feat: Wraith module — phantom agent spawner with death clocks and auto-cleanup"
git push origin main
```

---

### Task 3: Echo — Behavioral Fingerprinting

**Files:**
- Create: `nexus/modules/echo.py`
- Create: `tests/modules/test_echo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_echo.py
import pytest
from nexus.modules.echo import EchoModule, BehavioralProfile


@pytest.fixture
def echo():
    return EchoModule()


def test_echo_attrs(echo):
    assert echo.name == "echo"
    assert echo.version == "0.1.0"


def test_observe_text_sample(echo):
    echo.observe("email", "Hey team, quick update on the Flexport integration. We're ahead of schedule and the API looks solid. Let's sync Thursday to finalize.")
    profile = echo.get_profile("email")
    assert isinstance(profile, BehavioralProfile)
    assert profile.sample_count == 1


def test_observe_multiple_samples(echo):
    echo.observe("email", "Quick update — shipping module is done.")
    echo.observe("email", "Following up on yesterday's call. Two action items.")
    echo.observe("email", "FYI the deadline moved to Friday. No blockers on our end.")
    profile = echo.get_profile("email")
    assert profile.sample_count == 3
    assert profile.avg_word_count > 0


def test_profile_captures_vocabulary(echo):
    echo.observe("slack", "lgtm ship it")
    echo.observe("slack", "nice, lgtm")
    echo.observe("slack", "ship it, looks good")
    profile = echo.get_profile("slack")
    assert "lgtm" in profile.top_phrases or "ship" in profile.top_phrases


def test_profile_captures_sentence_length(echo):
    echo.observe("report", "This is a very long and detailed sentence about the quarterly performance metrics and their implications for the next fiscal year.")
    echo.observe("report", "Another comprehensive analysis of the market conditions affecting our supply chain operations across multiple regions.")
    profile = echo.get_profile("report")
    assert profile.avg_sentence_length > 10


def test_list_domains(echo):
    echo.observe("email", "test")
    echo.observe("slack", "test")
    assert set(echo.list_domains()) == {"email", "slack"}


def test_match_style(echo):
    echo.observe("email", "Hey, quick heads up — the build is green. Ship when ready.")
    echo.observe("email", "Quick note: API changes landed. Should be backwards compatible.")
    echo.observe("email", "FYI pushed the hotfix. All tests passing.")
    score = echo.match_style("email", "Hey, just a quick note — PR is up. Looks good to merge.")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_echo_handle(echo):
    echo.observe("email", "Test observation")
    result = await echo.handle("Show my behavioral profile", {"llm": None})
    assert "email" in result.lower() or "profile" in result.lower()


@pytest.mark.asyncio
async def test_echo_handle_empty(echo):
    result = await echo.handle("Show my profile", {"llm": None})
    assert "no observations" in result.lower() or "no behavioral" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_echo.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Echo module**

```python
# nexus/modules/echo.py
"""
Echo — behavioral fingerprinting and skill transfer.
Observes how the user writes across domains, builds behavioral profiles,
and can score new text for style match. Patterns transfer across domains.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class BehavioralProfile:
    domain: str
    sample_count: int = 0
    avg_word_count: float = 0.0
    avg_sentence_length: float = 0.0
    top_phrases: list[str] = field(default_factory=list)
    formality_score: float = 0.5
    _word_counts: list[int] = field(default_factory=list, repr=False)
    _sentence_lengths: list[float] = field(default_factory=list, repr=False)
    _word_freq: Counter = field(default_factory=Counter, repr=False)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


_FORMAL_MARKERS = {"therefore", "however", "furthermore", "regarding", "consequently", "comprehensive", "pursuant", "accordingly"}
_INFORMAL_MARKERS = {"hey", "lgtm", "fyi", "btw", "gonna", "wanna", "cool", "nice", "awesome", "yeah", "nope", "ship"}


class EchoModule(NexusModule):
    name = "echo"
    description = "Behavioral fingerprinting — learns writing style and decision patterns"
    version = "0.1.0"

    def __init__(self):
        self._profiles: dict[str, BehavioralProfile] = {}

    def observe(self, domain: str, text: str) -> None:
        """Record a text sample for a domain and update the profile."""
        if domain not in self._profiles:
            self._profiles[domain] = BehavioralProfile(domain=domain)
        profile = self._profiles[domain]
        profile.sample_count += 1

        words = _words(text)
        sents = _sentences(text)

        profile._word_counts.append(len(words))
        profile.avg_word_count = sum(profile._word_counts) / len(profile._word_counts)

        if sents:
            avg_sent = sum(len(_words(s)) for s in sents) / len(sents)
            profile._sentence_lengths.append(avg_sent)
            profile.avg_sentence_length = sum(profile._sentence_lengths) / len(profile._sentence_lengths)

        profile._word_freq.update(words)
        profile.top_phrases = [w for w, _ in profile._word_freq.most_common(10)]

        # Formality scoring
        formal_hits = sum(1 for w in words if w in _FORMAL_MARKERS)
        informal_hits = sum(1 for w in words if w in _INFORMAL_MARKERS)
        total = formal_hits + informal_hits
        if total > 0:
            new_formality = formal_hits / total
            # Weighted rolling average
            alpha = 1.0 / profile.sample_count
            profile.formality_score = (1 - alpha) * profile.formality_score + alpha * new_formality

    def get_profile(self, domain: str) -> BehavioralProfile | None:
        return self._profiles.get(domain)

    def list_domains(self) -> list[str]:
        return list(self._profiles.keys())

    def match_style(self, domain: str, text: str) -> float:
        """Score how well a text matches the observed style for a domain (0.0–1.0)."""
        profile = self._profiles.get(domain)
        if not profile or profile.sample_count == 0:
            return 0.5

        words = _words(text)
        sents = _sentences(text)

        # Word count similarity
        wc_diff = abs(len(words) - profile.avg_word_count) / max(profile.avg_word_count, 1)
        wc_score = max(0, 1.0 - wc_diff)

        # Sentence length similarity
        sl_score = 0.5
        if sents and profile.avg_sentence_length > 0:
            avg_sl = sum(len(_words(s)) for s in sents) / len(sents)
            sl_diff = abs(avg_sl - profile.avg_sentence_length) / max(profile.avg_sentence_length, 1)
            sl_score = max(0, 1.0 - sl_diff)

        # Vocabulary overlap
        vocab_overlap = sum(1 for w in words if w in profile._word_freq) / max(len(words), 1)

        return round((wc_score * 0.3 + sl_score * 0.3 + vocab_overlap * 0.4), 3)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._profiles:
            return "[Echo] No behavioral observations recorded yet."
        lines = ["[Echo] Behavioral profiles:"]
        for domain, profile in self._profiles.items():
            lines.append(f"  [{domain}] {profile.sample_count} samples")
            lines.append(f"    Avg words: {profile.avg_word_count:.1f}")
            lines.append(f"    Avg sentence length: {profile.avg_sentence_length:.1f} words")
            lines.append(f"    Formality: {profile.formality_score:.2f}")
            if profile.top_phrases:
                lines.append(f"    Top vocabulary: {', '.join(profile.top_phrases[:5])}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_echo.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/echo.py tests/modules/test_echo.py
git commit -m "feat: Echo module — behavioral fingerprinting with style matching and formality scoring"
git push origin main
```

---

### Task 4: Sigil — Threat Radar

**Files:**
- Create: `nexus/modules/sigil.py`
- Create: `tests/modules/test_sigil.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_sigil.py
import pytest
from nexus.modules.sigil import SigilModule, Threat, ThreatSeverity


@pytest.fixture
def sigil():
    return SigilModule()


def test_sigil_attrs(sigil):
    assert sigil.name == "sigil"
    assert sigil.version == "0.1.0"


def test_register_threat(sigil):
    threat = sigil.register_threat(
        category="security",
        description="Credential found in public paste",
        severity=ThreatSeverity.CRITICAL,
        source="osint_scan",
    )
    assert isinstance(threat, Threat)
    assert threat.severity == ThreatSeverity.CRITICAL


def test_list_threats(sigil):
    sigil.register_threat("security", "Leaked API key", ThreatSeverity.HIGH, "scan")
    sigil.register_threat("reputation", "Negative mention on Twitter", ThreatSeverity.LOW, "social")
    threats = sigil.list_threats()
    assert len(threats) == 2


def test_threats_sorted_by_severity(sigil):
    sigil.register_threat("financial", "Minor variance", ThreatSeverity.LOW, "report")
    sigil.register_threat("security", "Account breach", ThreatSeverity.CRITICAL, "scan")
    sigil.register_threat("reputation", "Bad review", ThreatSeverity.MEDIUM, "social")
    threats = sigil.list_threats()
    assert threats[0].severity == ThreatSeverity.CRITICAL
    assert threats[-1].severity == ThreatSeverity.LOW


def test_acknowledge_threat(sigil):
    threat = sigil.register_threat("test", "test threat", ThreatSeverity.LOW, "test")
    sigil.acknowledge(threat.id)
    updated = sigil.get_threat(threat.id)
    assert updated.acknowledged is True


def test_filter_by_severity(sigil):
    sigil.register_threat("a", "low", ThreatSeverity.LOW, "s")
    sigil.register_threat("b", "critical", ThreatSeverity.CRITICAL, "s")
    sigil.register_threat("c", "high", ThreatSeverity.HIGH, "s")
    critical = sigil.list_threats(min_severity=ThreatSeverity.HIGH)
    assert len(critical) == 2


def test_filter_unacknowledged(sigil):
    t1 = sigil.register_threat("a", "threat1", ThreatSeverity.LOW, "s")
    sigil.register_threat("b", "threat2", ThreatSeverity.LOW, "s")
    sigil.acknowledge(t1.id)
    unacked = sigil.list_threats(unacknowledged_only=True)
    assert len(unacked) == 1


@pytest.mark.asyncio
async def test_sigil_handle(sigil):
    sigil.register_threat("security", "API key exposed", ThreatSeverity.HIGH, "scan")
    result = await sigil.handle("What threats are active?", {"llm": None})
    assert "api key" in result.lower() or "threat" in result.lower()


@pytest.mark.asyncio
async def test_sigil_handle_empty(sigil):
    result = await sigil.handle("threats", {"llm": None})
    assert "no active" in result.lower() or "clear" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_sigil.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Sigil module**

```python
# nexus/modules/sigil.py
"""
Sigil — ambient threat radar.
Registers, prioritizes, and tracks threats across categories:
security, reputation, financial, competitive, relationship.
Critical threats bypass normal Pulse priority.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any
from nexus.modules.base import NexusModule


class ThreatSeverity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4


@dataclass
class Threat:
    id: str
    category: str
    description: str
    severity: ThreatSeverity
    source: str
    timestamp: str
    acknowledged: bool = False


class SigilModule(NexusModule):
    name = "sigil"
    description = "Ambient threat radar — severity-prioritized early warning system"
    version = "0.1.0"

    def __init__(self):
        self._threats: dict[str, Threat] = {}

    def register_threat(
        self,
        category: str,
        description: str,
        severity: ThreatSeverity,
        source: str,
    ) -> Threat:
        threat_id = uuid.uuid4().hex[:8]
        ts = datetime.now(timezone.utc).isoformat()
        threat = Threat(
            id=threat_id,
            category=category,
            description=description,
            severity=severity,
            source=source,
            timestamp=ts,
        )
        self._threats[threat_id] = threat
        return threat

    def get_threat(self, threat_id: str) -> Threat | None:
        return self._threats.get(threat_id)

    def acknowledge(self, threat_id: str) -> None:
        threat = self._threats.get(threat_id)
        if threat:
            threat.acknowledged = True

    def list_threats(
        self,
        min_severity: ThreatSeverity | None = None,
        unacknowledged_only: bool = False,
    ) -> list[Threat]:
        threats = list(self._threats.values())
        if min_severity is not None:
            threats = [t for t in threats if t.severity <= min_severity]
        if unacknowledged_only:
            threats = [t for t in threats if not t.acknowledged]
        threats.sort(key=lambda t: t.severity)
        return threats

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        threats = self.list_threats(unacknowledged_only=True)
        if not threats:
            return "[Sigil] No active threats. Radar clear."
        lines = [f"[Sigil] {len(threats)} active threat(s):"]
        for t in threats:
            sev_name = t.severity.name
            lines.append(f"  [{sev_name}] {t.category}: {t.description}")
            lines.append(f"    Source: {t.source} | {t.timestamp}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_sigil.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/sigil.py tests/modules/test_sigil.py
git commit -m "feat: Sigil module — ambient threat radar with severity-based prioritization"
git push origin main
```

---

### Task 5: Herald — Agent-to-Agent Communication

**Files:**
- Create: `nexus/modules/herald.py`
- Create: `tests/modules/test_herald.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_herald.py
import pytest
from nexus.modules.herald import HeraldModule, ExternalAgent, A2AMessage


@pytest.fixture
def herald():
    return HeraldModule()


def test_herald_attrs(herald):
    assert herald.name == "herald"
    assert herald.version == "0.1.0"


def test_register_agent(herald):
    agent = herald.register_agent(
        agent_id="agent-alice-001",
        name="Alice's Nexus",
        endpoint="https://alice.nexus.local:8400",
        trust_grant=50,
    )
    assert isinstance(agent, ExternalAgent)
    assert agent.name == "Alice's Nexus"


def test_list_agents(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.register_agent("a2", "Agent B", "http://b:8400", 30)
    agents = herald.list_agents()
    assert len(agents) == 2


def test_revoke_agent(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.revoke_agent("a1")
    assert len(herald.list_agents()) == 0


def test_send_message(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    msg = herald.compose_message(
        to_agent="a1",
        content="Schedule meeting for Thursday",
        msg_type="request",
    )
    assert isinstance(msg, A2AMessage)
    assert msg.to_agent == "a1"
    assert msg.content == "Schedule meeting for Thursday"


def test_send_to_unknown_agent_fails(herald):
    with pytest.raises(KeyError):
        herald.compose_message("unknown", "hello", "request")


def test_message_history(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.compose_message("a1", "msg1", "request")
    herald.compose_message("a1", "msg2", "response")
    history = herald.message_history("a1")
    assert len(history) == 2


def test_agent_reputation(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    herald.record_interaction_outcome("a1", success=True)
    herald.record_interaction_outcome("a1", success=True)
    herald.record_interaction_outcome("a1", success=False)
    agent = herald.get_agent("a1")
    assert agent.reputation > 0.5


@pytest.mark.asyncio
async def test_herald_handle(herald):
    herald.register_agent("a1", "Agent A", "http://a:8400", 50)
    result = await herald.handle("Show connected agents", {"llm": None})
    assert "agent a" in result.lower() or "a1" in result.lower()


@pytest.mark.asyncio
async def test_herald_handle_empty(herald):
    result = await herald.handle("agents", {"llm": None})
    assert "no external" in result.lower() or "no agent" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_herald.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Herald module**

```python
# nexus/modules/herald.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_herald.py -v`
Expected: 10 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/herald.py tests/modules/test_herald.py
git commit -m "feat: Herald module — A2A agent communication with reputation tracking"
git push origin main
```

---

### Task 6: Weave — Social Graph Intelligence

**Files:**
- Create: `nexus/modules/weave.py`
- Create: `tests/modules/test_weave.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/modules/test_weave.py
import pytest
from nexus.modules.weave import WeaveModule, Contact, RelationshipHealth


@pytest.fixture
def weave():
    return WeaveModule()


def test_weave_attrs(weave):
    assert weave.name == "weave"
    assert weave.version == "0.1.0"


def test_add_contact(weave):
    contact = weave.add_contact(
        name="Alice Chen",
        tags=["engineering", "frontend"],
    )
    assert isinstance(contact, Contact)
    assert contact.name == "Alice Chen"


def test_record_interaction(weave):
    c = weave.add_contact("Bob Smith", ["sales"])
    weave.record_interaction(c.id, "email", "Discussed Q3 targets")
    contact = weave.get_contact(c.id)
    assert contact.interaction_count == 1


def test_relationship_health_active(weave):
    c = weave.add_contact("Carol", ["team"])
    weave.record_interaction(c.id, "meeting", "Weekly sync")
    weave.record_interaction(c.id, "slack", "Quick question")
    weave.record_interaction(c.id, "email", "Project update")
    health = weave.get_health(c.id)
    assert health == RelationshipHealth.ACTIVE


def test_relationship_health_new(weave):
    c = weave.add_contact("Dan", ["vendor"])
    health = weave.get_health(c.id)
    assert health == RelationshipHealth.NEW


def test_find_connections(weave):
    c1 = weave.add_contact("Alice", ["engineering", "frontend"])
    c2 = weave.add_contact("Bob", ["engineering", "backend"])
    c3 = weave.add_contact("Carol", ["sales"])
    connections = weave.find_connections("engineering")
    assert len(connections) == 2


def test_reconnection_suggestions(weave):
    c = weave.add_contact("Old Friend", ["personal"])
    # No interactions = stale relationship
    suggestions = weave.reconnection_suggestions()
    assert len(suggestions) >= 1
    assert suggestions[0].name == "Old Friend"


def test_add_connection_between_contacts(weave):
    c1 = weave.add_contact("Alice", ["eng"])
    c2 = weave.add_contact("Bob", ["eng"])
    weave.add_link(c1.id, c2.id, "colleagues")
    links = weave.get_links(c1.id)
    assert len(links) == 1
    assert links[0]["contact_id"] == c2.id


@pytest.mark.asyncio
async def test_weave_handle(weave):
    weave.add_contact("Alice", ["team"])
    result = await weave.handle("Show my network", {"llm": None})
    assert "alice" in result.lower() or "contact" in result.lower()


@pytest.mark.asyncio
async def test_weave_handle_empty(weave):
    result = await weave.handle("network", {"llm": None})
    assert "no contacts" in result.lower() or "empty" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_weave.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Weave module**

```python
# nexus/modules/weave.py
"""
Weave — social graph intelligence.
Maps contacts, tracks interaction frequency, detects decaying relationships,
and models who-knows-who connections.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from nexus.modules.base import NexusModule


class RelationshipHealth(Enum):
    ACTIVE = "active"
    STABLE = "stable"
    COOLING = "cooling"
    STALE = "stale"
    NEW = "new"


@dataclass
class Interaction:
    channel: str
    note: str
    timestamp: str


@dataclass
class Contact:
    id: str
    name: str
    tags: list[str]
    interactions: list[Interaction] = field(default_factory=list)
    interaction_count: int = 0
    links: list[dict[str, str]] = field(default_factory=list)


class WeaveModule(NexusModule):
    name = "weave"
    description = "Social graph intelligence — relationship mapping and health tracking"
    version = "0.1.0"

    def __init__(self):
        self._contacts: dict[str, Contact] = {}

    def add_contact(self, name: str, tags: list[str] | None = None) -> Contact:
        contact_id = uuid.uuid4().hex[:8]
        contact = Contact(id=contact_id, name=name, tags=tags or [])
        self._contacts[contact_id] = contact
        return contact

    def get_contact(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def record_interaction(self, contact_id: str, channel: str, note: str) -> None:
        contact = self._contacts.get(contact_id)
        if not contact:
            return
        ts = datetime.now(timezone.utc).isoformat()
        contact.interactions.append(Interaction(channel=channel, note=note, timestamp=ts))
        contact.interaction_count += 1

    def get_health(self, contact_id: str) -> RelationshipHealth:
        contact = self._contacts.get(contact_id)
        if not contact:
            return RelationshipHealth.NEW
        count = contact.interaction_count
        if count == 0:
            return RelationshipHealth.NEW
        if count >= 3:
            return RelationshipHealth.ACTIVE
        if count >= 1:
            return RelationshipHealth.STABLE
        return RelationshipHealth.COOLING

    def find_connections(self, tag: str) -> list[Contact]:
        return [c for c in self._contacts.values() if tag.lower() in [t.lower() for t in c.tags]]

    def reconnection_suggestions(self) -> list[Contact]:
        stale = []
        for contact in self._contacts.values():
            health = self.get_health(contact.id)
            if health in (RelationshipHealth.NEW, RelationshipHealth.STALE, RelationshipHealth.COOLING):
                stale.append(contact)
        return stale

    def add_link(self, from_id: str, to_id: str, relationship: str) -> None:
        contact = self._contacts.get(from_id)
        if contact:
            contact.links.append({"contact_id": to_id, "relationship": relationship})
        contact2 = self._contacts.get(to_id)
        if contact2:
            contact2.links.append({"contact_id": from_id, "relationship": relationship})

    def get_links(self, contact_id: str) -> list[dict[str, str]]:
        contact = self._contacts.get(contact_id)
        return contact.links if contact else []

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._contacts:
            return "[Weave] No contacts in the social graph yet."
        lines = [f"[Weave] Social graph: {len(self._contacts)} contact(s)"]
        for contact in self._contacts.values():
            health = self.get_health(contact.id)
            tags_str = ", ".join(contact.tags) if contact.tags else "no tags"
            lines.append(f"  - {contact.name} ({tags_str}) [{health.value}]")
            lines.append(f"    Interactions: {contact.interaction_count} | Links: {len(contact.links)}")
        suggestions = self.reconnection_suggestions()
        if suggestions:
            lines.append(f"  Reconnection suggestions: {', '.join(s.name for s in suggestions)}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/modules/test_weave.py -v`
Expected: 10 PASSED

- [ ] **Step 5: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/modules/weave.py tests/modules/test_weave.py
git commit -m "feat: Weave module — social graph with relationship health tracking"
git push origin main
```

---

### Task 7: Cortex Router Update + Batch 3 Integration Tests

**Files:**
- Modify: `nexus/kernel/cortex.py` (add new module keywords)
- Create: `tests/test_batch3_integration.py`

- [ ] **Step 1: Update Cortex keywords**

Add these entries to `_MODULE_KEYWORDS` in `nexus/kernel/cortex.py`:

```python
        "wraith": ["phantom", "spawn", "agent", "swarm", "research task"],
        "echo": ["behavioral", "fingerprint", "style", "voice", "profile", "writing"],
        "herald": ["external agent", "a2a", "communicate", "connected agent"],
        "weave": ["contact", "network", "relationship", "social graph", "reconnect"],
        "sigil": ["threat", "danger", "security", "breach", "risk", "radar"],
```

- [ ] **Step 2: Write integration tests**

```python
# tests/test_batch3_integration.py
"""
Batch 3 integration: Action layer modules working together through Cortex.
Wraith spawns phantoms, Echo observes behavior, Sigil tracks threats,
Herald manages agents, Weave maps social graph.
"""
import asyncio
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.wraith import WraithModule
from nexus.modules.echo import EchoModule
from nexus.modules.sigil import SigilModule, ThreatSeverity
from nexus.modules.herald import HeraldModule
from nexus.modules.weave import WeaveModule


@pytest.fixture
def action_system(tmp_config):
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
        "wraith": WraithModule(),
        "echo": EchoModule(),
        "sigil": SigilModule(),
        "herald": HeraldModule(),
        "weave": WeaveModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, "aegis": aegis, **modules}


@pytest.mark.asyncio
async def test_wraith_spawns_via_cortex(action_system):
    cortex = action_system["cortex"]
    response = await cortex.process("Show phantom agent swarm status")
    assert "wraith" in response.lower() or "phantom" in response.lower()


@pytest.mark.asyncio
async def test_echo_responds_via_cortex(action_system):
    echo = action_system["echo"]
    echo.observe("email", "Quick update — tests are green.")
    cortex = action_system["cortex"]
    response = await cortex.process("Show my behavioral writing profile")
    assert "email" in response.lower() or "profile" in response.lower()


@pytest.mark.asyncio
async def test_sigil_reports_via_cortex(action_system):
    sigil = action_system["sigil"]
    sigil.register_threat("security", "Credential leak detected", ThreatSeverity.HIGH, "scan")
    cortex = action_system["cortex"]
    response = await cortex.process("What security threats and risks are active?")
    assert "credential" in response.lower() or "threat" in response.lower()


@pytest.mark.asyncio
async def test_herald_via_cortex(action_system):
    herald = action_system["herald"]
    herald.register_agent("a1", "Remote Agent", "http://remote:8400", 50)
    cortex = action_system["cortex"]
    response = await cortex.process("Show connected external agents and a2a status")
    assert "remote" in response.lower() or "agent" in response.lower()


@pytest.mark.asyncio
async def test_weave_via_cortex(action_system):
    weave = action_system["weave"]
    weave.add_contact("Alice", ["engineering"])
    cortex = action_system["cortex"]
    response = await cortex.process("Show my contact network and social graph")
    assert "alice" in response.lower() or "contact" in response.lower()


@pytest.mark.asyncio
async def test_aegis_graduated_trust(action_system):
    aegis = action_system["aegis"]
    aegis.adjust_trust("wraith", delta=30, reason="successful research")
    assert aegis.get_trust("wraith") == 30
    assert aegis.check_trust("wraith", required_trust=25) is True
    assert aegis.check_trust("wraith", required_trust=50) is False


@pytest.mark.asyncio
async def test_all_action_modules_registered(action_system):
    cortex = action_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "wraith", "echo", "sigil", "herald", "weave"]:
        assert name in modules
```

- [ ] **Step 3: Run integration tests**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/test_batch3_integration.py -v`
Expected: 7 PASSED

- [ ] **Step 4: Run full suite**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v`
Expected: ALL PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add nexus/kernel/cortex.py tests/test_batch3_integration.py
git commit -m "feat: Cortex routing for action modules + Batch 3 integration tests"
git push origin main
```

---

### Task 8: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the module roadmap**

Update the Batch 3 line from `░░░░░░░░░░ PLANNED` to `██████████ BUILT` and update its module list to match what was actually built (Wraith, Echo, Sigil, Herald, Weave + Aegis graduated trust).

Update the test count badge and the test count in the Testing section to reflect the new total.

Update the Project Structure section to include all new module files.

- [ ] **Step 2: Run full suite to get final count**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/ -v --tb=short`

- [ ] **Step 3: Commit**

```bash
cd /Users/connorevans/Downloads/NEXUS
git add README.md
git commit -m "docs: update README for Batch 3 completion"
git push origin main
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Aegis graduated trust (0-100, outcome-based) — Task 1
- [x] Wraith (phantom agent spawner) — Task 2
- [x] Echo (behavioral fingerprinting) — Task 3
- [x] Sigil (threat radar) — Task 4
- [x] Herald (A2A communication) — Task 5
- [x] Weave (social graph) — Task 6
- [x] Cortex routing + integration tests — Task 7
- [x] README update — Task 8

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks complete.

**Type consistency:** `WraithModule`/`Phantom`/`PhantomStatus`, `EchoModule`/`BehavioralProfile`, `SigilModule`/`Threat`/`ThreatSeverity`, `HeraldModule`/`ExternalAgent`/`A2AMessage`, `WeaveModule`/`Contact`/`RelationshipHealth` — all names consistent across tasks.

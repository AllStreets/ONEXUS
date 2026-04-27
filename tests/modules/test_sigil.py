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

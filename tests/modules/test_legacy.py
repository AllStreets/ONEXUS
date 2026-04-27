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

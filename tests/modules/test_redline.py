# tests/modules/test_redline.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.redline import RedlineModule


@pytest.fixture
def redline():
    return RedlineModule()


def test_redline_attrs(redline):
    assert redline.name == "redline"
    assert redline.version == "0.1.0"


def test_detect_unlimited_liability(redline):
    text = "The contractor shall have unlimited liability for all damages arising from this agreement."
    findings = redline.analyze(text)
    assert any(f.clause_type == "Liability" for f in findings)
    assert any(f.severity == "high" for f in findings)


def test_detect_non_compete(redline):
    text = "Employee agrees to a non-compete restriction for 3 years following termination."
    findings = redline.analyze(text)
    assert any(f.clause_type == "Non-Compete" for f in findings)


def test_detect_auto_renewal(redline):
    text = "This agreement will auto-renew for successive one-year terms."
    findings = redline.analyze(text)
    assert any(f.clause_type == "Auto-Renewal" for f in findings)


def test_detect_ip_assignment(redline):
    text = "All intellectual property created during this engagement shall belong to the company."
    findings = redline.analyze(text)
    assert any(f.clause_type == "IP Assignment" for f in findings)


def test_detect_missing_liability_cap(redline):
    text = "This is a simple agreement between two parties."
    findings = redline.analyze(text)
    assert any(f.clause_type == "Missing Protection" and "liability" in f.issue.lower() for f in findings)


def test_detect_missing_termination(redline):
    text = "This is a simple agreement between two parties."
    findings = redline.analyze(text)
    assert any(f.clause_type == "Missing Protection" and "termination" in f.issue.lower() for f in findings)


def test_clean_contract(redline):
    text = (
        "This agreement includes limitation of liability capped at fees paid. "
        "Termination: Either party may terminate with 30 days written notice."
    )
    findings = redline.analyze(text)
    # Should have no missing protections for liability or termination
    assert not any(f.issue == "No limitation of liability clause found" for f in findings)
    assert not any(f.issue == "No termination clause found" for f in findings)


def test_risk_score_high(redline):
    text = "Unlimited liability. Non-compete for 5 years. IP assignment belongs to company."
    findings = redline.analyze(text)
    score = redline.risk_score(findings)
    assert score >= 30


def test_risk_score_zero(redline):
    assert redline.risk_score([]) == 0


def test_findings_sorted_by_severity(redline):
    text = (
        "Auto-renew annually. Unlimited liability for all damages. "
        "Force majeure clause applies. Non-compete 2 years."
    )
    findings = redline.analyze(text)
    if len(findings) >= 2:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        for i in range(len(findings) - 1):
            assert severity_order[findings[i].severity] <= severity_order[findings[i + 1].severity]


@pytest.mark.asyncio
async def test_handle_returns_analysis(redline):
    context = {"llm": None, "engram": None}
    result = await redline.handle(
        "The contractor agrees to unlimited liability and a non-compete for 5 years.",
        context,
    )
    assert "[Redline]" in result
    assert "Risk Score" in result
    assert "DISCLAIMER" in result


@pytest.mark.asyncio
async def test_handle_stores_review(redline):
    context = {"llm": None, "engram": None}
    await redline.handle("Some contract text here.", context)
    assert len(redline._reviews) == 1

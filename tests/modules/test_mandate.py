# tests/modules/test_mandate.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.mandate import MandateModule, Control, GapAnalysis


@pytest.fixture
def mandate():
    return MandateModule()


def test_mandate_attrs(mandate):
    assert mandate.name == "mandate"
    assert mandate.version == "0.1.0"


def test_detect_framework_gdpr(mandate):
    assert mandate.detect_framework("Check our GDPR compliance") == "gdpr"
    assert mandate.detect_framework("We handle personal data with consent") == "gdpr"


def test_detect_framework_hipaa(mandate):
    assert mandate.detect_framework("HIPAA audit needed") == "hipaa"
    assert mandate.detect_framework("We handle patient health records") == "hipaa"


def test_detect_framework_soc2(mandate):
    assert mandate.detect_framework("SOC2 readiness check") == "soc2"
    # Default fallback
    assert mandate.detect_framework("Run a compliance check") == "soc2"


def test_list_frameworks(mandate):
    frameworks = mandate.list_frameworks()
    assert "gdpr" in frameworks
    assert "soc2" in frameworks
    assert "hipaa" in frameworks


def test_assess_gdpr(mandate):
    practices = (
        "We obtain user consent for processing personal data. "
        "Users can request deletion and access their data. "
        "We have breach notification procedures within 72 hours."
    )
    analysis = mandate.assess("gdpr", practices)
    assert analysis.framework == "GDPR"
    assert analysis.controls_met + analysis.controls_partial + analysis.controls_missing == 10
    assert analysis.controls_met > 0


def test_assess_returns_all_controls(mandate):
    analysis = mandate.assess("soc2", "nothing relevant here")
    assert len(analysis.controls) == 9
    # With no matching text, most should be missing
    assert analysis.controls_missing >= 5


def test_assess_hipaa(mandate):
    practices = (
        "We encrypt all ePHI in transit and at rest. "
        "Access controls with unique user IDs and auto-logoff. "
        "Audit mechanisms for all access to protected health information."
    )
    analysis = mandate.assess("hipaa", practices)
    assert analysis.framework == "HIPAA"
    assert analysis.controls_met > 0


def test_control_statuses(mandate):
    analysis = mandate.assess("gdpr", "")
    for ctrl in analysis.controls:
        assert ctrl.status in ("met", "partial", "missing", "unknown")


@pytest.mark.asyncio
async def test_handle_returns_assessment(mandate):
    context = {"llm": None, "engram": None}
    result = await mandate.handle(
        "Check our GDPR compliance. We collect user consent and allow data deletion.",
        context,
    )
    assert "[Mandate]" in result
    assert "GDPR" in result
    assert "Score:" in result


@pytest.mark.asyncio
async def test_handle_with_llm(mandate):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Remediation: implement data portability API"
    context = {"llm": mock_llm, "engram": None}
    result = await mandate.handle("Check SOC2 compliance.", context)
    assert "[Mandate]" in result
    # LLM should be called for missing controls remediation
    assert mock_llm.complete.called


@pytest.mark.asyncio
async def test_handle_stores_analysis(mandate):
    context = {"llm": None, "engram": None}
    await mandate.handle("HIPAA audit", context)
    assert len(mandate._analyses) == 1

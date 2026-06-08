# tests/modules/test_specter.py
import pytest
from nexus.modules.specter import SpecterModule, RedTeamReport, StakeLevel


@pytest.fixture
def specter():
    return SpecterModule()


def test_specter_attrs(specter):
    assert specter.name == "specter"
    assert specter.version == "1.0.0"


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
    # Use adversarial analysis path (not "red team" audit path, which requires chronicle)
    result = await specter.handle(
        "Should I accept a 2-year non-compete clause for a 20% raise?",
        {"llm": None},
    )
    assert "counter" in result.lower() or "risk" in result.lower() or "assumption" in result.lower()


@pytest.mark.asyncio
async def test_specter_handle_low_stakes(specter):
    result = await specter.handle("What should I eat for lunch?", {"llm": None})
    assert "low" in result.lower() or "stake" in result.lower()

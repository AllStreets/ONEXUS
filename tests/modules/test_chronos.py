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

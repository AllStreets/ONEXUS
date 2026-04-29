# tests/modules/test_tally.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.tally import TallyModule


@pytest.fixture
def tally():
    return TallyModule()


def test_tally_attrs(tally):
    assert tally.name == "tally"
    assert tally.version == "0.1.0"


def test_parse_amount(tally):
    assert tally._parse_amount("$50K") == 50000.0
    assert tally._parse_amount("1M") == 1000000.0
    assert tally._parse_amount("25000") == 25000.0
    assert tally._parse_amount("$1,500") == 1500.0


def test_extract_assumptions(tally):
    text = "Our revenue is $50K MRR, growing 12% monthly, burn rate $80K/month, cash of $500K"
    assumptions = tally.extract_assumptions(text)
    assert assumptions["monthly_revenue"] == 50000.0
    assert assumptions["monthly_growth_rate"] == 0.12
    assert assumptions["monthly_expenses"] == 80000.0
    assert assumptions["starting_cash"] == 500000.0


def test_project_basic(tally):
    projections = tally.project(
        monthly_revenue=10000,
        monthly_expenses=8000,
        monthly_growth_rate=0.1,
        starting_cash=50000,
        months=6,
    )
    assert len(projections) == 6
    assert projections[0].revenue == 10000
    assert projections[0].net == 2000.0
    assert projections[0].cumulative == 52000.0


def test_project_growth(tally):
    projections = tally.project(10000, 8000, 0.1, 0, 3)
    # Month 2 should have higher revenue
    assert projections[1].revenue > projections[0].revenue


def test_calculate_runway_runs_out(tally):
    projections = tally.project(5000, 10000, 0, 20000, 12)
    runway = tally.calculate_runway(projections)
    assert runway == 4  # $20K starting, -$5K/mo net: month 4 goes to 0


def test_calculate_runway_profitable(tally):
    projections = tally.project(20000, 10000, 0, 50000, 12)
    runway = tally.calculate_runway(projections)
    assert runway == -1  # Never runs out


def test_calculate_break_even(tally):
    projections = tally.project(5000, 10000, 0.2, 100000, 24)
    be = tally.calculate_break_even(projections)
    assert be > 0  # Should eventually break even with 20% growth


def test_build_scenarios(tally):
    assumptions = {
        "monthly_revenue": 10000,
        "monthly_expenses": 15000,
        "monthly_growth_rate": 0.1,
        "starting_cash": 100000,
        "projection_months": 24,
    }
    scenarios = tally.build_scenarios(assumptions)
    assert len(scenarios) == 3
    assert scenarios[0].name == "Best Case"
    assert scenarios[1].name == "Base Case"
    assert scenarios[2].name == "Worst Case"


@pytest.mark.asyncio
async def test_handle_with_assumptions(tally):
    context = {"llm": None, "engram": None}
    result = await tally.handle(
        "Revenue $50K, expenses $80K/month, growing 10%, cash $200K, 24 months",
        context,
    )
    assert "[Tally]" in result
    assert "Best Case" in result
    assert "Base Case" in result


@pytest.mark.asyncio
async def test_handle_no_data(tally):
    context = {"llm": None, "engram": None}
    result = await tally.handle("tell me about money", context)
    assert "[Tally]" in result
    assert "could not" in result.lower() or "assumptions" in result.lower()

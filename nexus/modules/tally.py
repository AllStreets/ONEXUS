"""
Tally -- financial projection model builder.
Generates revenue/expense projections, runway calculations, and
scenario analysis from plain-English assumptions.

Inspired by:
  - zulip/finbot (Apache 2.0) — Python financial projection engine
  - gopalakrishnanarjun/modelmyfinance (MIT) — financial modeling package
  - 369geofreeman/Financial_Models (MIT) — quantitative finance models
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Projection:
    month: int
    revenue: float
    expenses: float
    net: float
    cumulative: float


@dataclass
class Scenario:
    name: str
    projections: list[Projection]
    runway_months: int  # -1 means infinite (profitable)
    break_even_month: int  # -1 means never


class TallyModule(NexusModule):
    name = "tally"
    description = "Financial projection builder -- generates revenue/expense models with runway and scenario analysis"
    version = "0.1.0"

    def __init__(self):
        self._scenarios: list[Scenario] = []

    @staticmethod
    def _parse_amount(text: str) -> float:
        """Parse a dollar amount from text like '$50K', '50000', '50k'."""
        text = text.strip().replace(',', '').replace('$', '')
        multiplier = 1.0
        if text.lower().endswith('k'):
            multiplier = 1000
            text = text[:-1]
        elif text.lower().endswith('m'):
            multiplier = 1_000_000
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return 0.0

    @staticmethod
    def extract_assumptions(text: str) -> dict[str, float]:
        """Extract financial assumptions from natural language."""
        assumptions: dict[str, float] = {}
        text_lower = text.lower()

        # Revenue / MRR
        rev_match = re.search(r'(?:revenue|mrr|income)\s*(?:of|is|:)?\s*\$?([\d,.]+[kKmM]?)', text)
        if rev_match:
            assumptions["monthly_revenue"] = TallyModule._parse_amount(rev_match.group(1))

        # Growth rate
        growth_match = re.search(r'(?:grow(?:ing|th)?|increase)\s*(?:at|of|by)?\s*([\d.]+)\s*%', text)
        if growth_match:
            assumptions["monthly_growth_rate"] = float(growth_match.group(1)) / 100

        # Expenses / burn rate
        exp_match = re.search(r'(?:burn|expense|cost|spending)\s*(?:rate|of|is|:)?\s*\$?([\d,.]+[kKmM]?)', text)
        if exp_match:
            assumptions["monthly_expenses"] = TallyModule._parse_amount(exp_match.group(1))

        # Cash / runway starting point
        cash_match = re.search(r'(?:cash|bank|savings|runway|capital)\s*(?:of|is|:)?\s*\$?([\d,.]+[kKmM]?)', text)
        if cash_match:
            assumptions["starting_cash"] = TallyModule._parse_amount(cash_match.group(1))

        # Projection months
        months_match = re.search(r'(\d+)\s*months?', text)
        if months_match:
            assumptions["projection_months"] = float(months_match.group(1))

        return assumptions

    def project(
        self,
        monthly_revenue: float,
        monthly_expenses: float,
        monthly_growth_rate: float = 0.0,
        starting_cash: float = 0.0,
        months: int = 24,
    ) -> list[Projection]:
        """Generate monthly projections."""
        projections: list[Projection] = []
        cumulative = starting_cash
        revenue = monthly_revenue

        for month in range(1, months + 1):
            net = revenue - monthly_expenses
            cumulative += net
            projections.append(Projection(
                month=month,
                revenue=round(revenue, 2),
                expenses=round(monthly_expenses, 2),
                net=round(net, 2),
                cumulative=round(cumulative, 2),
            ))
            revenue *= (1 + monthly_growth_rate)

        return projections

    def calculate_runway(self, projections: list[Projection]) -> int:
        """Find the month where cash runs out. -1 if never."""
        for p in projections:
            if p.cumulative <= 0:
                return p.month
        return -1

    def calculate_break_even(self, projections: list[Projection]) -> int:
        """Find the month where revenue >= expenses. -1 if never."""
        for p in projections:
            if p.net >= 0:
                return p.month
        return -1

    def build_scenarios(self, assumptions: dict[str, float]) -> list[Scenario]:
        """Generate best/base/worst case scenarios."""
        revenue = assumptions.get("monthly_revenue", 0)
        expenses = assumptions.get("monthly_expenses", 0)
        growth = assumptions.get("monthly_growth_rate", 0)
        cash = assumptions.get("starting_cash", 0)
        months = int(assumptions.get("projection_months", 24))

        scenarios: list[Scenario] = []

        configs = [
            ("Best Case", growth * 1.5, expenses * 0.85),
            ("Base Case", growth, expenses),
            ("Worst Case", growth * 0.5, expenses * 1.15),
        ]

        for name, g, e in configs:
            projections = self.project(revenue, e, g, cash, months)
            runway = self.calculate_runway(projections)
            break_even = self.calculate_break_even(projections)
            scenarios.append(Scenario(name=name, projections=projections,
                                      runway_months=runway, break_even_month=break_even))

        return scenarios

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Extract assumptions
        assumptions = self.extract_assumptions(message)

        if not assumptions.get("monthly_revenue") and not assumptions.get("monthly_expenses"):
            # Use LLM to parse complex financial descriptions
            if llm:
                prompt = (
                    "Extract financial assumptions from this text. Return ONLY these values:\n"
                    "MONTHLY_REVENUE: <number>\n"
                    "MONTHLY_EXPENSES: <number>\n"
                    "GROWTH_RATE: <percentage as decimal>\n"
                    "STARTING_CASH: <number>\n"
                    "MONTHS: <number>\n\n"
                    f"Text: {message[:2000]}"
                )
                try:
                    response = await llm.complete(prompt)
                    # Parse LLM response
                    for line in response.split('\n'):
                        if 'MONTHLY_REVENUE' in line:
                            val = re.search(r'[\d,.]+', line)
                            if val:
                                assumptions["monthly_revenue"] = float(val.group().replace(',', ''))
                        elif 'MONTHLY_EXPENSES' in line:
                            val = re.search(r'[\d,.]+', line)
                            if val:
                                assumptions["monthly_expenses"] = float(val.group().replace(',', ''))
                        elif 'GROWTH_RATE' in line:
                            val = re.search(r'[\d.]+', line)
                            if val:
                                assumptions["monthly_growth_rate"] = float(val.group())
                        elif 'STARTING_CASH' in line:
                            val = re.search(r'[\d,.]+', line)
                            if val:
                                assumptions["starting_cash"] = float(val.group().replace(',', ''))
                except Exception:
                    pass

        if not assumptions:
            return "[Tally] Could not extract financial assumptions. Provide revenue, expenses, growth rate, and cash position."

        # Set defaults
        assumptions.setdefault("monthly_revenue", 0)
        assumptions.setdefault("monthly_expenses", 0)
        assumptions.setdefault("monthly_growth_rate", 0)
        assumptions.setdefault("starting_cash", 0)
        assumptions.setdefault("projection_months", 24)

        # Build scenarios
        scenarios = self.build_scenarios(assumptions)
        self._scenarios.extend(scenarios)

        # Store in memory
        if engram:
            try:
                base = scenarios[1]  # Base case
                engram.episodic.store(
                    f"Financial projection: ${assumptions['monthly_revenue']:.0f}/mo revenue, "
                    f"${assumptions['monthly_expenses']:.0f}/mo expenses, "
                    f"runway: {base.runway_months} months",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Tally] Financial Projection"]
        lines.append(f"\n  Assumptions:")
        lines.append(f"    Revenue:     ${assumptions['monthly_revenue']:,.2f}/mo")
        lines.append(f"    Expenses:    ${assumptions['monthly_expenses']:,.2f}/mo")
        lines.append(f"    Growth:      {assumptions['monthly_growth_rate']*100:.1f}%/mo")
        lines.append(f"    Cash:        ${assumptions['starting_cash']:,.2f}")

        for scenario in scenarios:
            lines.append(f"\n  -- {scenario.name} --")
            runway_str = f"Month {scenario.runway_months}" if scenario.runway_months > 0 else "Never (profitable)"
            be_str = f"Month {scenario.break_even_month}" if scenario.break_even_month > 0 else "Never"
            lines.append(f"    Cash-zero:   {runway_str}")
            lines.append(f"    Break-even:  {be_str}")

            # Show key months
            key_months = [0, 2, 5, 11, 17, 23]
            lines.append(f"    {'Month':>8} {'Revenue':>12} {'Expenses':>12} {'Net':>12} {'Cash':>14}")
            for idx in key_months:
                if idx < len(scenario.projections):
                    p = scenario.projections[idx]
                    lines.append(
                        f"    {p.month:>8} {p.revenue:>12,.2f} {p.expenses:>12,.2f} "
                        f"{p.net:>12,.2f} {p.cumulative:>14,.2f}"
                    )

        return "\n".join(lines)

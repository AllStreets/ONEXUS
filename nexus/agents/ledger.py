"""
Ledger -- financial transaction categorizer and analyzer.
Parses bank/credit card CSV data, categorizes transactions, flags anomalies,
and generates spending summaries.

Inspired by:
  - robintw/BankClassify (MIT) — Naive Bayes bank statement classifier
  - j-convey/BankTextCategorizer (MIT) — BERT-based transaction categorization
  - HarrisonTotty/tcat (MIT) — rule-based transaction categorization library
  - eli-goodfriend/banking-class (MIT) — probabilistic transaction parser
"""
import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class Transaction:
    date: str
    description: str
    amount: float
    category: str = "Uncategorized"
    flagged: bool = False
    flag_reason: str = ""


# Keyword-based categorization rules
_CATEGORY_RULES: dict[str, list[str]] = {
    "Groceries": ["grocery", "supermarket", "whole foods", "trader joe", "kroger",
                   "safeway", "publix", "aldi", "costco", "walmart supercenter"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "mcdonald", "burger",
               "pizza", "doordash", "uber eats", "grubhub", "chipotle", "subway"],
    "Transportation": ["uber", "lyft", "gas", "fuel", "shell", "chevron", "bp",
                        "parking", "toll", "transit", "metro", "railway", "airline"],
    "Housing": ["rent", "mortgage", "hoa", "property tax", "homeowner"],
    "Utilities": ["electric", "water", "internet", "comcast", "at&t", "verizon",
                   "phone", "utility", "gas bill", "power"],
    "Healthcare": ["pharmacy", "cvs", "walgreens", "doctor", "hospital", "dental",
                    "medical", "health", "insurance premium", "copay"],
    "Entertainment": ["netflix", "spotify", "hulu", "amazon prime", "disney",
                       "movie", "theater", "concert", "gaming", "steam", "playstation"],
    "Shopping": ["amazon", "target", "best buy", "apple store", "clothing",
                  "fashion", "shoes", "nordstrom", "macys"],
    "Subscriptions": ["subscription", "monthly", "annual plan", "membership",
                       "patreon", "substack", "github"],
    "Income": ["payroll", "direct deposit", "salary", "paycheck", "dividend",
                "interest", "refund", "reimbursement"],
    "Transfers": ["transfer", "zelle", "venmo", "paypal", "wire transfer",
                   "ach", "withdrawal", "deposit"],
    "Taxes": ["irs", "tax payment", "state tax", "federal tax"],
    "Education": ["tuition", "student loan", "udemy", "coursera", "textbook",
                   "university", "college"],
    "Fitness": ["gym", "fitness", "peloton", "yoga", "crossfit"],
}


class LedgerModule(AgentModule):
    name = "ledger"
    description = "Financial transaction categorizer — parses CSV statements, categorizes spending, flags anomalies"
    version = "0.1.0"

    watch_events: list = []
    coordination_targets: list = ["tally", "mandate"]

    def __init__(self):
        self._transactions: list[Transaction] = []
        self._custom_rules: dict[str, list[str]] = {}

    def categorize(self, description: str) -> str:
        """Categorize a transaction description using keyword matching."""
        desc_lower = description.lower()

        # Check custom rules first
        for category, keywords in self._custom_rules.items():
            if any(kw in desc_lower for kw in keywords):
                return category

        # Then default rules
        for category, keywords in _CATEGORY_RULES.items():
            if any(kw in desc_lower for kw in keywords):
                return category

        return "Uncategorized"

    def add_rule(self, category: str, keywords: list[str]) -> None:
        """Add custom categorization keywords."""
        self._custom_rules.setdefault(category, []).extend(
            kw.lower() for kw in keywords
        )

    def parse_csv(self, csv_text: str) -> list[Transaction]:
        """Parse CSV bank statement into transactions."""
        transactions: list[Transaction] = []
        reader = csv.DictReader(io.StringIO(csv_text))

        if reader.fieldnames is None:
            return transactions

        # Detect column names (flexible matching)
        fields = {f.lower().strip(): f for f in reader.fieldnames}
        date_col = next((fields[k] for k in fields if "date" in k), None)
        desc_col = next(
            (fields[k] for k in fields if any(w in k for w in ("description", "memo", "narration", "payee"))),
            None,
        )
        amt_col = next((fields[k] for k in fields if "amount" in k), None)
        debit_col = next((fields[k] for k in fields if "debit" in k), None)
        credit_col = next((fields[k] for k in fields if "credit" in k), None)

        for row in reader:
            date = row.get(date_col, "") if date_col else ""
            description = row.get(desc_col, "") if desc_col else ""
            if not description:
                continue

            # Parse amount
            amount = 0.0
            if amt_col and row.get(amt_col):
                try:
                    amount = float(re.sub(r'[^\d.\-]', '', row[amt_col]))
                except ValueError:
                    pass
            elif debit_col or credit_col:
                try:
                    debit = float(re.sub(r'[^\d.\-]', '', row.get(debit_col, '0') or '0'))
                    credit = float(re.sub(r'[^\d.\-]', '', row.get(credit_col, '0') or '0'))
                    amount = credit - debit
                except ValueError:
                    pass

            category = self.categorize(description)
            transactions.append(Transaction(
                date=date.strip(),
                description=description.strip(),
                amount=amount,
                category=category,
            ))

        return transactions

    def detect_anomalies(self, transactions: list[Transaction]) -> list[Transaction]:
        """Flag duplicate charges and unusually large transactions."""
        # Calculate per-category averages
        cat_amounts: dict[str, list[float]] = defaultdict(list)
        for t in transactions:
            if t.amount < 0:  # Only expenses
                cat_amounts[t.category].append(abs(t.amount))

        cat_avg: dict[str, float] = {}
        for cat, amounts in cat_amounts.items():
            cat_avg[cat] = sum(amounts) / len(amounts) if amounts else 0

        # Find duplicates (same amount + similar description within 3 entries)
        flagged: list[Transaction] = []
        for i, t in enumerate(transactions):
            # Anomaly: >3x category average
            avg = cat_avg.get(t.category, 0)
            if avg > 0 and abs(t.amount) > avg * 3 and abs(t.amount) > 50:
                t.flagged = True
                t.flag_reason = f"Amount ${abs(t.amount):.2f} is {abs(t.amount)/avg:.1f}x the category average"
                flagged.append(t)

            # Duplicate detection
            for j in range(max(0, i - 5), i):
                other = transactions[j]
                if (abs(t.amount - other.amount) < 0.01
                        and t.amount != 0
                        and t.description[:20].lower() == other.description[:20].lower()):
                    t.flagged = True
                    t.flag_reason = f"Possible duplicate of entry on {other.date}"
                    flagged.append(t)
                    break

        return flagged

    def spending_summary(self, transactions: list[Transaction]) -> dict[str, float]:
        """Summarize spending by category."""
        summary: dict[str, float] = defaultdict(float)
        for t in transactions:
            summary[t.category] += t.amount
        return dict(sorted(summary.items(), key=lambda x: x[1]))

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Try to parse as CSV
        transactions = self.parse_csv(message)

        if not transactions:
            # If not CSV, use LLM to analyze financial text
            if llm:
                prompt = (
                    "Analyze the following financial data. Categorize transactions, "
                    "identify spending patterns, flag any anomalies or duplicate charges, "
                    "and provide a spending summary by category.\n\n"
                    f"Data:\n{message[:3000]}"
                )
                try:
                    return f"[Ledger] {await llm.complete(prompt)}"
                except Exception:
                    pass
            return "[Ledger] Could not parse transaction data. Provide CSV with date, description, and amount columns."

        self._transactions.extend(transactions)

        # Detect anomalies
        anomalies = self.detect_anomalies(transactions)

        # Generate summary
        summary = self.spending_summary(transactions)

        # Store in memory
        if engram:
            try:
                total_in = sum(t.amount for t in transactions if t.amount > 0)
                total_out = sum(t.amount for t in transactions if t.amount < 0)
                engram.episodic.store(
                    f"Financial analysis: {len(transactions)} transactions, "
                    f"income ${total_in:.2f}, expenses ${abs(total_out):.2f}, "
                    f"{len(anomalies)} anomalies",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Ledger] Analyzed {len(transactions)} transactions"]

        # Category breakdown
        lines.append("\n  Spending by Category:")
        for cat, total in summary.items():
            marker = "+" if total > 0 else "-"
            lines.append(f"    {cat:.<30} {marker}${abs(total):.2f}")

        # Totals
        total_in = sum(t.amount for t in transactions if t.amount > 0)
        total_out = sum(t.amount for t in transactions if t.amount < 0)
        lines.append(f"\n  Total Income:   +${total_in:.2f}")
        lines.append(f"  Total Expenses: -${abs(total_out):.2f}")
        lines.append(f"  Net:            {'+'if total_in + total_out >= 0 else '-'}${abs(total_in + total_out):.2f}")

        # Anomalies
        if anomalies:
            lines.append(f"\n  Flagged Anomalies ({len(anomalies)}):")
            for a in anomalies:
                lines.append(f"    ! {a.date} | {a.description[:40]} | ${abs(a.amount):.2f}")
                lines.append(f"      Reason: {a.flag_reason}")

        # Uncategorized count
        uncat = sum(1 for t in transactions if t.category == "Uncategorized")
        if uncat > 0:
            lines.append(f"\n  {uncat} transaction(s) could not be auto-categorized.")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        keywords = ("money", "spending", "transaction", "expense", "purchase", "charge", "payment")
        if any(kw in message.lower() for kw in keywords):
            return "Run ledger analysis to categorize transactions and flag anomalies."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        cortex = context.get("cortex")
        if not cortex:
            return ""
        parts: list[str] = []
        try:
            tally_result = await cortex.route("tally", analysis_result, context)
            if tally_result:
                parts.append(f"[tally] {tally_result}")
        except Exception:
            pass
        try:
            mandate_result = await cortex.route("mandate", analysis_result, context)
            if mandate_result:
                parts.append(f"[mandate] {mandate_result}")
        except Exception:
            pass
        return "\n".join(parts)

# tests/modules/test_ledger.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.ledger import LedgerModule, Transaction


@pytest.fixture
def ledger():
    return LedgerModule()


def test_ledger_attrs(ledger):
    assert ledger.name == "ledger"
    assert ledger.version == "0.1.0"
    assert ledger.description


def test_categorize_grocery(ledger):
    assert ledger.categorize("WHOLE FOODS MARKET #123") == "Groceries"


def test_categorize_dining(ledger):
    assert ledger.categorize("STARBUCKS COFFEE 456") == "Dining"


def test_categorize_unknown(ledger):
    assert ledger.categorize("XYZZY CORP PAYMENT") == "Uncategorized"


def test_custom_rules(ledger):
    ledger.add_rule("Pet Supplies", ["petco", "petsmart"])
    assert ledger.categorize("PETCO STORE #789") == "Pet Supplies"


def test_parse_csv(ledger):
    csv_data = (
        "Date,Description,Amount\n"
        "2024-01-15,WHOLE FOODS MARKET,-85.42\n"
        "2024-01-16,STARBUCKS COFFEE,-5.75\n"
        "2024-01-17,PAYROLL DIRECT DEPOSIT,3500.00\n"
    )
    transactions = ledger.parse_csv(csv_data)
    assert len(transactions) == 3
    assert transactions[0].category == "Groceries"
    assert transactions[1].category == "Dining"
    assert transactions[2].category == "Income"
    assert transactions[0].amount == -85.42


def test_parse_csv_debit_credit(ledger):
    csv_data = (
        "Date,Description,Debit,Credit\n"
        "2024-01-15,GROCERY STORE,50.00,\n"
        "2024-01-16,SALARY,,2000.00\n"
    )
    transactions = ledger.parse_csv(csv_data)
    assert len(transactions) == 2
    assert transactions[0].amount == -50.0
    assert transactions[1].amount == 2000.0


def test_detect_anomalies(ledger):
    transactions = [
        Transaction("2024-01-01", "GROCERY STORE", -30.0, "Groceries"),
        Transaction("2024-01-02", "GROCERY STORE", -25.0, "Groceries"),
        Transaction("2024-01-03", "GROCERY STORE", -28.0, "Groceries"),
        Transaction("2024-01-04", "GROCERY STORE", -900.0, "Groceries"),  # ~36x the avg of ~27
    ]
    anomalies = ledger.detect_anomalies(transactions)
    assert len(anomalies) >= 1
    assert anomalies[0].flagged


def test_detect_duplicate(ledger):
    transactions = [
        Transaction("2024-01-01", "STARBUCKS COFFEE", -5.75, "Dining"),
        Transaction("2024-01-01", "STARBUCKS COFFEE", -5.75, "Dining"),
    ]
    anomalies = ledger.detect_anomalies(transactions)
    assert len(anomalies) >= 1
    assert "duplicate" in anomalies[0].flag_reason.lower()


def test_spending_summary(ledger):
    transactions = [
        Transaction("2024-01-01", "Groceries", -100.0, "Groceries"),
        Transaction("2024-01-02", "Coffee", -5.0, "Dining"),
        Transaction("2024-01-03", "Paycheck", 3000.0, "Income"),
    ]
    summary = ledger.spending_summary(transactions)
    assert "Groceries" in summary
    assert summary["Groceries"] == -100.0
    assert summary["Income"] == 3000.0


@pytest.mark.asyncio
async def test_handle_csv_input(ledger):
    csv_data = (
        "Date,Description,Amount\n"
        "2024-01-15,WHOLE FOODS,-85.42\n"
        "2024-01-16,STARBUCKS,-5.75\n"
    )
    context = {"llm": None, "engram": None}
    result = await ledger.handle(csv_data, context)
    assert "[Ledger]" in result
    assert "2" in result  # 2 transactions


@pytest.mark.asyncio
async def test_handle_non_csv(ledger):
    llm = AsyncMock()
    llm.complete.return_value = "Spending analysis: mostly on food"
    context = {"llm": llm, "engram": None}
    result = await ledger.handle("I spent $200 on groceries last month", context)
    assert "[Ledger]" in result

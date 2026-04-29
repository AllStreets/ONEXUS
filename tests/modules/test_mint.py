# tests/modules/test_mint.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.mint import MintModule, LineItem, Invoice


@pytest.fixture
def mint():
    return MintModule()


def test_mint_attrs(mint):
    assert mint.name == "mint"
    assert mint.version == "0.1.0"


def test_parse_line_items_qty_x_desc_at_price(mint):
    text = "2x Widget @ $10.00\n3x Gadget @ $25.50"
    items = mint.parse_line_items(text)
    assert len(items) == 2
    assert items[0].description == "Widget"
    assert items[0].quantity == 2
    assert items[0].unit_price == 10.00
    assert items[0].total == 20.00


def test_parse_line_items_bullet_format(mint):
    text = "- Consulting $150\n- Design $200"
    items = mint.parse_line_items(text)
    assert len(items) == 2
    assert items[0].quantity == 1.0
    assert items[0].total == 150.0


def test_parse_line_items_empty(mint):
    assert mint.parse_line_items("no items here") == []


def test_detect_tax_region(mint):
    assert mint.detect_tax_region("UK client") == "uk"
    assert mint.detect_tax_region("Apply EU VAT") == "eu"
    assert mint.detect_tax_region("Australian GST") == "au"
    assert mint.detect_tax_region("no tax info") == "none"


def test_extract_client(mint):
    assert mint.extract_client("Client: Acme Corp") == "Acme Corp"
    assert mint.extract_client("Bill to: John Smith") == "John Smith"
    assert mint.extract_client("no client info") == ""


def test_create_invoice(mint):
    items = [
        LineItem("Widget", 2, 10.0, 20.0),
        LineItem("Gadget", 1, 30.0, 30.0),
    ]
    invoice = mint.create_invoice(items, client="Acme", tax_rate=0.10)
    assert invoice.number == "INV-1001"
    assert invoice.subtotal == 50.0
    assert invoice.tax_amount == 5.0
    assert invoice.total == 55.0


def test_create_invoice_no_tax(mint):
    items = [LineItem("Service", 1, 100.0, 100.0)]
    invoice = mint.create_invoice(items)
    assert invoice.tax_amount == 0.0
    assert invoice.total == 100.0


def test_create_invoice_increments_number(mint):
    items = [LineItem("A", 1, 10.0, 10.0)]
    inv1 = mint.create_invoice(items)
    inv2 = mint.create_invoice(items)
    assert inv1.number == "INV-1001"
    assert inv2.number == "INV-1002"


def test_format_invoice(mint):
    items = [LineItem("Widget", 2, 10.0, 20.0)]
    invoice = mint.create_invoice(items, client="Acme Corp", tax_rate=0.10)
    formatted = mint.format_invoice(invoice)
    assert "INV-1001" in formatted
    assert "Acme Corp" in formatted
    assert "Widget" in formatted
    assert "Subtotal" in formatted
    assert "TOTAL" in formatted


@pytest.mark.asyncio
async def test_handle_generates_invoice(mint):
    context = {"llm": None, "engram": None}
    result = await mint.handle("2x Widget @ $10.00\n1x Service @ $50.00", context)
    assert "[Mint]" in result
    assert "INVOICE" in result
    assert len(mint._invoices) == 1


@pytest.mark.asyncio
async def test_handle_no_items(mint):
    context = {"llm": None, "engram": None}
    result = await mint.handle("generate an invoice", context)
    assert "Provide line items" in result


@pytest.mark.asyncio
async def test_handle_with_llm_no_items(mint):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Here is your invoice breakdown..."
    context = {"llm": mock_llm, "engram": None}
    result = await mint.handle("create invoice for consulting work", context)
    assert "[Mint]" in result
    mock_llm.complete.assert_called_once()

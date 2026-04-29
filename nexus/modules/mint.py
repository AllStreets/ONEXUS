"""
Mint -- invoice and receipt generator.
Creates structured invoices from line items, calculates totals/tax,
and formats output for various business document needs.

Inspired by:
  - CiCiApp/PyInvoice (MIT) -- Python invoice/receipt generator
  - by-cx/InvoiceGenerator (MIT) -- PDF invoice generation library
  - ecmonline/invoice-generator (MIT) -- YAML-driven invoice generator
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class LineItem:
    description: str
    quantity: float
    unit_price: float
    total: float


@dataclass
class Invoice:
    number: str
    client: str
    items: list[LineItem]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    currency: str = "USD"
    notes: str = ""


# Tax rates by region (simplified)
_TAX_RATES: dict[str, float] = {
    "us": 0.0,       # varies by state
    "uk": 0.20,
    "eu": 0.21,
    "ca": 0.13,
    "au": 0.10,
    "jp": 0.10,
    "none": 0.0,
}


class MintModule(NexusModule):
    name = "mint"
    description = "Invoice generator -- creates invoices from line items with tax calculation and formatting"
    version = "0.1.0"

    def __init__(self):
        self._invoices: list[Invoice] = []
        self._next_number: int = 1001

    @staticmethod
    def parse_line_items(text: str) -> list[LineItem]:
        """Parse line items from text."""
        items: list[LineItem] = []

        # Match: "2x Widget @ $10.00" or "Widget - 2 x $10" or "Widget: $10 x 2"
        patterns = [
            r'(\d+)\s*x\s+(.+?)\s*@\s*\$?([\d,.]+)',
            r'(.+?)\s*[-:]\s*(\d+)\s*x\s*\$?([\d,.]+)',
            r'(.+?)\s*[-:]\s*\$?([\d,.]+)\s*x\s*(\d+)',
            r'[-*]\s*(.+?)\s+\$?([\d,.]+)',
        ]

        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            for i, pattern in enumerate(patterns):
                match = re.match(pattern, stripped, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if i == 0:  # qty x desc @ price
                        qty = float(groups[0])
                        desc = groups[1].strip()
                        price = float(groups[2].replace(',', ''))
                    elif i == 1:  # desc - qty x price
                        desc = groups[0].strip()
                        qty = float(groups[1])
                        price = float(groups[2].replace(',', ''))
                    elif i == 2:  # desc - price x qty
                        desc = groups[0].strip()
                        price = float(groups[1].replace(',', ''))
                        qty = float(groups[2])
                    else:  # desc price (qty=1)
                        desc = groups[0].strip()
                        price = float(groups[1].replace(',', ''))
                        qty = 1.0

                    items.append(LineItem(
                        description=desc, quantity=qty,
                        unit_price=price, total=round(qty * price, 2),
                    ))
                    break

        return items

    @staticmethod
    def detect_tax_region(text: str) -> str:
        """Detect tax region from text."""
        text_lower = text.lower()
        # Check descriptive keywords first (before short codes that may match substrings)
        if any(w in text_lower for w in ("vat", "value added")):
            return "eu"
        if any(w in text_lower for w in ("gst", "goods and services", "australia")):
            return "au"
        # Check region codes with word boundaries
        for region in ("none", "uk", "eu", "ca", "au", "jp", "us"):
            if re.search(r'\b' + region + r'\b', text_lower):
                return region
        return "none"

    @staticmethod
    def extract_client(text: str) -> str:
        """Extract client name from text."""
        patterns = [
            r'(?:client|customer|bill\s*to|invoice\s*to|for)\s*[:\-]\s*(.+)',
            r'(?:to|for)\s+([A-Z][\w\s]+(?:Inc|LLC|Corp|Ltd|Co)\.?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def create_invoice(self, items: list[LineItem], client: str = "",
                        tax_rate: float = 0.0, currency: str = "USD",
                        notes: str = "") -> Invoice:
        """Create an invoice from line items."""
        subtotal = round(sum(item.total for item in items), 2)
        tax_amount = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax_amount, 2)

        invoice = Invoice(
            number=f"INV-{self._next_number}",
            client=client, items=items,
            subtotal=subtotal, tax_rate=tax_rate,
            tax_amount=tax_amount, total=total,
            currency=currency, notes=notes,
        )
        self._invoices.append(invoice)
        self._next_number += 1
        return invoice

    @staticmethod
    def format_invoice(invoice: Invoice) -> str:
        """Format an invoice as text."""
        lines = [
            f"  INVOICE {invoice.number}",
            f"  {'=' * 50}",
        ]
        if invoice.client:
            lines.append(f"  Bill To: {invoice.client}")
        lines.append(f"  Currency: {invoice.currency}")
        lines.append(f"  {'=' * 50}")
        lines.append(f"  {'Item':<30} {'Qty':>5} {'Price':>10} {'Total':>10}")
        lines.append(f"  {'-' * 55}")

        for item in invoice.items:
            lines.append(
                f"  {item.description:<30} {item.quantity:>5.0f} "
                f"${item.unit_price:>9.2f} ${item.total:>9.2f}"
            )

        lines.append(f"  {'-' * 55}")
        lines.append(f"  {'Subtotal':<46} ${invoice.subtotal:>9.2f}")
        if invoice.tax_rate > 0:
            lines.append(
                f"  {'Tax (' + f'{invoice.tax_rate*100:.0f}%' + ')':<46} "
                f"${invoice.tax_amount:>9.2f}"
            )
        lines.append(f"  {'TOTAL':<46} ${invoice.total:>9.2f}")

        if invoice.notes:
            lines.append(f"\n  Notes: {invoice.notes}")

        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        items = self.parse_line_items(message)
        client = self.extract_client(message)
        region = self.detect_tax_region(message)
        tax_rate = _TAX_RATES.get(region, 0.0)

        if not items:
            if llm:
                prompt = (
                    "Help create an invoice from the following description:\n\n"
                    f"{message[:3000]}\n\n"
                    "Extract: line items with quantities and prices, client name, tax region."
                )
                try:
                    result = await llm.complete(prompt)
                    return f"[Mint] Invoice Assistant\n\n{result[:2000]}"
                except Exception:
                    pass
            return (
                "[Mint] Provide line items to generate an invoice.\n"
                "  Formats: '2x Widget @ $10.00' or '- Widget $10' or 'Widget: $10 x 2'"
            )

        invoice = self.create_invoice(items, client=client, tax_rate=tax_rate)
        formatted = self.format_invoice(invoice)

        if engram:
            try:
                engram.episodic.store(
                    f"Invoice {invoice.number}: {len(items)} items, "
                    f"total ${invoice.total:.2f} ({invoice.currency})",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Mint] Invoice Generated"]
        lines.append(formatted)

        return "\n".join(lines)

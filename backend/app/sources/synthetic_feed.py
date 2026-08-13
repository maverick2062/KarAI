"""Generates a plausible demo bank/UPI feed so the product can be tried
end-to-end without a real Account Aggregator connection. Deterministic given
a seed, so the same seed always reproduces the same demo dataset (useful for
tests and for a reliable product demo)."""

import random
from datetime import date
from decimal import Decimal

from app.sources.base import RawTransaction, TransactionSource

_VENDOR_TEMPLATES = [
    ("Skyline Consulting", "Professional consulting fee for {month}", (8000, 15000)),
    ("Greenview Properties", "Office rent for {month}", (25000, 45000)),
    ("BuildRight Contractors", "Payment to contractor for renovation work", (10000, 60000)),
    ("Apex Freight Brokers", "Freight commission payout", (3000, 9000)),
    ("Metro Bank FD", "Fixed deposit interest credited", (2000, 8000)),
]

_MONTH_NAMES = [
    "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "January", "February", "March",
]


class SyntheticFeedGenerator(TransactionSource):
    """Generates ~12 months of recurring payments to a handful of synthetic
    vendors, some of which are designed to cross Section 393 thresholds partway
    through the financial year — useful for demoing TDS event detection."""

    def __init__(self, seed: int = 42, financial_year_start: date | None = None):
        self._rng = random.Random(seed)
        self._fy_start = financial_year_start or date(date.today().year, 4, 1)

    def fetch(self) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []

        for vendor_name, description_template, (low, high) in _VENDOR_TEMPLATES:
            for month_offset, month_name in enumerate(_MONTH_NAMES):
                if self._rng.random() < 0.15:  # occasionally skip a month, like real payments do
                    continue
                txn_date = self._fy_start.replace(
                    month=(self._fy_start.month - 1 + month_offset) % 12 + 1,
                    year=self._fy_start.year + (self._fy_start.month - 1 + month_offset) // 12,
                    day=self._rng.randint(1, 27),
                )
                amount = Decimal(self._rng.randint(low, high))
                transactions.append(
                    RawTransaction(
                        transaction_date=txn_date,
                        amount=amount,
                        party_name=vendor_name,
                        description=description_template.format(month=month_name),
                        external_ref=f"SYN-{vendor_name[:4].upper()}-{month_offset}",
                    )
                )

        transactions.sort(key=lambda t: t.transaction_date)
        return transactions

"""Generates a synthetic Annual Information Statement (AIS) so discrepancy
detection can be demoed without real IT-portal OAuth access. Deliberately
introduces a few realistic mismatches against the user's own reported
transactions — a missing entry, an amount that doesn't quite match, and an
AIS-only entry the user never reported — so the diffing logic in
``app.ais_mock.diffing`` has something real to find.
"""

import random
from dataclasses import dataclass
from decimal import Decimal

from app.models.transaction import Transaction


@dataclass(frozen=True)
class AISRecordInput:
    reporting_entity: str
    amount: Decimal
    category: str


def generate_synthetic_ais(
    user_transactions: list[Transaction],
    seed: int = 42,
) -> list[AISRecordInput]:
    rng = random.Random(seed)
    records: list[AISRecordInput] = []

    for txn in user_transactions:
        roll = rng.random()
        vendor_name = txn.vendor.name if txn.vendor else "Unknown Payee"
        category = txn.declared_category or "unclassified"

        if roll < 0.08:
            continue  # simulates AIS not yet reflecting this transaction (reporting lag)
        elif roll < 0.16:
            # Amount mismatch — off by a small, plausible rounding/reporting difference.
            drift = Decimal(rng.randint(-500, 500))
            records.append(AISRecordInput(vendor_name, txn.amount + drift, category))
        else:
            records.append(AISRecordInput(vendor_name, txn.amount, category))

    # A couple of AIS-only entries the user never reported (e.g. bank-reported
    # interest they forgot to log) — these are exactly what the product should
    # proactively surface before CBDT's own AI-driven scrutiny does.
    if user_transactions:
        records.append(AISRecordInput("Unreported Savings Bank", Decimal(rng.randint(2000, 9000)), "interest_other_than_securities"))

    return records

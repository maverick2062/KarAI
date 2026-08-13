"""Compares AIS (mocked or uploaded) records against the user's own reported
transactions and flags discrepancies — exactly the kind of pre-scrutiny check
CBDT's own AI systems (ADVAIT, Project Insight) run, but surfaced to the
taxpayer proactively instead of as a post-filing notice.

Pure function over plain dataclasses (no ORM/DB coupling) so it's trivial to
unit test exhaustively; the router layer converts SQLAlchemy Transaction rows
into ``ReportedAmount`` before calling this.
"""

import enum
from dataclasses import dataclass
from decimal import Decimal

from app.ais_mock.synthetic_ais import AISRecordInput

AMOUNT_TOLERANCE = Decimal("100")  # rupee tolerance before flagging a mismatch


class AISDiscrepancyType(str, enum.Enum):
    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_FROM_USER_RECORDS = "missing_from_user_records"  # AIS has it, user didn't report it
    MISSING_FROM_AIS = "missing_from_ais"  # user reported it, AIS doesn't (yet) have it


@dataclass(frozen=True)
class ReportedAmount:
    vendor_name: str
    category: str
    amount: Decimal


@dataclass(frozen=True)
class AISDiscrepancy:
    discrepancy_type: AISDiscrepancyType
    reporting_entity: str
    category: str
    ais_amount: Decimal | None
    reported_amount: Decimal | None
    message: str


def _key(name: str, category: str) -> tuple[str, str]:
    return name.strip().lower(), category.strip().lower()


def find_discrepancies(
    ais_records: list[AISRecordInput],
    reported: list[ReportedAmount],
) -> list[AISDiscrepancy]:
    reported_totals: dict[tuple[str, str], Decimal] = {}
    for item in reported:
        key = _key(item.vendor_name, item.category)
        reported_totals[key] = reported_totals.get(key, Decimal("0")) + item.amount

    # AIS records must be aggregated per (vendor, category) BEFORE comparing —
    # a real AIS (and the synthetic/uploaded ones here) can contain multiple
    # line items per payee across the year, just like reported transactions
    # do. Comparing each raw AIS line against the payee's full-year reported
    # total would manufacture a false mismatch for every single line item.
    ais_totals: dict[tuple[str, str], Decimal] = {}
    ais_display_names: dict[tuple[str, str], str] = {}
    for record in ais_records:
        key = _key(record.reporting_entity, record.category)
        ais_totals[key] = ais_totals.get(key, Decimal("0")) + record.amount
        ais_display_names.setdefault(key, record.reporting_entity)

    discrepancies: list[AISDiscrepancy] = []

    for key in sorted(set(reported_totals) | set(ais_totals)):
        name, category = key
        ais_amount = ais_totals.get(key)
        reported_amount = reported_totals.get(key)
        display_name = ais_display_names.get(key, name.title())

        if ais_amount is not None and reported_amount is not None:
            if abs(ais_amount - reported_amount) > AMOUNT_TOLERANCE:
                discrepancies.append(
                    AISDiscrepancy(
                        discrepancy_type=AISDiscrepancyType.AMOUNT_MISMATCH,
                        reporting_entity=display_name,
                        category=category,
                        ais_amount=ais_amount,
                        reported_amount=reported_amount,
                        message=(
                            f"Your AIS shows ₹{ais_amount:,.2f} from {display_name}, but you "
                            f"reported ₹{reported_amount:,.2f}. Reconcile this before filing to avoid a "
                            "mismatch notice."
                        ),
                    )
                )
        elif ais_amount is not None:
            discrepancies.append(
                AISDiscrepancy(
                    discrepancy_type=AISDiscrepancyType.MISSING_FROM_USER_RECORDS,
                    reporting_entity=display_name,
                    category=category,
                    ais_amount=ais_amount,
                    reported_amount=None,
                    message=(
                        f"Your AIS shows ₹{ais_amount:,.2f} from {display_name} that you "
                        "haven't reported. Unreconciled AIS entries are a common trigger for CBDT scrutiny."
                    ),
                )
            )
        else:
            discrepancies.append(
                AISDiscrepancy(
                    discrepancy_type=AISDiscrepancyType.MISSING_FROM_AIS,
                    reporting_entity=name.title(),
                    category=category,
                    ais_amount=None,
                    reported_amount=reported_amount,
                    message=(
                        f"You reported ₹{reported_amount:,.2f} to {name.title()} that doesn't yet appear in "
                        "your AIS. This is often just a reporting lag rather than an error."
                    ),
                )
            )

    return discrepancies

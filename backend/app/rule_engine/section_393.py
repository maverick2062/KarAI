"""Section 393 TDS rule table (Income Tax Act 2025, effective 1 April 2026).

Section 393 consolidated the old Income Tax Act 1961's scattered non-salary TDS
sections (194A, 194C, 194H, 194I, 194J, 194-IA, 194S, ...) into a single table.
The thresholds and rates below mirror the commonly-published, publicly-known
values for these payment categories as carried into the consolidated table.

IMPORTANT: this table is a versioned, swappable config, not a hardcoded belief.
CBDT circulars are now legally binding under ITA 2025 and rates/thresholds are
routinely revised in the annual Finance Bill. Before this is used for any real
filing decision, the table must be reconciled against the current CBDT
notification for the applicable financial year. Every value below carries a
``source_note`` for exactly that reason, and every API response built on top
of this table must surface the disclaimer in ``RULE_TABLE_DISCLAIMER``.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


RULE_TABLE_VERSION = "ITA2025-S393-v1"

RULE_TABLE_DISCLAIMER = (
    "AI-assisted, advisory only. TDS categories, thresholds, and rates are "
    "based on publicly known Section 393 mappings and may lag official CBDT "
    "notifications. Verify with a Chartered Accountant or the CBDT circular "
    "in force before filing or relying on this for a compliance decision."
)


class PayeeScope(str, Enum):
    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"
    UNIVERSAL = "universal"


class ThresholdBasis(str, Enum):
    PER_PAYEE_PER_FY = "per_payee_per_fy"
    PER_TRANSACTION = "per_transaction"
    NONE = "none"  # TDS applies from the first rupee (typical for NR payments)


class TDSCategory(str, Enum):
    PROFESSIONAL_FEES = "professional_fees"
    RENT = "rent"
    CONTRACTOR_PAYMENTS = "contractor_payments"
    COMMISSION_BROKERAGE = "commission_brokerage"
    INTEREST_OTHER_THAN_SECURITIES = "interest_other_than_securities"
    DIVIDEND = "dividend"
    LOTTERY_WINNINGS = "lottery_winnings"
    PROPERTY_PURCHASE = "property_purchase"
    VIRTUAL_DIGITAL_ASSETS = "virtual_digital_assets"
    NON_RESIDENT_PAYMENT = "non_resident_payment"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class TDSRule:
    table_item: str
    category: TDSCategory
    description: str
    threshold_amount: Decimal
    threshold_basis: ThresholdBasis
    rate_percent: Decimal
    rate_notes: str
    payee_scope: PayeeScope
    source_note: str
    old_act_reference: str


SECTION_393_TABLE: dict[TDSCategory, TDSRule] = {
    TDSCategory.PROFESSIONAL_FEES: TDSRule(
        table_item="Section 393 — Table Item 3 (Professional/Technical Fees)",
        category=TDSCategory.PROFESSIONAL_FEES,
        description="Fees for professional or technical services paid to a resident.",
        threshold_amount=Decimal("30000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("10"),
        rate_notes="10% standard; 2% for certain technical/call-centre services — verify classification.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194J. Verify against current CBDT notification.",
        old_act_reference="194J",
    ),
    TDSCategory.RENT: TDSRule(
        table_item="Section 393 — Table Item 5 (Rent)",
        category=TDSCategory.RENT,
        description="Rent paid for land, building, furniture, plant, or machinery.",
        threshold_amount=Decimal("240000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("10"),
        rate_notes="10% for land/building/furniture; 2% for plant/machinery/equipment — verify asset type.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194I. Verify against current CBDT notification.",
        old_act_reference="194I",
    ),
    TDSCategory.CONTRACTOR_PAYMENTS: TDSRule(
        table_item="Section 393 — Table Item 2 (Contractor/Sub-Contractor Payments)",
        category=TDSCategory.CONTRACTOR_PAYMENTS,
        description="Payments to resident contractors or sub-contractors for work.",
        threshold_amount=Decimal("100000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("2"),
        rate_notes="1% for individual/HUF payees, 2% for others; single-payment threshold of 30,000 also applies — verify.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194C. Verify against current CBDT notification.",
        old_act_reference="194C",
    ),
    TDSCategory.COMMISSION_BROKERAGE: TDSRule(
        table_item="Section 393 — Table Item 6 (Commission or Brokerage)",
        category=TDSCategory.COMMISSION_BROKERAGE,
        description="Commission or brokerage paid to a resident.",
        threshold_amount=Decimal("20000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("2"),
        rate_notes="Verify current rate — has been amended in recent Finance Bills.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194H. Verify against current CBDT notification.",
        old_act_reference="194H",
    ),
    TDSCategory.INTEREST_OTHER_THAN_SECURITIES: TDSRule(
        table_item="Section 393 — Table Item 1 (Interest other than on Securities)",
        category=TDSCategory.INTEREST_OTHER_THAN_SECURITIES,
        description="Interest paid by banks/others, other than interest on securities.",
        threshold_amount=Decimal("40000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("10"),
        rate_notes="₹50,000 threshold for senior-citizen payees; ₹5,000 threshold for non-bank payers — verify payer/payee type.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194A. Verify against current CBDT notification.",
        old_act_reference="194A",
    ),
    TDSCategory.DIVIDEND: TDSRule(
        table_item="Section 393 — Table Item 4 (Dividend)",
        category=TDSCategory.DIVIDEND,
        description="Dividend paid by a domestic company to a resident shareholder.",
        threshold_amount=Decimal("10000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("10"),
        rate_notes="Verify current threshold — has been revised in recent Finance Bills.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194. Verify against current CBDT notification.",
        old_act_reference="194",
    ),
    TDSCategory.LOTTERY_WINNINGS: TDSRule(
        table_item="Section 393 — Table Item 7 (Winnings from Lottery/Game Shows)",
        category=TDSCategory.LOTTERY_WINNINGS,
        description="Winnings from lotteries, crossword puzzles, card games, game shows.",
        threshold_amount=Decimal("10000"),
        threshold_basis=ThresholdBasis.PER_TRANSACTION,
        rate_percent=Decimal("30"),
        rate_notes="Flat rate on net winnings per transaction/aggregate in FY — verify aggregation rule.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194B. Verify against current CBDT notification.",
        old_act_reference="194B",
    ),
    TDSCategory.PROPERTY_PURCHASE: TDSRule(
        table_item="Section 393 — Table Item 8 (Transfer of Immovable Property)",
        category=TDSCategory.PROPERTY_PURCHASE,
        description="Consideration paid for transfer of immovable property (other than agricultural land).",
        threshold_amount=Decimal("5000000"),
        threshold_basis=ThresholdBasis.PER_TRANSACTION,
        rate_percent=Decimal("1"),
        rate_notes="Universal — applies regardless of payee's tax status. Verify stamp-duty-value comparison rule.",
        payee_scope=PayeeScope.UNIVERSAL,
        source_note="Consolidates old Section 194-IA. Verify against current CBDT notification.",
        old_act_reference="194-IA",
    ),
    TDSCategory.VIRTUAL_DIGITAL_ASSETS: TDSRule(
        table_item="Section 393 — Table Item 9 (Virtual Digital Assets)",
        category=TDSCategory.VIRTUAL_DIGITAL_ASSETS,
        description="Consideration paid for transfer of virtual digital assets (crypto, NFTs).",
        threshold_amount=Decimal("50000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("1"),
        rate_notes="₹10,000 threshold applies for non-specified-person payers — verify payer category.",
        payee_scope=PayeeScope.UNIVERSAL,
        source_note="Consolidates old Section 194S. Verify against current CBDT notification.",
        old_act_reference="194S",
    ),
    TDSCategory.NON_RESIDENT_PAYMENT: TDSRule(
        table_item="Section 393(2) (Payments to Non-Residents)",
        category=TDSCategory.NON_RESIDENT_PAYMENT,
        description="Royalties, technical fees, interest, or other sums paid to a non-resident.",
        threshold_amount=Decimal("0"),
        threshold_basis=ThresholdBasis.NONE,
        rate_percent=Decimal("20"),
        rate_notes=(
            "TDS applies from the first rupee. Rate depends on payment type, applicable DTAA, "
            "and surcharge/cess — this default rate is a placeholder only. Non-resident "
            "scenarios are explicitly flagged for professional CA review, not auto-computed."
        ),
        payee_scope=PayeeScope.NON_RESIDENT,
        source_note="Consolidates old Section 195. DTAA lookup is out of scope for this prototype.",
        old_act_reference="195",
    ),
}


def get_rule(category: TDSCategory) -> TDSRule | None:
    """Return the TDS rule for a category, or None if it carries no TDS obligation
    under Section 393 (e.g. salary is governed separately under Section 392)."""
    return SECTION_393_TABLE.get(category)


def all_rules() -> list[TDSRule]:
    return list(SECTION_393_TABLE.values())

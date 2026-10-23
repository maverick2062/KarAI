"""Advisory Section 393 TDS rule table (Income Tax Act 2025).

Section 393 consolidated several non-salary TDS provisions from the Income-tax
Act, 1961. This prototype does not yet model all statutory payer, payee,
payment-type, and valuation distinctions.

IMPORTANT: the values below are incomplete, advisory mappings, not a verified
implementation of the current law. Do not rely on them to decide whether or
how much tax to deduct. Reconcile each rule with the applicable Act, Rules,
notifications, and taxpayer facts before using it for compliance.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


RULE_TABLE_VERSION = "ITA2025-S393-advisory-v3"

RULE_TABLE_DISCLAIMER = (
    "Advisory prototype only — this rule table is incomplete and is not a "
    "verified implementation of current tax law. It does not model all payer, "
    "payee, payment-type, or valuation conditions. Do not rely on this result "
    "to decide withholding. Verify the applicable law and facts with a "
    "Chartered Accountant before taking action."
)


class PayeeScope(str, Enum):
    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"
    UNIVERSAL = "universal"


class ThresholdBasis(str, Enum):
    PER_PAYEE_PER_FY = "per_payee_per_fy"
    PER_TRANSACTION = "per_transaction"
    NONE = "none"


class TDSDecisionStatus(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REVIEW = "needs_review"


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
    single_payment_threshold_amount: Decimal | None = None
    threshold_inclusive: bool = False


SECTION_393_TABLE: dict[TDSCategory, TDSRule] = {
    TDSCategory.PROFESSIONAL_FEES: TDSRule(
        table_item="Section 393 — Table Sl. No. 6(iii) (Professional/Technical Fees)",
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
        table_item="Section 393 — Table Sl. No. 2 (Rent)",
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
        table_item="Section 393 — Table Sl. No. 6(i) (Contractor/Sub-Contractor Payments)",
        category=TDSCategory.CONTRACTOR_PAYMENTS,
        description=(
            "Payments to resident contractors or sub-contractors for work; TDS applies "
            "if a single payment exceeds ₹30,000 or annual payments exceed ₹1,00,000."
        ),
        threshold_amount=Decimal("100000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("2"),
        rate_notes="1% for individual/HUF payees, 2% for others; verify the applicable rate.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Consolidates old Section 194C. Verify against current CBDT notification.",
        old_act_reference="194C",
        single_payment_threshold_amount=Decimal("30000"),
    ),
    TDSCategory.COMMISSION_BROKERAGE: TDSRule(
        table_item="Section 393 — Table Sl. No. 1(ii) (Commission or Brokerage)",
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
        table_item="Section 393 — Table Sl. No. 5(ii)/(iii) (Interest other than on Securities)",
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
        table_item="Section 393 — Table Sl. No. 7 (Dividend)",
        category=TDSCategory.DIVIDEND,
        description="Dividend paid by a domestic company to a resident shareholder.",
        threshold_amount=Decimal("10000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("10"),
        rate_notes=(
            "The base table has no threshold; a ₹10,000 exemption is conditional on "
            "qualifying non-cash payments to individual shareholders."
        ),
        payee_scope=PayeeScope.RESIDENT,
        source_note=(
            "Section 393(6) includes a conditional dividend exemption; payer, payee, and "
            "payment-mode facts are not modeled."
        ),
        old_act_reference="194",
    ),
    TDSCategory.LOTTERY_WINNINGS: TDSRule(
        table_item="Section 393(3) — Table Sl. No. 1 (Lottery/Game-Show Winnings)",
        category=TDSCategory.LOTTERY_WINNINGS,
        description="Winnings from lotteries, crossword puzzles, card games, and games/shows.",
        threshold_amount=Decimal("10000"),
        threshold_basis=ThresholdBasis.PER_TRANSACTION,
        rate_percent=Decimal("30"),
        rate_notes="30% withholding rate for the supported lottery/game-show category; prizes in kind and online-game winnings require separate review.",
        payee_scope=PayeeScope.RESIDENT,
        source_note="Section 393(3), Table Sl. No. 1; amount must represent taxable winnings. Online-game winnings are not included in this branch.",
        old_act_reference="194B",
    ),
    TDSCategory.PROPERTY_PURCHASE: TDSRule(
        table_item="Section 393 — Table Sl. No. 3(i) (Transfer of Immovable Property)",
        category=TDSCategory.PROPERTY_PURCHASE,
        description="Consideration paid for transfer of immovable property (other than agricultural land).",
        threshold_amount=Decimal("5000000"),
        threshold_basis=ThresholdBasis.PER_TRANSACTION,
        rate_percent=Decimal("1"),
        rate_notes="Universal — applies regardless of payee's tax status. Verify stamp-duty-value comparison rule.",
        payee_scope=PayeeScope.UNIVERSAL,
        source_note="Consolidates old Section 194-IA. Verify against current CBDT notification.",
        old_act_reference="194-IA",
        threshold_inclusive=True,
    ),
    TDSCategory.VIRTUAL_DIGITAL_ASSETS: TDSRule(
        table_item="Section 393 — Table Sl. No. 8(vi) (Virtual Digital Assets)",
        category=TDSCategory.VIRTUAL_DIGITAL_ASSETS,
        description="Consideration paid for transfer of virtual digital assets (crypto, NFTs).",
        threshold_amount=Decimal("10000"),
        threshold_basis=ThresholdBasis.PER_PAYEE_PER_FY,
        rate_percent=Decimal("1"),
        rate_notes="1%; Section 393(6) provides a ₹50,000 annual threshold only for qualifying individual/HUF payers; otherwise the threshold is ₹10,000.",
        payee_scope=PayeeScope.UNIVERSAL,
        source_note="Section 393(1), Table Sl. No. 8(vi), with the conditional threshold in Section 393(6).",
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

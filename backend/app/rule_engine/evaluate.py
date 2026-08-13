"""Pure, side-effect-free evaluation functions for the Section 393 rule engine.

These functions take a rule and amounts and return a computation result — they
never touch a database or the network. Per-vendor cumulative tracking (which
requires transaction history) lives in ``app.tds_detector.tracker``; this
module is deliberately kept pure so it stays trivial to unit test exhaustively.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.rule_engine.section_393 import (
    RULE_TABLE_VERSION,
    TDSCategory,
    TDSRule,
    ThresholdBasis,
    get_rule,
)

# Keyword hints used when a transaction doesn't carry an explicit category —
# matched case-insensitively against the transaction description/party role.
# This is a simple, auditable heuristic, not an ML classifier: every category
# assignment must be traceable to either an explicit field or one of these
# keywords, so a user can always see *why* a transaction was classified a
# certain way.
CATEGORY_KEYWORDS: dict[TDSCategory, tuple[str, ...]] = {
    TDSCategory.PROFESSIONAL_FEES: ("professional fee", "consulting", "technical service", "freelance", "retainer"),
    TDSCategory.RENT: ("rent", "lease"),
    TDSCategory.CONTRACTOR_PAYMENTS: ("contractor", "sub-contractor", "subcontractor", "construction work"),
    TDSCategory.COMMISSION_BROKERAGE: ("commission", "brokerage"),
    TDSCategory.INTEREST_OTHER_THAN_SECURITIES: ("interest",),
    TDSCategory.DIVIDEND: ("dividend",),
    TDSCategory.LOTTERY_WINNINGS: ("lottery", "game show", "winnings"),
    TDSCategory.PROPERTY_PURCHASE: ("property purchase", "immovable property", "property sale"),
    TDSCategory.VIRTUAL_DIGITAL_ASSETS: ("crypto", "virtual digital asset", "nft", "vda"),
    TDSCategory.NON_RESIDENT_PAYMENT: ("non-resident", "nri payment", "foreign remittance"),
}


def classify_category(
    description: str,
    declared_category: str | None = None,
    payee_is_non_resident: bool = False,
) -> TDSCategory:
    """Classify a transaction into a Section 393 TDS category.

    Prefers an explicit ``declared_category`` (from CSV column or manual entry)
    when it matches a known category; otherwise falls back to keyword matching
    on the free-text description. Returns UNCLASSIFIED if nothing matches.
    """
    if declared_category:
        normalized = declared_category.strip().lower().replace(" ", "_").replace("-", "_")
        for category in TDSCategory:
            if category.value == normalized:
                return category

    if payee_is_non_resident:
        return TDSCategory.NON_RESIDENT_PAYMENT

    text = (description or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category

    return TDSCategory.UNCLASSIFIED


def _round_currency(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TDSComputationResult:
    category: TDSCategory
    rule: TDSRule | None
    cumulative_before: Decimal
    cumulative_after: Decimal
    threshold_crossed_this_transaction: bool
    tds_applicable: bool
    taxable_amount: Decimal
    tds_amount: Decimal
    rule_table_version: str = RULE_TABLE_VERSION


def compute_tds(
    category: TDSCategory,
    transaction_amount: Decimal,
    cumulative_amount_before: Decimal = Decimal("0"),
) -> TDSComputationResult:
    """Compute the TDS obligation for a single transaction given the payee's
    cumulative payment total for the financial year *before* this transaction.

    Follows the standard Indian TDS convention: once cumulative payments to a
    payee cross the category's threshold within the FY, TDS is due on the
    ENTIRE cumulative amount (not just the excess) — including catch-up on
    payments already made — and every subsequent payment in that FY is taxed
    on its own amount.
    """
    rule = get_rule(category)
    cumulative_after = cumulative_amount_before + transaction_amount

    if rule is None:
        return TDSComputationResult(
            category=category,
            rule=None,
            cumulative_before=cumulative_amount_before,
            cumulative_after=cumulative_after,
            threshold_crossed_this_transaction=False,
            tds_applicable=False,
            taxable_amount=Decimal("0"),
            tds_amount=Decimal("0"),
        )

    rate = rule.rate_percent / Decimal("100")

    if rule.threshold_basis == ThresholdBasis.NONE:
        taxable_amount = transaction_amount
        tds_applicable = True
        threshold_crossed_this_transaction = True

    elif rule.threshold_basis == ThresholdBasis.PER_TRANSACTION:
        tds_applicable = transaction_amount > rule.threshold_amount
        threshold_crossed_this_transaction = tds_applicable
        taxable_amount = transaction_amount if tds_applicable else Decimal("0")

    elif rule.threshold_basis == ThresholdBasis.PER_PAYEE_PER_FY:
        was_below = cumulative_amount_before <= rule.threshold_amount
        now_above = cumulative_after > rule.threshold_amount
        threshold_crossed_this_transaction = was_below and now_above

        if threshold_crossed_this_transaction:
            # Catch-up TDS on everything paid to this payee so far this FY.
            taxable_amount = cumulative_after
            tds_applicable = True
        elif cumulative_amount_before > rule.threshold_amount:
            # Already past threshold from an earlier payment — tax just this one.
            taxable_amount = transaction_amount
            tds_applicable = True
        else:
            taxable_amount = Decimal("0")
            tds_applicable = False
    else:  # pragma: no cover - exhaustive enum guard
        raise ValueError(f"Unhandled threshold basis: {rule.threshold_basis}")

    tds_amount = _round_currency(taxable_amount * rate) if tds_applicable else Decimal("0")

    return TDSComputationResult(
        category=category,
        rule=rule,
        cumulative_before=cumulative_amount_before,
        cumulative_after=cumulative_after,
        threshold_crossed_this_transaction=threshold_crossed_this_transaction,
        tds_applicable=tds_applicable,
        taxable_amount=taxable_amount,
        tds_amount=tds_amount,
    )

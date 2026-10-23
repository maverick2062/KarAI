"""Pure, side-effect-free evaluation functions for the Section 393 rule engine.

These functions take a rule and amounts and return a computation result — they
never touch a database or the network. Per-vendor cumulative tracking (which
requires transaction history) lives in ``app.tds_detector.tracker``; this
module is deliberately kept pure so it stays trivial to unit test exhaustively.
"""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
import re

from app.rule_engine.section_393 import (
    RULE_TABLE_VERSION,
    TDSCategory,
    TDSDecisionStatus,
    TDSRule,
    ThresholdBasis,
    get_rule,
)
from app.rule_engine.context import RuleContext

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
    TDSCategory.LOTTERY_WINNINGS: (
        "lottery",
        "crossword",
        "card game",
        "game show",
        "gambling",
        "betting",
    ),
    TDSCategory.PROPERTY_PURCHASE: ("property purchase", "immovable property", "property sale"),
    TDSCategory.VIRTUAL_DIGITAL_ASSETS: ("crypto", "virtual digital asset", "nft", "vda"),
    TDSCategory.NON_RESIDENT_PAYMENT: ("non-resident", "nri payment", "foreign remittance"),
}


def _keyword_matches(text: str, keyword: str) -> bool:
    pattern = re.escape(keyword).replace(r"\ ", r"\s+")
    return re.search(r"(?<!\w)" + pattern + r"(?!\w)", text) is not None


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
    if payee_is_non_resident:
        return TDSCategory.NON_RESIDENT_PAYMENT

    if declared_category:
        normalized = declared_category.strip().lower().replace(" ", "_").replace("-", "_")
        for category in TDSCategory:
            if category.value == normalized:
                return category

    text = (description or "").lower()
    matches = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(_keyword_matches(text, keyword) for keyword in keywords)
    ]

    if len(matches) == 1:
        return matches[0]

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
    taxable_amount: Decimal | None
    tds_amount: Decimal | None
    rate_percent: Decimal | None
    decision_status: TDSDecisionStatus
    review_reason: str | None = None
    pan_not_provided: bool = False
    single_payment_threshold_triggered: bool = False
    rule_table_version: str = RULE_TABLE_VERSION


def compute_tds(
    category: TDSCategory,
    transaction_amount: Decimal,
    cumulative_amount_before: Decimal = Decimal("0"),
    pan_provided: bool | None = None,
    context: RuleContext | None = None,
) -> TDSComputationResult:
    """Compute the TDS obligation for a single transaction given the payee's
    cumulative payment total for the financial year *before* this transaction.

    Follows the standard Indian TDS convention: once cumulative payments to a
    payee cross the category's threshold within the FY, TDS is due on the
    ENTIRE cumulative amount (not just the excess) — including catch-up on
    payments already made — and every subsequent payment in that FY is taxed
    on its own amount.
    """
    if (
        not isinstance(transaction_amount, Decimal)
        or not isinstance(cumulative_amount_before, Decimal)
    ):
        raise TypeError("Transaction and cumulative amounts must be Decimal values.")
    if not transaction_amount.is_finite() or transaction_amount <= 0:
        raise ValueError("Transaction amount must be finite and greater than zero.")
    if not cumulative_amount_before.is_finite() or cumulative_amount_before < 0:
        raise ValueError("Cumulative amount must be finite and non-negative.")

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
            taxable_amount=None,
            tds_amount=None,
            rate_percent=None,
            decision_status=TDSDecisionStatus.NEEDS_REVIEW,
            review_reason="Select or confirm the TDS category before a calculation can be made.",
        )

    rule, review_reason = _resolve_rule_context(category, rule, context, transaction_amount)
    if review_reason:
        return TDSComputationResult(
            category=category,
            rule=rule,
            cumulative_before=cumulative_amount_before,
            cumulative_after=cumulative_after,
            threshold_crossed_this_transaction=False,
            tds_applicable=False,
            taxable_amount=None,
            tds_amount=None,
            rate_percent=None,
            decision_status=TDSDecisionStatus.NEEDS_REVIEW,
            review_reason=review_reason,
        )

    pan_not_provided = pan_provided is False
    rate_percent = max(rule.rate_percent, Decimal("20")) if pan_not_provided else rule.rate_percent
    rate = rate_percent / Decimal("100")
    single_payment_threshold_triggered = False

    if rule.threshold_basis == ThresholdBasis.NONE:
        taxable_amount = transaction_amount
        tds_applicable = True
        threshold_crossed_this_transaction = True

    elif rule.threshold_basis == ThresholdBasis.PER_TRANSACTION:
        transaction_amount_for_threshold = transaction_amount
        threshold_amount = transaction_amount_for_threshold
        if category == TDSCategory.PROPERTY_PURCHASE and context is not None:
            transaction_amount_for_threshold = max(
                context.property_consideration_total or transaction_amount,
                context.property_stamp_duty_value or Decimal("0"),
            )
            threshold_amount = transaction_amount_for_threshold
        tds_applicable = (
            threshold_amount >= rule.threshold_amount
            if rule.threshold_inclusive
            else threshold_amount > rule.threshold_amount
        )
        threshold_crossed_this_transaction = tds_applicable
        taxable_amount = transaction_amount_for_threshold if tds_applicable else Decimal("0")

    elif rule.threshold_basis == ThresholdBasis.PER_PAYEE_PER_FY:
        was_below = cumulative_amount_before <= rule.threshold_amount
        now_above = cumulative_after > rule.threshold_amount
        annual_threshold_crossed = was_below and now_above
        already_above_annual_threshold = cumulative_amount_before > rule.threshold_amount
        single_payment_threshold_triggered = (
            rule.single_payment_threshold_amount is not None
            and transaction_amount > rule.single_payment_threshold_amount
            and not annual_threshold_crossed
            and not already_above_annual_threshold
        )
        threshold_crossed_this_transaction = (
            annual_threshold_crossed or single_payment_threshold_triggered
        )

        if annual_threshold_crossed:
            # Catch-up TDS on everything paid to this payee so far this FY.
            taxable_amount = cumulative_after
            tds_applicable = True
        elif already_above_annual_threshold:
            # Already past threshold from an earlier payment — tax just this one.
            taxable_amount = transaction_amount
            tds_applicable = True
        elif single_payment_threshold_triggered:
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
        rate_percent=rate_percent,
        decision_status=(
            TDSDecisionStatus.APPLICABLE if tds_applicable else TDSDecisionStatus.NOT_APPLICABLE
        ),
        pan_not_provided=pan_not_provided,
        single_payment_threshold_triggered=(
            single_payment_threshold_triggered
            if rule.threshold_basis == ThresholdBasis.PER_PAYEE_PER_FY
            else False
        ),
    )


def _resolve_rule_context(
    category: TDSCategory,
    rule: TDSRule,
    context: RuleContext | None,
    transaction_amount: Decimal,
) -> tuple[TDSRule, str | None]:
    if category == TDSCategory.CONTRACTOR_PAYMENTS:
        if context is None or context.payer_is_designated_person is None:
            return rule, "Confirm whether the payer is a designated person under Section 393."
        if not context.payer_is_designated_person:
            return rule, "The non-designated-payer contractor branch is not modeled."
        if context.payee_is_individual_or_huf is None:
            return rule, "Confirm whether the contractor is an individual/HUF to determine the rate."
        return replace(rule, rate_percent=Decimal("1") if context.payee_is_individual_or_huf else Decimal("2")), None

    if category == TDSCategory.PROFESSIONAL_FEES:
        if context is None or context.payer_is_specified_person is None:
            return rule, "Confirm payer type to select the applicable Section 393 Table Sl. No. 6 branch."
        if not context.payer_is_specified_person:
            return rule, "The non-specified-payer professional/contractor branch is not modeled."
        if context.service_kind not in {"professional", "technical", "call_centre", "cinematographic_royalty"}:
            return rule, "Select the service type to determine the applicable threshold and rate."
        is_lower_rate = context.service_kind in {"technical", "call_centre", "cinematographic_royalty"}
        return replace(
            rule,
            threshold_amount=Decimal("50000"),
            rate_percent=Decimal("2") if is_lower_rate else Decimal("10"),
        ), None

    if category == TDSCategory.COMMISSION_BROKERAGE:
        if context is None or context.payer_is_specified_person is None:
            return rule, "Confirm whether the payer is a specified person under Section 393."
        if not context.payer_is_specified_person:
            return rule, "The non-specified-payer commission branch is not modeled."
        return rule, None

    if category == TDSCategory.PROPERTY_PURCHASE:
        if context is None or context.property_stamp_duty_value is None:
            return rule, "Enter the stamp-duty value; the deduction base is the higher applicable value."
        if context.property_consideration_total is None:
            return rule, "Enter the aggregate consideration for the property to evaluate the threshold."
        if context.property_payment_is_full_consideration is not True:
            return rule, "Installment treatment is not modeled; confirm this is a single full-consideration payment."
        if context.property_consideration_total != transaction_amount:
            return rule, "The transaction amount must match the full property consideration to calculate TDS."
        return rule, None

    if category == TDSCategory.DIVIDEND:
        if (
            context is None
            or context.payee_is_individual_shareholder is None
            or context.dividend_payment_is_non_cash is None
        ):
            return rule, "Confirm shareholder type and payment mode to evaluate the dividend exception."
        if context.payee_is_individual_shareholder and context.dividend_payment_is_non_cash:
            return rule, None
        return rule, "Other dividend exceptions are not modeled; verify this payment before relying on a result."

    if category == TDSCategory.RENT:
        return rule, "Monthly rent aggregation, asset-specific rates, and deduction timing are not modeled."

    if category == TDSCategory.INTEREST_OTHER_THAN_SECURITIES:
        return rule, "Interest payer/payee categories and their different thresholds are not modeled."

    if category == TDSCategory.VIRTUAL_DIGITAL_ASSETS:
        if context is None or context.vda_consideration_is_cash is not True:
            return rule, "Only cash-consideration VDA transfers are modeled; non-cash or unknown consideration needs review."
        if context is None or context.vda_payer_is_individual_or_huf is None:
            return rule, "Confirm whether the payer is an individual/HUF to determine the VDA threshold."
        threshold = Decimal("10000")
        if context.vda_payer_is_individual_or_huf:
            if (
                context.vda_payer_turnover_within_limit is None
                or context.vda_payer_has_business_income is None
            ):
                return rule, (
                    "For an individual/HUF payer, confirm preceding-year turnover eligibility "
                    "and whether the payer has business/professional income."
                )
            if (
                context.vda_payer_turnover_within_limit
                and not context.vda_payer_has_business_income
            ):
                threshold = Decimal("50000")
        return replace(rule, threshold_amount=threshold), None

    if category == TDSCategory.LOTTERY_WINNINGS:
        if context is None or context.lottery_winnings_kind is None:
            return rule, "Select a lottery/game-show winnings type to distinguish this from online-game winnings."
        if context.lottery_winnings_are_cash is not True:
            return rule, "Only cash lottery/game-show winnings are modeled; non-cash or unknown prizes need review."
        return rule, None

    if category == TDSCategory.NON_RESIDENT_PAYMENT:
        return rule, "Non-resident withholding requires payment-specific law and treaty review."

    return rule, None

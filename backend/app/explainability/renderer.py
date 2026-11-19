"""Template-based plain-language explanation generator.

Deliberately NOT a black-box ML explainer (no SHAP/LIME here): every number
in a TDS computation comes from a deterministic rule lookup, so the
"explanation" is a matter of narrating that lookup, not approximating a
model's behaviour. Rule values are advisory and context-dependent; messages
must not be treated as confirmation of a legal obligation.
"""

from decimal import Decimal

from app.rule_engine.evaluate import TDSComputationResult
from app.rule_engine.section_393 import RULE_TABLE_DISCLAIMER, TDSDecisionStatus


def _format_inr(amount: Decimal) -> str:
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        grouped = whole[-3:]
        prefix = whole[:-3]
        while prefix:
            grouped = f"{prefix[-2:]},{grouped}"
            prefix = prefix[:-2]
        whole = grouped
    sign = "-" if amount < 0 else ""
    return f"{sign}{whole}.{fraction}"


def render_explanation(result: TDSComputationResult, vendor_name: str) -> str:
    if result.decision_status == TDSDecisionStatus.NEEDS_REVIEW:
        return (
            f"No TDS amount was calculated for {vendor_name}. Manual review is required: "
            f"{result.review_reason or 'required tax facts are missing.'} "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if result.rule is None:
        return (
            "This transaction wasn't classified under any Section 393 TDS category, "
            "so no deduction is suggested. If this looks wrong, set a category explicitly. "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    rule = result.rule

    pan_warning = (
        " PAN was not furnished, so the configured higher rate has been applied."
        if result.pan_not_provided
        else ""
    )

    if (
        not result.tds_applicable
        and result.rule.threshold_basis.value == "per_transaction"
        and result.tds_amount is not None
    ):
        return (
            f"No TDS due on this ₹{_format_inr(result.cumulative_after - result.cumulative_before)} payment to "
            f"{vendor_name} under {rule.table_item} — the transaction is below the "
            f"₹{_format_inr(rule.threshold_amount)} per-transaction threshold. {RULE_TABLE_DISCLAIMER}"
        )

    if not result.tds_applicable and result.tds_amount is not None:
        remaining = rule.threshold_amount - result.cumulative_after
        return (
            f"No TDS due yet under {rule.table_item}. Your total payments to {vendor_name} "
            f"this financial year are ₹{_format_inr(result.cumulative_after)}, below the "
            f"₹{_format_inr(rule.threshold_amount)} threshold (₹{_format_inr(remaining)} remaining before TDS applies). "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if result.tds_amount is None or result.rate_percent is None or result.taxable_amount is None:
        raise ValueError("A TDS calculation is missing its amount or rate.")

    if (
        result.single_payment_threshold_triggered
        and rule.single_payment_threshold_amount is not None
    ):
        return (
            f"This ₹{_format_inr(result.cumulative_after - result.cumulative_before)} payment to "
            f"{vendor_name} exceeds the ₹{_format_inr(rule.single_payment_threshold_amount)} "
            f"single-payment threshold under {rule.table_item}. TDS of {result.rate_percent}% "
            f"(₹{_format_inr(result.tds_amount)}) applies to this payment.{pan_warning} {rule.rate_notes} "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if result.threshold_crossed_this_transaction:
        return (
            f"This payment took your total payments to {vendor_name} this financial year to "
            f"₹{_format_inr(result.cumulative_after)}, crossing the ₹{_format_inr(rule.threshold_amount)} threshold under "
            f"{rule.table_item}. TDS of {result.rate_percent}% now applies on the full "
            f"₹{_format_inr(result.taxable_amount)} paid so far this year (₹{_format_inr(result.tds_amount)}), including "
            f"catch-up on earlier payments to the same payee.{pan_warning} {rule.rate_notes} "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    return (
        f"TDS applies under {rule.table_item} because your payments to {vendor_name} already "
        f"crossed the ₹{_format_inr(rule.threshold_amount)} threshold earlier this financial year. "
        f"Deduct {result.rate_percent}% (₹{_format_inr(result.tds_amount)}) on this ₹{_format_inr(result.taxable_amount)} "
        f"payment.{pan_warning} {rule.rate_notes} {RULE_TABLE_DISCLAIMER}"
    )

"""Template-based plain-language explanation generator.

Deliberately NOT a black-box ML explainer (no SHAP/LIME here): every number
in a TDS computation comes from a deterministic rule lookup, so the
"explanation" is a matter of clearly narrating that lookup, not approximating
a model's behaviour. This is what the research materials call the XAI-for-tax
layer — "This deduction is under Section 393 (Table Sl. No. 6(iii)) at 10% because
your total payments crossed ₹30,000" rather than just a bare number.
"""

from app.rule_engine.evaluate import TDSComputationResult
from app.rule_engine.section_393 import RULE_TABLE_DISCLAIMER


def render_explanation(result: TDSComputationResult, vendor_name: str) -> str:
    if result.rule is None:
        return (
            "This transaction wasn't classified under any Section 393 TDS category, "
            "so no deduction is suggested. If this looks wrong, set a category explicitly. "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    rule = result.rule

    pan_warning = (
        " PAN was not furnished, so the 20% higher-rate rule has been applied."
        if result.pan_not_provided
        else ""
    )

    if not result.tds_applicable and result.rule.threshold_basis.value == "per_transaction":
        return (
            f"No TDS due on this ₹{result.cumulative_after - result.cumulative_before:,.2f} payment to "
            f"{vendor_name} under {rule.table_item} — the transaction is below the "
            f"₹{rule.threshold_amount:,.2f} per-transaction threshold. {RULE_TABLE_DISCLAIMER}"
        )

    if not result.tds_applicable:
        remaining = rule.threshold_amount - result.cumulative_after
        return (
            f"No TDS due yet under {rule.table_item}. Your total payments to {vendor_name} "
            f"this financial year are ₹{result.cumulative_after:,.2f}, below the "
            f"₹{rule.threshold_amount:,.2f} threshold (₹{remaining:,.2f} remaining before TDS applies). "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if (
        result.single_payment_threshold_triggered
        and rule.single_payment_threshold_amount is not None
    ):
        return (
            f"This ₹{result.cumulative_after - result.cumulative_before:,.2f} payment to "
            f"{vendor_name} exceeds the ₹{rule.single_payment_threshold_amount:,.2f} "
            f"single-payment threshold under {rule.table_item}. TDS of {result.rate_percent}% "
            f"(₹{result.tds_amount:,.2f}) applies to this payment.{pan_warning} {rule.rate_notes} "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if result.threshold_crossed_this_transaction:
        return (
            f"This payment took your total payments to {vendor_name} this financial year to "
            f"₹{result.cumulative_after:,.2f}, crossing the ₹{rule.threshold_amount:,.2f} threshold under "
            f"{rule.table_item}. TDS of {result.rate_percent}% now applies on the full "
            f"₹{result.taxable_amount:,.2f} paid so far this year (₹{result.tds_amount:,.2f}), including "
            f"catch-up on earlier payments to the same payee.{pan_warning} {rule.rate_notes} "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    return (
        f"TDS applies under {rule.table_item} because your payments to {vendor_name} already "
        f"crossed the ₹{rule.threshold_amount:,.2f} threshold earlier this financial year. "
        f"Deduct {result.rate_percent}% (₹{result.tds_amount:,.2f}) on this ₹{result.taxable_amount:,.2f} "
        f"payment.{pan_warning} {rule.rate_notes} {RULE_TABLE_DISCLAIMER}"
    )

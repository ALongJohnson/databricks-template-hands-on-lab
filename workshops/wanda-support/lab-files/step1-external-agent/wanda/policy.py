"""Wanderbricks refund policy (fictional), as the support team applies it today."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

# The lab's sample data ends in July 2025, so the agent treats 1 July 2025 as "today".
TODAY = date(2025, 7, 1)

POLICY_TEXT = """Wanderbricks cancellation and refund policy:
- Cancelled 14 or more days before check-in: full refund.
- Cancelled 7 to 13 days before check-in: 50% refund.
- Cancelled less than 7 days before check-in: no refund.
- Only bookings with a completed payment can be refunded.
- Refunds are paid to the original payment method."""


def refund_quote(total_paid: Decimal, check_in: date, today: date = TODAY) -> dict:
    days = (check_in - today).days
    if days >= 14:
        share, rule = Decimal("1.0"), "full refund (14 or more days before check-in)"
    elif days >= 7:
        share, rule = Decimal("0.5"), "50% refund (7 to 13 days before check-in)"
    else:
        share, rule = Decimal("0"), "no refund (less than 7 days before check-in)"
    amount = (total_paid * share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"days_before_check_in": days, "rule": rule, "refund_amount": str(amount)}

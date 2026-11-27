"""Wanda's one write action. It pauses for a human to approve before it runs."""

from agents import function_tool


@function_tool(needs_approval=True)
def issue_refund(booking_id: int, amount: float, reason: str) -> str:
    """Issue a refund to the guest's original payment method. Only call after quote_refund, for the quoted amount."""
    # In production this calls your payments API. The approval gate and the trace are the governance.
    return f"Refund of {amount:.2f} issued for booking {booking_id} ({reason})."

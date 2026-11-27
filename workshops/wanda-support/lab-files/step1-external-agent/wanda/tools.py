"""Tools for the external agent. They read a CSV snapshot that the data team exported by hand.

Nobody governs this copy: there is no access control, no lineage back to the source tables,
and no audit trail of who read which guest's data.
"""
import csv
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from agents import function_tool

from wanda.policy import POLICY_TEXT, refund_quote

DATA = Path(__file__).resolve().parent.parent / "data"
REFUNDS = Path(__file__).resolve().parent.parent / "refunds.csv"


def _rows(name: str) -> list[dict]:
    with open(DATA / f"{name}.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def _booking(booking_id: int) -> dict | None:
    for row in _rows("bookings"):
        if int(row["booking_id"]) == booking_id:
            return row
    return None


def _paid(booking_id: int) -> Decimal:
    return sum(
        (Decimal(p["amount"]) for p in _rows("payments")
         if int(p["booking_id"]) == booking_id and p["status"] == "completed"),
        Decimal("0"),
    )


@function_tool
def get_booking(booking_id: int) -> str:
    """Look up one booking: dates, status, guest, property and payments."""
    b = _booking(booking_id)
    if b is None:
        return json.dumps({"error": f"Booking {booking_id} not found"})
    prop = next((p for p in _rows("properties") if p["property_id"] == b["property_id"]), {})
    guest = next((g for g in _rows("guests") if g["user_id"] == b["user_id"]), {})
    pays = [p for p in _rows("payments") if int(p["booking_id"]) == booking_id]
    return json.dumps({**b, "property": prop.get("title"), "guest": guest.get("name"),
                       "guest_country": guest.get("country"), "payments": pays})


@function_tool
def list_guest_bookings(user_id: int) -> str:
    """List a guest's upcoming bookings."""
    rows = [b for b in _rows("bookings") if int(b["user_id"]) == user_id]
    return json.dumps(rows)


@function_tool
def quote_refund(booking_id: int) -> str:
    """Work out how much a guest gets back if they cancel a booking today, under the refund policy."""
    b = _booking(booking_id)
    if b is None:
        return json.dumps({"error": f"Booking {booking_id} not found"})
    paid = _paid(booking_id)
    if paid == 0:
        return json.dumps({"booking_id": booking_id, "refund_amount": "0.00",
                           "rule": "no completed payment, nothing to refund"})
    quote = refund_quote(paid, date.fromisoformat(b["check_in"]))
    return json.dumps({"booking_id": booking_id, "total_paid": str(paid), **quote})


@function_tool
def get_refund_policy() -> str:
    """Return the refund policy text."""
    return POLICY_TEXT


@function_tool
def issue_refund(booking_id: int, amount: float, reason: str) -> str:
    """Issue a refund to the guest's original payment method. Only call after quote_refund."""
    new = not REFUNDS.exists()
    with open(REFUNDS, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["booking_id", "amount", "reason", "issued_at"])
        w.writerow([booking_id, f"{amount:.2f}", reason, datetime.now(timezone.utc).isoformat()])
    return json.dumps({"status": "refund issued", "booking_id": booking_id, "amount": f"{amount:.2f}"})


ALL_TOOLS = [get_booking, list_guest_bookings, quote_refund, get_refund_policy, issue_refund]

"""Deterministic expense-policy checks. Every claim is checked here; the AI
reviewer (agents/policy_agent.py) is an optional second opinion."""
import sqlite3
from datetime import date


def category_policy(conn: sqlite3.Connection, code: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM expense_categories WHERE code = ?", (code,)).fetchone()


def month_spend(conn: sqlite3.Connection, employee_id: int, code: str, month: str,
                exclude_claim_id: int | None = None) -> float:
    """Total of this employee's non-rejected claims in a category for a month (YYYY-MM)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM claims WHERE employee_id = ? AND category_code = ? "
        "AND substr(expense_date, 1, 7) = ? AND status != 'rejected' AND id != COALESCE(?, -1)",
        (employee_id, code, month, exclude_claim_id),
    ).fetchone()
    return float(row[0])


def check_claim(conn: sqlite3.Connection, *, employee_id: int, category_code: str, expense_date: date,
                amount: float, merchant: str, has_receipt: bool, attendees: str | None,
                claim_id: int | None = None) -> list[str]:
    """Returns human-readable policy flags. An empty list means the claim is within policy."""
    policy = category_policy(conn, category_code)
    if policy is None:
        return [f"Unknown expense category '{category_code}'."]

    flags: list[str] = []
    name = policy["name"]

    if amount > policy["limit_per_claim"]:
        flags.append(f"Over the per-claim limit for {name} (${policy['limit_per_claim']:.2f}).")

    if policy["monthly_limit"] is not None:
        month = expense_date.isoformat()[:7]
        total = month_spend(conn, employee_id, category_code, month, claim_id) + amount
        if total > policy["monthly_limit"]:
            flags.append(f"Monthly {name} spend would be ${total:.2f}, over the ${policy['monthly_limit']:.2f} limit.")

    if amount > policy["receipt_required_over"] and not has_receipt:
        flags.append(f"Receipt required for {name} over ${policy['receipt_required_over']:.2f}.")

    if policy["requires_attendees"] and not (attendees or "").strip():
        flags.append(f"{name} must list the attendees.")

    if expense_date > date.today():
        flags.append("Expense date is in the future.")
    elif (date.today() - expense_date).days > 90:
        flags.append("Expense is older than 90 days.")

    duplicate = conn.execute(
        "SELECT id FROM claims WHERE employee_id = ? AND expense_date = ? AND amount = ? "
        "AND lower(merchant) = lower(?) AND status != 'rejected' AND id != COALESCE(?, -1)",
        (employee_id, expense_date.isoformat(), amount, merchant, claim_id),
    ).fetchone()
    if duplicate:
        flags.append(f"Possible duplicate of claim #{duplicate['id']}.")

    return flags

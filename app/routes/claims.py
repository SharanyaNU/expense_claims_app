"""Claims: create, list, submit, manager decision, AI review.

Who is calling comes from the X-Employee-Id header. That is a demo stand-in
for real sign-in, which is not built yet (see README roadmap).
"""
import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException

from app import policy
from app.agents import policy_agent
from app.db import get_conn, utcnow
from app.models import Claim, ClaimCreate, Decision

router = APIRouter(prefix="/api", tags=["claims"])

_CLAIM_SELECT = (
    "SELECT c.*, e.full_name AS employee_name, e.manager_id, k.name AS category_name "
    "FROM claims c JOIN employees e ON e.id = c.employee_id "
    "JOIN expense_categories k ON k.code = c.category_code"
)


def current_employee(x_employee_id: int = Header(...), conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM employees WHERE id = ?", (x_employee_id,)).fetchone()
    if row is None:
        raise HTTPException(401, "Unknown employee")
    return row


def _to_claim(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["has_receipt"] = bool(data["has_receipt"])
    data["policy_flags"] = json.loads(data["policy_flags"] or "[]")
    data["ai_review"] = json.loads(data["ai_review"]) if data["ai_review"] else None
    return data


def _load_claim(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row:
    row = conn.execute(f"{_CLAIM_SELECT} WHERE c.id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Claim not found")
    return row


def _can_view(me: sqlite3.Row, claim: sqlite3.Row) -> bool:
    return me["id"] in (claim["employee_id"], claim["manager_id"]) or me["role"] == "finance"


@router.post("/claims", response_model=Claim, status_code=201)
def create_claim(body: ClaimCreate, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    if policy.category_policy(conn, body.category_code) is None:
        raise HTTPException(422, f"Unknown expense category '{body.category_code}'")
    flags = policy.check_claim(
        conn, employee_id=me["id"], category_code=body.category_code, expense_date=body.expense_date,
        amount=body.amount, merchant=body.merchant, has_receipt=body.has_receipt, attendees=body.attendees,
    )
    cur = conn.execute(
        "INSERT INTO claims (employee_id, category_code, expense_date, amount, merchant, description, attendees, "
        "has_receipt, policy_flags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (me["id"], body.category_code, body.expense_date.isoformat(), round(body.amount, 2), body.merchant.strip(),
         body.description.strip(), body.attendees, int(body.has_receipt), json.dumps(flags), utcnow()),
    )
    conn.commit()
    return _to_claim(_load_claim(conn, cur.lastrowid))


@router.get("/claims", response_model=list[Claim])
def my_claims(status: str | None = None, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    sql, args = f"{_CLAIM_SELECT} WHERE c.employee_id = ?", [me["id"]]
    if status:
        sql += " AND c.status = ?"
        args.append(status)
    rows = conn.execute(sql + " ORDER BY c.expense_date DESC, c.id DESC", args).fetchall()
    return [_to_claim(r) for r in rows]


@router.get("/claims/{claim_id}", response_model=Claim)
def get_claim(claim_id: int, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    claim = _load_claim(conn, claim_id)
    if not _can_view(me, claim):
        raise HTTPException(403, "Not allowed to view this claim")
    return _to_claim(claim)


@router.post("/claims/{claim_id}/submit", response_model=Claim)
def submit_claim(claim_id: int, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    claim = _load_claim(conn, claim_id)
    if claim["employee_id"] != me["id"]:
        raise HTTPException(403, "Only the claimant can submit a claim")
    if claim["status"] != "draft":
        raise HTTPException(409, f"Claim is already {claim['status']}")
    if claim["manager_id"] is None:
        raise HTTPException(409, "You have no manager to approve this claim")
    if date.fromisoformat(claim["expense_date"]) > date.today():
        raise HTTPException(422, "Expense date is in the future")

    # Re-check at submission: other claims may have changed the monthly totals.
    flags = policy.check_claim(
        conn, employee_id=me["id"], category_code=claim["category_code"],
        expense_date=date.fromisoformat(claim["expense_date"]), amount=claim["amount"], merchant=claim["merchant"],
        has_receipt=bool(claim["has_receipt"]), attendees=claim["attendees"], claim_id=claim_id,
    )
    conn.execute("UPDATE claims SET status = 'submitted', submitted_at = ?, policy_flags = ? WHERE id = ?",
                 (utcnow(), json.dumps(flags), claim_id))
    conn.commit()
    return _to_claim(_load_claim(conn, claim_id))


@router.get("/approvals/inbox", response_model=list[Claim])
def approval_inbox(me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    if me["role"] != "manager":
        raise HTTPException(403, "Only managers have an approval inbox")
    rows = conn.execute(
        f"{_CLAIM_SELECT} WHERE e.manager_id = ? AND c.status = 'submitted' ORDER BY c.submitted_at",
        (me["id"],),
    ).fetchall()
    return [_to_claim(r) for r in rows]


@router.post("/claims/{claim_id}/decision", response_model=Claim)
def decide(claim_id: int, body: Decision, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    claim = _load_claim(conn, claim_id)
    if claim["employee_id"] == me["id"]:
        raise HTTPException(403, "You cannot approve your own claim")
    if claim["manager_id"] != me["id"]:
        raise HTTPException(403, "Only the claimant's manager can decide this claim")
    if claim["status"] != "submitted":
        raise HTTPException(409, f"Claim is {claim['status']}, not submitted")
    if body.decision == "rejected" and not (body.comment or "").strip():
        raise HTTPException(422, "A comment is required when rejecting")

    conn.execute("INSERT INTO approvals (claim_id, approver_id, decision, comment, decided_at) VALUES (?, ?, ?, ?, ?)",
                 (claim_id, me["id"], body.decision, body.comment, utcnow()))
    conn.execute("UPDATE claims SET status = ? WHERE id = ?", (body.decision, claim_id))
    conn.commit()
    return _to_claim(_load_claim(conn, claim_id))


@router.post("/claims/{claim_id}/ai-review")
async def ai_review(claim_id: int, me=Depends(current_employee), conn: sqlite3.Connection = Depends(get_conn)):
    claim = _load_claim(conn, claim_id)
    if claim["manager_id"] != me["id"]:
        raise HTTPException(403, "Only the claimant's manager can request an AI review")
    result = await policy_agent.review_claim(conn, claim)
    if result.get("available") and "error" not in result:
        conn.execute("UPDATE claims SET ai_review = ? WHERE id = ?", (json.dumps(result), claim_id))
        conn.commit()
    return result


@router.get("/finance/payout-queue")
def payout_queue():
    raise HTTPException(501, "Finance payouts are not built yet")

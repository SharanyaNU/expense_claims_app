"""Read-only reference data: employees and expense categories."""
import sqlite3

from fastapi import APIRouter, Depends

from app.db import get_conn
from app.models import Category, Employee

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/employees", response_model=list[Employee])
def list_employees(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT e.id, e.full_name, e.email, e.role, d.name AS department, e.manager_id "
        "FROM employees e JOIN departments d ON d.id = e.department_id ORDER BY e.full_name"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/categories", response_model=list[Category])
def list_categories(conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()
    return [{**dict(r), "requires_attendees": bool(r["requires_attendees"])} for r in rows]

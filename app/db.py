"""SQLite connection, schema creation and demo seed data."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "expenses.sqlite3"


def db_path() -> Path:
    return Path(os.getenv("EXPENSES_DB_PATH", DEFAULT_DB_PATH))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # One connection per request, used sequentially; async endpoints may run on a
    # different thread from the one that opened it.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO departments (id, name, cost_center) VALUES (?, ?, ?)",
        [(1, "Engineering", "CC-100"), (2, "Sales", "CC-200"), (3, "Finance", "CC-300")],
    )
    conn.executemany(
        "INSERT INTO employees (id, full_name, email, role, department_id, manager_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Priya Nair", "priya.nair@example.com", "manager", 1, None),
            (2, "Arjun Mehta", "arjun.mehta@example.com", "employee", 1, 1),
            (3, "Lena Fischer", "lena.fischer@example.com", "employee", 1, 1),
            (4, "Daniel Okafor", "daniel.okafor@example.com", "manager", 2, None),
            (5, "Sofia Rossi", "sofia.rossi@example.com", "employee", 2, 4),
            (6, "Meera Iyer", "meera.iyer@example.com", "finance", 3, None),
        ],
    )
    conn.executemany(
        "INSERT INTO expense_categories (code, name, limit_per_claim, monthly_limit, receipt_required_over, "
        "requires_attendees) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("AIRFARE", "Airfare", 600, None, 0, 0),
            ("HOTEL", "Hotel", 200, 1200, 0, 0),
            ("MEALS", "Meals", 75, 400, 25, 0),
            ("GROUND", "Taxi and ground transport", 100, 300, 25, 0),
            ("SUPPLIES", "Office supplies", 150, 150, 25, 0),
            ("CLIENT_ENT", "Client entertainment", 250, 500, 0, 1),
        ],
    )
    now = utcnow()
    conn.executemany(
        "INSERT INTO claims (employee_id, category_code, expense_date, amount, merchant, description, attendees, "
        "has_receipt, status, policy_flags, created_at, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (2, "HOTEL", "2026-10-14", 185.0, "Marriott Pune", "Client workshop, 1 night", None, 1, "submitted", "[]",
             now, now),
            (2, "MEALS", "2026-10-14", 92.5, "Barbeque Nation", "Team dinner during workshop", None, 1, "submitted",
             '["Over the per-claim limit for Meals ($75.00)."]', now, now),
            (3, "GROUND", "2026-10-20", 38.0, "Uber", "Airport to office", None, 0, "draft",
             '["Receipt required for Taxi and ground transport over $25.00."]', now, None),
            (5, "CLIENT_ENT", "2026-10-22", 210.0, "The Table", "Dinner with Acme Corp", "J. Smith (Acme), S. Rossi",
             1, "approved", "[]", now, now),
        ],
    )

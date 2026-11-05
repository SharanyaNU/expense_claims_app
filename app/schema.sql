-- Expense claims portal schema (SQLite).

CREATE TABLE IF NOT EXISTS departments (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    cost_center   TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    role          TEXT NOT NULL CHECK (role IN ('employee', 'manager', 'finance')),
    department_id INTEGER NOT NULL REFERENCES departments(id),
    manager_id    INTEGER REFERENCES employees(id)
);

-- Company expense policy, one row per category.
CREATE TABLE IF NOT EXISTS expense_categories (
    code                   TEXT PRIMARY KEY,
    name                   TEXT NOT NULL,
    limit_per_claim        REAL NOT NULL,         -- hard cap for one claim, in USD
    monthly_limit          REAL,                  -- per employee per calendar month; NULL = none
    receipt_required_over  REAL NOT NULL DEFAULT 25,
    requires_attendees     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS claims (
    id              INTEGER PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    category_code   TEXT NOT NULL REFERENCES expense_categories(code),
    expense_date    TEXT NOT NULL,                 -- ISO date
    amount          REAL NOT NULL CHECK (amount > 0),
    currency        TEXT NOT NULL DEFAULT 'USD',
    merchant        TEXT NOT NULL,
    description     TEXT NOT NULL,
    attendees       TEXT,                          -- required for client entertainment
    has_receipt     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'paid')),
    policy_flags    TEXT,                          -- JSON list written by the policy check
    ai_review       TEXT,                          -- JSON written by the AI reviewer
    created_at      TEXT NOT NULL,
    submitted_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_claims_employee ON claims(employee_id, status);

CREATE TABLE IF NOT EXISTS approvals (
    id           INTEGER PRIMARY KEY,
    claim_id     INTEGER NOT NULL REFERENCES claims(id),
    approver_id  INTEGER NOT NULL REFERENCES employees(id),
    decision     TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comment      TEXT,
    decided_at   TEXT NOT NULL
);

-- Finance payout batches. Not used yet (see README roadmap).
CREATE TABLE IF NOT EXISTS reimbursements (
    id            INTEGER PRIMARY KEY,
    claim_id      INTEGER NOT NULL UNIQUE REFERENCES claims(id),
    paid_by       INTEGER NOT NULL REFERENCES employees(id),
    payment_ref   TEXT NOT NULL,
    paid_at       TEXT NOT NULL
);

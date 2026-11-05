# Expense Claims Portal

Employees submit business expenses, the portal checks them against company policy, their manager approves or rejects
them, and finance reimburses them. An optional AI reviewer (Microsoft Agent Framework) gives managers a second opinion.

This is a deliberately unfinished (about 30%) application, used as a realistic codebase for end-to-end testing.

## Status: about 30% complete

| Area | State |
|---|---|
| Expense policy per category (per-claim limit, monthly limit, receipt threshold, attendees) | Done |
| Create a claim as a draft, with policy flags | Done |
| Submit a draft for approval (policy re-checked) | Done |
| Manager approval inbox, approve / reject (comment required to reject) | Done |
| AI policy reviewer for managers (Agent Framework, 2 tools) | Done (needs Azure OpenAI) |
| Web UI: My claims, Approvals | Done |
| Edit or delete a draft | Not started |
| Receipt upload and storage | Not started (only a "has receipt" checkbox) |
| Sign-in and roles | Not started (the caller is chosen with "Acting as" / `X-Employee-Id`) |
| Finance payout batches (`reimbursements` table) | Not started (`/api/finance/payout-queue` returns 501) |
| Reports: spend by department, category, month | Not started |
| Email notifications | Not started |
| Multi-currency | Not started (USD only) |
| Approval delegation when a manager is away | Not started |

## How it works

```
Employee                         Manager                          Finance (not built)
  create draft ──► policy check     │                                │
  submit ───────► policy re-check ──► inbox ──► AI review (optional)  │
                                    approve / reject ───────────────► payout batch ──► paid
```

Claim statuses: `draft` → `submitted` → `approved` or `rejected` → `paid` (not reachable yet).

### Policy rules (`app/policy.py`)

| Rule | Example |
|---|---|
| Per-claim limit | Meals: $75 |
| Monthly limit per employee and category | Meals: $400 a month |
| Receipt required above a threshold | Meals over $25; hotels and airfare always |
| Attendees required | Client entertainment |
| Date | not in the future; not older than 90 days |
| Duplicates | same employee, date, amount and merchant |

Flags are warnings shown to the manager. A future date and an unknown category block the claim.

### Business rules on decisions

- Only the claimant can submit their claim; only drafts can be submitted.
- Only the claimant's manager can approve or reject it, and nobody can decide their own claim.
- Rejecting requires a comment.
- An employee without a manager cannot submit.

### AI reviewer (`app/agents/policy_agent.py`)

An Agent Framework `Agent` with two tools, `get_category_policy` and `get_month_spend`, both bound to the claimant so
the model cannot look up other employees. It returns a recommendation (`approve`, `reject`, `needs_info`), a risk level
and reasons. It never changes a claim's status. Without the `AZURE_OPENAI_*` settings the endpoint reports that it is
not configured, and everything else keeps working.

## API

Interactive docs at `/docs`; the OpenAPI spec at `/openapi.json`. Calls under `/api/claims` and `/api/approvals` need
an `X-Employee-Id` header.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/employees` | Employees (for "Acting as") |
| GET | `/api/categories` | Expense policy |
| POST | `/api/claims` | Create a draft claim |
| GET | `/api/claims?status=` | Caller's claims |
| GET | `/api/claims/{id}` | One claim (claimant, their manager, or finance) |
| POST | `/api/claims/{id}/submit` | Submit a draft |
| GET | `/api/approvals/inbox` | Manager's submitted claims |
| POST | `/api/claims/{id}/decision` | `{"decision": "approved" \| "rejected", "comment": "..."}` |
| POST | `/api/claims/{id}/ai-review` | AI recommendation for the manager |
| GET | `/api/finance/payout-queue` | 501 Not implemented |

## Demo data

| Id | Name | Role | Manager |
|---|---|---|---|
| 1 | Priya Nair | manager (Engineering) | |
| 2 | Arjun Mehta | employee | Priya |
| 3 | Lena Fischer | employee | Priya |
| 4 | Daniel Okafor | manager (Sales) | |
| 5 | Sofia Rossi | employee | Daniel |
| 6 | Meera Iyer | finance | |

Four sample claims are seeded, including one over the meals limit and one draft missing a receipt. Delete
`data/expenses.sqlite3` to reset.

## Run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # optional: Azure OpenAI for the AI reviewer
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000.

## Project layout

```
app/
  main.py              FastAPI app, static UI, startup
  db.py                SQLite connection, schema, seed data
  schema.sql           tables: departments, employees, expense_categories, claims, approvals, reimbursements
  models.py            request/response models
  policy.py            policy rules
  routes/reference.py  health, employees, categories
  routes/claims.py     claims, submission, approvals, AI review
  agents/policy_agent.py  AI reviewer
  static/              index.html, app.js, style.css
```

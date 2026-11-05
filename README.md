# Expense Claims Portal

Employees submit business expenses, the portal checks them against company policy, their manager approves or rejects
them, and finance reimburses them. An optional AI reviewer (Microsoft Agent Framework) gives managers a second opinion.

## Status

Project skeleton only: a FastAPI app with a health check. Claims, policy rules, approvals, the AI reviewer and the web UI
are in progress.

## Run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # optional: Azure OpenAI for the AI reviewer
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/api/health or http://localhost:8000/docs.

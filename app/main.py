"""FastAPI entry point for the Expense Claims Portal."""
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Only this app's own .env, never one found further up the directory tree.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Expense Claims Portal", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

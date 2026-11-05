"""FastAPI entry point: JSON API under /api and the web UI at /."""
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Only this app's own .env, never one found further up the directory tree.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.db import init_db  # noqa: E402
from app.routes import claims, reference  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Expense Claims Portal", version="0.3.0", lifespan=lifespan)
app.include_router(reference.router)
app.include_router(claims.router)
app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="static")

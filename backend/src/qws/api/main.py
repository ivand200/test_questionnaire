import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from qws.adapters.store import Store
from qws.core.models import LoadIssue
from qws.services import seed_loader

REPO_DIR = Path(__file__).resolve().parents[4]
DIST_DIR = REPO_DIR / "frontend" / "dist"
SEED_PATH = REPO_DIR / "data" / "seed.json"
DEFAULT_DB_PATH = "qws.db"


class QuestionSummary(BaseModel):
    id: str
    topic: str
    text: str
    status: Literal["new", "draft", "unresolved", "error"]


class LazyStaticFiles(StaticFiles):
    """StaticFiles that tolerates a missing directory: requests 404 until it exists."""

    async def check_config(self) -> None:
        pass


def create_app(
    dist_dir: Path = DIST_DIR,
    db_path: Path | str | None = None,
    seed_path: Path = SEED_PATH,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = Store(db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH)
        store.init_schema()
        app.state.store = store
        app.state.load_issues = seed_loader.load(json.loads(seed_path.read_text()), store)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/load-issues")
    def load_issues(request: Request) -> list[LoadIssue]:
        return request.app.state.load_issues

    @app.get("/api/questions")
    def questions(request: Request) -> list[QuestionSummary]:
        return [QuestionSummary(**q) for q in request.app.state.store.list_questions()]

    # Mounted last so every /api/* route above wins over the static files.
    # dist may not exist yet; files are looked up per request, so a build made
    # after startup is served without a restart.
    app.mount("/", LazyStaticFiles(directory=dist_dir, html=True, check_dir=False))

    return app


app = create_app()

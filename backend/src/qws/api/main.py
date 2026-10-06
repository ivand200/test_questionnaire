import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.replay_drafter import ReplayDrafter
from qws.adapters.store import Store
from qws.config import (
    DEFAULT_DB_PATH,
    REPLAY_PATH,
    REPO_DIR,
    SEED_PATH,
    drafter_config,
)
from qws.core import rules
from qws.core.models import LoadIssue, QuestionView
from qws.services import seed_loader
from qws.services.draft_service import (
    Conflict,
    DraftService,
    Drafter,
    DrafterConfig,
    UnknownQuestion,
)

DIST_DIR = REPO_DIR / "frontend" / "dist"


class QuestionSummary(BaseModel):
    id: str
    topic: str
    text: str
    status: Literal["new", "draft", "unresolved", "error"]


class LazyStaticFiles(StaticFiles):
    """StaticFiles that tolerates a missing directory: requests 404 until it exists."""

    async def check_config(self) -> None:
        pass


def drafter_from_env(config: DrafterConfig, replay_path: Path = REPLAY_PATH) -> Drafter:
    """`MODEL_MODE=real` asks the model; anything else (empty too) is replay."""
    if os.environ.get("MODEL_MODE") == "real":
        return RealDrafter(config.model, os.environ.get("OPENAI_API_KEY", ""), config.settings)
    return ReplayDrafter(config.model, config.settings, replay_path)


def create_app(
    dist_dir: Path = DIST_DIR,
    db_path: Path | str | None = None,
    seed_path: Path = SEED_PATH,
    drafter: Drafter | None = None,
    replay_path: Path = REPLAY_PATH,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = Store(db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH)
        store.init_schema()
        app.state.store = store
        app.state.load_issues = seed_loader.load(json.loads(seed_path.read_text()), store)
        config = drafter_config()
        app.state.service = DraftService(
            store, drafter or drafter_from_env(config, replay_path), config
        )
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

    @app.get("/api/questions/{question_id}")
    def question(question_id: str, request: Request) -> QuestionView:
        store: Store = request.app.state.store
        found = store.get_question(question_id)
        if found is None:
            raise HTTPException(404, f"Unknown question {question_id}.")
        return rules.question_view(found, store.get_draft(question_id))

    @app.post("/api/questions/{question_id}/draft")
    def draft(question_id: str, request: Request) -> QuestionView:
        result = request.app.state.service.ask(question_id)
        if isinstance(result, UnknownQuestion):
            raise HTTPException(404, f"Unknown question {question_id}.")
        if isinstance(result, Conflict):
            raise HTTPException(409, f"Question {question_id} already has a draft.")
        return result

    # Mounted last so every /api/* route above wins over the static files.
    # dist may not exist yet; files are looked up per request, so a build made
    # after startup is served without a restart.
    app.mount("/", LazyStaticFiles(directory=dist_dir, html=True, check_dir=False))

    return app


app = create_app()

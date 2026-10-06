import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.replay_drafter import ReplayDrafter
from qws.config import (
    DEMO_PATH,
    REPLAY_PATH,
    REPO_DIR,
    SEED_PATH,
    drafter_config,
    open_store,
)
from qws.core.models import LoadIssue, QuestionSummary, QuestionView, RunAllResult
from qws.services.draft_service import (
    Conflict,
    DraftService,
    Drafter,
    DrafterConfig,
    UnknownQuestion,
)

DIST_DIR = REPO_DIR / "frontend" / "dist"


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
    demo_path: Path | None = DEMO_PATH,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store, app.state.load_issues = open_store(db_path, seed_path, demo_path)
        app.state.store = store
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
        return request.app.state.store.list_questions()

    @app.get("/api/questions/{question_id}")
    def question(question_id: str, request: Request) -> QuestionView:
        view = request.app.state.store.get_question_view(question_id)
        if view is None:
            raise HTTPException(404, f"Unknown question {question_id}.")
        return view

    @app.post("/api/questions/{question_id}/draft")
    def draft(question_id: str, request: Request) -> QuestionView:
        result = request.app.state.service.ask(question_id)
        if isinstance(result, UnknownQuestion):
            raise HTTPException(404, f"Unknown question {question_id}.")
        if isinstance(result, Conflict):
            raise HTTPException(409, f"Question {question_id} already has a draft.")
        return result

    @app.post("/api/questionnaire/run")
    def run_all(request: Request) -> RunAllResult:
        return RunAllResult(asked=request.app.state.service.run_all())

    # Mounted last so every /api/* route above wins over the static files.
    # dist may not exist yet; files are looked up per request, so a build made
    # after startup is served without a restart.
    app.mount("/", LazyStaticFiles(directory=dist_dir, html=True, check_dir=False))

    return app


app = create_app()

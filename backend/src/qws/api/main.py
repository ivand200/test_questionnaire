import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

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
from qws.core.models import ApproveRequest, BumpResult, EditRequest, LeaveOpenRequest, LoadIssue, QuestionSummary, QuestionView, RunAllResult, Status, SummaryCounts, UnknownQuestion
from qws.services.draft_service import (
    Conflict,
    DraftService,
    Drafter,
    DrafterConfig,
)
from qws.services.review_service import NotAllowed, ReviewService

DIST_DIR = REPO_DIR / "frontend" / "dist"


class LazyStaticFiles(StaticFiles):
    """StaticFiles that tolerates a missing directory: requests 404 until it exists.

    A path that is not `/api...` and not a built file gets `index.html`, so a reload of a
    client route such as `/questions/Q3` works. An unknown `/api...` path stays a 404.
    """

    async def check_config(self) -> None:
        pass

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


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
        app.state.review = ReviewService(store)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/load-issues")
    def load_issues(request: Request) -> list[LoadIssue]:
        return request.app.state.load_issues

    @app.get("/api/questions")
    def questions(request: Request, status: Status | None = None) -> list[QuestionSummary]:
        return request.app.state.store.list_questions(status)

    @app.post("/api/documents/{document_id}/bump-version")
    def bump_version(document_id: str, request: Request) -> BumpResult:
        version = request.app.state.store.bump_version(document_id)
        if version is None:
            raise HTTPException(404, f"Unknown document {document_id}.")
        return BumpResult(id=document_id, version=version)

    @app.get("/api/summary")
    def summary(request: Request) -> SummaryCounts:
        return request.app.state.store.summary()

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
            raise HTTPException(409, f"Question {question_id} {result.reason}")
        return result

    @app.put("/api/questions/{question_id}/draft")
    def edit_draft(question_id: str, body: EditRequest, request: Request) -> QuestionView:
        result = request.app.state.review.edit(question_id, body.answer)
        if isinstance(result, UnknownQuestion):
            raise HTTPException(404, f"Unknown question {question_id}.")
        if isinstance(result, NotAllowed):
            raise HTTPException(409, result.reason)
        return result

    @app.post("/api/questions/{question_id}/approve")
    def approve(question_id: str, body: ApproveRequest, request: Request) -> QuestionView:
        result = request.app.state.review.approve(question_id, body.approver)
        if isinstance(result, UnknownQuestion):
            raise HTTPException(404, f"Unknown question {question_id}.")
        if isinstance(result, NotAllowed):
            raise HTTPException(409, result.reason)
        return result

    @app.post("/api/questions/{question_id}/leave-open")
    def leave_open(question_id: str, body: LeaveOpenRequest, request: Request) -> QuestionView:
        result = request.app.state.review.leave_open(question_id, body.note)
        if isinstance(result, UnknownQuestion):
            raise HTTPException(404, f"Unknown question {question_id}.")
        if isinstance(result, NotAllowed):
            raise HTTPException(409, result.reason)
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

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qws.api.main import create_app
from qws.config import REPLAY_PATH, SEED_PATH
from qws.services.draft_service import Drafter

ALL = [f"Q{n}" for n in range(1, 11)]  # Q1 to Q8 from the Seed file, Q9 and Q10 from the Demo file
EDIT = "No. CSV export needs a paid plan."
ORIGINAL = "No. Free-plan users cannot export CSV; CSV exports are available only on paid plans."


@pytest.fixture(autouse=True)
def no_model_env(monkeypatch):
    for name in ("MODEL_MODE", "MODEL_NAME", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def make_client(
    tmp_path: Path, replay_path: Path = REPLAY_PATH, drafter: Drafter | None = None
) -> TestClient:
    # The real Seed, the Demo file and the committed Replay file, as `make dev` runs them.
    return TestClient(
        create_app(
            tmp_path / "dist", tmp_path / "test.db", SEED_PATH, drafter, replay_path=replay_path
        )
    )


def model_calls(tmp_path: Path, question_id: str) -> list[tuple]:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return conn.execute(
            "SELECT label, raw_response, error, input_tokens, output_tokens, id FROM model_call"
            " WHERE question_id = ? ORDER BY id",
            (question_id,),
        ).fetchall()
    finally:
        conn.close()


def call_count(tmp_path: Path, question_id: str) -> int:
    return len(model_calls(tmp_path, question_id))


def draft_row(tmp_path, question_id: str) -> dict | None:
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM draft WHERE question_id = ?", (question_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def approved_count(tmp_path) -> int:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return conn.execute("SELECT COUNT(*) FROM approved_answer").fetchone()[0]
    finally:
        conn.close()

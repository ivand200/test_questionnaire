import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qws.api.main import create_app
from qws.config import REPLAY_PATH, SEED_PATH
from qws.services.draft_service import Drafter

ALL = [f"Q{n}" for n in range(1, 10)]  # Q1 to Q8 from the Seed file, Q9 from the Demo file


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

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qws.adapters.replay_drafter import ReplayDrafter
from qws.api.main import create_app
from qws.adapters.store import Store
from qws.config import REPLAY_PATH, SEED_PATH, drafter_config
from qws.core import rules
from qws.services import seed_loader

SUPPORT_EXCERPT = (
    "Email support is available Monday to Friday, 09:00 to 17:00 UTC. Live chat is not offered."
)


@pytest.fixture(autouse=True)
def no_model_env(monkeypatch):
    for name in ("MODEL_MODE", "MODEL_NAME", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def make_client(tmp_path: Path, replay_path: Path = REPLAY_PATH) -> TestClient:
    # The committed Replay file and the default configuration, as `make dev` runs them.
    return TestClient(
        create_app(tmp_path / "dist", tmp_path / "test.db", SEED_PATH, replay_path=replay_path)
    )


def empty_replay_file(tmp_path: Path) -> Path:
    path = tmp_path / "empty-responses.json"
    path.write_text("[]")
    return path


def test_replay_gives_the_q3_draft_from_the_committed_file_with_no_key(tmp_path):
    # spec: 4.1-a
    # GIVEN MODEL_MODE empty, no OPENAI_API_KEY, the committed Replay file has the Q3 entry
    with make_client(tmp_path) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status draft, cites SUPPORT-v1:p1; the model call is cached with no token counts
    assert body["status"] == "draft"
    assert [c["passage_id"] for c in body["citations"]] == ["SUPPORT-v1:p1"]
    assert body["citations"][0]["excerpt"] == SUPPORT_EXCERPT
    conn = sqlite3.connect(tmp_path / "test.db")
    [(label, input_tokens, output_tokens)] = conn.execute(
        "SELECT label, input_tokens, output_tokens FROM model_call"
    ).fetchall()
    conn.close()
    assert (label, input_tokens, output_tokens) == ("cached", None, None)


def test_replay_with_no_entry_gives_error_and_no_exception(tmp_path, monkeypatch):
    # spec: 4.2-a
    # GIVEN MODEL_MODE is replay; the Replay file is empty, so it has no entry for Q4
    monkeypatch.setenv("MODEL_MODE", "replay")
    with make_client(tmp_path, empty_replay_file(tmp_path)) as client:
        # WHEN the user asks for a draft of Q4
        response = client.post("/api/questions/Q4/draft")

    # THEN Q4 has status error with the message; no exception reaches the client
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == "No saved response for this input."
    assert body["allowed_actions"] == ["retry"]


def test_after_a_replay_error_the_other_questions_keep_their_status(tmp_path):
    # spec: 4.2-b
    # GIVEN as 4.2-a
    with make_client(tmp_path, empty_replay_file(tmp_path)) as client:
        # WHEN the same request is made
        client.post("/api/questions/Q4/draft")
        statuses = {q["id"]: q["status"] for q in client.get("/api/questions").json()}

    # THEN Q3 and Q5 to Q8 keep their status
    assert statuses["Q4"] == "error"
    assert {statuses[i] for i in ("Q1", "Q2", "Q3", "Q5", "Q6", "Q7", "Q8")} == {"new"}


def test_changing_the_system_prompt_changes_the_input_hash_and_replay_gives_the_error(tmp_path):
    # spec: 4.5-a
    # GIVEN the Q3 input hash h1 (the committed entry)
    store = Store(tmp_path / "test.db")
    store.init_schema()
    seed_loader.load(json.loads(SEED_PATH.read_text()), store)
    config = drafter_config()
    passages = rules.current_passages(store.list_documents(), store.list_passages())
    q3 = store.get_question("Q3")
    h1 = rules.build_prompt(q3, passages, config.model, config.settings)
    drafter = ReplayDrafter(config.model, config.settings, REPLAY_PATH)
    assert drafter.draft(h1).error is None

    # WHEN one word of the system prompt changes
    system = rules.SYSTEM_PROMPT.replace("Never", "Always")
    changed = rules.build_prompt(q3, passages, config.model, config.settings, system=system)

    # THEN the input hash is not h1; replay mode gives the error of 4.2-a
    assert changed.input_hash != h1.input_hash
    assert drafter.draft(changed).error == "No saved response for this input."

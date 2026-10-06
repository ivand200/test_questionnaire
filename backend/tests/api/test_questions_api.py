import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from qws.api.main import SEED_PATH, create_app

REAL_SEED = json.loads(SEED_PATH.read_text())


def make_client(tmp_path: Path, seed: dict | None = None) -> TestClient:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed or REAL_SEED))
    return TestClient(create_app(tmp_path / "dist", tmp_path / "test.db", seed_path, demo_path=None))


def test_load_issues_is_empty_for_the_real_seed(tmp_path):
    # spec: 1.5-a
    # GIVEN the real Seed is loaded
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/load-issues
        response = client.get("/api/load-issues")

    # THEN HTTP 200, body []
    assert response.status_code == 200
    assert response.json() == []


def test_load_issues_lists_the_duplicate_document(tmp_path):
    # spec: 1.5-b
    # GIVEN the Seed of 1.3-a is loaded
    seed = copy.deepcopy(REAL_SEED)
    second = copy.deepcopy(seed["documents"][1])
    second["version"] = 9
    seed["documents"].append(second)
    with make_client(tmp_path, seed) as client:
        # WHEN a client sends GET /api/load-issues
        response = client.get("/api/load-issues")

    # THEN HTTP 200, one item: kind duplicate_id, id EXPORT-v2, a short message
    assert response.status_code == 200
    [issue] = response.json()
    assert issue["kind"] == "duplicate_id"
    assert issue["id"] == "EXPORT-v2"
    assert issue["message"]


def test_questions_lists_q1_to_q8_in_seed_order_all_new(tmp_path):
    # spec: 5.1-a
    # GIVEN the real Seed is loaded
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/questions
        response = client.get("/api/questions")

    # THEN HTTP 200, 8 items Q1 to Q8 in this order, all with status new
    assert response.status_code == 200
    body = response.json()
    assert [q["id"] for q in body] == [f"Q{n}" for n in range(1, 9)]
    assert {q["status"] for q in body} == {"new"}
    assert body[2] == {
        "id": "Q3",
        "topic": "support",
        "text": "When is email support available?",
        "status": "new",
    }


def test_a_restart_on_the_same_database_changes_nothing(tmp_path):
    # spec: 1.2-a
    # GIVEN the Backend has started once on a Database
    with make_client(tmp_path) as client:
        first = client.get("/api/questions").json()

    # WHEN it starts again on the same Database
    with make_client(tmp_path) as client:
        second = client.get("/api/questions").json()
        issues = client.get("/api/load-issues").json()

    # THEN the questions are the same and there are no load issues
    assert second == first
    assert issues == []

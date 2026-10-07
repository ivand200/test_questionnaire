import json
import sqlite3

from conftest import ScriptedDrafter, make_client
from qws.config import SEED_PATH


def created_at_of_draft_call(tmp_path, question_id: str) -> str:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return conn.execute(
            "SELECT m.created_at FROM draft d JOIN model_call m ON m.id = d.model_call_id"
            " WHERE d.question_id = ?",
            (question_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def test_health_shows_replay_mode_when_model_mode_is_not_set(tmp_path):
    # spec: 4.1-a
    # GIVEN MODEL_MODE is not set
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/health
        response = client.get("/api/health")

    # THEN the body is {"status": "ok", "mode": "replay"}
    assert response.json() == {"status": "ok", "mode": "replay"}


def test_health_shows_real_mode_when_model_mode_is_real(tmp_path, monkeypatch):
    # spec: 4.1-b
    # GIVEN MODEL_MODE=real and a fake Drafter
    monkeypatch.setenv("MODEL_MODE", "real")
    with make_client(tmp_path, drafter=ScriptedDrafter()) as client:
        # WHEN a client sends GET /api/health
        response = client.get("/api/health")

    # THEN the body is {"status": "ok", "mode": "real"}
    assert response.json() == {"status": "ok", "mode": "real"}


def test_q3_drafted_from_the_replay_file_has_the_call_info(tmp_path):
    # spec: 4.2-a
    # GIVEN the committed Replay file; Q3 drafted
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN a client sends GET /api/questions/Q3
        body = client.get("/api/questions/Q3").json()

    # THEN call is the label, model and created_at of the draft call
    assert body["call"] == {
        "label": "cached",
        "model": "gpt-6-luna",
        "when": created_at_of_draft_call(tmp_path, "Q3"),
    }


def test_a_question_not_asked_has_no_call(tmp_path):
    # spec: 4.2-b
    # GIVEN Q3 not asked
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/questions/Q3
        body = client.get("/api/questions/Q3").json()

    # THEN call is null
    assert body["call"] is None


def test_q1_citation_and_replaced_passage_have_version_and_date(tmp_path):
    # spec: 4.3-a
    # GIVEN the committed Replay file; Q1 drafted
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q1/draft")

        # WHEN a client sends GET /api/questions/Q1
        body = client.get("/api/questions/Q1").json()

    # THEN the citation EXPORT-v2:p1 has date 2026-08-01; the replaced passage has version 1
    # and date 2026-01-01
    [citation] = body["citations"]
    assert (citation["passage_id"], citation["date"]) == ("EXPORT-v2:p1", "2026-08-01")
    [replaced] = body["replaced"]
    assert (replaced["passage_id"], replaced["version"], replaced["date"]) == (
        "EXPORT-v1:p1",
        1,
        "2026-01-01",
    )


def test_queue_rows_have_owner_and_warning_count(tmp_path):
    # spec: 4.4-a
    # GIVEN the committed Replay file; Q1 drafted, Q3 not asked
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q1/draft")

        # WHEN a client sends GET /api/questions
        rows = {q["id"]: q for q in client.get("/api/questions").json()}

    # THEN Q1 has owner Product reviewer and 1 warning; Q3 has owner Support reviewer and 0
    assert (rows["Q1"]["owner"], rows["Q1"]["warning_count"]) == ("Product reviewer", 1)
    assert (rows["Q3"]["owner"], rows["Q3"]["warning_count"]) == ("Support reviewer", 0)


def test_q10_has_two_warnings_after_run_all(tmp_path):
    # spec: 4.4-b
    # GIVEN the committed Replay file; Run all ran
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN a client sends GET /api/questions
        rows = {q["id"]: q for q in client.get("/api/questions").json()}

    # THEN Q10 has warning_count 2 (support_check and superseded), as its view says
    assert rows["Q10"]["warning_count"] == 2
    with make_client(tmp_path) as client:
        kinds = [w["kind"] for w in client.get("/api/questions/Q10").json()["warnings"]]
    assert sorted(kinds) == ["superseded", "support_check"]


def test_documents_lists_the_five_seed_documents_with_replaced_by(tmp_path):
    # spec: 4.5-a
    # GIVEN the real Seed
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/documents
        response = client.get("/api/documents")

    # THEN 5 items in Seed order; EXPORT-v1 is replaced by EXPORT-v2; no item has status
    assert response.status_code == 200
    docs = response.json()
    assert [d["id"] for d in docs] == [
        "EXPORT-v1",
        "EXPORT-v2",
        "SUPPORT-v1",
        "ACCESS-v1",
        "BILLING-v1",
    ]
    v1, v2 = docs[0], docs[1]
    assert (v1["version"], v1["date"], v1["supersedes_id"], v1["replaced_by"]) == (
        1,
        "2026-01-01",
        None,
        "EXPORT-v2",
    )
    assert (v2["version"], v2["supersedes_id"], v2["replaced_by"]) == (2, "EXPORT-v1", None)
    seed = json.loads(SEED_PATH.read_text())
    seed_v2 = next(d for d in seed["documents"] if d["id"] == "EXPORT-v2")
    assert v2["passages"] == [{"id": p["id"], "text": p["text"]} for p in seed_v2["passages"]]
    assert all("status" not in d for d in docs)


def test_a_bump_shows_in_the_documents(tmp_path):
    # spec: 4.5-b
    # GIVEN the real Seed; EXPORT-v2 was bumped
    with make_client(tmp_path) as client:
        client.post("/api/documents/EXPORT-v2/bump-version")

        # WHEN a client sends GET /api/documents
        docs = {d["id"]: d for d in client.get("/api/documents").json()}

    # THEN EXPORT-v2 has version 3
    assert docs["EXPORT-v2"]["version"] == 3


import json
import sqlite3

from conftest import EDIT, ORIGINAL, approved_count, call_count, draft_row, make_client


def approved_rows(tmp_path) -> list[dict]:
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM approved_answer")]
    finally:
        conn.close()


def approved_q1(client):
    """Run all from the replay file, edit Q1, approve it as Anna. Returns the approve response."""
    client.post("/api/questionnaire/run")
    client.put("/api/questions/Q1/draft", json={"answer": EDIT})
    return client.post("/api/questions/Q1/approve", json={"approver": "Anna"})


def test_approve_saves_the_edit_with_a_snapshot_of_the_cited_document(tmp_path):
    # spec: 2.1-a
    # GIVEN Q1 has a saved edit
    with make_client(tmp_path) as client:
        # WHEN the client sends POST /api/questions/Q1/approve with approver Anna
        response = approved_q1(client)

    # THEN 200; approved; the edit; Anna; the time; snapshot only EXPORT-v2; one row;
    # the draft row keeps the model answer; 1 model call
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["answer"] == EDIT
    assert body["approved"]["approver"] == "Anna"
    assert body["approved"]["approved_at"]
    assert body["approved"]["source_versions"] == {"EXPORT-v2": 2}
    assert [c["passage_id"] for c in body["citations"]] == ["EXPORT-v2:p1"]
    assert body["citations"][0]["excerpt"]
    rows = approved_rows(tmp_path)
    assert len(rows) == 1
    assert json.loads(rows[0]["source_versions"]) == {"EXPORT-v2": 2}
    assert draft_row(tmp_path, "Q1")["model_answer"] == ORIGINAL
    assert call_count(tmp_path, "Q1") == 1


def test_approve_without_an_edit_uses_the_model_answer(tmp_path):
    # spec: 2.1-b
    # GIVEN Q3 has a draft from the replay file with no edit
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN the client sends POST /api/questions/Q3/approve
        response = client.post("/api/questions/Q3/approve", json={"approver": "Anna"})

    # THEN approved with the model answer; the snapshot has only SUPPORT-v1
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "approved"
    assert body["answer"] == "Email support is available Monday to Friday, 09:00 to 17:00 UTC."
    assert body["approved"]["source_versions"] == {"SUPPORT-v1": 1}


def test_approve_of_an_unresolved_question_gives_409_and_saves_nothing(tmp_path):
    # spec: 2.2-a
    # GIVEN Q2 is unresolved
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends POST /api/questions/Q2/approve
        response = client.post("/api/questions/Q2/approve", json={"approver": "Anna"})
        status = client.get("/api/questions/Q2").json()["status"]

    # THEN 409 with a short message; no row; Q2 is still unresolved
    assert response.status_code == 409
    assert 0 < len(response.json()["detail"]) < 100
    assert approved_count(tmp_path) == 0
    assert status == "unresolved"


def test_approve_of_a_new_question_gives_409(tmp_path):
    # spec: 2.2-b
    # GIVEN Q3 is new
    with make_client(tmp_path) as client:
        # WHEN the client sends POST /api/questions/Q3/approve
        response = client.post("/api/questions/Q3/approve", json={"approver": "Anna"})

    # THEN 409; no row
    assert response.status_code == 409
    assert approved_count(tmp_path) == 0


def test_approve_of_a_draft_with_no_citation_gives_409(tmp_path):
    # spec: 2.2-c
    # GIVEN Q3 has a draft row with status draft and an empty citation list
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q3/draft")
        conn = sqlite3.connect(tmp_path / "test.db")
        with conn:
            conn.execute("UPDATE draft SET citations = '[]' WHERE question_id = 'Q3'")
        conn.close()

        # WHEN the client sends POST /api/questions/Q3/approve
        response = client.post("/api/questions/Q3/approve", json={"approver": "Anna"})

    # THEN 409; no row
    assert response.status_code == 409
    assert approved_count(tmp_path) == 0


def test_a_blank_approver_gives_422_and_saves_nothing(tmp_path):
    # spec: 2.3-a
    # GIVEN Q1 has a draft
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends POST /api/questions/Q1/approve with a blank approver
        response = client.post("/api/questions/Q1/approve", json={"approver": "  "})
        status = client.get("/api/questions/Q1").json()["status"]

    # THEN 422; no row; Q1 is still draft
    assert response.status_code == 422
    assert approved_count(tmp_path) == 0
    assert status == "draft"


def test_a_second_approve_keeps_the_first_approver_and_makes_no_second_row(tmp_path):
    # spec: 2.4-a
    # GIVEN Q1 is approved by Anna
    with make_client(tmp_path) as client:
        approved_q1(client)

        # WHEN the client sends POST /api/questions/Q1/approve with approver Bob
        response = client.post("/api/questions/Q1/approve", json={"approver": "Bob"})

    # THEN 200; the approver is still Anna; one row
    assert response.status_code == 200
    assert response.json()["approved"]["approver"] == "Anna"
    assert len(approved_rows(tmp_path)) == 1


def test_the_approved_answer_wins_over_the_kept_draft_row(tmp_path):
    # spec: 4.1-a
    # GIVEN Q1 is approved by Anna; its draft row is still there with status draft
    with make_client(tmp_path) as client:
        approved_q1(client)
        assert draft_row(tmp_path, "Q1")["status"] == "draft"

        # WHEN the client sends GET /api/questions/Q1 and GET /api/questions
        view = client.get("/api/questions/Q1").json()
        queue = {q["id"]: q["status"] for q in client.get("/api/questions").json()}

    # THEN approved with the edit, Anna and the snapshot; the queue shows Q1 approved
    # (the summary count is checked in ticket 5)
    assert view["status"] == "approved"
    assert view["answer"] == EDIT
    assert view["approved"]["approver"] == "Anna"
    assert view["approved"]["source_versions"] == {"EXPORT-v2": 2}
    assert queue["Q1"] == "approved"

import sqlite3

from conftest import call_count, make_client

EDIT = "No. CSV export needs a paid plan."
ORIGINAL = "No. Free-plan users cannot export CSV; CSV exports are available only on paid plans."


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


def edited_q1(tmp_path):
    """Run all from the replay file, then edit Q1. Returns the edit response."""
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        return client.put("/api/questions/Q1/draft", json={"answer": EDIT})


def test_edit_saves_the_reviewer_answer_and_keeps_the_model_answer(tmp_path):
    # spec: 1.1-a
    # GIVEN the real Seed; Q1 has a draft from the replay file
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        assert client.get("/api/questions/Q1").json()["answer"] == ORIGINAL

        # WHEN the client sends PUT /api/questions/Q1/draft with a new answer
        response = client.put("/api/questions/Q1/draft", json={"answer": EDIT})

    # THEN 200; status draft; the new answer; edited true; model_answer unchanged
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["answer"] == EDIT
    assert body["edited"] is True
    row = draft_row(tmp_path, "Q1")
    assert row["model_answer"] == ORIGINAL
    assert row["reviewer_answer"] == EDIT
    assert approved_count(tmp_path) == 0
    assert call_count(tmp_path, "Q1") == 1


def test_an_edit_survives_a_restart(tmp_path):
    # spec: 1.1-b
    # GIVEN Q1 has a saved edit
    edited_q1(tmp_path)

    # WHEN the app is started again on the same Database and the client sends GET /api/questions/Q1
    with make_client(tmp_path) as client:
        body = client.get("/api/questions/Q1").json()

    # THEN status draft; the edited answer; edited true
    assert body["status"] == "draft"
    assert body["answer"] == EDIT
    assert body["edited"] is True


def test_edit_of_an_unresolved_question_gives_409_and_saves_nothing(tmp_path):
    # spec: 1.2-a
    # GIVEN Q2 is unresolved
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        assert client.get("/api/questions/Q2").json()["status"] == "unresolved"

        # WHEN the client sends PUT /api/questions/Q2/draft
        response = client.put("/api/questions/Q2/draft", json={"answer": "Yes."})

    # THEN 409 with a message; reviewer_answer of Q2 is still empty
    assert response.status_code == 409
    assert response.json()["detail"]
    assert draft_row(tmp_path, "Q2")["reviewer_answer"] is None


def test_edit_of_a_new_question_gives_409_and_makes_no_draft_row(tmp_path):
    # spec: 1.2-b
    # GIVEN Q3 is new
    with make_client(tmp_path) as client:
        # WHEN the client sends PUT /api/questions/Q3/draft
        response = client.put("/api/questions/Q3/draft", json={"answer": "Yes."})

    # THEN 409; Q3 has no draft row
    assert response.status_code == 409
    assert draft_row(tmp_path, "Q3") is None


def test_a_blank_edit_gives_422_and_saves_nothing(tmp_path):
    # spec: 1.2-c
    # GIVEN Q1 has a draft
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends PUT /api/questions/Q1/draft with a blank answer
        response = client.put("/api/questions/Q1/draft", json={"answer": "   "})

    # THEN 422; reviewer_answer of Q1 is still empty
    assert response.status_code == 422
    assert draft_row(tmp_path, "Q1")["reviewer_answer"] is None


def test_an_edit_without_approval_stays_a_draft_when_asked_again_or_run_all(tmp_path):
    # spec: 1.3-a
    # GIVEN Q1 has a saved edit, no approval
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        client.put("/api/questions/Q1/draft", json={"answer": EDIT})

        # WHEN the client asks Q1 again, runs all, and reads Q1
        asked_again = client.post("/api/questions/Q1/draft")
        run = client.post("/api/questionnaire/run")
        body = client.get("/api/questions/Q1").json()

    # THEN 409; Q1 is not asked; still draft with the edit; no approval; 1 model call
    assert asked_again.status_code == 409
    assert "Q1" not in run.json()["asked"]
    assert body["status"] == "draft"
    assert body["answer"] == EDIT
    assert approved_count(tmp_path) == 0
    assert call_count(tmp_path, "Q1") == 1


def test_allowed_actions_follow_the_status(tmp_path):
    # spec: 4.5-a
    # GIVEN Q1 draft, Q2 unresolved, Q9 error (replay file) and Q3 new
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q1/draft")
        client.post("/api/questions/Q2/draft")
        client.post("/api/questions/Q9/draft")

        # WHEN the client sends GET /api/questions/{id} for each
        actions = {
            i: client.get(f"/api/questions/{i}").json()["allowed_actions"]
            for i in ("Q3", "Q1", "Q2", "Q9")
        }

    # THEN the allowed actions follow the status
    assert actions == {
        "Q3": ["generate"],
        "Q1": ["edit", "approve", "leave_open"],
        "Q2": ["leave_open"],
        "Q9": ["retry"],
    }

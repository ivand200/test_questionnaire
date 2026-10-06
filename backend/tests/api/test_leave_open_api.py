from conftest import EDIT, approved_count, draft_row, make_client
from test_approve_api import approved_q1

NOTE = "Check with the product team."


def test_leave_open_on_a_draft_saves_the_note_and_keeps_the_edit(tmp_path):
    # spec: 3.1-a
    # GIVEN Q1 has a saved edit
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        client.put("/api/questions/Q1/draft", json={"answer": EDIT})

        # WHEN the client sends POST /api/questions/Q1/leave-open with a note
        response = client.post("/api/questions/Q1/leave-open", json={"note": NOTE})

    # THEN 200; unresolved; the note; the edit is kept; only leave_open; no approved row
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unresolved"
    assert body["note"] == NOTE
    assert body["answer"] == EDIT
    assert body["allowed_actions"] == ["leave_open"]
    assert draft_row(tmp_path, "Q1")["reviewer_answer"] == EDIT
    assert approved_count(tmp_path) == 0


def test_leave_open_on_an_unresolved_question_replaces_the_note_and_survives_a_restart(tmp_path):
    # spec: 3.2-a
    # GIVEN the real Seed; Q2 is unresolved from the replay file
    note = "Ask the product team if JSON export is planned."
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends POST /api/questions/Q2/leave-open, then the app is started again
        first = client.post("/api/questions/Q2/leave-open", json={"note": note})
    with make_client(tmp_path) as client:
        view = client.get("/api/questions/Q2").json()
        approve = client.post("/api/questions/Q2/approve", json={"approver": "Anna"})

    # THEN 200; after the restart unresolved, owner, note, no answer; Approve gives 409; no row
    assert first.status_code == 200
    assert view["status"] == "unresolved"
    assert view["owner"] == "Product reviewer"
    assert view["note"] == note
    assert not view["answer"].startswith(("Yes", "No"))
    assert approve.status_code == 409
    assert approved_count(tmp_path) == 0


def test_leave_open_on_a_new_question_gives_409_and_saves_nothing(tmp_path):
    # spec: 3.3-a
    # GIVEN Q3 is new
    with make_client(tmp_path) as client:
        # WHEN the client sends POST /api/questions/Q3/leave-open
        response = client.post("/api/questions/Q3/leave-open", json={"note": "x"})

    # THEN 409; Q3 has no draft row
    assert response.status_code == 409
    assert draft_row(tmp_path, "Q3") is None


def test_leave_open_on_an_error_question_gives_409_and_saves_no_note(tmp_path):
    # spec: 3.3-a (status error, as the ticket lists it)
    # GIVEN Q9 is error
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q9/draft")

        # WHEN the client sends POST /api/questions/Q9/leave-open
        response = client.post("/api/questions/Q9/leave-open", json={"note": "x"})
        view = client.get("/api/questions/Q9").json()

    # THEN 409; still error; no note
    assert response.status_code == 409
    assert view["status"] == "error"
    assert draft_row(tmp_path, "Q9")["note"] is None


def test_leave_open_on_an_approved_question_gives_409_and_saves_no_note(tmp_path):
    # spec: 3.3-b
    # GIVEN Q1 is approved
    with make_client(tmp_path) as client:
        approved_q1(client)

        # WHEN the client sends POST /api/questions/Q1/leave-open
        response = client.post("/api/questions/Q1/leave-open", json={"note": "x"})
        view = client.get("/api/questions/Q1").json()

    # THEN 409; still approved; no note
    assert response.status_code == 409
    assert view["status"] == "approved"
    assert draft_row(tmp_path, "Q1")["note"] is None


def test_leave_open_with_a_blank_note_gives_422_and_saves_nothing(tmp_path):
    # spec: 3.3-c
    # GIVEN Q2 is unresolved
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends POST /api/questions/Q2/leave-open with an empty note
        response = client.post("/api/questions/Q2/leave-open", json={"note": ""})

    # THEN 422; no note
    assert response.status_code == 422
    assert draft_row(tmp_path, "Q2")["note"] is None

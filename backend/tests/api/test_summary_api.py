from conftest import make_client
from test_approve_api import approved_rows


def run_all_then_approve_q1(client):
    client.post("/api/questionnaire/run")
    return client.post("/api/questions/Q1/approve", json={"approver": "Anna"})


def test_summary_counts_after_run_all(tmp_path):
    # spec: 5.1-a
    # GIVEN the real Seed and Demo file; Run all from the replay file ran
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends GET /api/summary
        response = client.get("/api/summary")

    # THEN the counts are 0 new, 7 draft, 1 unresolved, 0 approved, 0 needs_review, 1 error, 7 answered
    assert response.status_code == 200
    assert response.json() == {
        "new": 0, "draft": 7, "unresolved": 1, "approved": 0, "needs_review": 0, "error": 1,
        "answered": 7,
    }


def test_summary_counts_an_approved_question_once_as_approved(tmp_path):
    # spec: 5.1-b, 4.1-a
    # GIVEN as 5.1-a, then Q1 is approved (its draft row is kept)
    with make_client(tmp_path) as client:
        run_all_then_approve_q1(client)

        # WHEN the client sends GET /api/summary
        response = client.get("/api/summary")

    # THEN draft is 6 and approved is 1; answered stays 7
    assert response.json() == {
        "new": 0, "draft": 6, "unresolved": 1, "approved": 1, "needs_review": 0, "error": 1,
        "answered": 7,
    }
    assert len(approved_rows(tmp_path)) == 1


def test_filter_approved_returns_only_q1(tmp_path):
    # spec: 5.2-a
    # GIVEN as 5.1-b
    with make_client(tmp_path) as client:
        run_all_then_approve_q1(client)

        # WHEN the client sends GET /api/questions?status=approved
        response = client.get("/api/questions", params={"status": "approved"})

    # THEN only Q1
    assert response.status_code == 200
    assert [q["id"] for q in response.json()] == ["Q1"]
    assert response.json()[0]["status"] == "approved"


def test_filter_draft_returns_seed_order(tmp_path):
    # spec: 5.2-b
    # GIVEN as 5.1-b
    with make_client(tmp_path) as client:
        run_all_then_approve_q1(client)

        # WHEN the client sends GET /api/questions?status=draft
        response = client.get("/api/questions", params={"status": "draft"})
        everything = client.get("/api/questions").json()

    # THEN Q3, Q4, Q5, Q6, Q7, Q8 in this order; without status all 9 come back
    assert [q["id"] for q in response.json()] == ["Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
    assert len(everything) == 9


def test_an_unknown_status_filter_gives_422(tmp_path):
    # spec: 2.3-b
    # GIVEN as 5.1-b
    with make_client(tmp_path) as client:
        run_all_then_approve_q1(client)

        # WHEN the client sends GET /api/questions?status=bogus
        response = client.get("/api/questions", params={"status": "bogus"})

    # THEN 422
    assert response.status_code == 422

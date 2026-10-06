import json

from conftest import EDIT, call_count, make_client
from test_approve_api import approved_q1, approved_rows


def approve_q1_and_q3(client):
    """Run all, edit and approve Q1 as Anna, approve Q3 as Anna."""
    approved_q1(client)
    client.post("/api/questions/Q3/approve", json={"approver": "Anna"})


def bump(client, document_id: str = "EXPORT-v2"):
    return client.post(f"/api/documents/{document_id}/bump-version")


def test_a_bumped_source_makes_the_approved_answer_needs_review(tmp_path):
    # spec: 2.1-a
    # GIVEN Q1 is approved by Anna (snapshot {"EXPORT-v2": 2}); EXPORT-v2 is bumped to version 3
    with make_client(tmp_path) as client:
        approved_q1(client)
        row_before = approved_rows(tmp_path)
        bump(client)

        # WHEN the client sends GET /api/questions/Q1
        response = client.get("/api/questions/Q1")

    # THEN needs_review with the old answer, Anna, the old snapshot, version 2 and current_version 3,
    # one source_changed warning, the replaced text, the three actions; the row is unchanged
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["answer"] == EDIT
    assert body["edited"] is False
    assert body["approved"]["approver"] == "Anna"
    assert body["approved"]["source_versions"] == {"EXPORT-v2": 2}
    assert [(c["passage_id"], c["version"], c["current_version"]) for c in body["citations"]] == [
        ("EXPORT-v2:p1", 2, 3)
    ]
    [warning] = [w for w in body["warnings"] if w["kind"] == "source_changed"]
    assert "EXPORT-v2" in warning["message"]
    assert "2" in warning["message"] and "3" in warning["message"]
    assert [r["passage_id"] for r in body["replaced"]] == ["EXPORT-v1:p1"]
    assert body["allowed_actions"] == ["edit", "approve", "leave_open"]
    assert approved_rows(tmp_path) == row_before


def test_needs_review_is_computed_on_read_and_kept_after_a_restart(tmp_path):
    # spec: 1.3-a
    # GIVEN Q1 is approved by Anna; EXPORT-v2 is bumped to version 3
    with make_client(tmp_path) as client:
        approved_q1(client)
        bump(client)

    # WHEN the app is started again on the same Database and the client sends GET /api/questions/Q1
    with make_client(tmp_path) as client:
        response = client.get("/api/questions/Q1")

    # THEN needs_review; the citation has version 2 and current_version 3
    body = response.json()
    assert body["status"] == "needs_review"
    assert [(c["version"], c["current_version"]) for c in body["citations"]] == [(2, 3)]
    row = approved_rows(tmp_path)[0]
    assert json.loads(row["source_versions"]) == {"EXPORT-v2": 2}


def test_the_summary_counts_needs_review_on_its_own(tmp_path):
    # spec: 2.3-a
    # GIVEN Run all ran; Q1 and Q3 are approved by Anna
    with make_client(tmp_path) as client:
        approve_q1_and_q3(client)

        # WHEN the client sends GET /api/summary, then EXPORT-v2 is bumped and it is sent again
        before = client.get("/api/summary").json()
        bump(client)
        after = client.get("/api/summary").json()

    # THEN needs_review is 0 before; after it is 1, not in approved and not in answered
    assert before == {
        "new": 0, "draft": 5, "unresolved": 1, "approved": 2, "needs_review": 0, "error": 1,
        "answered": 7,
    }
    assert after == {
        "new": 0, "draft": 5, "unresolved": 1, "approved": 1, "needs_review": 1, "error": 1,
        "answered": 6,
    }


def test_the_status_filter_returns_needs_review_and_approved_separately(tmp_path):
    # spec: 2.3-b
    # GIVEN Q1 and Q3 are approved; EXPORT-v2 is bumped to version 3
    with make_client(tmp_path) as client:
        approve_q1_and_q3(client)
        bump(client)

        # WHEN the client sends GET /api/questions with status needs_review, approved, bogus
        review = client.get("/api/questions", params={"status": "needs_review"})
        approved = client.get("/api/questions", params={"status": "approved"})
        bogus = client.get("/api/questions", params={"status": "bogus"})

    # THEN only Q1; only Q3; 422
    assert [(q["id"], q["status"]) for q in review.json()] == [("Q1", "needs_review")]
    assert [(q["id"], q["status"]) for q in approved.json()] == [("Q3", "approved")]
    assert bogus.status_code == 422


def test_a_bump_of_a_document_not_in_the_snapshot_changes_nothing(tmp_path):
    # spec: 2.4-a
    # GIVEN Q1 is approved by Anna (snapshot {"EXPORT-v2": 2})
    with make_client(tmp_path) as client:
        approved_q1(client)

        # WHEN the client bumps EXPORT-v1 (a replaced document), then sends GET /api/questions/Q1
        bumped = bump(client, "EXPORT-v1")
        body = client.get("/api/questions/Q1").json()

    # THEN EXPORT-v1 is at version 2; Q1 is approved with no source_changed warning
    assert bumped.json() == {"id": "EXPORT-v1", "version": 2}
    assert body["status"] == "approved"
    assert [w for w in body["warnings"] if w["kind"] == "source_changed"] == []
    assert call_count(tmp_path, "Q1") == 1

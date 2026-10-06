import json

from conftest import EDIT, call_count, draft_row, make_client
from qws.adapters.replay_drafter import ReplayDrafter
from qws.config import REPLAY_PATH, drafter_config
from qws.core.models import DrafterReply, Prompt
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


class GuardedReplayDrafter:
    """Replays like the app does, but fails the test if asked about one of the guarded questions."""

    def __init__(self, guarded_texts: set[str]) -> None:
        config = drafter_config()
        self._replay = ReplayDrafter(config.model, config.settings, REPLAY_PATH)
        self._guarded = guarded_texts
        self.asked: list[str] = []

    def draft(self, prompt: Prompt) -> DrafterReply:
        text = prompt.user.split("\n", 1)[0].removeprefix("Question: ")
        assert text not in self._guarded, f"the Drafter must not be asked: {text}"
        self.asked.append(text)
        return self._replay.draft(prompt)


def test_a_needs_review_answer_is_not_reused_and_makes_no_model_call(tmp_path):
    # spec: 2.2-a
    # GIVEN Run all ran; Q1 and Q3 are approved by Anna; EXPORT-v2 is bumped to version 3;
    # the app is started again with a Drafter that fails the test if asked about Q1 or Q3
    with make_client(tmp_path) as client:
        client.post("/api/questionnaire/run")
        approve_q1_and_q3(client)
        bump(client)
        texts = {client.get(f"/api/questions/{q}").json()["text"] for q in ("Q1", "Q3")}
        q9_text = client.get("/api/questions/Q9").json()["text"]
    drafter = GuardedReplayDrafter(texts)
    with make_client(tmp_path, drafter=drafter) as client:
        # WHEN the client sends GET Q1, POST Q1/draft, POST run, GET summary
        view = client.get("/api/questions/Q1").json()
        draft = client.post("/api/questions/Q1/draft")
        run = client.post("/api/questionnaire/run")
        summary = client.get("/api/summary").json()
        q3 = client.get("/api/questions/Q3").json()
        q9 = client.get("/api/questions/Q9").json()

    # THEN Q1 is needs_review with the old answer; the draft call gives 409 with a short message;
    # only Q9 is asked (and stays error); the summary counts needs_review; Q3 is approved;
    # Q1 and Q3 have 1 model call each; the Drafter was not asked about Q1 or Q3
    assert view["status"] == "needs_review"
    assert view["answer"] == EDIT
    assert draft.status_code == 409
    assert 0 < len(draft.json()["detail"]) < 100
    assert run.json() == {"asked": ["Q9"]}
    assert drafter.asked == [q9_text]
    assert q9["status"] == "error"
    assert summary == {
        "new": 0, "draft": 5, "unresolved": 1, "approved": 1, "needs_review": 1, "error": 1,
        "answered": 6,
    }
    assert q3["status"] == "approved"
    assert call_count(tmp_path, "Q1") == 1
    assert call_count(tmp_path, "Q3") == 1


class NeverAskedDrafter:
    """A Drafter that fails the test if it is called."""

    def draft(self, prompt: Prompt) -> DrafterReply:
        raise AssertionError("the Drafter must not be called")


def test_approving_again_replaces_the_approved_answer_with_the_new_versions(tmp_path):
    # spec: 3.1-a
    # GIVEN Q1 is needs_review (approved by Anna on v2, EXPORT-v2 is now v3)
    with make_client(tmp_path) as client:
        approved_q1(client)
        bump(client)

        # WHEN the client approves as Ben, the app is started again with a Drafter that fails if
        # called, then GET Q1 and POST Q1/draft
        approve = client.post("/api/questions/Q1/approve", json={"approver": "Ben"})
    with make_client(tmp_path, drafter=NeverAskedDrafter()) as client:
        view = client.get("/api/questions/Q1")
        draft = client.post("/api/questions/Q1/draft")

    # THEN approved by Ben on v3 with the old answer and no source_changed warning; one row;
    # the draft row is kept; after the restart the view is the same; no model call
    assert approve.status_code == 200
    body = approve.json()
    assert body["status"] == "approved"
    assert body["approved"]["approver"] == "Ben"
    assert body["answer"] == EDIT
    assert body["approved"]["source_versions"] == {"EXPORT-v2": 3}
    assert [(c["passage_id"], c["version"], c["current_version"]) for c in body["citations"]] == [
        ("EXPORT-v2:p1", 3, 3)
    ]
    assert [w for w in body["warnings"] if w["kind"] == "source_changed"] == []
    assert len(approved_rows(tmp_path)) == 1
    assert draft_row(tmp_path, "Q1") is not None
    assert view.json() == body
    assert draft.status_code == 200
    assert draft.json() == body
    assert call_count(tmp_path, "Q1") == 1


def test_an_edit_then_approve_saves_the_edit_as_the_new_approved_answer(tmp_path):
    # spec: 3.1-b
    # GIVEN Q1 is needs_review
    new_answer = "No. Free plans cannot export CSV."
    with make_client(tmp_path) as client:
        approved_q1(client)
        bump(client)

        # WHEN the client edits Q1, then approves as Ben
        client.put("/api/questions/Q1/draft", json={"answer": new_answer})
        response = client.post("/api/questions/Q1/approve", json={"approver": "Ben"})

    # THEN approved with the edit and the new snapshot; one row
    body = response.json()
    assert body["status"] == "approved"
    assert body["answer"] == new_answer
    assert body["approved"]["source_versions"] == {"EXPORT-v2": 3}
    [row] = approved_rows(tmp_path)
    assert row["answer"] == new_answer


def test_the_approved_citations_hold_only_the_passage_id_and_the_excerpt(tmp_path):
    # spec: 3.1-c
    # GIVEN Q1 is needs_review
    with make_client(tmp_path) as client:
        approved_q1(client)
        bump(client)

        # WHEN the client approves as Ben
        client.post("/api/questions/Q1/approve", json={"approver": "Ben"})

    # THEN the saved citations have only passage_id and excerpt
    [row] = approved_rows(tmp_path)
    citations = json.loads(row["citations"])
    assert citations
    assert all(set(c) == {"passage_id", "excerpt"} for c in citations)


def test_a_blank_approver_leaves_a_needs_review_answer_as_it_was(tmp_path):
    # spec: 3.5-a
    # GIVEN Q1 is needs_review
    with make_client(tmp_path) as client:
        approved_q1(client)
        bump(client)
        row_before = approved_rows(tmp_path)

        # WHEN the client approves with a blank approver
        response = client.post("/api/questions/Q1/approve", json={"approver": "  "})
        status = client.get("/api/questions/Q1").json()["status"]

    # THEN 422; Q1 is needs_review; the row still has Anna and {"EXPORT-v2": 2}
    assert response.status_code == 422
    assert status == "needs_review"
    rows = approved_rows(tmp_path)
    assert rows == row_before
    assert rows[0]["approver"] == "Anna"
    assert json.loads(rows[0]["source_versions"]) == {"EXPORT-v2": 2}

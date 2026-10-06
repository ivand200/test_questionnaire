from conftest import ALL, call_count, make_client
from qws.core.models import DrafterReply, Prompt
from test_approve_api import approved_q1, approved_rows
from test_edit_api import EDIT


class FailingDrafter:
    """Fails the test if it is called."""

    def __init__(self) -> None:
        self.calls = 0

    def draft(self, prompt: Prompt) -> DrafterReply:
        self.calls += 1
        raise AssertionError("the Drafter must not be called for an approved question")


def test_ask_again_on_an_approved_question_returns_the_approved_view_with_no_model_call(tmp_path):
    # spec: 4.2-a
    # GIVEN Q1 is approved by Anna; the app is started again with a Drafter that fails if called
    with make_client(tmp_path) as client:
        approved_q1(client)
    drafter = FailingDrafter()
    with make_client(tmp_path, drafter=drafter) as client:
        # WHEN the client sends POST /api/questions/Q1/draft
        response = client.post("/api/questions/Q1/draft")

    # THEN 200; approved view with the edit, Anna and the snapshot; no Drafter call; 1 model call
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["answer"] == EDIT
    assert body["approved"]["approver"] == "Anna"
    assert body["approved"]["source_versions"] == {"EXPORT-v2": 2}
    assert drafter.calls == 0
    assert call_count(tmp_path, "Q1") == 1
    assert len(approved_rows(tmp_path)) == 1


def test_run_all_skips_an_approved_question_and_asks_the_rest(tmp_path):
    # spec: 4.3-a
    # GIVEN Q1 is approved; Q2 to Q9 are new
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q1/draft")
        client.post("/api/questions/Q1/approve", json={"approver": "Anna"})

        # WHEN the client sends POST /api/questionnaire/run
        response = client.post("/api/questionnaire/run")

    # THEN asked is Q2 to Q9; Q1 is not asked and keeps 1 model call
    assert response.json() == {"asked": ALL[1:]}
    assert call_count(tmp_path, "Q1") == 1


def test_an_approved_answer_survives_a_restart(tmp_path):
    # spec: 4.4-a
    # GIVEN Q1 is approved by Anna
    with make_client(tmp_path) as client:
        approved_q1(client)
        before = client.get("/api/questions/Q1").json()

    # WHEN the app is started again on the same Database and the client sends GET /api/questions/Q1
    with make_client(tmp_path) as client:
        after = client.get("/api/questions/Q1").json()

    # THEN the body is the same as before the restart
    assert after == before
    assert after["status"] == "approved"

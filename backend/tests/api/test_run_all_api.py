import json

from fastapi.testclient import TestClient

from conftest import ALL, call_count, make_client
from qws.core.models import DrafterReply, Prompt

TIMEOUT = "Model call failed: timeout."
Q2_TEXT = "Is JSON export available?"
Q4_TEXT = "Is live chat offered?"
Q9_TEXT = "What is the response time for priority support tickets?"


class ScriptedDrafter:
    """Replies `supported` for every question; the texts in `failing` time out each time.

    Replies `not_documented` for the texts in `unresolved`. Keeps the question texts it was asked.
    """

    def __init__(self, failing=(), unresolved=()) -> None:
        self.failing = set(failing)
        self.unresolved = set(unresolved)
        self.asked: list[str] = []

    def draft(self, prompt: Prompt) -> DrafterReply:
        text = prompt.user.split("\n", 1)[0].removeprefix("Question: ")
        self.asked.append(text)
        base = {"label": "real", "model": "m1", "settings": {"temperature": 0}}
        if text in self.failing:
            return DrafterReply(error=TIMEOUT, **base)
        if text in self.unresolved:
            raw = {"answer": "Not documented.", "verdict": "not_documented", "citations": []}
        else:
            raw = {"answer": "Yes.", "verdict": "supported", "citations": ["SUPPORT-v1:p1"]}
        return DrafterReply(raw_reply=json.dumps(raw), **base)


def statuses(client: TestClient) -> dict[str, str]:
    return {q["id"]: q["status"] for q in client.get("/api/questions").json()}


def test_run_all_asks_every_new_question_and_lists_them_in_seed_order(tmp_path):
    # spec: 4.1-a
    # GIVEN all 9 questions are new
    drafter = ScriptedDrafter(unresolved=[Q2_TEXT], failing=[Q9_TEXT])
    with make_client(tmp_path, drafter=drafter) as client:
        # WHEN the client sends POST /api/questionnaire/run
        response = client.post("/api/questionnaire/run")

        # THEN asked lists Q1 to Q9 in Seed order and the statuses are saved
        assert response.status_code == 200
        assert response.json() == {"asked": ALL}
        found = statuses(client)
    assert found["Q1"] == "draft"
    assert found["Q2"] == "unresolved"
    assert found["Q9"] == "error"
    assert drafter.asked[0] == "Can free-plan users export CSV?"
    assert len(drafter.asked) == 9


def test_a_second_run_asks_only_the_question_that_is_still_an_error(tmp_path):
    # spec: 4.1-b
    # GIVEN a run is done and Q9 is still error
    drafter = ScriptedDrafter(unresolved=[Q2_TEXT], failing=[Q9_TEXT])
    with make_client(tmp_path, drafter=drafter) as client:
        client.post("/api/questionnaire/run")

        # WHEN the client sends POST /api/questionnaire/run again
        response = client.post("/api/questionnaire/run")

    # THEN asked is Q9; Q9 has 2 model calls; Q1 to Q8 have 1 each
    assert response.json() == {"asked": ["Q9"]}
    assert call_count(tmp_path, "Q9") == 2
    assert [call_count(tmp_path, f"Q{n}") for n in range(1, 9)] == [1] * 8


def test_run_all_skips_questions_with_a_draft_or_unresolved(tmp_path):
    # spec: 4.2-a
    # GIVEN Q3 has a draft and Q2 is unresolved; Q9 is error; the others are new
    drafter = ScriptedDrafter(unresolved=[Q2_TEXT], failing=[Q9_TEXT])
    with make_client(tmp_path, drafter=drafter) as client:
        client.post("/api/questions/Q3/draft")
        client.post("/api/questions/Q2/draft")
        client.post("/api/questions/Q9/draft")
        before = {i: client.get(f"/api/questions/{i}").json() for i in ("Q2", "Q3")}
        drafter.asked.clear()

        # WHEN the client sends POST /api/questionnaire/run
        response = client.post("/api/questionnaire/run")

        # THEN Q2 and Q3 are not asked; they keep 1 model call and the same draft
        assert response.json() == {"asked": ["Q1", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9"]}
        after = {i: client.get(f"/api/questions/{i}").json() for i in ("Q2", "Q3")}
    assert after == before
    assert Q2_TEXT not in drafter.asked
    assert "When is email support available?" not in drafter.asked
    assert call_count(tmp_path, "Q2") == 1
    assert call_count(tmp_path, "Q3") == 1


def test_a_timeout_for_q4_does_not_stop_the_other_questions(tmp_path):
    # spec: 4.3-a
    # GIVEN a Drafter that replies for every question except Q4, which times out; all 9 are new
    drafter = ScriptedDrafter(failing=[Q4_TEXT])
    with make_client(tmp_path, drafter=drafter) as client:
        # WHEN the client sends POST /api/questionnaire/run
        response = client.post("/api/questionnaire/run")

        # THEN Q4 is error with the message; the other 8 are draft; asked has all 9 IDs
        q4 = client.get("/api/questions/Q4").json()
        found = statuses(client)
    assert response.json() == {"asked": ALL}
    assert q4["status"] == "error"
    assert q4["error"] == TIMEOUT
    assert [i for i, s in found.items() if s == "draft"] == [i for i in ALL if i != "Q4"]

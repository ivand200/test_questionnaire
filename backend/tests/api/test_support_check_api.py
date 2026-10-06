"""Part 5: the judge runs after a good draft. Spec ids are those of p5-support-check."""

import json

from conftest import call_count, draft_row
from test_draft_api import Q1_REPLY, FakeDrafter, db_rows, failed, make_client, ok, reply_json

Q3_ANSWER = "Email support is available Monday to Friday, 09:00 to 17:00 UTC."
Q3_REPLY = reply_json(answer=Q3_ANSWER, citations=["SUPPORT-v1:p1"])
SUPPORTS = json.dumps({"result": "supports", "reason": "The passage states the hours."})
SUPPORT_TEXT = (
    "Email support is available Monday to Friday, 09:00 to 17:00 UTC. Live chat is not offered."
)


def test_a_good_q3_draft_asks_the_judge_once_and_saves_both_calls(tmp_path):
    # spec: 1.1-a
    # GIVEN the real Seed; a fake Drafter whose Q3 draft is supported and whose judge says supports
    drafter = FakeDrafter(ok(Q3_REPLY), judge_replies=[ok(SUPPORTS)])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client sends POST /api/questions/Q3/draft
        response = client.post("/api/questions/Q3/draft")

    # THEN status draft, no warnings, the draft actions; one judge call whose user text holds the
    # answer and the passage text; 2 model calls; the draft row points at the first one
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["answer"] == Q3_ANSWER
    assert body["warnings"] == []
    assert body["allowed_actions"] == ["edit", "approve", "leave_open"]
    assert len(drafter.prompts) == 1
    [judge_prompt] = drafter.judge_prompts
    assert Q3_ANSWER in judge_prompt.user
    assert SUPPORT_TEXT in judge_prompt.user
    calls = db_rows(tmp_path, "model_call")
    assert len(calls) == 2
    assert json.loads(calls[1]["prompt"])["user"] == judge_prompt.user
    assert calls[1]["raw_response"] == SUPPORTS
    assert draft_row(tmp_path, "Q3")["model_call_id"] == calls[0]["id"]


def test_the_judge_prompt_holds_only_the_cited_passage(tmp_path):
    # spec: 1.1-b
    # GIVEN the real Seed; a fake Drafter that gives a supported Q1 draft citing EXPORT-v2:p1
    drafter = FakeDrafter(ok(Q1_REPLY))
    with make_client(tmp_path, drafter) as client:
        # WHEN the client sends POST /api/questions/Q1/draft
        client.post("/api/questions/Q1/draft")

    # THEN the judge text holds EXPORT-v2:p1 and neither EXPORT-v1:p1 nor SUPPORT-v1:p1
    [judge_prompt] = drafter.judge_prompts
    assert "[EXPORT-v2:p1]" in judge_prompt.user
    assert "CSV exports are available on every plan." not in judge_prompt.user
    assert "SUPPORT-v1:p1" not in judge_prompt.user
    assert SUPPORT_TEXT not in judge_prompt.user
    assert judge_prompt.passage_ids == ["EXPORT-v2:p1"]
    assert "Question: " in judge_prompt.user and "No, paid plans only." in judge_prompt.user


def test_an_unresolved_draft_makes_one_call_and_no_judge_call(tmp_path):
    # spec: 1.2-a, 1.2-b
    # GIVEN a Q2 reply not_documented, and a Q3 reply that cites BILLING-v9:p1 (not sent)
    drafter = FakeDrafter(
        ok(reply_json("not_documented", citations=())),
        ok(reply_json(citations=["BILLING-v9:p1"])),
    )
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for both drafts
        q2 = client.post("/api/questions/Q2/draft").json()
        q3 = client.post("/api/questions/Q3/draft").json()

    # THEN both are unresolved, each has 1 model call, and the Drafter got no judge call
    assert q2["status"] == "unresolved"
    assert q3["status"] == "unresolved"
    assert [w["kind"] for w in q3["warnings"]] == ["citation_not_found"]
    assert call_count(tmp_path, "Q2") == 1
    assert call_count(tmp_path, "Q3") == 1
    assert drafter.judge_prompts == []


def test_an_error_draft_makes_no_judge_call(tmp_path):
    # spec: 1.2
    # GIVEN the Drafter fails for Q3
    drafter = FakeDrafter(failed("Model call failed: timeout."))
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN status error, 1 model call, no judge call
    assert body["status"] == "error"
    assert call_count(tmp_path, "Q3") == 1
    assert drafter.judge_prompts == []


def test_edit_approve_and_a_repeated_ask_make_no_drafter_call(tmp_path):
    # spec: 1.3-a
    # GIVEN as 1.1-a, and Q3 was drafted
    drafter = FakeDrafter(ok(Q3_REPLY), judge_replies=[ok(SUPPORTS)])
    with make_client(tmp_path, drafter) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN the client edits, approves, and asks for the draft again
        edit = {"answer": "Email support is open on weekdays, 09:00 to 17:00 UTC."}
        assert client.put("/api/questions/Q3/draft", json=edit).status_code == 200
        assert client.post("/api/questions/Q3/approve", json={"approver": "Anna"}).status_code == 200
        again = client.post("/api/questions/Q3/draft")

    # THEN the last call gives the approved view; Q3 still has 2 model calls; the Drafter got one
    # draft call and one judge call in all
    assert again.status_code == 200
    assert again.json()["status"] == "approved"
    assert call_count(tmp_path, "Q3") == 2
    assert len(drafter.prompts) == 1
    assert len(drafter.judge_prompts) == 1


def test_a_judge_failure_is_saved_and_changes_nothing_yet(tmp_path):
    # spec: 1.1, 2.2 (the warning comes in ticket 4)
    # GIVEN the judge times out
    judge_error = failed("Model call failed: timeout.")
    drafter = FakeDrafter(ok(Q3_REPLY), judge_replies=[judge_error])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN the draft is a normal draft; the second model call keeps the error and no raw reply
    assert body["status"] == "draft"
    assert body["warnings"] == []
    first, second = db_rows(tmp_path, "model_call")
    assert second["error"] == "Model call failed: timeout."
    assert second["raw_response"] is None
    assert first["error"] is None


def test_a_judge_reply_that_is_not_valid_is_saved_with_its_raw_text_and_an_error(tmp_path):
    # spec: 2.2-b
    # GIVEN the judge replies with text that is not a Support reply
    drafter = FakeDrafter(ok(Q3_REPLY), judge_replies=[ok("not json")])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN the draft is a normal draft; the second call keeps the raw text and the error
    assert body["status"] == "draft"
    _, second = db_rows(tmp_path, "model_call")
    assert second["raw_response"] == "not json"
    assert second["error"] == "Model reply was not valid."

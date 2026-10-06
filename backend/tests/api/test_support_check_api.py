"""Part 5: the judge runs after a good draft. Spec ids are those of p5-support-check."""

import json

from conftest import REPLAY_PATH, call_count, draft_row
from conftest import make_client as replay_client
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


# Q10 comes in ticket 5. Until then Q1 stands in for it: its draft cites EXPORT-v2:p1, which
# replaces EXPORT-v1:p1, so the view also holds a `superseded` warning.
CONTRADICTS = json.dumps(
    {"result": "contradicts", "reason": "The passage says free-plan users cannot export CSV."}
)
UNCLEAR = json.dumps({"result": "unclear", "reason": "The passage does not name the plan."})
LYING = reply_json(answer="Yes. Free-plan users can export CSV.", citations=["EXPORT-v2:p1"])
ACTIONS = ["edit", "approve", "leave_open"]


def warning_kinds(body: dict) -> list[str]:
    return [w["kind"] for w in body["warnings"]]


def test_a_contradicting_judge_adds_one_warning_and_keeps_the_draft_status(tmp_path):
    # spec: 2.1-a
    # GIVEN a fake Drafter whose Q1 draft cites EXPORT-v2:p1 and whose judge says contradicts
    drafter = FakeDrafter(ok(LYING), judge_replies=[ok(CONTRADICTS)])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client sends POST /api/questions/Q1/draft
        response = client.post("/api/questions/Q1/draft")

    # THEN status draft; kinds support_check then superseded; the exact message; the draft actions;
    # the draft row holds one support_check warning and no superseded warning
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["answer"] == "Yes. Free-plan users can export CSV."
    assert warning_kinds(body) == ["support_check", "superseded"]
    assert body["warnings"][0]["message"] == (
        "Support check (model draft): the cited passages contradict this answer. "
        "The passage says free-plan users cannot export CSV."
    )
    assert body["allowed_actions"] == ACTIONS
    saved = json.loads(draft_row(tmp_path, "Q1")["warnings"])
    assert [w["kind"] for w in saved] == ["support_check"]


def test_an_unclear_judge_gives_the_do_not_clearly_support_message(tmp_path):
    # spec: 2.1-c
    # GIVEN as 2.1-a, but the judge says unclear
    drafter = FakeDrafter(ok(LYING), judge_replies=[ok(UNCLEAR)])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client sends POST /api/questions/Q1/draft
        body = client.post("/api/questions/Q1/draft").json()

    # THEN the message is the unclear one and the status is draft
    assert body["status"] == "draft"
    assert body["warnings"][0]["kind"] == "support_check"
    assert body["warnings"][0]["message"] == (
        "Support check (model draft): the cited passages do not clearly support this answer. "
        "The passage does not name the plan."
    )


def test_a_judge_timeout_gives_a_failed_warning_and_approve_still_works(tmp_path):
    # spec: 2.2-a
    # GIVEN as 2.1-a, but the judge call returns the timeout error
    drafter = FakeDrafter(ok(LYING), judge_replies=[failed("Model call failed: timeout.")])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for a draft, then approves it
        body = client.post("/api/questions/Q1/draft").json()
        approved = client.post("/api/questions/Q1/approve", json={"approver": "Anna"})

    # THEN one support_check_failed warning with that error; the second call keeps the error and no
    # raw reply; the actions include approve; the approve call gives status approved
    assert body["status"] == "draft"
    support = [w for w in body["warnings"] if w["kind"].startswith("support_check")]
    assert [w["kind"] for w in support] == ["support_check_failed"]
    assert support[0]["message"] == (
        "Support check (model draft): the check did not run. Model call failed: timeout."
    )
    assert "approve" in body["allowed_actions"]
    _, second = db_rows(tmp_path, "model_call")
    assert second["error"] == "Model call failed: timeout."
    assert second["raw_response"] is None
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_a_judge_reply_that_is_not_valid_gives_a_failed_warning_and_keeps_the_raw_text(tmp_path):
    # spec: 2.2-b
    # GIVEN the judge replies with text that is not a Support reply
    drafter = FakeDrafter(ok(Q3_REPLY), judge_replies=[ok("not json")])
    with make_client(tmp_path, drafter) as client:
        # WHEN the client asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN the message holds the short error; the second call keeps the raw text and the error
    assert body["status"] == "draft"
    assert warning_kinds(body) == ["support_check_failed"]
    assert body["warnings"][0]["message"] == (
        "Support check (model draft): the check did not run. Model reply was not valid."
    )
    _, second = db_rows(tmp_path, "model_call")
    assert second["raw_response"] == "not json"
    assert second["error"] == "Model reply was not valid."


def test_a_replay_file_with_no_judge_entry_gives_a_failed_warning(tmp_path):
    # spec: 2.2-c
    # GIVEN MODEL_MODE empty; a Replay file with the draft entries and no judge entries
    entries = [
        e for e in json.loads(REPLAY_PATH.read_text()) if '"result"' not in (e.get("raw_response") or "")
    ]
    replay_path = tmp_path / "no-judge.json"
    replay_path.write_text(json.dumps(entries))
    with replay_client(tmp_path, replay_path) as client:
        # WHEN the client asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN status draft; the message says the check did not run, with the replay error
    assert body["status"] == "draft"
    assert warning_kinds(body) == ["support_check_failed"]
    assert body["warnings"][0]["message"] == (
        "Support check (model draft): the check did not run. No saved response for this input."
    )


def test_the_support_warning_stays_after_an_edit_and_a_restart(tmp_path):
    # spec: 2.3-a
    # GIVEN a fake Drafter as 2.1-a; Q1 was drafted
    drafter = FakeDrafter(ok(LYING), judge_replies=[ok(CONTRADICTS)])
    with make_client(tmp_path, drafter) as client:
        client.post("/api/questions/Q1/draft")

        # WHEN the client edits the answer, and the app starts again on the same Database
        answer = {"answer": "No. Free plans cannot export CSV."}
        assert client.put("/api/questions/Q1/draft", json=answer).status_code == 200
    with make_client(tmp_path, FakeDrafter()) as client:
        body = client.get("/api/questions/Q1").json()

    # THEN status draft, edited, the support_check warning is still listed, 2 model calls
    assert body["status"] == "draft"
    assert body["edited"] is True
    assert "support_check" in warning_kinds(body)
    assert call_count(tmp_path, "Q1") == 2
    assert len(drafter.judge_prompts) == 1

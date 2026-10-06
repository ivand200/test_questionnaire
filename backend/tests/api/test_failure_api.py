import json

import pytest

from conftest import ALL, make_client, model_calls
from qws.config import REPLAY_PATH

TIMEOUT = "Model call failed: timeout."


def q9_entry(entries: list[dict]) -> dict:
    [entry] = [e for e in entries if e.get("label") == "simulated"]
    return entry


def test_the_demo_question_q9_is_listed_last_and_there_are_no_load_issues(tmp_path):
    # spec: 3.1-a
    # GIVEN the real Seed and the Demo file with Q9
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/questions
        body = client.get("/api/questions").json()
        issues = client.get("/api/load-issues").json()

    # THEN 9 items Q1 to Q9 in this order; Q9 has topic support and status new; no load issues
    assert [q["id"] for q in body] == ALL
    assert body[8]["topic"] == "support"
    assert body[8]["status"] == "new"
    assert issues == []


def test_asking_q9_in_replay_mode_gives_a_simulated_error(tmp_path):
    # spec: 3.2-a
    # GIVEN MODEL_MODE empty; the committed Replay file has a Simulated entry for Q9
    with make_client(tmp_path) as client:
        # WHEN the user asks for a draft of Q9
        body = client.post("/api/questions/Q9/draft").json()

    # THEN status error with the message; no answer; retry allowed; one simulated model call
    assert body["status"] == "error"
    assert body["error"] == TIMEOUT
    assert body["answer"] is None
    assert body["allowed_actions"] == ["retry"]
    [(label, raw, error, input_tokens, output_tokens, _)] = model_calls(tmp_path, "Q9")
    assert (label, raw, error, input_tokens, output_tokens) == (
        "simulated", None, TIMEOUT, None, None,
    )


@pytest.mark.parametrize("fields", [{"raw_response": "{}", "error": TIMEOUT}, {}])
def test_a_replay_entry_with_both_or_neither_of_reply_and_error_is_not_valid(tmp_path, fields):
    # spec: 3.3-a
    # GIVEN a Replay file entry for Q9 with both or neither of raw_response and error
    entry = q9_entry(json.loads(REPLAY_PATH.read_text()))
    entry.pop("error", None)
    entry.pop("raw_response", None)
    path = tmp_path / "responses.json"
    path.write_text(json.dumps([{**entry, **fields}]))
    with make_client(tmp_path, path) as client:
        # WHEN the user asks for a draft of Q9
        body = client.post("/api/questions/Q9/draft").json()

    # THEN Q9 has status error with the message "Replay file is not valid."
    assert body["status"] == "error"
    assert body["error"] == "Replay file is not valid."


def test_a_bad_replay_entry_makes_only_the_question_with_that_input_hash_not_valid(tmp_path):
    # spec: 3.3-a
    # GIVEN the committed Replay file, but the Q9 entry has both raw_response and error
    entries = json.loads(REPLAY_PATH.read_text())
    q9_entry(entries)["raw_response"] = "{}"
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(entries))
    with make_client(tmp_path, path) as client:
        # WHEN the user asks for a draft of Q3 and of Q9
        q3 = client.post("/api/questions/Q3/draft").json()
        q9 = client.post("/api/questions/Q9/draft").json()

    # THEN Q3 replays as a draft; only Q9 has the message "Replay file is not valid."
    assert q3["status"] == "draft"
    assert q9["status"] == "error"
    assert q9["error"] == "Replay file is not valid."


def test_the_label_is_cached_for_q3_simulated_for_q9_and_null_for_a_question_with_no_draft(tmp_path):
    # spec: 3.4-a
    # GIVEN Q3 has a draft from the Replay file; Q9 has status error; Q2 is new
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q3/draft")
        client.post("/api/questions/Q9/draft")

        # WHEN a client reads Q3, Q9 and Q2
        labels = {i: client.get(f"/api/questions/{i}").json()["label"] for i in ("Q3", "Q9", "Q2")}

    # THEN label is cached, simulated, null
    assert labels == {"Q3": "cached", "Q9": "simulated", "Q2": None}


def test_retry_on_q9_adds_a_second_simulated_call_and_keeps_the_first(tmp_path):
    # spec: 3.5-a
    # GIVEN Q9 has status error and one model call
    with make_client(tmp_path) as client:
        client.post("/api/questions/Q9/draft")
        [first] = model_calls(tmp_path, "Q9")

        # WHEN the client sends POST /api/questions/Q9/draft
        body = client.post("/api/questions/Q9/draft").json()

    # THEN 2 model calls, both simulated; the first is unchanged; Q9 is still error with retry
    calls = model_calls(tmp_path, "Q9")
    assert len(calls) == 2
    assert [c[0] for c in calls] == ["simulated", "simulated"]
    assert calls[0] == first
    assert body["status"] == "error"
    assert body["allowed_actions"] == ["retry"]


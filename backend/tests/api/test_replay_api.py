import json
import sqlite3
from pathlib import Path

from conftest import ALL, call_count, make_client
from qws.adapters.replay_drafter import ReplayDrafter
from qws.adapters.replay_file import read_entries
from qws.config import REPLAY_PATH, drafter_config, open_store
from qws.core import rules
from qws.core.models import Prompt

SUPPORT_EXCERPT = (
    "Email support is available Monday to Friday, 09:00 to 17:00 UTC. Live chat is not offered."
)


def empty_replay_file(tmp_path: Path) -> Path:
    path = tmp_path / "empty-responses.json"
    path.write_text("[]")
    return path


def test_replay_gives_the_q3_draft_from_the_committed_file_with_no_key(tmp_path):
    # spec: 4.1-a
    # GIVEN MODEL_MODE empty, no OPENAI_API_KEY, the committed Replay file has the Q3 entry
    with make_client(tmp_path) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status draft, cites SUPPORT-v1:p1; the model call is cached with no token counts
    assert body["status"] == "draft"
    assert [c["passage_id"] for c in body["citations"]] == ["SUPPORT-v1:p1"]
    assert body["citations"][0]["excerpt"] == SUPPORT_EXCERPT
    conn = sqlite3.connect(tmp_path / "test.db")
    [draft_call, judge_call] = conn.execute(
        "SELECT label, input_tokens, output_tokens, error FROM model_call ORDER BY id"
    ).fetchall()
    conn.close()
    assert draft_call == ("cached", None, None, None)
    # the committed file holds the judge reply too
    assert judge_call == ("cached", None, None, None)


def test_replay_with_no_entry_gives_error_and_no_exception(tmp_path, monkeypatch):
    # spec: 4.2-a
    # GIVEN MODEL_MODE is replay; the Replay file is empty, so it has no entry for Q4
    monkeypatch.setenv("MODEL_MODE", "replay")
    with make_client(tmp_path, empty_replay_file(tmp_path)) as client:
        # WHEN the user asks for a draft of Q4
        response = client.post("/api/questions/Q4/draft")

    # THEN Q4 has status error with the message; no exception reaches the client
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == "No saved response for this input."
    assert body["allowed_actions"] == ["retry"]


def test_after_a_replay_error_the_other_questions_keep_their_status(tmp_path):
    # spec: 4.2-b
    # GIVEN as 4.2-a
    with make_client(tmp_path, empty_replay_file(tmp_path)) as client:
        # WHEN the same request is made
        client.post("/api/questions/Q4/draft")
        statuses = {q["id"]: q["status"] for q in client.get("/api/questions").json()}

    # THEN Q3 and Q5 to Q8 keep their status
    assert statuses["Q4"] == "error"
    assert {statuses[i] for i in ("Q1", "Q2", "Q3", "Q5", "Q6", "Q7", "Q8")} == {"new"}


def test_changing_the_system_prompt_changes_the_input_hash_and_replay_gives_the_error(tmp_path):
    # spec: 4.5-a
    # GIVEN the Q3 input hash h1 (the committed entry)
    store, _ = open_store(tmp_path / "test.db")
    config = drafter_config()
    passages = rules.current_passages(store.list_documents(), store.list_passages())
    q3 = store.get_question("Q3")
    h1 = rules.build_prompt(q3, passages, config.model, config.settings)
    drafter = ReplayDrafter(config.model, config.settings, REPLAY_PATH)
    assert drafter.draft(h1).error is None

    # WHEN one word of the system prompt changes
    system = rules.SYSTEM_PROMPT.replace("Never", "Always")
    changed = rules.build_prompt(q3, passages, config.model, config.settings, system=system)

    # THEN the input hash is not h1; replay mode gives the error of 4.2-a
    assert changed.input_hash != h1.input_hash
    assert drafter.draft(changed).error == "No saved response for this input."


def test_the_committed_replay_file_has_one_entry_for_each_of_the_10_questions(tmp_path):
    # spec: 5.3-a
    # GIVEN the committed Replay file and the 10 questions
    store, _ = open_store(tmp_path / "test.db")
    config = drafter_config()
    passages = rules.current_passages(store.list_documents(), store.list_passages())
    hashes = [e.input_hash for e in read_entries(REPLAY_PATH)]

    # WHEN the Backend builds the prompt of each
    built = [
        rules.build_prompt(q, passages, config.model, config.settings).input_hash
        for q in map(store.get_question, ALL)
    ]

    # THEN each of the 10 input hashes has one entry in the file
    assert [hashes.count(h) for h in built] == [1] * 10


def test_replay_gives_the_expected_q1_q2_and_q3_results(tmp_path):
    # spec: 5.4-a
    # GIVEN the committed Replay file; expected-seed-results.json says Q1 cites EXPORT-v2:p1,
    # Q2 is unresolved with no citation, Q3 cites SUPPORT-v1:p1
    with make_client(tmp_path) as client:
        # WHEN the Backend asks Q1, Q2 and Q3 in replay mode
        q1, q2, q3 = (client.post(f"/api/questions/{i}/draft").json() for i in ("Q1", "Q2", "Q3"))

    # THEN Q1 is a draft citing only EXPORT-v2:p1; Q2 is unresolved with no citation; Q3 cites SUPPORT-v1:p1
    assert q1["status"] == "draft"
    assert [c["passage_id"] for c in q1["citations"]] == ["EXPORT-v2:p1"]
    assert q2["status"] == "unresolved"
    assert q2["citations"] == []
    assert q2["owner"] == "Product reviewer"
    assert q3["status"] == "draft"
    assert [c["passage_id"] for c in q3["citations"]] == ["SUPPORT-v1:p1"]


def test_run_all_in_replay_mode_with_no_key_shows_every_demo_case(tmp_path):
    # spec: 4.1-a, 3.5-a
    # GIVEN MODEL_MODE empty, no key, the committed Replay file; all 10 questions are new
    with make_client(tmp_path) as client:
        # WHEN the client sends POST /api/questionnaire/run, then reads Q1 to Q10
        response = client.post("/api/questionnaire/run")
        found = {i: client.get(f"/api/questions/{i}").json() for i in ALL}

    # THEN asked is Q1 to Q10; no support_check_failed warning anywhere; Q3 has no support_check
    # warning and Q10 has one; Q2 is unresolved with 1 model call; Q9 is error with label
    # simulated; every other question is draft
    assert response.json() == {"asked": ALL}
    kinds = {i: [w["kind"] for w in found[i]["warnings"]] for i in ALL}
    assert not [i for i in ALL if "support_check_failed" in kinds[i]]
    assert "support_check" not in kinds["Q3"]
    assert kinds["Q10"].count("support_check") == 1
    assert found["Q2"]["status"] == "unresolved"
    assert call_count(tmp_path, "Q2") == 1
    assert found["Q9"]["status"] == "error"
    assert found["Q9"]["label"] == "simulated"
    assert [i for i in ALL if found[i]["status"] == "draft"] == [
        i for i in ALL if i not in ("Q2", "Q9")
    ]


def replay_entry(label: str, raw_response: str | None, error: str | None) -> dict:
    return {
        "input_hash": "h1", "label": label, "model": "m1", "settings": {"temperature": 0},
        "raw_response": raw_response, "error": error, "recorded_at": "2026-10-07T00:00:00+00:00",
    }


def lookup(tmp_path: Path, entry: dict):
    path = tmp_path / "responses.json"
    path.write_text(json.dumps([{k: v for k, v in entry.items() if v is not None}]))
    prompt = Prompt(
        system="s", user="u", model="m1", settings={"temperature": 0}, passage_ids=[],
        input_hash="h1",
    )
    return ReplayDrafter("m1", {"temperature": 0}, path).draft(prompt)


def test_a_simulated_entry_with_a_raw_response_gives_a_simulated_reply(tmp_path):
    # spec: 3.3-a
    # GIVEN a Replay file entry with label simulated, a raw response and no error
    entry = replay_entry("simulated", '{"answer": "Yes."}', None)

    # WHEN the ReplayDrafter looks up its input hash
    reply = lookup(tmp_path, entry)

    # THEN the reply has label simulated, that raw reply and no error
    assert (reply.label, reply.raw_reply, reply.error) == ("simulated", '{"answer": "Yes."}', None)


def test_a_simulated_entry_with_a_raw_response_and_an_error_is_not_valid(tmp_path):
    # spec: 3.3-b
    # GIVEN a Replay file entry with label simulated, a raw response and an error
    entry = replay_entry("simulated", '{"answer": "Yes."}', "Model call failed: timeout.")

    # WHEN the ReplayDrafter looks up its input hash
    reply = lookup(tmp_path, entry)

    # THEN the reply has the error "Replay file is not valid."
    assert reply.error == "Replay file is not valid."
    assert reply.raw_reply is None

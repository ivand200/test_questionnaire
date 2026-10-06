import json
import sqlite3
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.simulated_drafter import LYING_DRAFT, SimulatedDrafter
from qws.adapters.store import Store
from qws.config import MODEL_SETTINGS, SEED_PATH, open_store
from qws.services import seed_loader
from qws.services.draft_service import DrafterConfig
from qws.core.rules import SUPPORT_SYSTEM_PROMPT
from qws.services.recorder import RECORDING_LIST, SIMULATED_LIST, Recorder

KEY = "secret-key-123"
RAW = json.dumps(
    {"answer": "Monday to Friday, 09:00-17:00 UTC", "verdict": "supported", "citations": ["SUPPORT-v1:p1"]}
)


JUDGE_RAW = json.dumps({"result": "supports", "reason": "The passage states the hours."})
CONTRADICTS = json.dumps(
    {"result": "contradicts", "reason": "The passage says free-plan users cannot export CSV."}
)


def answer(messages, info):
    """A fake model: the judge prompt gets a Support reply, the draft prompt gets a draft reply."""
    judging = info.instructions == SUPPORT_SYSTEM_PROMPT
    return ModelResponse(parts=[TextPart(JUDGE_RAW if judging else RAW)])


def make_recorder(
    tmp_path: Path, model: FunctionModel | None = None
) -> tuple[Recorder, RealDrafter, Store]:
    store = Store(tmp_path / "test.db")
    store.init_schema()
    seed_loader.load(json.loads(SEED_PATH.read_text()), store)
    drafter = RealDrafter("m1", KEY, MODEL_SETTINGS, model=model or FunctionModel(answer))
    return Recorder(store, DrafterConfig("m1", MODEL_SETTINGS)), drafter, store


def test_record_writes_a_draft_and_a_judge_entry_for_q3_and_no_key(tmp_path):
    # spec: 3.1-a
    # GIVEN a developer machine with a key and a fake model that answers the draft and judge prompts
    recorder, drafter, _ = make_recorder(tmp_path)
    path = tmp_path / "replay" / "responses.json"

    # WHEN the Recorder records Q3
    failures = recorder.record(["Q3"], drafter, path)

    # THEN no failures; 2 real entries with different hashes and one raw response each; no key
    assert failures == []
    draft_entry, judge_entry = json.loads(path.read_text())
    for entry in (draft_entry, judge_entry):
        assert set(entry) == {
            "input_hash", "label", "model", "settings", "raw_response", "recorded_at"
        }
        assert entry["label"] == "real"
        assert entry["model"] == "m1"
    assert draft_entry["input_hash"] != judge_entry["input_hash"]
    assert draft_entry["raw_response"] == RAW
    assert judge_entry["raw_response"] == JUDGE_RAW
    assert KEY not in path.read_text()

    # AND the Database has 2 model calls for Q3
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        count = conn.execute("SELECT COUNT(*) FROM model_call WHERE question_id = 'Q3'").fetchone()[0]
    finally:
        conn.close()
    assert count == 2


def test_a_judge_timeout_is_reported_and_only_the_draft_entry_is_kept(tmp_path):
    # spec: 3.4-a
    # GIVEN a fake model that answers the draft prompt and times out on the judge prompt
    def draft_then_timeout(messages, info):
        if info.instructions == SUPPORT_SYSTEM_PROMPT:
            raise TimeoutError("slow")
        return ModelResponse(parts=[TextPart(RAW)])

    recorder, drafter, _ = make_recorder(tmp_path, FunctionModel(draft_then_timeout))
    path = tmp_path / "responses.json"

    # WHEN the Recorder records Q3
    failures = recorder.record(["Q3"], drafter, path)

    # THEN the judge failure is reported and the file has only the draft entry
    assert failures == ["Q3: judge: Model call failed: timeout."]
    [entry] = json.loads(path.read_text())
    assert entry["raw_response"] == RAW
def test_recording_the_same_input_twice_keeps_one_entry(tmp_path):
    # spec: 4.4-b
    # GIVEN the Replay file already has the Q3 entry for this input hash
    recorder, drafter, _ = make_recorder(tmp_path)
    path = tmp_path / "responses.json"
    recorder.record(["Q3"], drafter, path)

    # WHEN the Recorder runs again with a fake model
    recorder.record(["Q3"], drafter, path)

    # THEN the file still has one entry per hash (the draft and the judge)
    entries = json.loads(path.read_text())
    assert len(entries) == 2


def test_a_failed_call_adds_no_entry_and_is_reported(tmp_path):
    # GIVEN a model that fails
    def fails(messages, info):
        raise TimeoutError("slow")

    recorder, _, _ = make_recorder(tmp_path)
    drafter = RealDrafter("m1", KEY, MODEL_SETTINGS, model=FunctionModel(fails))
    path = tmp_path / "responses.json"

    # WHEN the Recorder runs
    failures = recorder.record(["Q3"], drafter, path)

    # THEN the failure is reported and the file is not created
    assert failures == ["Q3: Model call failed: timeout."]
    assert not path.exists()


def test_the_recorder_writes_a_simulated_entry_for_q9_and_never_asks_the_real_model(tmp_path):
    # spec: 5.2-a
    # GIVEN the Seed and the Demo file; no model is built, so none can be asked
    store, _ = open_store(tmp_path / "test.db")
    recorder = Recorder(store, DrafterConfig("m1", MODEL_SETTINGS))
    path = tmp_path / "responses.json"

    # WHEN the Recorder runs with Q9 through SimulatedDrafter
    failures = recorder.record(["Q9"], SimulatedDrafter("m1", MODEL_SETTINGS), path)

    # THEN the file has one entry for Q9 with label simulated, the error, and no raw_response
    assert failures == []
    [entry] = json.loads(path.read_text())
    assert entry["label"] == "simulated"
    assert entry["error"] == "Model call failed: timeout."
    assert "raw_response" not in entry


def test_the_recorder_writes_q9_q10_and_the_q10_judge_entry_and_asks_no_draft_prompt(tmp_path):
    # spec: 3.2-a
    # GIVEN a fake model that answers only judge prompts with `contradicts`
    prompts: list[str | None] = []

    def judge_only(messages, info):
        prompts.append(info.instructions)
        assert info.instructions == SUPPORT_SYSTEM_PROMPT, "a draft prompt reached the model"
        return ModelResponse(parts=[TextPart(CONTRADICTS)])

    store, _ = open_store(tmp_path / "test.db")
    recorder = Recorder(store, DrafterConfig("m1", MODEL_SETTINGS))
    judge = RealDrafter("m1", KEY, MODEL_SETTINGS, model=FunctionModel(judge_only))
    path = tmp_path / "responses.json"
    assert SIMULATED_LIST == ["Q9", "Q10"]

    # WHEN the Recorder records Q9 as simulated and Q10 as the Lying draft with that model as judge
    failures = recorder.record(SIMULATED_LIST, SimulatedDrafter("m1", MODEL_SETTINGS, judge), path)

    # THEN the file has the Q9 timeout entry, a Q10 simulated draft entry with the Lying draft and
    # no error, and a Q10 real judge entry; the fake model got one prompt, the judge prompt
    assert failures == []
    q9, q10_draft, q10_judge = json.loads(path.read_text())
    assert q9["label"] == "simulated"
    assert q9["error"] == "Model call failed: timeout."
    assert "raw_response" not in q9
    assert q10_draft["label"] == "simulated"
    assert q10_draft["raw_response"] == LYING_DRAFT
    assert "error" not in q10_draft
    assert q10_judge["label"] == "real"
    assert q10_judge["raw_response"] == CONTRADICTS
    assert len({q9["input_hash"], q10_draft["input_hash"], q10_judge["input_hash"]}) == 3
    assert prompts == [SUPPORT_SYSTEM_PROMPT]


def test_a_failed_simulated_judge_is_reported_and_gets_no_entry(tmp_path):
    # spec: 3.4
    # GIVEN the SimulatedDrafter with no judge Drafter, so its judge call fails with the timeout
    store, _ = open_store(tmp_path / "test.db")
    recorder = Recorder(store, DrafterConfig("m1", MODEL_SETTINGS))
    path = tmp_path / "responses.json"

    # WHEN the Recorder records Q10
    failures = recorder.record(["Q10"], SimulatedDrafter("m1", MODEL_SETTINGS), path)

    # THEN the judge failure is reported and the file has only the simulated draft entry
    assert failures == ["Q10: judge: Model call failed: timeout."]
    [entry] = json.loads(path.read_text())
    assert entry["label"] == "simulated"
    assert entry["raw_response"] == LYING_DRAFT


def test_the_recording_list_is_q1_to_q8_and_a_second_run_keeps_one_entry_per_hash(tmp_path):
    # spec: 5.1-a
    # GIVEN a fake model that replies for each question; an empty Replay file
    recorder, drafter, _ = make_recorder(tmp_path)
    path = tmp_path / "responses.json"
    assert RECORDING_LIST == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]

    # WHEN the Recorder runs the recording list
    failures = recorder.record(RECORDING_LIST, drafter, path)

    # THEN no failures; the draft entries have 8 different input hashes
    assert failures == []
    entries = json.loads(path.read_text())
    assert len({e["input_hash"] for e in entries}) == len(entries)
    assert len(entries) >= 8

    # AND a second run keeps the same number of entries
    recorder.record(RECORDING_LIST, drafter, path)
    assert len(json.loads(path.read_text())) == len(entries)

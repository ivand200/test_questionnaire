import json
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.simulated_drafter import SimulatedDrafter
from qws.adapters.store import Store
from qws.config import MODEL_SETTINGS, SEED_PATH, open_store
from qws.services import seed_loader
from qws.services.draft_service import DrafterConfig
from qws.services.recorder import RECORDING_LIST, Recorder

KEY = "secret-key-123"
RAW = json.dumps(
    {"answer": "Monday to Friday, 09:00-17:00 UTC", "verdict": "supported", "citations": ["SUPPORT-v1:p1"]}
)


def make_recorder(tmp_path: Path) -> tuple[Recorder, RealDrafter]:
    store = Store(tmp_path / "test.db")
    store.init_schema()
    seed_loader.load(json.loads(SEED_PATH.read_text()), store)
    model = FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart(RAW)]))
    drafter = RealDrafter("m1", KEY, MODEL_SETTINGS, model=model)
    return Recorder(store, DrafterConfig("m1", MODEL_SETTINGS)), drafter


def test_record_writes_one_q3_entry_with_its_fields_and_no_key(tmp_path):
    # spec: 4.4-a
    # GIVEN a developer machine with a key and a model (a fake model stands in for the real one)
    recorder, drafter = make_recorder(tmp_path)
    path = tmp_path / "replay" / "responses.json"

    # WHEN the developer runs the Recorder
    failures = recorder.record(["Q3"], drafter, path)

    # THEN the file has one Q3 entry with all its fields; the file has no key value
    assert failures == []
    [entry] = json.loads(path.read_text())
    assert set(entry) == {
        "input_hash", "label", "model", "settings", "raw_response", "recorded_at"
    }
    assert entry["label"] == "real"
    assert entry["model"] == "m1"
    assert entry["raw_response"] == RAW
    assert KEY not in path.read_text()


def test_recording_the_same_input_twice_keeps_one_entry(tmp_path):
    # spec: 4.4-b
    # GIVEN the Replay file already has the Q3 entry for this input hash
    recorder, drafter = make_recorder(tmp_path)
    path = tmp_path / "responses.json"
    recorder.record(["Q3"], drafter, path)

    # WHEN the Recorder runs again with a fake model
    recorder.record(["Q3"], drafter, path)

    # THEN the file still has one entry for that hash
    entries = json.loads(path.read_text())
    assert len(entries) == 1


def test_a_failed_call_adds_no_entry_and_is_reported(tmp_path):
    # GIVEN a model that fails
    def fails(messages, info):
        raise TimeoutError("slow")

    recorder, _ = make_recorder(tmp_path)
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


def test_the_recording_list_is_q1_to_q8_and_a_second_run_keeps_one_entry_per_hash(tmp_path):
    # spec: 5.1-a
    # GIVEN a fake model that replies for each question; an empty Replay file
    recorder, drafter = make_recorder(tmp_path)
    path = tmp_path / "responses.json"
    assert RECORDING_LIST == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]

    # WHEN the Recorder runs the recording list
    failures = recorder.record(RECORDING_LIST, drafter, path)

    # THEN the file has 8 entries with 8 different input hashes
    assert failures == []
    assert len({e["input_hash"] for e in json.loads(path.read_text())}) == 8

    # AND a second run still has 8
    recorder.record(RECORDING_LIST, drafter, path)
    assert len(json.loads(path.read_text())) == 8

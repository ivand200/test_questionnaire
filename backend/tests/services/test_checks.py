import json
from pathlib import Path

import pytest

from qws.adapters.replay_file import read_entries
from qws.config import REFERENCE_PATH, REPLAY_PATH, drafter_config, open_store
from qws.core import rules
from qws.services import checks

IDS = ["C1", "C2", "C3", "C4", "C5", "C6"]


@pytest.fixture(autouse=True)
def no_model_env(monkeypatch):
    for name in ("MODEL_MODE", "MODEL_NAME", "OPENAI_API_KEY", "DB_PATH"):
        monkeypatch.delenv(name, raising=False)


def run_main(tmp_path: Path, cases: Path = REFERENCE_PATH, replay: Path = REPLAY_PATH):
    results = tmp_path / "docs" / "check-results.md"
    return checks.main(cases, replay, results), results


def lines_of(capsys) -> list[str]:
    return capsys.readouterr().out.splitlines()


def reference() -> dict:
    return json.loads(REFERENCE_PATH.read_text())


def test_the_reference_file_has_six_cases_each_with_a_source():
    # spec: 2.1-a
    # GIVEN the committed Reference file
    # WHEN a test loads it
    cases = reference()["cases"]

    # THEN 6 cases with IDs C1 to C6 in order; each source is not empty; the C3 source names both passages
    assert [c["id"] for c in cases] == IDS
    assert all(c["source"].strip() for c in cases)
    assert "EXPORT-v2:p1" in cases[2]["source"]
    assert "EXPORT-v1:p1" in cases[2]["source"]


def test_c5_expects_needs_review_no_new_model_calls_and_the_new_version():
    # spec: 2.2-a
    # GIVEN the committed Reference file
    # WHEN a test reads the expected values of C5
    expected = reference()["cases"][4]["expected"]

    # THEN needs_review, 0 new model calls and {"EXPORT-v2": 3}
    assert expected["after_bump"]["status"] == "needs_review"
    assert expected["after_bump"]["new_model_calls"] == 0
    assert expected["after_reapprove"]["source_versions"] == {"EXPORT-v2": 3}


def test_make_checks_passes_all_six_cases_and_writes_six_rows(tmp_path, capsys):
    # spec: 1.1-a
    # GIVEN the real Seed, Demo file, committed Replay file and Reference file; no MODEL_MODE or key
    # WHEN the user runs make checks
    code, results = run_main(tmp_path)

    # THEN 6 lines for C1 to C6, each PASS; exit code 0; the results file has 6 rows
    lines = lines_of(capsys)
    assert code == 0
    assert [line.split()[0] for line in lines] == IDS
    assert all(" PASS " in line for line in lines)
    rows = [l for l in results.read_text().splitlines() if l.startswith("| C") and l[3].isdigit()]
    assert len(rows) == 6


def test_make_checks_changes_neither_the_database_nor_the_replay_file(tmp_path, monkeypatch, capsys):
    # spec: 1.1-b
    # GIVEN a Database file at DB_PATH where Q1 is approved; MODEL_MODE=real with no key, so a real call would fail
    db = tmp_path / "demo.db"
    store, _ = open_store(db)
    store.save_edit("Q1", "No.")
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("MODEL_MODE", "real")
    before, replay_before = db.read_bytes(), REPLAY_PATH.read_bytes()

    # WHEN the user runs make checks
    code, _ = run_main(tmp_path)

    # THEN the file at DB_PATH has the same bytes; the Replay file is unchanged; every case still passes,
    # so no model call was real
    assert db.read_bytes() == before
    assert REPLAY_PATH.read_bytes() == replay_before
    assert code == 0, lines_of(capsys)


def replay_without_the_q3_draft(tmp_path: Path) -> Path:
    store, _ = open_store(tmp_path / "hash.db")
    config = drafter_config()
    passages = rules.current_passages(store.list_documents(), store.list_passages())
    q3 = rules.build_prompt(store.get_question("Q3"), passages, config.model, config.settings)
    entries = [e for e in read_entries(REPLAY_PATH) if e.input_hash != q3.input_hash]
    path = tmp_path / "responses.json"
    path.write_text(json.dumps([e.model_dump(exclude_none=True) for e in entries]))
    return path


def test_a_missing_q3_replay_entry_fails_c1_with_status_error(tmp_path, capsys):
    # spec: 1.2-a
    # GIVEN the Replay file has no entry for the Q3 draft prompt
    replay = replay_without_the_q3_draft(tmp_path)

    # WHEN the user runs make checks
    code, _ = run_main(tmp_path, replay=replay)

    # THEN C1 shows expected status=draft and observed status=error. C6 also fails: it asks Run all
    # and expects Q3 to be a draft, and Q3 has the same prompt. C2 to C5 pass.
    by_id = {line.split()[0]: line for line in lines_of(capsys)}
    expected, observed = by_id["C1"].split("  expected: ")[1].split("  observed: ")
    assert " FAIL " in by_id["C1"]
    assert expected.startswith("status=draft")
    assert observed.startswith("status=error")
    assert [i for i in IDS if " FAIL " in by_id[i]] == ["C1", "C6"]
    assert code == 1


def test_a_failed_case_shows_both_values_and_the_others_still_pass(tmp_path, capsys):
    # spec: 1.3-a
    # GIVEN a copy of the Reference file where C2 expects status draft
    data = reference()
    data["cases"][1]["expected"]["status"] = "draft"
    copy = tmp_path / "cases.json"
    copy.write_text(json.dumps(data))

    # WHEN the user runs make checks with that copy
    code, results = run_main(tmp_path, cases=copy)

    # THEN C2 shows expected draft, observed unresolved and FAIL; the others PASS; exit code 1;
    # the results file lists C2 under "Failures"
    by_id = {line.split()[0]: line for line in lines_of(capsys)}
    assert " FAIL " in by_id["C2"]
    assert "expected: status=draft;" in by_id["C2"]
    assert "observed: status=unresolved;" in by_id["C2"]
    assert [i for i in IDS if " PASS " in by_id[i]] == ["C1", "C3", "C4", "C5", "C6"]
    assert code == 1
    failures = results.read_text().split("## Failures")[1]
    assert "C2" in failures
    assert "C1" not in failures


@pytest.mark.parametrize("text", ["not json", '{"cases": []}', '{"cases": [{"id": "C1"}]}'])
def test_a_reference_file_that_is_not_valid_gives_exit_2_and_no_results_file(tmp_path, capsys, text):
    # spec: 1.4-a
    # GIVEN the Reference file has the text "not json" (or no cases, or a case with no fields)
    bad = tmp_path / "cases.json"
    bad.write_text(text)
    results = tmp_path / "docs" / "check-results.md"
    results.parent.mkdir()
    results.write_text("old")

    # WHEN the user runs make checks
    code = checks.main(bad, REPLAY_PATH, results)

    # THEN "Reference file is not valid."; exit code 2; the results file is not changed
    assert lines_of(capsys) == ["Reference file is not valid."]
    assert code == 2
    assert results.read_text() == "old"


def test_a_missing_reference_file_gives_exit_2(tmp_path, capsys):
    # spec: 1.4-a
    # GIVEN no Reference file
    # WHEN the user runs make checks
    code, results = run_main(tmp_path, cases=tmp_path / "missing.json")

    # THEN "Reference file is not valid."; exit code 2; no results file
    assert lines_of(capsys) == ["Reference file is not valid."]
    assert code == 2
    assert not results.exists()


def test_the_results_file_has_the_date_the_header_six_rows_and_none_under_failures(tmp_path):
    # spec: 1.5-a
    # GIVEN the real files
    # WHEN the user runs make checks
    _, results = run_main(tmp_path)

    # THEN the run date, the table header, 6 rows and "None." under "Failures"
    text = results.read_text()
    assert "Run date: 20" in text
    assert "| Case | Question | Expected | Observed | Result |" in text
    assert len([l for l in text.splitlines() if l.startswith("| C") and l[3].isdigit()]) == 6
    assert text.split("## Failures")[1].strip() == "None."

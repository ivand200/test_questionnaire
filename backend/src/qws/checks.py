"""`make checks`: run the six Reference cases in replay mode and write the Check results file."""

import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter, ValidationError

from qws.adapters.replay_drafter import ReplayDrafter
from qws.api.main import create_app
from qws.config import REFERENCE_PATH, REPLAY_PATH, RESULTS_PATH, drafter_config

CASE_IDS = ["C1", "C2", "C3", "C4", "C5", "C6"]
INVALID = "Reference file is not valid."
EDIT = "No. CSV export needs a paid plan."
APPROVER = "Check runner"
MISSING = "<missing>"


class ReferenceFileInvalid(Exception):
    """The Reference file is missing or is not valid."""


class Case(BaseModel):
    id: str
    question_id: str
    name: str
    source: str
    expected: dict[str, Any]


@dataclass
class CaseResult:
    id: str
    question_id: str
    name: str
    expected: str
    observed: str
    passed: bool


Facts = dict[str, Any]


def load_cases(path: Path) -> list[Case]:
    try:
        cases = TypeAdapter(list[Case]).validate_python(json.loads(path.read_text())["cases"])
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as error:
        raise ReferenceFileInvalid(INVALID) from error
    if [c.id for c in cases] != CASE_IDS:
        raise ReferenceFileInvalid(INVALID)
    return cases


class Session:
    """One app on one Database. A second Session on the same file stands for a restart."""

    def __init__(self, client: TestClient, db_path: Path) -> None:
        self.client = client
        self._db_path = db_path

    def view(self, question_id: str) -> dict:
        return self.client.get(f"/api/questions/{question_id}").json()

    def ask(self, question_id: str) -> dict:
        return self.client.post(f"/api/questions/{question_id}/draft").json()

    def edit(self, question_id: str, answer: str) -> dict:
        return self.client.put(f"/api/questions/{question_id}/draft", json={"answer": answer}).json()

    def approve(self, question_id: str) -> dict:
        return self.client.post(
            f"/api/questions/{question_id}/approve", json={"approver": APPROVER}
        ).json()

    def bump(self, document_id: str) -> None:
        self.client.post(f"/api/documents/{document_id}/bump-version")

    def run_all(self) -> None:
        self.client.post("/api/questionnaire/run")

    def model_calls(self) -> int:
        """Read only: the count of model calls in the Database."""
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        try:
            return conn.execute("SELECT COUNT(*) FROM model_call").fetchone()[0]
        finally:
            conn.close()


@contextmanager
def session(workdir: Path, replay_path: Path) -> Iterator[Session]:
    """An app on the Database `workdir/check.db`, always in replay mode whatever MODEL_MODE says."""
    config = drafter_config()
    db_path = workdir / "check.db"
    app = create_app(
        workdir / "dist",
        db_path,
        drafter=ReplayDrafter(config.model, config.settings, replay_path),
        replay_path=replay_path,
    )
    with TestClient(app) as client:
        yield Session(client, db_path)


def facts_of(view: dict) -> Facts:
    return {
        "status": view["status"],
        "citations": [c["passage_id"] for c in view["citations"]],
        "replaced": [r["passage_id"] for r in view["replaced"]],
        "warning_kinds": [w["kind"] for w in view["warnings"]],
        "answer": view["answer"],
        "owner": view["owner"],
        "allowed_actions": view["allowed_actions"],
        "error": view["error"],
        "label": view["label"],
        "approved": view["approved"] is not None,
        "source_versions": view["approved"]["source_versions"] if view["approved"] else None,
    }


def first_draft(workdir: Path, replay_path: Path, question_id: str) -> Facts:
    with session(workdir, replay_path) as s:
        return facts_of(s.ask(question_id))


def case_c4(workdir: Path, replay_path: Path, question_id: str) -> Facts:
    with session(workdir, replay_path) as s:
        s.ask(question_id)
        after_edit = facts_of(s.edit(question_id, EDIT))
        after_approve = facts_of(s.approve(question_id))
        after_approve["answer_is_edit"] = after_approve["answer"] == EDIT
        before = s.model_calls()
        s.ask(question_id)
        return {
            "after_edit": after_edit,
            "after_approve": after_approve,
            "ask_again_new_model_calls": s.model_calls() - before,
        }


def case_c5(workdir: Path, replay_path: Path, question_id: str) -> Facts:
    with session(workdir, replay_path) as s:
        s.ask(question_id)
        s.edit(question_id, EDIT)
        s.approve(question_id)
    with session(workdir, replay_path) as s:  # a restart: a second app on the same Database
        after_restart = facts_of(s.view(question_id))
        s.bump("EXPORT-v2")
        before = s.model_calls()
        after_bump = facts_of(s.view(question_id))
        s.ask(question_id)  # not allowed on needs_review: no model call
        after_bump["new_model_calls"] = s.model_calls() - before
        after_reapprove = facts_of(s.approve(question_id))
        return {
            "after_restart": after_restart,
            "after_bump": after_bump,
            "after_reapprove": after_reapprove,
        }


def case_c6(workdir: Path, replay_path: Path, question_id: str) -> Facts:
    with session(workdir, replay_path) as s:
        facts = facts_of(s.ask(question_id))
        s.run_all()
        facts["after_run_all"] = {"q3_status": s.view("Q3")["status"]}
        return facts


FLOWS: dict[str, Callable[[Path, Path, str], Facts]] = {
    "C1": first_draft,
    "C2": first_draft,
    "C3": first_draft,
    "C4": case_c4,
    "C5": case_c5,
    "C6": case_c6,
}


def observe(expected: Any, facts: Any) -> Any:
    """The observed values in the shape of `expected`: one value for each expected key."""
    if not isinstance(expected, dict):
        return facts
    facts = facts if isinstance(facts, dict) else {}
    answer = facts.get("answer") or ""
    observed: dict[str, Any] = {}
    for key, want in expected.items():
        if key == "answer_contains":
            observed[key] = [text for text in want if text in answer]
        elif key == "answer_starts_with":
            observed[key] = answer[: len(want)]
        elif key == "warning_kinds_include":
            observed[key] = [k for k in want if k in facts.get("warning_kinds", [])]
        elif isinstance(want, dict):
            observed[key] = observe(want, facts.get(key))
        else:
            observed[key] = facts.get(key, MISSING)
    return observed


def render(value: Any) -> str:
    """`key=value; key=value`, with a nested group in braces and a list in brackets."""
    if isinstance(value, dict):
        return "; ".join(f"{k}={'{' + render(v) + '}' if isinstance(v, dict) else render(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "[" + ", ".join(render(v) for v in value) + "]"
    return str(value)


def run_case(case: Case, replay_path: Path) -> CaseResult:
    with tempfile.TemporaryDirectory() as workdir:
        try:
            facts = FLOWS[case.id](Path(workdir), replay_path, case.question_id)
            observed = observe(case.expected, facts)
        except Exception as error:  # a failed case never stops the others
            observed = {"error": f"{type(error).__name__}: {error}"}
    return CaseResult(
        case.id,
        case.question_id,
        case.name,
        render(case.expected),
        render(observed),
        observed == case.expected,
    )


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def results_text(results: list[CaseResult], today: date) -> str:
    lines = [
        "# Check results",
        "",
        f"Run date: {today.isoformat()}",
        "",
        "| Case | Question | Expected | Observed | Result |",
        "| ---- | -------- | -------- | -------- | ------ |",
    ]
    for r in results:
        verdict = "PASS" if r.passed else "FAIL"
        lines.append(
            f"| {r.id} {cell(r.name)} | {r.question_id} | {cell(r.expected)} | {cell(r.observed)} | {verdict} |"
        )
    failures = [r for r in results if not r.passed]
    lines += ["", "## Failures", ""]
    if failures:
        lines += [f"- {r.id} {r.name}: expected {r.expected}; observed {r.observed}" for r in failures]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def run(
    cases_path: Path = REFERENCE_PATH,
    replay_path: Path = REPLAY_PATH,
    results_path: Path = RESULTS_PATH,
) -> list[CaseResult]:
    """Run the Reference cases, write the Check results file, return one result per case.
    Raises ReferenceFileInvalid before anything is written."""
    cases = load_cases(cases_path)
    results = [run_case(case, replay_path) for case in cases]
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(results_text(results, date.today()))
    return results


def main(
    cases_path: Path = REFERENCE_PATH,
    replay_path: Path = REPLAY_PATH,
    results_path: Path = RESULTS_PATH,
) -> int:
    """Print one line for each case. Exit code 0 when all pass, 1 when a case fails, 2 for a bad Reference file."""
    try:
        results = run(cases_path, replay_path, results_path)
    except ReferenceFileInvalid as error:
        print(error)
        return 2
    for r in results:
        verdict = "PASS" if r.passed else "FAIL"
        print(f"{r.id} {r.question_id} {verdict}  expected: {r.expected}  observed: {r.observed}")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else REFERENCE_PATH))

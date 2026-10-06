import copy
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from qws.adapters.real_drafter import RealDrafter
from qws.api.main import create_app
from qws.config import MODEL_SETTINGS, SEED_PATH
from qws.core.models import DrafterReply, Prompt

REAL_SEED = json.loads(SEED_PATH.read_text())
SUPPORT_EXCERPT = (
    "Email support is available Monday to Friday, 09:00 to 17:00 UTC. Live chat is not offered."
)


def reply_json(verdict="supported", answer="Monday to Friday, 09:00–17:00 UTC", citations=("SUPPORT-v1:p1",)):
    return json.dumps({"answer": answer, "verdict": verdict, "citations": list(citations)})


class FakeDrafter:
    """Returns scripted replies, one per call, and keeps the prompts it was given."""

    def __init__(self, *replies: DrafterReply) -> None:
        self._replies = list(replies)
        self.prompts: list[Prompt] = []

    def draft(self, prompt: Prompt) -> DrafterReply:
        self.prompts.append(prompt)
        return self._replies.pop(0)


def ok(raw: str | None = None, **fields) -> DrafterReply:
    fields.setdefault("label", "real")
    fields.setdefault("model", "m1")
    fields.setdefault("settings", {"temperature": 0})
    return DrafterReply(raw_reply=raw if raw is not None else reply_json(), **fields)


def failed(error: str) -> DrafterReply:
    return DrafterReply(error=error, label="real", model="m1", settings={"temperature": 0})


def make_client(tmp_path: Path, drafter=None, seed: dict | None = None) -> TestClient:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed or REAL_SEED))
    return TestClient(create_app(tmp_path / "dist", tmp_path / "test.db", seed_path, drafter))


def db_rows(tmp_path: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    finally:
        conn.close()


def test_asking_for_q3_saves_a_draft_with_the_exact_passage_as_excerpt(tmp_path):
    # spec: 2.1-a
    # GIVEN the real Seed; Q3 is new; the Drafter replies supported and cites SUPPORT-v1:p1
    drafter = FakeDrafter(ok())
    with make_client(tmp_path, drafter) as client:
        # WHEN the user asks for a draft of Q3
        response = client.post("/api/questions/Q3/draft")

        # THEN Q3 has status draft with one citation and its exact excerpt; one model call
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "draft"
        assert body["answer"] == "Monday to Friday, 09:00–17:00 UTC"
        assert body["citations"] == [{"passage_id": "SUPPORT-v1:p1", "excerpt": SUPPORT_EXCERPT}]
        assert client.get("/api/questions").json()[2]["status"] == "draft"  # spec: 5.1-b
    assert len(db_rows(tmp_path, "model_call")) == 1


def test_a_question_with_status_error_can_be_asked_again(tmp_path):
    # spec: 2.1-b
    # GIVEN Q3 has status error and one failed model call
    drafter = FakeDrafter(failed("Model call failed: timeout."), ok())
    with make_client(tmp_path, drafter) as client:
        assert client.post("/api/questions/Q3/draft").json()["status"] == "error"
        first_call = db_rows(tmp_path, "model_call")[0]

        # WHEN the user asks for a draft of Q3
        response = client.post("/api/questions/Q3/draft")

    # THEN the Drafter is called once more; 2 model calls; the first is unchanged; Q3 has the new result
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    calls = db_rows(tmp_path, "model_call")
    assert len(drafter.prompts) == 2
    assert len(calls) == 2
    assert calls[0] == first_call


def test_the_prompt_for_q3_has_only_the_passages_of_current_documents(tmp_path):
    # spec: 2.2-a
    # GIVEN the real Seed
    drafter = FakeDrafter(ok())
    with make_client(tmp_path, drafter) as client:
        # WHEN the Backend builds the prompt for Q3
        client.post("/api/questions/Q3/draft")

    # THEN the passages sent are EXPORT-v2:p1, SUPPORT-v1:p1, ACCESS-v1:p1, BILLING-v1:p1 in order
    [prompt] = drafter.prompts
    assert prompt.passage_ids == ["EXPORT-v2:p1", "SUPPORT-v1:p1", "ACCESS-v1:p1", "BILLING-v1:p1"]
    assert "EXPORT-v1:p1" not in prompt.user


def test_a_newer_date_without_supersedes_does_not_remove_a_document(tmp_path):
    # spec: 2.2-b
    # GIVEN documents A (2026-01-01) and B (2026-08-01); B has no supersedes
    seed = {
        "documents": [
            {"id": "A-v1", "version": 1, "date": "2026-01-01", "status": "current",
             "passages": [{"id": "A-v1:p1", "text": "Text of A."}]},
            {"id": "B-v1", "version": 1, "date": "2026-08-01", "status": "current",
             "passages": [{"id": "B-v1:p1", "text": "Text of B."}]},
        ],
        "questions": [{"id": "Q1", "topic": "support", "text": "Anything?"}],
        "owners": {"support": "Support lead"},
    }
    drafter = FakeDrafter(ok())
    with make_client(tmp_path, drafter, seed) as client:
        # WHEN the Backend builds a prompt
        client.post("/api/questions/Q1/draft")

    # THEN the passages of A and B are both sent
    assert drafter.prompts[0].passage_ids == ["A-v1:p1", "B-v1:p1"]


def test_the_system_part_has_no_passage_text(tmp_path):
    # spec: 2.3-a
    # GIVEN the real Seed
    drafter = FakeDrafter(ok())
    with make_client(tmp_path, drafter) as client:
        # WHEN the Backend builds the prompt for Q3
        client.post("/api/questions/Q3/draft")

    # THEN the system part has no passage text; the user part has the question and each sent ID with its text
    [prompt] = drafter.prompts
    assert SUPPORT_EXCERPT not in prompt.system
    assert "SUPPORT-v1:p1" not in prompt.system
    assert "When is email support available?" in prompt.user
    assert f"[SUPPORT-v1:p1] {SUPPORT_EXCERPT}" in prompt.user


@pytest.mark.parametrize("raw", [reply_json(), reply_json("not_documented", citations=())])
def test_asking_for_a_question_with_a_draft_or_unresolved_gives_409_and_no_model_call(tmp_path, raw):
    # spec: 2.4-a
    # GIVEN Q3 has status draft (or unresolved) and 1 model call
    drafter = FakeDrafter(ok(raw))
    with make_client(tmp_path, drafter) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN a client sends POST /api/questions/Q3/draft
        response = client.post("/api/questions/Q3/draft")

    # THEN HTTP 409; the Drafter is not called; there is still 1 model call
    assert response.status_code == 409
    assert len(drafter.prompts) == 1
    assert len(db_rows(tmp_path, "model_call")) == 1


def test_a_restart_on_the_same_database_keeps_the_draft_and_the_model_call(tmp_path):
    # spec: 2.5-a
    # GIVEN Q3 has status draft with citation SUPPORT-v1:p1
    with make_client(tmp_path, FakeDrafter(ok())) as client:
        client.post("/api/questions/Q3/draft")
        before = client.get("/api/questions/Q3").json()
    calls_before = db_rows(tmp_path, "model_call")

    # WHEN the Backend restarts on the same Database
    with make_client(tmp_path, FakeDrafter()) as client:
        after = client.get("/api/questions/Q3").json()

    # THEN Q3 has status draft; the same answer, citation and excerpt; the same model call
    assert after["status"] == "draft"
    assert after == before
    assert db_rows(tmp_path, "model_call") == calls_before


def test_a_model_call_keeps_prompt_raw_reply_model_settings_label_latency_and_tokens(tmp_path):
    # spec: 2.6-a
    # GIVEN the Drafter replied for Q3 with label real, model m1, 12 input tokens
    raw = reply_json()
    drafter = FakeDrafter(
        ok(raw, settings={"temperature": 0}, latency_ms=340, input_tokens=12, output_tokens=7)
    )
    with make_client(tmp_path, drafter) as client:
        # WHEN the draft is saved
        client.post("/api/questions/Q3/draft")

    # THEN one model call row has all of it
    [call] = db_rows(tmp_path, "model_call")
    assert json.loads(call["prompt"]) == {
        "system": drafter.prompts[0].system,
        "user": drafter.prompts[0].user,
    }
    assert call["raw_response"] == raw
    assert call["model"] == "m1"
    assert json.loads(call["settings"]) == {"temperature": 0}
    assert call["label"] == "real"
    assert call["latency_ms"] == 340
    assert (call["input_tokens"], call["output_tokens"]) == (12, 7)
    assert call["input_hash"] == drafter.prompts[0].input_hash
    assert call["question_id"] == "Q3"


def test_a_citation_that_was_not_sent_gives_unresolved_and_citation_not_found(tmp_path):
    # spec: 3.1-a
    # GIVEN the Drafter replies supported, citing SUPPORT-v1:p1 and EXPORT-v1:p1 (not sent)
    drafter = FakeDrafter(ok(reply_json(citations=["SUPPORT-v1:p1", "EXPORT-v1:p1"])))
    with make_client(tmp_path, drafter) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status unresolved; one warning citation_not_found for EXPORT-v1:p1; never draft
    assert body["status"] == "unresolved"
    [warning] = body["warnings"]
    assert warning["kind"] == "citation_not_found"
    assert warning["passage_id"] == "EXPORT-v1:p1"
    assert [c["passage_id"] for c in body["citations"]] == ["SUPPORT-v1:p1"]


def test_an_empty_citation_list_gives_unresolved_and_no_citation(tmp_path):
    # spec: 3.1-b
    # GIVEN the Drafter replies supported, citations []
    with make_client(tmp_path, FakeDrafter(ok(reply_json(citations=[])))) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status unresolved; one warning no_citation
    assert body["status"] == "unresolved"
    assert [w["kind"] for w in body["warnings"]] == ["no_citation"]


def test_the_verdict_not_documented_gives_unresolved_with_no_warning(tmp_path):
    # spec: 3.2-a
    # GIVEN the Drafter replies not_documented, citations []
    raw = reply_json("not_documented", "Not in our documents.", [])
    with make_client(tmp_path, FakeDrafter(ok(raw))) as client:
        # WHEN the user asks for a draft of Q2
        body = client.post("/api/questions/Q2/draft").json()

    # THEN Q2 has status unresolved; no warning
    assert body["status"] == "unresolved"
    assert body["warnings"] == []


def test_a_raw_reply_that_is_not_valid_gives_error_and_no_answer(tmp_path):
    # spec: 3.3-a
    # GIVEN the raw reply is "not json"
    with make_client(tmp_path, FakeDrafter(ok("not json"))) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status error; the message is "Model reply was not valid."; no answer is saved
    assert body["status"] == "error"
    assert body["error"] == "Model reply was not valid."
    assert body["answer"] is None
    assert db_rows(tmp_path, "model_call")[0]["raw_response"] == "not json"


def test_real_mode_with_no_key_gives_a_short_error_without_key_or_traceback(tmp_path, monkeypatch):
    # spec: 4.3-a
    # GIVEN MODEL_MODE is real; OPENAI_API_KEY is empty
    monkeypatch.setenv("MODEL_MODE", "real")
    monkeypatch.setenv("MODEL_NAME", "some-model")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with make_client(tmp_path) as client:
        # WHEN the user asks for a draft of Q3
        response = client.post("/api/questions/Q3/draft")

    # THEN Q3 has status error; a short message; no key and no Traceback
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["error"]
    assert "Traceback" not in body["error"]


def test_a_real_drafter_that_times_out_gives_a_short_error(tmp_path):
    # spec: 4.3-b
    # GIVEN MODEL_MODE is real; the model adapter raises a timeout
    def times_out(messages, info):
        raise TimeoutError("secret-key-123 took too long")

    drafter = RealDrafter("m1", "secret-key-123", MODEL_SETTINGS, model=FunctionModel(times_out))
    with make_client(tmp_path, drafter) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN Q3 has status error; the message is "Model call failed: timeout."
    assert body["status"] == "error"
    assert body["error"] == "Model call failed: timeout."
    [call] = db_rows(tmp_path, "model_call")
    assert call["label"] == "real"


def test_a_real_drafter_returns_the_raw_reply_and_the_token_counts(tmp_path):
    # spec: 2.6-a
    # GIVEN the real adapter on a fake model that replies with a valid JSON text
    raw = reply_json()
    model = FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart(raw)]))
    drafter = RealDrafter("m1", "k", MODEL_SETTINGS, model=model)
    with make_client(tmp_path, drafter) as client:
        # WHEN the user asks for a draft of Q3
        body = client.post("/api/questions/Q3/draft").json()

    # THEN the draft cites SUPPORT-v1:p1 and the model call keeps the raw reply, label real and tokens
    assert body["status"] == "draft"
    [call] = db_rows(tmp_path, "model_call")
    assert call["raw_response"] == raw
    assert call["label"] == "real"
    assert call["input_tokens"] > 0
    assert call["output_tokens"] > 0
    assert call["latency_ms"] is not None


def test_get_question_returns_the_draft_view_with_allowed_actions(tmp_path):
    # spec: 5.2-a
    # GIVEN Q3 has status draft
    with make_client(tmp_path, FakeDrafter(ok())) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN a client sends GET /api/questions/Q3
        response = client.get("/api/questions/Q3")

    # THEN HTTP 200; the answer; one citation with its excerpt; no warnings; allowed_actions []
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Monday to Friday, 09:00–17:00 UTC"
    assert body["citations"] == [{"passage_id": "SUPPORT-v1:p1", "excerpt": SUPPORT_EXCERPT}]
    assert body["warnings"] == []
    assert body["allowed_actions"] == []


def test_get_question_for_a_new_question_allows_generate(tmp_path):
    # spec: 5.2-b
    # GIVEN Q3 has status new
    with make_client(tmp_path) as client:
        # WHEN a client sends GET /api/questions/Q3
        body = client.get("/api/questions/Q3").json()

    # THEN allowed_actions is ["generate"]; answer and citations are empty
    assert body["status"] == "new"
    assert body["allowed_actions"] == ["generate"]
    assert body["answer"] is None
    assert body["citations"] == []


def test_get_question_for_an_error_allows_retry(tmp_path):
    # spec: 5.2-b
    # GIVEN Q3 has status error
    with make_client(tmp_path, FakeDrafter(failed("Model call failed: timeout."))) as client:
        client.post("/api/questions/Q3/draft")

        # WHEN a client sends GET /api/questions/Q3
        body = client.get("/api/questions/Q3").json()

    # THEN allowed_actions is ["retry"] and the error message is shown
    assert body["allowed_actions"] == ["retry"]
    assert body["error"] == "Model call failed: timeout."


def test_an_unknown_question_gives_404_on_get_and_post(tmp_path):
    # spec: 5.2-c
    # GIVEN the real Seed is loaded
    with make_client(tmp_path, FakeDrafter()) as client:
        # WHEN a client sends GET and POST for Q99
        got = client.get("/api/questions/Q99")
        posted = client.post("/api/questions/Q99/draft")

    # THEN HTTP 404
    assert got.status_code == 404
    assert posted.status_code == 404

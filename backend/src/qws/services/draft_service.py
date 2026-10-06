from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from pydantic import ValidationError

from qws.adapters.store import Store
from qws.core import rules
from qws.core.models import (
    DraftRow,
    DrafterReply,
    ModelCallRow,
    Prompt,
    QuestionView,
    Reply,
)

INVALID_REPLY = "Model reply was not valid."


class Drafter(Protocol):
    """Asks a model for an answer. Never raises: a failure comes back in `error`."""

    def draft(self, prompt: Prompt) -> DrafterReply: ...


@dataclass(frozen=True)
class DrafterConfig:
    model: str
    settings: dict[str, int | float | str]


class Conflict:
    """The question already has a draft or an unresolved result."""


class UnknownQuestion:
    """No question has this ID."""


class DraftService:
    def __init__(self, store: Store, drafter: Drafter, config: DrafterConfig) -> None:
        self._store = store
        self._drafter = drafter
        self._config = config

    def ask(self, question_id: str) -> QuestionView | Conflict | UnknownQuestion:
        question = self._store.get_question(question_id)
        if question is None:
            return UnknownQuestion()
        existing = self._store.get_draft(question_id)
        if existing is not None and existing.status in ("draft", "unresolved"):
            return Conflict()

        passages = rules.current_passages(
            self._store.list_documents(), self._store.list_passages()
        )
        prompt = rules.build_prompt(question, passages, self._config.model, self._config.settings)
        reply = self._drafter.draft(prompt)

        error = reply.error
        checked = None
        if error is None:
            try:
                checked = rules.check_reply(Reply.model_validate_json(reply.raw_reply or ""), passages)
            except ValidationError:
                error = INVALID_REPLY

        now = datetime.now(UTC).isoformat()
        call = ModelCallRow(
            question_id=question_id,
            input_hash=prompt.input_hash,
            prompt=prompt.model_dump_json(include={"system", "user"}),
            model=reply.model,
            settings=reply.settings,
            raw_response=reply.raw_reply,
            error=error,
            label=reply.label,
            created_at=now,
            latency_ms=reply.latency_ms,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )
        if checked is None:
            draft = DraftRow(
                question_id=question_id,
                status="error",
                verdict=None,
                model_answer=None,
                citations=[],
                warnings=[],
                model_call_id=None,
                updated_at=now,
            )
        else:
            draft = DraftRow(
                question_id=question_id,
                status=checked.status,
                verdict=checked.verdict,
                model_answer=checked.answer,
                citations=checked.citations,
                warnings=checked.warnings,
                model_call_id=None,
                updated_at=now,
            )
        self._store.save_result(call, draft)
        return rules.question_view(question, self._store.get_draft(question_id))

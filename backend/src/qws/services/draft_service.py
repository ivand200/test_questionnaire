import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from pydantic import ValidationError

from qws.adapters.store import Store
from qws.core import rules
from qws.core.models import (
    Checked,
    DraftRow,
    DrafterReply,
    ModelCallRow,
    PassageRow,
    Prompt,
    QuestionRow,
    QuestionView,
    Reply,
    SupportReply,
    UnknownQuestion,
    Warning,
)

INVALID_REPLY = "Model reply was not valid."


class Drafter(Protocol):
    """Asks a model for an answer. Never raises: a failure comes back in `error`."""

    def draft(self, prompt: Prompt) -> DrafterReply: ...

    def judge(self, prompt: Prompt) -> DrafterReply: ...


@dataclass(frozen=True)
class DrafterConfig:
    model: str
    settings: dict[str, int | float | str]


@dataclass(frozen=True)
class Conflict:
    """The question cannot be asked now: it has a draft or an unresolved result, is being asked
    right now, or needs review. `reason` is a short message for the client."""

    reason: str = "already has a draft."


@dataclass(frozen=True)
class Attempt:
    """One ask of the Drafter: the model call to save, and the reply if it was valid."""

    call: ModelCallRow
    reply: Reply | None
    passages: list[PassageRow]


def _model_call(question: QuestionRow, prompt: Prompt, drafted: DrafterReply, error: str | None):
    return ModelCallRow(
        question_id=question.id,
        input_hash=prompt.input_hash,
        prompt=prompt.model_dump_json(include={"system", "user"}),
        model=drafted.model,
        settings=drafted.settings,
        raw_response=drafted.raw_reply,
        error=error,
        label=drafted.label,
        created_at=datetime.now(UTC).isoformat(),
        latency_ms=drafted.latency_ms,
        input_tokens=drafted.input_tokens,
        output_tokens=drafted.output_tokens,
    )


def attempt(
    store: Store, drafter: Drafter, config: DrafterConfig, question: QuestionRow
) -> Attempt:
    """Build the prompt from the current passages, call the Drafter, validate the raw reply."""
    passages = rules.current_passages(store.list_documents(), store.list_passages())
    prompt = rules.build_prompt(question, passages, config.model, config.settings)
    drafted = drafter.draft(prompt)

    error = drafted.error
    reply = None
    if error is None:
        try:
            reply = Reply.model_validate_json(drafted.raw_reply or "")
        except ValidationError:
            error = INVALID_REPLY
    return Attempt(call=_model_call(question, prompt, drafted, error), reply=reply, passages=passages)


@dataclass(frozen=True)
class Asked:
    """The result of `ask_model`: the draft step, and the support check when it ran."""

    call: ModelCallRow
    checked: Checked | None
    judge_call: ModelCallRow | None
    support: SupportReply | None  # the valid Support reply; None when there is no judge call or it failed


def ask_model(
    store: Store, drafter: Drafter, config: DrafterConfig, question: QuestionRow
) -> Asked:
    """Draft, check, and (only for a checked status `draft`) ask the judge. Saves nothing."""
    made = attempt(store, drafter, config, question)
    checked = rules.check_reply(made.reply, made.passages) if made.reply else None
    if checked is None or checked.status != "draft":
        return Asked(made.call, checked, None, None)

    prompt = rules.build_support_prompt(
        question.text, checked.answer, checked.citations, config.model, config.settings
    )
    judged = drafter.judge(prompt)
    error = judged.error
    support = None
    if error is None:
        try:
            support = SupportReply.model_validate_json(judged.raw_reply or "")
        except ValidationError:
            error = INVALID_REPLY
    return Asked(made.call, checked, _model_call(question, prompt, judged, error), support)


def _draft_warnings(asked: Asked) -> list[Warning]:
    """The warnings of the checked draft, plus the support warning when the judge ran."""
    if asked.checked is None:
        return []
    warnings = list(asked.checked.warnings)
    if asked.judge_call is not None:
        extra = rules.support_warning(asked.support, asked.judge_call.error)
        if extra is not None:
            warnings.append(extra)
    return warnings


class DraftService:
    def __init__(self, store: Store, drafter: Drafter, config: DrafterConfig) -> None:
        self._store = store
        self._drafter = drafter
        self._config = config
        self._asking: set[str] = set()  # questions whose model call is running
        self._asking_lock = threading.Lock()

    def ask(self, question_id: str) -> QuestionView | Conflict | UnknownQuestion:
        question = self._store.get_question(question_id)
        if question is None:
            return UnknownQuestion()
        with self._asking_lock:
            if question_id in self._asking:
                return Conflict("is being asked right now.")
            self._asking.add(question_id)
        try:
            return self._ask(question)
        finally:
            with self._asking_lock:
                self._asking.discard(question_id)

    def run_all(self) -> list[str]:
        """Ask every question with status new or error, one after the other in Seed order.

        Returns the IDs that were asked. A question that has a draft, is unresolved, is approved, or
        is being asked right now is skipped. `ask` never raises, so one failure does not stop the loop.
        """
        asked: list[str] = []
        for summary in self._store.list_questions():
            if summary.status not in ("new", "error"):
                continue
            if isinstance(self.ask(summary.id), QuestionView):
                asked.append(summary.id)
        return asked

    def _ask(self, question: QuestionRow) -> QuestionView | Conflict:
        if self._store.get_approval(question.question_hash) is not None:
            # Reuse: the approved answer wins; no model call.
            view = self._store.get_question_view(question.id)
            assert view is not None
            if view.status == "needs_review":
                return Conflict("needs review: its source changed. Edit or approve it first.")
            return view
        existing = self._store.get_draft(question.id)
        if existing is not None and existing.status in ("draft", "unresolved"):
            return Conflict()

        asked = ask_model(self._store, self._drafter, self._config, question)
        checked = asked.checked
        draft = DraftRow(
            question_id=question.id,
            status=checked.status if checked else "error",
            verdict=checked.verdict if checked else None,
            model_answer=checked.answer if checked else None,
            citations=checked.citations if checked else [],
            warnings=_draft_warnings(asked),
            model_call_id=None,
            updated_at=asked.call.created_at,
        )
        self._store.save_result(asked.call, draft, asked.judge_call)
        view = self._store.get_question_view(question.id)
        assert view is not None
        return view

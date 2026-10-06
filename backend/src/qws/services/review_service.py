from dataclasses import dataclass
from datetime import UTC, datetime

from qws.adapters.store import Store
from qws.core import rules
from qws.core.models import Action, ApprovedRow, Citation, QuestionView, UnknownQuestion


@dataclass(frozen=True)
class NotAllowed:
    """The status of the question does not allow this action."""

    reason: str


class ReviewService:
    """A reviewer's actions on a draft. Never calls the Drafter."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def edit(self, question_id: str, answer: str) -> QuestionView | NotAllowed | UnknownQuestion:
        """Save the reviewer's wording of a draft. It is not an approval."""
        view = self._store.get_question_view(question_id)
        if view is None:
            return UnknownQuestion()
        refused = self._refuse_unless_allowed(view, "edit")
        if refused:
            return refused
        self._store.save_edit(question_id, answer)
        updated = self._store.get_question_view(question_id)
        assert updated is not None
        return updated

    def approve(
        self, question_id: str, approver: str
    ) -> QuestionView | NotAllowed | UnknownQuestion:
        """Save the approved answer of a draft that has a citation. Approving twice changes nothing.

        A needs_review question is approved again: the new answer, approver and versions replace the
        old row.
        """
        view = self._store.get_question_view(question_id)
        question = self._store.get_question(question_id)
        if view is None or question is None:
            return UnknownQuestion()
        if view.status == "approved":
            return view
        refused = self._refuse_unless_allowed(view, "approve")
        if refused:
            return refused
        if not view.citations:
            return NotAllowed(f"Question {view.id} has no citation: cannot approve.")
        self._store.save_approval(
            ApprovedRow(
                question_hash=question.question_hash,
                question_text=question.text,
                topic=question.topic,
                answer=view.answer or "",
                citations=[Citation(passage_id=c.passage_id, excerpt=c.excerpt) for c in view.citations],
                source_versions=rules.source_versions(
                    view.citations, self._store.list_documents(), self._store.list_passages()
                ),
                approver=approver,
                approved_at=datetime.now(UTC).isoformat(),
            )
        )
        updated = self._store.get_question_view(question_id)
        assert updated is not None
        return updated

    def leave_open(
        self, question_id: str, note: str
    ) -> QuestionView | NotAllowed | UnknownQuestion:
        """Save a note; a draft becomes unresolved, an unresolved or needs_review question keeps its status."""
        view = self._store.get_question_view(question_id)
        if view is None:
            return UnknownQuestion()
        refused = self._refuse_unless_allowed(view, "leave_open")
        if refused:
            return refused
        self._store.save_note(question_id, note, keep_status=view.status == "needs_review")
        updated = self._store.get_question_view(question_id)
        assert updated is not None
        return updated

    @staticmethod
    def _refuse_unless_allowed(view: QuestionView, action: Action) -> NotAllowed | None:
        if action in view.allowed_actions:
            return None
        return NotAllowed(f"Question {view.id} has status {view.status}: cannot {action}.")

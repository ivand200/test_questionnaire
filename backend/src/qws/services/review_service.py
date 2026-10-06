from dataclasses import dataclass

from qws.adapters.store import Store
from qws.core.models import Action, QuestionView
from qws.services.draft_service import UnknownQuestion


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

    @staticmethod
    def _refuse_unless_allowed(view: QuestionView, action: Action) -> NotAllowed | None:
        if action in view.allowed_actions:
            return None
        return NotAllowed(f"Question {view.id} has status {view.status}: cannot {action}.")

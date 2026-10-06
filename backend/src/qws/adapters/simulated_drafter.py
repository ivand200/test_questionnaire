import json

from qws.core.models import DrafterReply, Prompt
from qws.services.draft_service import Drafter

TIMEOUT_ERROR = "Model call failed: timeout."
LYING_QUESTION = "Does the free plan include CSV export?"  # Q10 in the Demo file
LYING_DRAFT = json.dumps(
    {
        "answer": "Yes. Free-plan users can export CSV.",
        "verdict": "supported",
        "citations": ["EXPORT-v2:p1"],
    }
)


class SimulatedDrafter:
    """Writes the Simulated entries; only the Recorder uses it. The draft for Q10 is the fixed
    Lying draft: it cites a real passage that says the opposite. Every other draft fails with a
    timeout. Both are labelled `simulated` and no model is called for them. The judge call goes to
    the real Drafter given here; without one it fails with the timeout too."""

    def __init__(
        self,
        model: str,
        settings: dict[str, int | float | str],
        judge: Drafter | None = None,
    ) -> None:
        self._model = model
        self._settings = settings
        self._judge = judge

    def _reply(self, **fields) -> DrafterReply:
        return DrafterReply(label="simulated", model=self._model, settings=self._settings, **fields)

    def draft(self, prompt: Prompt) -> DrafterReply:
        if prompt.user.startswith(f"Question: {LYING_QUESTION}\n"):
            return self._reply(raw_reply=LYING_DRAFT)
        return self._reply(error=TIMEOUT_ERROR)

    def judge(self, prompt: Prompt) -> DrafterReply:
        if self._judge is None:
            return self._reply(error=TIMEOUT_ERROR)
        return self._judge.judge(prompt)

from qws.core.models import DrafterReply, Prompt

TIMEOUT_ERROR = "Model call failed: timeout."


class SimulatedDrafter:
    """Always fails with a timeout, labelled `simulated`. Only the Recorder uses it, to write the
    Simulated entry; no model is called."""

    def __init__(self, model: str, settings: dict[str, int | float | str]) -> None:
        self._model = model
        self._settings = settings

    def draft(self, prompt: Prompt) -> DrafterReply:
        return DrafterReply(
            label="simulated", model=self._model, settings=self._settings, error=TIMEOUT_ERROR
        )

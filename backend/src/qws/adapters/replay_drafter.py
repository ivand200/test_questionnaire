from qws.core.models import DrafterReply, Prompt


class ReplayDrafter:
    """Placeholder until the replay ticket: no entry is ever found.

    The replay ticket makes it read replay/responses.json by input hash.
    """

    def __init__(self, model: str, settings: dict[str, int | float | str]) -> None:
        self._model = model
        self._settings = settings

    def draft(self, prompt: Prompt) -> DrafterReply:
        return DrafterReply(
            error="No saved response for this input.",
            label="cached",
            model=self._model,
            settings=self._settings,
        )

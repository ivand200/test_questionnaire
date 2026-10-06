from pathlib import Path

from qws.adapters.replay_file import read_entries
from qws.core.models import DrafterReply, Prompt

NO_ENTRY = "No saved response for this input."
BAD_FILE = "Replay file is not valid."


class ReplayDrafter:
    """Takes the reply from the replay file by input hash. Needs no key; never raises."""

    def __init__(self, model: str, settings: dict[str, int | float | str], path: Path) -> None:
        self._model = model
        self._settings = settings
        self._path = path

    def _reply(self, **fields) -> DrafterReply:
        return DrafterReply(label="cached", model=self._model, settings=self._settings, **fields)

    def draft(self, prompt: Prompt) -> DrafterReply:
        try:
            entries = read_entries(self._path)
        except (OSError, ValueError):
            return self._reply(error=BAD_FILE)
        for entry in entries:
            if entry.input_hash == prompt.input_hash:
                return self._reply(raw_reply=entry.raw_response)
        return self._reply(error=NO_ENTRY)

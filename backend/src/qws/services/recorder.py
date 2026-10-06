"""`make record`: ask the real model for the recording questions and save the replies."""

import os
import sys
from pathlib import Path

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.replay_file import add_entry
from qws.adapters.simulated_drafter import SimulatedDrafter
from qws.adapters.store import Store
from qws.config import REPLAY_PATH, drafter_config, open_store
from qws.core.models import ModelCallRow, ReplayEntry
from qws.services.draft_service import Drafter, DrafterConfig, ask_model

RECORDING_LIST = [f"Q{n}" for n in range(1, 9)]  # Q1 to Q8, asked with the real model
SIMULATED_LIST = ["Q9", "Q10"]  # drafts written through SimulatedDrafter; only the Q10 judge asks the real model


class Recorder:
    def __init__(self, store: Store, config: DrafterConfig) -> None:
        self._store = store
        self._config = config

    def record(self, question_ids: list[str], drafter: Drafter, path: Path) -> list[str]:
        """Run `ask_model` for each question; save each model call and one replay entry per call
        that has a raw reply or is simulated. Returns a message per failure."""
        failures: list[str] = []
        for question_id in question_ids:
            question = self._store.get_question(question_id)
            if question is None:
                failures.append(f"{question_id}: unknown question.")
                continue
            asked = ask_model(self._store, drafter, self._config, question)
            for call, prefix in ((asked.call, ""), (asked.judge_call, "judge: ")):
                if call is None:
                    continue
                self._store.save_model_call(call)
                failure = self._write_entry(path, call, draft=call is asked.call)
                if failure is not None:
                    failures.append(f"{question_id}: {prefix}{failure}")
        return failures

    @staticmethod
    def _write_entry(path: Path, call: ModelCallRow, draft: bool) -> str | None:
        """Write the entry of one call; return its error text when it gets no entry. Only a draft
        call can be a Simulated entry: a failed judge call never gets an entry."""
        if draft and call.label == "simulated":
            raw_response, error = call.raw_response, call.error
        elif call.error is not None or call.raw_response is None:
            return call.error
        else:
            raw_response, error = call.raw_response, None
        add_entry(
            path,
            ReplayEntry(
                input_hash=call.input_hash,
                label=call.label,
                model=call.model,
                settings=call.settings,
                raw_response=raw_response,
                error=error,
                recorded_at=call.created_at,
            ),
        )
        return None


def main() -> int:
    store, _ = open_store()
    config = drafter_config()
    recorder = Recorder(store, config)
    real = RealDrafter(config.model, os.environ.get("OPENAI_API_KEY", ""), config.settings)
    simulated = SimulatedDrafter(config.model, config.settings, judge=real)
    failures = recorder.record(SIMULATED_LIST, simulated, REPLAY_PATH)
    failures += recorder.record(RECORDING_LIST, real, REPLAY_PATH)
    for message in failures:
        print(message, file=sys.stderr)
    if not failures:
        print(f"Recorded {', '.join(SIMULATED_LIST + RECORDING_LIST)} with {config.model} in {REPLAY_PATH}.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

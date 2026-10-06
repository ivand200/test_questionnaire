"""`make record`: ask the real model for the recording questions and save the replies."""

import os
import sys
from pathlib import Path

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.replay_file import add_entry
from qws.adapters.simulated_drafter import SimulatedDrafter
from qws.adapters.store import Store
from qws.config import DEMO_PATH, REPLAY_PATH, drafter_config, open_store
from qws.core.models import ReplayEntry
from qws.services.draft_service import Drafter, DrafterConfig, attempt

RECORDING_LIST = ["Q3"]
SIMULATED_LIST = ["Q9"]  # written through SimulatedDrafter; the real model is never asked


class Recorder:
    def __init__(self, store: Store, config: DrafterConfig) -> None:
        self._store = store
        self._config = config

    def record(self, question_ids: list[str], drafter: Drafter, path: Path) -> list[str]:
        """Save one model call and one replay entry per question. Returns a message per failure."""
        failures: list[str] = []
        for question_id in question_ids:
            question = self._store.get_question(question_id)
            if question is None:
                failures.append(f"{question_id}: unknown question.")
                continue
            call = attempt(self._store, drafter, self._config, question).call
            self._store.save_model_call(call)
            if call.label == "simulated" and call.error is not None:
                add_entry(
                    path,
                    ReplayEntry(
                        input_hash=call.input_hash,
                        label=call.label,
                        model=call.model,
                        settings=call.settings,
                        error=call.error,
                        recorded_at=call.created_at,
                    ),
                )
                continue
            if call.error is not None or call.raw_response is None:
                failures.append(f"{question_id}: {call.error}")
                continue
            add_entry(
                path,
                ReplayEntry(
                    input_hash=call.input_hash,
                    label=call.label,
                    model=call.model,
                    settings=call.settings,
                    raw_response=call.raw_response,
                    recorded_at=call.created_at,
                ),
            )
        return failures


def main() -> int:
    store, _ = open_store(demo_path=DEMO_PATH)
    config = drafter_config()
    recorder = Recorder(store, config)
    simulated = SimulatedDrafter(config.model, config.settings)
    real = RealDrafter(config.model, os.environ.get("OPENAI_API_KEY", ""), config.settings)
    failures = recorder.record(SIMULATED_LIST, simulated, REPLAY_PATH)
    failures += recorder.record(RECORDING_LIST, real, REPLAY_PATH)
    for message in failures:
        print(message, file=sys.stderr)
    if not failures:
        print(f"Recorded {', '.join(SIMULATED_LIST + RECORDING_LIST)} with {config.model} in {REPLAY_PATH}.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""`make record`: ask the real model for the recording questions and save the replies."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from qws.adapters.real_drafter import RealDrafter
from qws.adapters.replay_file import add_entry
from qws.adapters.store import Store
from qws.config import DEFAULT_DB_PATH, REPLAY_PATH, SEED_PATH, drafter_config
from qws.core import rules
from qws.core.models import ModelCallRow, ReplayEntry, Reply
from qws.services import seed_loader
from qws.services.draft_service import Drafter, DrafterConfig

RECORDING_LIST = ["Q3"]


class Recorder:
    def __init__(self, store: Store, config: DrafterConfig) -> None:
        self._store = store
        self._config = config

    def record(self, question_ids: list[str], drafter: Drafter, path: Path) -> list[str]:
        """Save one model call and one replay entry per question. Returns a message per failure."""
        passages = rules.current_passages(
            self._store.list_documents(), self._store.list_passages()
        )
        failures: list[str] = []
        for question_id in question_ids:
            question = self._store.get_question(question_id)
            if question is None:
                failures.append(f"{question_id}: unknown question.")
                continue
            prompt = rules.build_prompt(question, passages, self._config.model, self._config.settings)
            reply = drafter.draft(prompt)

            error = reply.error
            if error is None:
                try:
                    Reply.model_validate_json(reply.raw_reply or "")
                except ValidationError:
                    error = "Model reply was not valid."
            now = datetime.now(UTC).isoformat()
            self._store.save_model_call(
                ModelCallRow(
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
            )
            if error is not None or reply.raw_reply is None:
                failures.append(f"{question_id}: {error}")
                continue
            add_entry(
                path,
                ReplayEntry(
                    input_hash=prompt.input_hash,
                    label=reply.label,
                    model=reply.model,
                    settings=reply.settings,
                    raw_response=reply.raw_reply,
                    recorded_at=now,
                ),
            )
        return failures


def main() -> int:
    store = Store(os.environ.get("DB_PATH") or DEFAULT_DB_PATH)
    store.init_schema()
    seed_loader.load(json.loads(SEED_PATH.read_text()), store)
    config = drafter_config()
    drafter = RealDrafter(config.model, os.environ.get("OPENAI_API_KEY", ""), config.settings)
    failures = Recorder(store, config).record(RECORDING_LIST, drafter, REPLAY_PATH)
    for message in failures:
        print(message, file=sys.stderr)
    if not failures:
        print(f"Recorded {', '.join(RECORDING_LIST)} with {config.model} in {REPLAY_PATH}.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

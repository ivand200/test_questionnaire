"""Settings shared by the API and the recorder."""

import os
from pathlib import Path

from qws.services.draft_service import DrafterConfig

REPO_DIR = Path(__file__).resolve().parents[3]
SEED_PATH = REPO_DIR / "data" / "seed.json"
REPLAY_PATH = REPO_DIR / "replay" / "responses.json"
DEFAULT_DB_PATH = "qws.db"
# The model is part of the input hash, so replay needs the same name that `make record` used.
DEFAULT_MODEL_NAME = "gpt-4.1-mini"
MODEL_SETTINGS: dict[str, int | float | str] = {"temperature": 0, "max_tokens": 1000}


def drafter_config() -> DrafterConfig:
    return DrafterConfig(os.environ.get("MODEL_NAME") or DEFAULT_MODEL_NAME, MODEL_SETTINGS)

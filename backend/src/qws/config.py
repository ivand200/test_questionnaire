"""Settings shared by the API and the recorder."""

import json
import os
from pathlib import Path

from qws.adapters.store import Store
from qws.core.models import LoadIssue
from qws.services import seed_loader
from qws.services.draft_service import DrafterConfig

REPO_DIR = Path(__file__).resolve().parents[3]
SEED_PATH = REPO_DIR / "data" / "seed.json"
DEMO_PATH = REPO_DIR / "data" / "demo.json"
REPLAY_PATH = REPO_DIR / "replay" / "responses.json"
DEFAULT_DB_PATH = "qws.db"
# The model is part of the input hash, so replay needs the same name that `make record` used.
DEFAULT_MODEL_NAME = "gpt-6-luna"
MODEL_SETTINGS: dict[str, int | float | str] = {
    "temperature": 0,
    "max_tokens": 1000,
    "openai_reasoning_effort": "medium",
}


def drafter_config() -> DrafterConfig:
    return DrafterConfig(os.environ.get("MODEL_NAME") or DEFAULT_MODEL_NAME, MODEL_SETTINGS)


def open_store(
    db_path: Path | str | None = None,
    seed_path: Path = SEED_PATH,
    demo_path: Path | None = None,
) -> tuple[Store, list[LoadIssue]]:
    """Open the Database, create its tables and load the seed. Shared by the API and the recorder.

    The questions of the Demo file are added to the seed in memory, after the Seed questions;
    the Seed file is never changed.
    """
    store = Store(db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH)
    store.init_schema()
    seed = json.loads(seed_path.read_text())
    if demo_path is not None:
        seed["questions"] = seed["questions"] + json.loads(demo_path.read_text())["questions"]
    return store, seed_loader.load(seed, store)

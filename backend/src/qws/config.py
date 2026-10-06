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
REPLAY_PATH = REPO_DIR / "replay" / "responses.json"
DEFAULT_DB_PATH = "qws.db"
# The model is part of the input hash, so replay needs the same name that `make record` used.
DEFAULT_MODEL_NAME = "gpt-4.1-mini"
MODEL_SETTINGS: dict[str, int | float | str] = {"temperature": 0, "max_tokens": 1000}


def drafter_config() -> DrafterConfig:
    return DrafterConfig(os.environ.get("MODEL_NAME") or DEFAULT_MODEL_NAME, MODEL_SETTINGS)


def open_store(
    db_path: Path | str | None = None, seed_path: Path = SEED_PATH
) -> tuple[Store, list[LoadIssue]]:
    """Open the Database, create its tables and load the seed. Shared by the API and the recorder."""
    store = Store(db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH)
    store.init_schema()
    return store, seed_loader.load(json.loads(seed_path.read_text()), store)

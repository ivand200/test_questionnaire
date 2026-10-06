import os
from pathlib import Path

from pydantic import TypeAdapter

from qws.core.models import ReplayEntry

_ENTRIES = TypeAdapter(list[ReplayEntry])


def read_entries(path: Path) -> list[ReplayEntry]:
    """The entries of the replay file; none when the file does not exist. Raises ValueError if the file is not valid JSON of entries."""
    if not path.exists():
        return []
    return _ENTRIES.validate_json(path.read_text())


def add_entry(path: Path, entry: ReplayEntry) -> None:
    """Add the entry; an entry with the same input hash is replaced, so there is one per hash."""
    entries = [e for e in read_entries(path) if e.input_hash != entry.input_hash]
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(_ENTRIES.dump_json(entries, indent=2, exclude_none=True) + b"\n")
    os.replace(temp, path)

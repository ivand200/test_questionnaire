import subprocess
from pathlib import Path

from qws.config import REPO_DIR


def run_reset(db: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["make", "-C", str(REPO_DIR), "reset"],
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "DB_PATH": str(db)},
        capture_output=True,
        text=True,
    )


def test_reset_deletes_the_three_database_files(tmp_path):
    # spec: 3.3-a
    # GIVEN a Database file with its -wal and -shm files
    db = tmp_path / "qws.db"
    files = [db, tmp_path / "qws.db-wal", tmp_path / "qws.db-shm"]
    for file in files:
        file.write_text("x")

    # WHEN the user runs make reset
    result = run_reset(db)

    # THEN the three files are gone and the exit code is 0
    assert result.returncode == 0
    assert [file.exists() for file in files] == [False, False, False]


def test_reset_without_database_files_succeeds(tmp_path):
    # spec: 3.3-b
    # GIVEN no Database file
    db = tmp_path / "qws.db"

    # WHEN the user runs make reset
    result = run_reset(db)

    # THEN the exit code is 0
    assert result.returncode == 0

import sqlite3

from conftest import make_client


def stored_versions(tmp_path) -> dict[str, int]:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return dict(conn.execute("SELECT id, version FROM document").fetchall())
    finally:
        conn.close()


def passage_text(tmp_path, passage_id: str) -> str:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return conn.execute("SELECT text FROM passage WHERE id = ?", (passage_id,)).fetchone()[0]
    finally:
        conn.close()


def test_bump_adds_one_to_the_version_of_that_document_only(tmp_path):
    # spec: 1.1-a
    # GIVEN the real Seed: EXPORT-v2 is version 2 and EXPORT-v1 is version 1
    with make_client(tmp_path) as client:
        text_before = passage_text(tmp_path, "EXPORT-v2:p1")

        # WHEN the client sends POST /api/documents/EXPORT-v2/bump-version twice
        first = client.post("/api/documents/EXPORT-v2/bump-version")
        second = client.post("/api/documents/EXPORT-v2/bump-version")

    # THEN version 3, then 4; EXPORT-v1 is still version 1; the text of EXPORT-v2:p1 is unchanged
    assert first.status_code == 200
    assert first.json() == {"id": "EXPORT-v2", "version": 3}
    assert second.status_code == 200
    assert second.json() == {"id": "EXPORT-v2", "version": 4}
    versions = stored_versions(tmp_path)
    assert versions["EXPORT-v2"] == 4
    assert versions["EXPORT-v1"] == 1
    assert passage_text(tmp_path, "EXPORT-v2:p1") == text_before


def test_bump_of_an_unknown_document_gives_404_and_changes_nothing(tmp_path):
    # spec: 1.2-a
    # GIVEN the real Seed
    with make_client(tmp_path) as client:
        before = stored_versions(tmp_path)

        # WHEN the client sends POST /api/documents/NOPE-v1/bump-version
        response = client.post("/api/documents/NOPE-v1/bump-version")

    # THEN 404; every document keeps its version
    assert response.status_code == 404
    assert stored_versions(tmp_path) == before


def test_a_bumped_version_survives_a_restart(tmp_path):
    # spec: 1.3-a
    # GIVEN EXPORT-v2 is bumped to version 3
    with make_client(tmp_path) as client:
        client.post("/api/documents/EXPORT-v2/bump-version")

    # WHEN the app is started again on the same Database (loading the Seed again)
    with make_client(tmp_path):
        pass

    # THEN EXPORT-v2 is still version 3
    assert stored_versions(tmp_path)["EXPORT-v2"] == 3

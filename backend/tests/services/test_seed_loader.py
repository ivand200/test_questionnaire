import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from qws.adapters.store import Store
from qws.services import seed_loader

REAL_SEED = json.loads((Path(__file__).resolve().parents[3] / "data" / "seed.json").read_text())

TABLES = ["document", "passage", "question", "owner"]


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def store(db_path):
    store = Store(db_path)
    store.init_schema()
    return store


def rows(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    finally:
        conn.close()


def seed_copy():
    return copy.deepcopy(REAL_SEED)


def test_real_seed_loads_all_rows_with_seed_ids_and_supersedes_link(store, db_path):
    # spec: 1.1-a
    # GIVEN the real Seed and an empty Database
    # WHEN the Backend loads
    issues = seed_loader.load(REAL_SEED, store)

    # THEN 5 documents, 5 passages, 8 questions, 4 owners; EXPORT-v2 supersedes EXPORT-v1
    assert issues == []
    assert [len(rows(db_path, t)) for t in TABLES] == [5, 5, 8, 4]
    documents = {d["id"]: d for d in rows(db_path, "document")}
    assert documents["EXPORT-v2"]["supersedes_id"] == "EXPORT-v1"
    assert documents["EXPORT-v1"]["supersedes_id"] is None
    assert {p["id"] for p in rows(db_path, "passage")} >= {"EXPORT-v2:p1", "SUPPORT-v1:p1"}


def test_questions_get_their_question_hash(store, db_path):
    # spec: 1.1-b
    # GIVEN the real Seed, empty Database
    # WHEN the Backend loads
    seed_loader.load(REAL_SEED, store)

    # THEN Q3 has the SHA-256 hex of the topic and text; Q1 and Q3 differ
    hashes = {q["id"]: q["question_hash"] for q in rows(db_path, "question")}
    assert hashes["Q3"] == hashlib.sha256(b"support|when is email support available?").hexdigest()
    assert hashes["Q1"] != hashes["Q3"]


def test_second_load_changes_no_row(store, db_path):
    # spec: 1.2-a
    # GIVEN the real Seed is loaded
    seed_loader.load(REAL_SEED, store)
    before = {t: rows(db_path, t) for t in TABLES}

    # WHEN the Backend loads the Seed again
    issues = seed_loader.load(REAL_SEED, store)

    # THEN the counts are 5, 5, 8, 4 and every row is equal to the row before
    assert issues == []
    assert {t: rows(db_path, t) for t in TABLES} == before
    assert [len(before[t]) for t in TABLES] == [5, 5, 8, 4]


def test_duplicate_document_id_keeps_first_row_and_loads_the_rest(store, db_path):
    # spec: 1.3-a
    # GIVEN a Seed with two documents EXPORT-v2, the second with another version
    seed = seed_copy()
    second = copy.deepcopy(seed["documents"][1])
    second["version"] = 9
    seed["documents"].append(second)

    # WHEN the Backend loads
    issues = seed_loader.load(seed, store)

    # THEN one EXPORT-v2 row with the first version; issue duplicate_id; the other 4 load
    documents = rows(db_path, "document")
    assert len(documents) == 5
    assert [d["version"] for d in documents if d["id"] == "EXPORT-v2"] == [2]
    assert [(i.kind, i.id) for i in issues] == [("duplicate_id", "EXPORT-v2")]


def test_duplicate_question_id_keeps_first_row_and_loads_the_rest(store, db_path):
    # spec: 1.3-b
    # GIVEN a Seed with two questions Q1, the second with another text
    seed = seed_copy()
    seed["questions"].append({"id": "Q1", "topic": "exports", "text": "Something else?"})

    # WHEN the Backend loads
    issues = seed_loader.load(seed, store)

    # THEN one Q1 row with the first text; issue duplicate_id; Q2 to Q8 load
    questions = rows(db_path, "question")
    assert [q["id"] for q in questions] == [f"Q{n}" for n in range(1, 9)]
    assert questions[0]["text"] == "Can free-plan users export CSV?"
    assert [(i.kind, i.id) for i in issues] == [("duplicate_id", "Q1")]


def test_passage_with_no_document_is_not_stored(store, db_path):
    # spec: 1.4-a
    # GIVEN a Seed with passage X-v1:p1 and no document X-v1
    seed = seed_copy()
    seed["passages"] = [{"id": "X-v1:p1", "text": "Orphan."}]

    # WHEN the Backend loads
    issues = seed_loader.load(seed, store)

    # THEN the passage is not stored; issue missing_document; the other passages load
    ids = [p["id"] for p in rows(db_path, "passage")]
    assert "X-v1:p1" not in ids
    assert len(ids) == 5
    assert [(i.kind, i.id) for i in issues] == [("missing_document", "X-v1:p1")]


def test_supersedes_a_missing_document_is_stored_without_the_link(store, db_path):
    # spec: 1.4-b
    # GIVEN a Seed where EXPORT-v2 supersedes EXPORT-v0, which is absent
    seed = seed_copy()
    seed["documents"][1]["supersedes"] = "EXPORT-v0"

    # WHEN the Backend loads
    issues = seed_loader.load(seed, store)

    # THEN EXPORT-v2 is stored with no supersedes_id; issue missing_superseded
    export_v2 = next(d for d in rows(db_path, "document") if d["id"] == "EXPORT-v2")
    assert export_v2["supersedes_id"] is None
    assert [(i.kind, i.id) for i in issues] == [("missing_superseded", "EXPORT-v2")]


def test_question_with_no_owner_is_stored_and_reported(store, db_path):
    # spec: 1.4-c
    # GIVEN a Seed with a question of topic legal and no owner legal
    seed = seed_copy()
    seed["questions"].append({"id": "Q9", "topic": "legal", "text": "Is there a DPA?"})

    # WHEN the Backend loads
    issues = seed_loader.load(seed, store)

    # THEN the question is stored; issue missing_owner for that question
    assert "Q9" in [q["id"] for q in rows(db_path, "question")]
    assert [(i.kind, i.id) for i in issues] == [("missing_owner", "Q9")]

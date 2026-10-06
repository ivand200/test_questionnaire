import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from qws.core.models import (
    DocumentRow,
    DraftRow,
    ModelCallRow,
    OwnerRow,
    PassageRow,
    QuestionRow,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema.sql"


class Store:
    """Plain sqlite3 + schema.sql. One short connection per call."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            with conn:  # one transaction: commit, or roll back on error
                yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        with self._connect() as conn:
            conn.executescript(SCHEMA_PATH.read_text())

    def insert_missing(
        self,
        documents: list[DocumentRow],
        passages: list[PassageRow],
        owners: list[OwnerRow],
        questions: list[QuestionRow],
    ) -> None:
        """Insert seed rows whose ID is not stored yet. Stored rows are never changed."""
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO document (id, version, date, status, supersedes_id)"
                " VALUES (:id, :version, :date, :status, :supersedes_id)",
                [d.model_dump() for d in documents],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO passage (id, document_id, text)"
                " VALUES (:id, :document_id, :text)",
                [p.model_dump() for p in passages],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO owner (topic, reviewer) VALUES (:topic, :reviewer)",
                [o.model_dump() for o in owners],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO question (id, topic, text, question_hash)"
                " VALUES (:id, :topic, :text, :question_hash)",
                [q.model_dump() for q in questions],
            )

    def list_questions(self) -> list[dict[str, str]]:
        """Every question in Seed order with its computed status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT q.id, q.topic, q.text, COALESCE(d.status, 'new') AS status"
                " FROM question q LEFT JOIN draft d ON d.question_id = q.id"
                " ORDER BY q.rowid"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_question(self, question_id: str) -> QuestionRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM question WHERE id = ?", (question_id,)).fetchone()
        return QuestionRow(**dict(row)) if row else None

    def list_documents(self) -> list[DocumentRow]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM document ORDER BY rowid").fetchall()
        return [DocumentRow(**dict(r)) for r in rows]

    def list_passages(self) -> list[PassageRow]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM passage ORDER BY rowid").fetchall()
        return [PassageRow(**dict(r)) for r in rows]

    def get_draft(self, question_id: str) -> DraftRow | None:
        """The draft row; `error` is the message of its model call."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT d.*, m.error AS error FROM draft d"
                " LEFT JOIN model_call m ON m.id = d.model_call_id"
                " WHERE d.question_id = ?",
                (question_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["citations"] = json.loads(data["citations"])
        data["warnings"] = json.loads(data["warnings"])
        return DraftRow(**data)

    def save_result(self, call: ModelCallRow, draft: DraftRow) -> None:
        """Insert the model call (never changed later) and set the draft, in one transaction."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO model_call (question_id, input_hash, prompt, model, settings,"
                " raw_response, error, label, created_at, latency_ms, input_tokens, output_tokens)"
                " VALUES (:question_id, :input_hash, :prompt, :model, :settings, :raw_response,"
                " :error, :label, :created_at, :latency_ms, :input_tokens, :output_tokens)",
                {**call.model_dump(), "settings": json.dumps(call.settings, sort_keys=True)},
            )
            conn.execute(
                "INSERT OR REPLACE INTO draft (question_id, status, verdict, model_answer,"
                " citations, warnings, model_call_id, updated_at)"
                " VALUES (:question_id, :status, :verdict, :model_answer, :citations,"
                " :warnings, :model_call_id, :updated_at)",
                {
                    **draft.model_dump(exclude={"citations", "warnings", "error"}),
                    "citations": json.dumps([c.model_dump() for c in draft.citations]),
                    "warnings": json.dumps([w.model_dump() for w in draft.warnings]),
                    "model_call_id": cursor.lastrowid,
                },
            )

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast

from qws.core.models import (
    DocumentRow,
    DraftRow,
    ModelCallRow,
    OwnerRow,
    PassageRow,
    QuestionRow,
    QuestionSummary,
    QuestionView,
    Status,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema.sql"


def _status(draft_status: str | None) -> Status:
    """The one place that sets a question's status: the draft row status, else new."""
    return cast(Status, draft_status or "new")


def _allowed_actions(status: Status) -> list[Literal["generate", "retry"]]:
    return {"new": ["generate"], "error": ["retry"]}.get(status, [])


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

    def list_questions(self) -> list[QuestionSummary]:
        """Every question in Seed order with its status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT q.id, q.topic, q.text, d.status AS draft_status"
                " FROM question q LEFT JOIN draft d ON d.question_id = q.id"
                " ORDER BY q.rowid"
            ).fetchall()
        return [
            QuestionSummary(
                id=r["id"], topic=r["topic"], text=r["text"], status=_status(r["draft_status"])
            )
            for r in rows
        ]

    def get_question_view(self, question_id: str) -> QuestionView | None:
        """The question with its status, draft, error message and allowed actions."""
        question = self.get_question(question_id)
        if question is None:
            return None
        draft = self.get_draft(question_id)
        status = _status(draft.status if draft else None)
        return QuestionView(
            id=question.id,
            topic=question.topic,
            text=question.text,
            status=status,
            answer=draft.model_answer if draft else None,
            citations=draft.citations if draft else [],
            warnings=draft.warnings if draft else [],
            error=draft.error if draft and status == "error" else None,
            allowed_actions=_allowed_actions(status),
        )

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

    @staticmethod
    def _insert_call(conn: sqlite3.Connection, call: ModelCallRow) -> int:
        cursor = conn.execute(
            "INSERT INTO model_call (question_id, input_hash, prompt, model, settings,"
            " raw_response, error, label, created_at, latency_ms, input_tokens, output_tokens)"
            " VALUES (:question_id, :input_hash, :prompt, :model, :settings, :raw_response,"
            " :error, :label, :created_at, :latency_ms, :input_tokens, :output_tokens)",
            {**call.model_dump(), "settings": json.dumps(call.settings, sort_keys=True)},
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def save_model_call(self, call: ModelCallRow) -> None:
        """Insert a model call that has no draft (a recording)."""
        with self._connect() as conn:
            self._insert_call(conn, call)

    def save_result(self, call: ModelCallRow, draft: DraftRow) -> None:
        """Insert the model call (never changed later) and set the draft, in one transaction."""
        with self._connect() as conn:
            call_id = self._insert_call(conn, call)
            conn.execute(
                "INSERT OR REPLACE INTO draft (question_id, status, verdict, model_answer,"
                " citations, warnings, model_call_id, updated_at)"
                " VALUES (:question_id, :status, :verdict, :model_answer, :citations,"
                " :warnings, :model_call_id, :updated_at)",
                {
                    **draft.model_dump(exclude={"citations", "warnings", "error"}),
                    "citations": json.dumps([c.model_dump() for c in draft.citations]),
                    "warnings": json.dumps([w.model_dump() for w in draft.warnings]),
                    "model_call_id": call_id,
                },
            )

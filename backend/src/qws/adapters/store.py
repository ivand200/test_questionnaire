import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from qws.core import rules
from qws.core.models import (
    Approval,
    ApprovedRow,
    Citation,
    DocumentRow,
    DraftRow,
    ModelCallRow,
    OwnerRow,
    PassageRow,
    QuestionRow,
    QuestionSummary,
    QuestionView,
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

    def list_questions(self) -> list[QuestionSummary]:
        """Every question in Seed order with its status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT q.id, q.topic, q.text, d.status AS draft_status,"
                " a.id IS NOT NULL AS has_approval"
                " FROM question q LEFT JOIN draft d ON d.question_id = q.id"
                " LEFT JOIN approved_answer a ON a.question_hash = q.question_hash"
                " ORDER BY q.rowid"
            ).fetchall()
        return [
            QuestionSummary(
                id=r["id"], topic=r["topic"], text=r["text"], status=rules.question_status(bool(r["has_approval"]), r["draft_status"]),
            )
            for r in rows
        ]

    def get_question_view(self, question_id: str) -> QuestionView | None:
        """The question with its status, draft, error message and allowed actions."""
        question = self.get_question(question_id)
        if question is None:
            return None
        draft = self.get_draft(question_id)
        approval = self.get_approval(question.question_hash)
        status = rules.question_status(approval is not None, draft.status if draft else None)
        citations = approval.citations if approval else draft.citations if draft else []
        if approval:
            answer = approval.answer
        else:
            answer = (draft.reviewer_answer or draft.model_answer) if draft else None
        # Computed on every read and never saved.
        replaced, superseded = rules.superseded_evidence(
            citations, self.list_documents(), self.list_passages()
        )
        return QuestionView(
            id=question.id,
            topic=question.topic,
            text=question.text,
            status=status,
            answer=answer,
            citations=citations,
            warnings=([] if approval else draft.warnings if draft else []) + superseded,
            owner=self.get_owner(question.topic),
            replaced=replaced,
            label=draft.label if draft else None,
            error=draft.error if draft and status == "error" else None,
            edited=status != "approved" and bool(draft and draft.reviewer_answer),
            note=draft.note if draft else None,
            approved=Approval(
                approver=approval.approver,
                approved_at=approval.approved_at,
                source_versions=approval.source_versions,
            )
            if approval
            else None,
            allowed_actions=rules.allowed_actions(status),
        )

    def get_owner(self, topic: str) -> str | None:
        """The reviewer of a topic from the owner table; None when the topic has no row."""
        with self._connect() as conn:
            row = conn.execute("SELECT reviewer FROM owner WHERE topic = ?", (topic,)).fetchone()
        return row["reviewer"] if row else None

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
        """The draft row; `error` and `label` come from its model call."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT d.*, m.error AS error, m.label AS label FROM draft d"
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

    def save_edit(self, question_id: str, answer: str) -> None:
        """Set the reviewer answer of a draft. The model answer is never changed."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE draft SET reviewer_answer = ? WHERE question_id = ? AND status = 'draft'",
                (answer, question_id),
            )

    def save_note(self, question_id: str, note: str) -> None:
        """Set the note and make the draft `unresolved`. The edit and the model answer are kept."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE draft SET note = ?, status = 'unresolved'"
                " WHERE question_id = ? AND status IN ('draft', 'unresolved')",
                (note, question_id),
            )

    def get_approval(self, question_hash: str) -> ApprovedRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approved_answer WHERE question_hash = ?", (question_hash,)
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["citations"] = [Citation(**c) for c in json.loads(data["citations"])]
        data["source_versions"] = json.loads(data["source_versions"])
        return ApprovedRow(**data)

    def save_approval(self, approval: ApprovedRow) -> None:
        """One write. The question hash is unique, so a second approval changes nothing."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO approved_answer (question_hash, question_text, topic,"
                " answer, citations, source_versions, approver, approved_at)"
                " VALUES (:question_hash, :question_text, :topic, :answer, :citations,"
                " :source_versions, :approver, :approved_at)",
                {
                    **approval.model_dump(exclude={"citations", "source_versions"}),
                    "citations": json.dumps([c.model_dump() for c in approval.citations]),
                    "source_versions": json.dumps(approval.source_versions),
                },
            )

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
                    **draft.model_dump(exclude={"citations", "warnings", "error", "label"}),
                    "citations": json.dumps([c.model_dump() for c in draft.citations]),
                    "warnings": json.dumps([w.model_dump() for w in draft.warnings]),
                    "model_call_id": call_id,
                },
            )

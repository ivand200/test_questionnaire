from qws.adapters.store import Store
from qws.core.models import (
    DocumentRow,
    LoadIssue,
    OwnerRow,
    PassageRow,
    QuestionRow,
    Seed,
)
from qws.core.rules import question_hash


def load(raw_seed: dict, store: Store) -> list[LoadIssue]:
    """Insert the seed rows that are not stored yet. Return the problems found."""
    seed = Seed.model_validate(raw_seed)
    issues: list[LoadIssue] = []

    def duplicate(kind_of_row: str, row_id: str) -> None:
        issues.append(
            LoadIssue(
                kind="duplicate_id",
                id=row_id,
                message=f"Duplicate {kind_of_row} ID {row_id}; kept the first row.",
            )
        )

    seed_document_ids = {d.id for d in seed.documents}

    documents: dict[str, DocumentRow] = {}
    passages: dict[str, PassageRow] = {}
    for doc in seed.documents:
        if doc.id in documents:
            duplicate("document", doc.id)
            continue
        supersedes_id = doc.supersedes
        if supersedes_id is not None and supersedes_id not in seed_document_ids:
            issues.append(
                LoadIssue(
                    kind="missing_superseded",
                    id=doc.id,
                    message=f"Document {doc.id} supersedes {supersedes_id}, which is not in the seed.",
                )
            )
            supersedes_id = None
        documents[doc.id] = DocumentRow(
            id=doc.id,
            version=doc.version,
            date=doc.date,
            status=doc.status,
            supersedes_id=supersedes_id,
        )
        for p in doc.passages:
            if p.id in passages:
                duplicate("passage", p.id)
                continue
            passages[p.id] = PassageRow(id=p.id, document_id=doc.id, text=p.text)

    for p in seed.passages:
        document_id = p.id.split(":")[0]
        if document_id not in seed_document_ids:
            issues.append(
                LoadIssue(
                    kind="missing_document",
                    id=p.id,
                    message=f"Passage {p.id} has no document {document_id}; not stored.",
                )
            )
        elif p.id in passages:
            duplicate("passage", p.id)
        else:
            passages[p.id] = PassageRow(id=p.id, document_id=document_id, text=p.text)

    questions: dict[str, QuestionRow] = {}
    for q in seed.questions:
        if q.id in questions:
            duplicate("question", q.id)
            continue
        if q.topic not in seed.owners:
            issues.append(
                LoadIssue(
                    kind="missing_owner",
                    id=q.id,
                    message=f"Question {q.id} has topic {q.topic}, which has no owner.",
                )
            )
        questions[q.id] = QuestionRow(
            id=q.id, topic=q.topic, text=q.text, question_hash=question_hash(q.topic, q.text)
        )

    owners = [OwnerRow(topic=t, reviewer=r) for t, r in seed.owners.items()]
    store.insert_missing(
        list(documents.values()), list(passages.values()), owners, list(questions.values())
    )
    return issues

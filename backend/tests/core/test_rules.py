import hashlib

from qws.core.models import Citation, DocumentRow, PassageRow, QuestionRow
from qws.core.rules import (
    SYSTEM_PROMPT,
    allowed_actions,
    build_prompt,
    changed_sources,
    question_hash,
    question_status,
    source_versions,
    summary_counts,
    superseded_evidence,
)


def test_question_hash_is_sha256_of_topic_and_normalized_text():
    # spec: 1.1-b
    # GIVEN topic "support" and text "When is email support available?"
    # WHEN the question hash is computed
    q3 = question_hash("support", "When is email support available?")
    q1 = question_hash("exports", "Can free-plan users export CSV?")

    # THEN it is the SHA-256 hex of "support|when is email support available?"
    expected = hashlib.sha256(b"support|when is email support available?").hexdigest()
    assert q3 == expected
    assert q1 != q3


def test_question_hash_ignores_case_and_repeated_spaces_but_keeps_punctuation():
    # spec: 1.1-b
    # GIVEN the same question with other spacing and case
    # WHEN the hashes are computed
    # THEN they are equal; a different punctuation gives another hash
    a = question_hash("support", "When is email support available?")
    assert question_hash("support", "  WHEN is  email support   available? ") == a
    assert question_hash("support", "When is email support available") != a


def _passage(passage_id: str, text: str = "text") -> PassageRow:
    return PassageRow(id=passage_id, document_id=passage_id.split(":")[0], text=text)


def test_one_word_changed_in_the_system_prompt_changes_the_input_hash():
    # spec: 4.5-a
    # GIVEN the Q3 input hash h1
    # (lower interface: the hash is a pure rule; the replay half of 4.5-a is in the replay ticket)
    question = QuestionRow(id="Q3", topic="support", text="When?", question_hash="x")
    passages = [_passage("SUPPORT-v1:p1")]
    h1 = build_prompt(question, passages, "m", {"temperature": 0}).input_hash

    # WHEN one word of the system prompt changes
    changed = SYSTEM_PROMPT.replace("Never", "Always", 1)
    h2 = build_prompt(question, passages, "m", {"temperature": 0}, system=changed).input_hash

    # THEN the input hash is not h1
    assert changed != SYSTEM_PROMPT
    assert h2 != h1


def test_the_input_hash_depends_on_model_settings_question_and_passage_order():
    # spec: 4.5-a
    # GIVEN a prompt input
    question = QuestionRow(id="Q3", topic="support", text="When?", question_hash="x")
    a, b = _passage("A-v1:p1"), _passage("B-v1:p1")
    base = build_prompt(question, [a, b], "m", {"temperature": 0}).input_hash

    # WHEN one part changes
    # THEN the hash changes; the same input gives the same hash
    assert build_prompt(question, [a, b], "m", {"temperature": 0}).input_hash == base
    assert build_prompt(question, [b, a], "m", {"temperature": 0}).input_hash != base
    assert build_prompt(question, [a, b], "m2", {"temperature": 0}).input_hash != base
    assert build_prompt(question, [a, b], "m", {"temperature": 1}).input_hash != base


def test_superseded_evidence_ignores_a_cited_document_that_replaces_nothing():
    # spec: 1.3-a (lower interface: the pure rule)
    # GIVEN B replaces A; the citation is a passage of C, which replaces nothing
    documents = [
        DocumentRow(id="A", version=1, date="d", status="s", supersedes_id=None),
        DocumentRow(id="B", version=2, date="d", status="s", supersedes_id="A"),
        DocumentRow(id="C", version=1, date="d", status="s", supersedes_id=None),
    ]
    passages = [_passage("A:p1"), _passage("B:p1"), _passage("C:p1")]

    # WHEN the rule runs
    cited_c = superseded_evidence([Citation(passage_id="C:p1", excerpt="t")], documents, passages)
    cited_b = superseded_evidence([Citation(passage_id="B:p1", excerpt="t")], documents, passages)

    # THEN C gives nothing; B gives the passages of A and one warning
    assert cited_c == ([], [])
    replaced, warnings = cited_b
    assert [(r.passage_id, r.replaced_by) for r in replaced] == [("A:p1", "B")]
    assert [w.kind for w in warnings] == ["superseded"]


def _documents(export_v2_version: int = 2, export_v1_version: int = 1) -> list[DocumentRow]:
    return [
        DocumentRow(id="EXPORT-v1", version=export_v1_version, date="d", status="s", supersedes_id=None),
        DocumentRow(
            id="EXPORT-v2", version=export_v2_version, date="d", status="s", supersedes_id="EXPORT-v1"
        ),
    ]


def test_status_is_approved_over_the_draft_status_else_draft_else_new():
    # spec: 4.1-a, 4.5-a
    # GIVEN an approved snapshot, or a draft status, or neither
    documents = _documents()

    # WHEN the status is computed
    approved = question_status({"EXPORT-v2": 2}, documents, "draft")
    unresolved = question_status(None, documents, "unresolved")
    new = question_status(None, documents, None)

    # THEN approved wins over the draft status; else the draft status; else new
    assert approved == "approved"
    assert unresolved == "unresolved"
    assert new == "new"


def test_a_changed_source_in_the_snapshot_makes_needs_review():
    # spec: 2.1-a, 2.4-a
    # GIVEN the snapshot {"EXPORT-v2": 2}
    snapshot = {"EXPORT-v2": 2}

    # WHEN EXPORT-v2 is at version 3, or only EXPORT-v1 (not in the snapshot) changed
    changed = _documents(export_v2_version=3)
    other = _documents(export_v1_version=2)

    # THEN the first is needs_review with (2, 3); the second stays approved and has no change
    assert question_status(snapshot, changed, "draft") == "needs_review"
    assert changed_sources(snapshot, changed) == {"EXPORT-v2": (2, 3)}
    assert question_status(snapshot, other, "draft") == "approved"
    assert changed_sources(snapshot, other) == {}
    assert allowed_actions("needs_review") == ["edit", "approve", "leave_open"]


def test_source_versions_has_only_cited_documents_never_replaced_ones():
    # spec: 2.1-a
    # GIVEN EXPORT-v2 (version 2) replaces EXPORT-v1; the citation is a passage of EXPORT-v2
    documents = [
        DocumentRow(id="EXPORT-v1", version=1, date="d", status="s", supersedes_id=None),
        DocumentRow(id="EXPORT-v2", version=2, date="d", status="s", supersedes_id="EXPORT-v1"),
    ]
    passages = [_passage("EXPORT-v1:p1"), _passage("EXPORT-v2:p1")]

    # WHEN the snapshot is computed
    snapshot = source_versions(
        [Citation(passage_id="EXPORT-v2:p1", excerpt="t")], documents, passages
    )

    # THEN only EXPORT-v2 is in it
    assert snapshot == {"EXPORT-v2": 2}


def test_summary_counts_answered_is_draft_plus_approved():
    # spec: 5.1-b, 2.3-a
    # GIVEN statuses of 9 questions, and one needs_review
    statuses = ["approved"] + ["draft"] * 6 + ["unresolved", "error"]
    with_review = ["needs_review"] + ["draft"] * 5 + ["approved", "unresolved", "error"]

    # WHEN the counts are made
    counts = summary_counts(statuses)
    review_counts = summary_counts(with_review)

    # THEN each status is counted and answered is 7; needs_review is not in approved or answered
    assert counts.model_dump() == {
        "new": 0, "draft": 6, "unresolved": 1, "approved": 1, "needs_review": 0, "error": 1,
        "answered": 7,
    }
    assert review_counts.model_dump() == {
        "new": 0, "draft": 5, "unresolved": 1, "approved": 1, "needs_review": 1, "error": 1,
        "answered": 6,
    }

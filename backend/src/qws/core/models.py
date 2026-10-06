from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


# Rows of the seed tables (what the Store keeps).
class DocumentRow(BaseModel):
    id: str
    version: int
    date: str
    status: str
    supersedes_id: str | None


class PassageRow(BaseModel):
    id: str
    document_id: str
    text: str


class OwnerRow(BaseModel):
    topic: str
    reviewer: str


class QuestionRow(BaseModel):
    id: str
    topic: str
    text: str
    question_hash: str


class LoadIssue(BaseModel):
    kind: Literal["duplicate_id", "missing_document", "missing_superseded", "missing_owner"]
    id: str
    message: str


# The seed file as it is read.
class SeedPassage(BaseModel):
    id: str
    text: str


class SeedDocument(BaseModel):
    id: str
    version: int
    date: str
    status: str
    supersedes: str | None = None
    passages: list[SeedPassage] = Field(default_factory=list)


class SeedQuestion(BaseModel):
    id: str
    topic: str
    text: str


class Seed(BaseModel):
    documents: list[SeedDocument]
    # Optional loose passages; their document is the ID part before ":".
    passages: list[SeedPassage] = Field(default_factory=list)
    questions: list[SeedQuestion]
    owners: dict[str, str]


# Drafting.
Verdict = Literal["supported", "not_documented", "conflict"]
Status = Literal["new", "draft", "unresolved", "approved", "needs_review", "error"]
Action = Literal["generate", "retry", "edit", "approve", "leave_open", "ask_again"]
Label = Literal["real", "cached", "simulated"]


class Reply(BaseModel):
    """What the model answers. Code sets the status, never the model."""

    answer: str
    verdict: Verdict
    citations: list[str]


class Citation(BaseModel):
    passage_id: str
    excerpt: str


class ViewCitation(Citation):
    """A citation as the view shows it. `version` is the cited document's version in the approved
    snapshot; None while the answer is not approved. `current_version` is that document's version
    now."""

    version: int | None = None
    current_version: int | None = None


class UnknownQuestion:
    """No question has this ID."""


class Warning(BaseModel):
    kind: Literal["citation_not_found", "no_citation", "superseded", "source_changed"]
    passage_id: str | None = None
    message: str


class ReplacedEvidence(BaseModel):
    """A passage of a document that a cited document replaces. Shown, never sent to the model."""

    passage_id: str
    excerpt: str
    replaced_by: str  # ID of the cited document that replaces it


class Prompt(BaseModel):
    """Instructions (system) and data (user) stay in separate parts."""

    system: str
    user: str
    model: str
    settings: dict[str, int | float | str]
    passage_ids: list[str]
    input_hash: str


class Checked(BaseModel):
    status: Literal["draft", "unresolved"]
    verdict: Verdict
    answer: str
    citations: list[Citation]
    warnings: list[Warning]


class DrafterReply(BaseModel):
    """What a Drafter gives back. Exactly one of raw_reply and error is set."""

    raw_reply: str | None = None
    error: str | None = None
    label: Label
    model: str
    settings: dict[str, int | float | str]
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelCallRow(BaseModel):
    question_id: str
    input_hash: str
    prompt: str  # JSON of the system and user parts
    model: str
    settings: dict[str, int | float | str]
    raw_response: str | None
    error: str | None
    label: Label
    created_at: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None


class DraftRow(BaseModel):
    question_id: str
    status: Literal["draft", "unresolved", "error"]
    verdict: Verdict | None
    model_answer: str | None
    reviewer_answer: str | None = None
    note: str | None = None
    citations: list[Citation]
    warnings: list[Warning]
    model_call_id: int | None
    updated_at: str
    error: str | None = None  # read from the model call; never written here
    label: Label | None = None  # read from the model call; never written here


class QuestionSummary(BaseModel):
    id: str
    topic: str
    text: str
    status: Status


class SummaryCounts(BaseModel):
    new: int
    draft: int
    unresolved: int
    approved: int
    needs_review: int
    error: int
    answered: int  # draft + approved; needs_review is not in it


class RunAllResult(BaseModel):
    asked: list[str]


class ApprovedRow(BaseModel):
    """An approved answer: final wording, saved excerpts and the cited document versions."""

    question_hash: str
    question_text: str
    topic: str
    answer: str
    citations: list[Citation]
    source_versions: dict[str, int]
    approver: str
    approved_at: str


class Approval(BaseModel):
    approver: str
    approved_at: str
    source_versions: dict[str, int]


class QuestionView(BaseModel):
    id: str
    topic: str
    text: str
    status: Status
    answer: str | None
    citations: list[ViewCitation]
    warnings: list[Warning]
    owner: str | None
    replaced: list[ReplacedEvidence]
    label: Label | None
    error: str | None
    edited: bool
    note: str | None
    approved: Approval | None = None
    allowed_actions: list[Action]


class EditRequest(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApproveRequest(BaseModel):
    approver: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class BumpResult(BaseModel):
    id: str
    version: int


class LeaveOpenRequest(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReplayEntry(BaseModel):
    """One saved reply in replay/responses.json, found by input hash.

    Exactly one of raw_response and error should be set; an error entry is a Simulated entry.
    ReplayDrafter checks this for the entry of the input hash it looks up.
    """

    input_hash: str
    label: Label
    model: str
    settings: dict[str, int | float | str]
    raw_response: str | None = None
    error: str | None = None
    recorded_at: str

    @property
    def is_simulated(self) -> bool:
        return self.error is not None

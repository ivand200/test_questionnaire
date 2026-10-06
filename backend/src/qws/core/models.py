from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
Status = Literal["new", "draft", "unresolved", "error"]
Label = Literal["real", "cached", "simulated"]


class Reply(BaseModel):
    """What the model answers. Code sets the status, never the model."""

    answer: str
    verdict: Verdict
    citations: list[str]


class Citation(BaseModel):
    passage_id: str
    excerpt: str


class Warning(BaseModel):
    kind: Literal["citation_not_found", "no_citation", "superseded"]
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


class RunAllResult(BaseModel):
    asked: list[str]


class QuestionView(BaseModel):
    id: str
    topic: str
    text: str
    status: Status
    answer: str | None
    citations: list[Citation]
    warnings: list[Warning]
    owner: str | None
    replaced: list[ReplacedEvidence]
    label: Label | None
    error: str | None
    allowed_actions: list[Literal["generate", "retry"]]


class ReplayEntry(BaseModel):
    """One saved reply in replay/responses.json, found by input hash.

    Exactly one of raw_response and error is set; an error entry is a Simulated entry.
    """

    input_hash: str
    label: Label
    model: str
    settings: dict[str, int | float | str]
    raw_response: str | None = None
    error: str | None = None
    recorded_at: str

    @model_validator(mode="after")
    def _exactly_one_of_reply_and_error(self) -> "ReplayEntry":
        if (self.raw_response is None) == (self.error is None):
            raise ValueError("exactly one of raw_response and error must be set")
        return self

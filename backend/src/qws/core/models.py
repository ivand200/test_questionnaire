from typing import Literal

from pydantic import BaseModel, Field


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

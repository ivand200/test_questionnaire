-- Seed tables: written by SeedLoader, read only afterwards.
-- App tables (model_call, draft, approved_answer): written by services.

CREATE TABLE IF NOT EXISTS document (
    id            TEXT PRIMARY KEY,
    version       INTEGER NOT NULL,
    date          TEXT NOT NULL,
    status        TEXT NOT NULL,  -- label only, never used for authority
    -- NULL when the target is missing (reported as a load issue). Deferred so
    -- rows of one seed can be inserted in any order.
    supersedes_id TEXT REFERENCES document (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS passage (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document (id),
    text        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS owner (
    topic    TEXT PRIMARY KEY,
    reviewer TEXT NOT NULL
);

-- topic has no foreign key to owner: a question with no owner still loads.
CREATE TABLE IF NOT EXISTS question (
    id            TEXT PRIMARY KEY,
    topic         TEXT NOT NULL,
    text          TEXT NOT NULL,
    question_hash TEXT NOT NULL  -- not unique: a repeated question is normal
);
CREATE INDEX IF NOT EXISTS question_hash_idx ON question (question_hash);

CREATE TABLE IF NOT EXISTS model_call (
    id            INTEGER PRIMARY KEY,
    question_id   TEXT NOT NULL REFERENCES question (id),
    input_hash    TEXT NOT NULL,
    prompt        TEXT NOT NULL,
    model         TEXT NOT NULL,
    settings      TEXT NOT NULL,  -- JSON
    raw_response  TEXT,
    error         TEXT,
    label         TEXT NOT NULL CHECK (label IN ('real', 'cached', 'simulated')),
    created_at    TEXT NOT NULL,
    latency_ms    INTEGER,
    input_tokens  INTEGER,        -- NULL on cached and simulated rows
    output_tokens INTEGER
);

CREATE TABLE IF NOT EXISTS draft (
    question_id     TEXT PRIMARY KEY REFERENCES question (id),
    status          TEXT NOT NULL CHECK (status IN ('draft', 'unresolved', 'error')),
    verdict         TEXT CHECK (verdict IN ('supported', 'not_documented', 'conflict')),
    model_answer    TEXT,
    reviewer_answer TEXT,
    note            TEXT,
    citations       TEXT NOT NULL DEFAULT '[]',  -- JSON
    warnings        TEXT NOT NULL DEFAULT '[]',  -- JSON
    model_call_id   INTEGER REFERENCES model_call (id),
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approved_answer (
    id              INTEGER PRIMARY KEY,
    question_hash   TEXT NOT NULL UNIQUE,
    question_text   TEXT NOT NULL,
    topic           TEXT NOT NULL,
    answer          TEXT NOT NULL,
    citations       TEXT NOT NULL,  -- JSON
    source_versions TEXT NOT NULL,  -- JSON
    approver        TEXT NOT NULL,
    approved_at     TEXT NOT NULL
);

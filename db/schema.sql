-- Git Activity Digest Agent — SQLite schema

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
    tags        TEXT,
    phase       TEXT,
    department  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    commit_hash     TEXT NOT NULL,
    author_name     TEXT,
    author_email    TEXT,
    committer_name  TEXT,
    committer_email TEXT,
    authored_at     TEXT NOT NULL,      -- ISO 8601, local time of the commit
    committed_at    TEXT NOT NULL,
    message         TEXT,
    branch          TEXT,
    parent_hashes   TEXT,               -- comma-separated (merges have 2+)
    files_changed   INTEGER DEFAULT 0,
    insertions      INTEGER DEFAULT 0,
    deletions       INTEGER DEFAULT 0,
    diff_path       TEXT,               -- relative path under DIFF_STORAGE_PATH, NULL if excluded/empty
    git_tags        TEXT,               -- comma-separated tags pointing at this commit
    collected_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, commit_hash)
);

CREATE INDEX IF NOT EXISTS idx_commits_project_authored ON commits(project_id, authored_at);
CREATE INDEX IF NOT EXISTS idx_commits_authored_date ON commits(date(authored_at));

CREATE TABLE IF NOT EXISTS notes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    note_date         TEXT NOT NULL,    -- YYYY-MM-DD, the day this note is associated with
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    text              TEXT NOT NULL,
    duration_minutes  INTEGER,
    tag               TEXT CHECK (tag IN ('meeting', 'demo', 'discussion', 'blocker', 'idea') OR tag IS NULL),
    project_id        INTEGER REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_date ON notes(note_date);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date      TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD
    narrative         TEXT,
    project_bullets   TEXT,              -- JSON: [{"project": "...", "bullets": ["...", "..."]}]
    other_activities  TEXT,              -- JSON: ["...", "..."] derived from notes
    model_used        TEXT,
    generated_at      TEXT,
    edited            INTEGER NOT NULL DEFAULT 0  -- 0/1 boolean
);

CREATE TABLE IF NOT EXISTS rollup_summaries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type       TEXT NOT NULL CHECK (period_type IN ('week', 'month')),
    period_start      TEXT NOT NULL,     -- YYYY-MM-DD
    period_end        TEXT NOT NULL,     -- YYYY-MM-DD
    narrative         TEXT,
    project_bullets   TEXT,              -- JSON, same shape as daily_summaries
    other_activities  TEXT,              -- JSON
    model_used        TEXT,
    generated_at      TEXT,
    edited            INTEGER NOT NULL DEFAULT 0,
    UNIQUE (period_type, period_start)
);

CREATE TABLE IF NOT EXISTS tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    text           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    due_date       TEXT,               -- YYYY-MM-DD, optional
    project_id     INTEGER REFERENCES projects(id) ON DELETE SET NULL,  -- optional, blank = generic
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT
);

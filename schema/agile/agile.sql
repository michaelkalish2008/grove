-- grove/schema/agile/board.sql
-- Agile board: epics, stories, sprints, ceremonies, learnings, skills

-- ── Epics ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS epics (
    id           INTEGER PRIMARY KEY,
    slug         TEXT UNIQUE NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    status       TEXT DEFAULT 'backlog',  -- backlog|active|done
    priority     INTEGER DEFAULT 50,      -- lower = higher priority
    created_at   TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- ── Stories ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stories (
    id           INTEGER PRIMARY KEY,
    epic_id      INTEGER NOT NULL REFERENCES epics(id),
    title        TEXT NOT NULL,
    description  TEXT,
    acceptance   TEXT,                   -- done criteria (markdown checklist)
    output       TEXT,                   -- artifact produced: file path, table, route
    refs         TEXT DEFAULT '[]',      -- JSON array of file paths to read before starting
    points       INTEGER,
    status       TEXT DEFAULT 'backlog', -- backlog|ready|in-progress|review|blocked|done|recurring
    branch       TEXT,
    is_recurring INTEGER DEFAULT 0,      -- 1 = ceremony; copied into every new sprint
    created_at   TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS story_deps (
    story_id    INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    blocks_id   INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, blocks_id),
    CHECK (story_id != blocks_id)
);

-- ── Sprints ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sprints (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    goal        TEXT,
    start_date  TEXT,
    end_date    TEXT,
    status      TEXT DEFAULT 'planned',  -- planned|active|closed
    velocity    INTEGER                  -- points completed at close
);

CREATE TABLE IF NOT EXISTS sprint_stories (
    sprint_id   INTEGER NOT NULL REFERENCES sprints(id),
    story_id    INTEGER NOT NULL REFERENCES stories(id),
    committed   INTEGER DEFAULT 1,  -- 1=committed, 0=stretch
    PRIMARY KEY (sprint_id, story_id)
);

-- ── Retrospectives & Standups ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS retrospectives (
    id           INTEGER PRIMARY KEY,
    sprint_id    INTEGER NOT NULL REFERENCES sprints(id) UNIQUE,
    went_well    TEXT,
    to_improve   TEXT,
    action_items TEXT,  -- JSON array of {owner, item, due}
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS standups (
    id          INTEGER PRIMARY KEY,
    sprint_id   INTEGER NOT NULL REFERENCES sprints(id),
    did         TEXT,   -- what was completed this session
    next        TEXT,   -- what will be worked on next session
    blockers    TEXT,   -- what is slowing velocity (NULL if none)
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── Learnings ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS learnings (
    id                INTEGER PRIMARY KEY,
    category          TEXT NOT NULL,  -- velocity|technical|process|collaboration
    title             TEXT NOT NULL,
    body              TEXT,
    source            TEXT,           -- retro|session|manual
    sprint_id         INTEGER REFERENCES sprints(id),
    created_at        TEXT DEFAULT (datetime('now')),
    embedding_path    TEXT,           -- .npy written by embed_learnings.py
    consolidated_into INTEGER REFERENCES learnings(id),
    is_canonical      INTEGER DEFAULT 1  -- 0 = tombstoned by consolidate_learnings.py
);

-- ── Skills registry ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,  -- fetch|inspect|process|embed|cluster|search|publish|stats|maintain|utils
    status      TEXT DEFAULT 'planned',  -- planned|ready|active|deprecated
    script_path TEXT,           -- relative path, e.g. scripts/search/semantic_search.py
    story_id    INTEGER REFERENCES stories(id),
    description TEXT,
    inputs      TEXT,           -- JSON: {name, type, description}[]
    outputs     TEXT,           -- JSON: stdout schema
    deps        TEXT,           -- JSON: [skill_slug | table_name]
    example     TEXT,           -- runnable example command
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_stories_status    ON stories(status);
CREATE INDEX IF NOT EXISTS idx_stories_epic      ON stories(epic_id);
CREATE INDEX IF NOT EXISTS idx_stories_recurring ON stories(is_recurring);
CREATE INDEX IF NOT EXISTS idx_story_deps        ON story_deps(story_id);
CREATE INDEX IF NOT EXISTS idx_sprint_stories    ON sprint_stories(sprint_id);
CREATE INDEX IF NOT EXISTS idx_standups_sprint   ON standups(sprint_id);
CREATE INDEX IF NOT EXISTS idx_skills_category   ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_status     ON skills(status);

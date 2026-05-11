-- grove/schema/swarm/swarm.sql
-- Judge scores for sampled LocalReActAgent outputs.
-- Applied by: grove.init(db, modules=["swarm"])

CREATE TABLE IF NOT EXISTS judge_scores (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    scored_at          TEXT    DEFAULT (datetime('now')),
    worker_id          INTEGER NOT NULL,
    worker_model       TEXT    NOT NULL,
    subtask            TEXT,
    prompt_version     TEXT    NOT NULL,
    accuracy           INTEGER CHECK (accuracy BETWEEN 0 AND 10),
    conciseness        INTEGER CHECK (conciseness BETWEEN 0 AND 10),
    hallucination_risk INTEGER CHECK (hallucination_risk BETWEEN 0 AND 10),
    tone               INTEGER CHECK (tone BETWEEN 0 AND 10),
    style_match        INTEGER CHECK (style_match BETWEEN 0 AND 10),
    overall            REAL,
    elapsed_s          REAL,
    raw_response       TEXT
);

CREATE INDEX IF NOT EXISTS idx_judge_scores_model
    ON judge_scores (worker_model, prompt_version);

CREATE INDEX IF NOT EXISTS idx_judge_scores_scored_at
    ON judge_scores (scored_at);

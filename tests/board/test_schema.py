"""Tests: agile schema correctness and grove.init() module registry."""

import sqlite3
from pathlib import Path

import grove


EXPECTED_TABLES = {
    "epics", "stories", "story_deps", "sprints", "sprint_stories",
    "retrospectives", "standups", "learnings", "skills",
}


def test_schema_creates_all_tables(db):
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"


def test_epics_slug_unique(db):
    db.execute("INSERT INTO epics (slug, title) VALUES ('alpha', 'Alpha')")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO epics (slug, title) VALUES ('alpha', 'Duplicate')")
        db.commit()


def test_stories_require_epic(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO stories (epic_id, title) VALUES (999, 'Orphan')")
        db.commit()


def test_grove_init_creates_module_registry(tmp_path):
    db_path = tmp_path / "grove.db"
    conn = grove.init(db_path, modules=["board"])
    conn.close()

    installed = grove.modules(db_path)
    assert "board" in installed


def test_grove_init_idempotent(tmp_path):
    db_path = tmp_path / "grove.db"
    grove.init(db_path, modules=["board"]).close()
    grove.init(db_path, modules=["board"]).close()  # second call must not raise

    installed = grove.modules(db_path)
    assert installed.count("board") == 1  # not duplicated


import pytest

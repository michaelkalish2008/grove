"""
conftest.py — shared fixtures for grove[board] tests.

FakeDB: in-memory SQLite with agile schema applied.
All tests use :memory: — no files created, no cleanup needed.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure grove package is importable from repo root
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

AGILE_SQL = REPO_ROOT / "schema" / "agile" / "agile.sql"
SCRIPTS_DIR = REPO_ROOT / "grove" / "board" / "scripts"


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory SQLite with full agile schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(AGILE_SQL.read_text())
    conn.commit()
    return conn


@pytest.fixture
def db_path(tmp_path) -> Path:
    """On-disk SQLite in a temp dir — for scripts that require a real file path."""
    p = tmp_path / "grove.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(AGILE_SQL.read_text())
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def seeded_db(db) -> sqlite3.Connection:
    """In-memory DB with one epic, one sprint, and three stories seeded."""
    db.execute("INSERT INTO epics (slug, title) VALUES ('test', 'Test Epic')")
    db.execute("""
        INSERT INTO sprints (name, goal, start_date, end_date, status)
        VALUES ('S01', 'Test sprint', '2026-01-01', '2026-01-14', 'active')
    """)
    db.executemany("""
        INSERT INTO stories (epic_id, title, points, status)
        VALUES (1, ?, ?, ?)
    """, [
        ("Story A", 3, "ready"),
        ("Story B", 2, "in-progress"),
        ("Story C", 1, "done"),
    ])
    db.commit()
    return db

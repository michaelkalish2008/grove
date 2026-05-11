"""Tests: validate_board.py checks using on-disk DB (scripts require real file)."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "grove" / "board" / "scripts"


def run_validate(db_path: Path, fix: bool = False) -> tuple[int, str]:
    cmd = [sys.executable, str(SCRIPTS / "validate_board.py"), "--db", str(db_path)]
    if fix:
        cmd.append("--fix")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def test_validate_clean_board(db_path):
    """Empty board (no stories) passes validation with no errors."""
    rc, out = run_validate(db_path)
    assert rc == 0
    assert "ERROR" not in out.upper() or "0 error" in out.lower()


def test_validate_detects_unpointed_sprint_story(db_path):
    """Stories in sprint without points are flagged."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO epics (slug, title) VALUES ('e', 'E')")
    conn.execute("INSERT INTO stories (epic_id, title, points) VALUES (1, 'No points', NULL)")
    conn.execute("INSERT INTO sprints (name, goal, start_date, end_date, status) VALUES ('S01','g','2026-01-01','2026-01-14','active')")
    conn.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1, 1)")
    conn.commit()
    conn.close()

    rc, out = run_validate(db_path)
    # Should warn about unpointed story (non-zero exit or warning in output)
    assert "unpointed" in out.lower() or rc != 0


def test_validate_detects_orphaned_sprint_story(db_path):
    """sprint_stories row pointing to non-existent story is flagged."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO sprints (name, goal, start_date, end_date, status) VALUES ('S01','g','2026-01-01','2026-01-14','active')")
    # Insert orphaned sprint_story (no FK enforcement in SQLite by default)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1, 999)")
    conn.commit()
    conn.close()

    rc, out = run_validate(db_path)
    assert "orphan" in out.lower() or rc != 0

"""Tests: story CRUD and status transitions via direct DB (no script dependency)."""

import sqlite3

import pytest


def test_create_story(seeded_db):
    rows = seeded_db.execute("SELECT * FROM stories ORDER BY id").fetchall()
    assert len(rows) == 3
    assert rows[0]["title"] == "Story A"
    assert rows[0]["status"] == "ready"


def test_story_points_nullable(db):
    db.execute("INSERT INTO epics (slug, title) VALUES ('e', 'E')")
    db.execute("INSERT INTO stories (epic_id, title) VALUES (1, 'No points yet')")
    db.commit()
    row = db.execute("SELECT points FROM stories WHERE title='No points yet'").fetchone()
    assert row["points"] is None


def test_story_status_transition(seeded_db):
    seeded_db.execute("UPDATE stories SET status='done', completed_at=datetime('now') WHERE id=1")
    seeded_db.commit()
    row = seeded_db.execute("SELECT status, completed_at FROM stories WHERE id=1").fetchone()
    assert row["status"] == "done"
    assert row["completed_at"] is not None


def test_sprint_story_assignment(seeded_db):
    seeded_db.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1, 1)")
    seeded_db.commit()
    row = seeded_db.execute(
        "SELECT COUNT(*) AS n FROM sprint_stories WHERE sprint_id=1"
    ).fetchone()
    assert row["n"] == 1


def test_sprint_story_no_duplicate(seeded_db):
    seeded_db.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1, 1)")
    seeded_db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        seeded_db.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1, 1)")
        seeded_db.commit()


def test_learning_links_to_sprint(seeded_db):
    seeded_db.execute("""
        INSERT INTO learnings (sprint_id, category, title, body)
        VALUES (1, 'technical', 'Test insight', 'Root cause found.')
    """)
    seeded_db.commit()
    row = seeded_db.execute("SELECT * FROM learnings WHERE sprint_id=1").fetchone()
    assert row["category"] == "technical"
    assert row["is_canonical"] == 1  # default: canonical until tombstoned by consolidation


def test_velocity_query(seeded_db):
    """Velocity = sum of points for done stories in sprint."""
    seeded_db.execute("INSERT INTO sprint_stories (sprint_id, story_id) VALUES (1,1),(1,2),(1,3)")
    seeded_db.commit()
    row = seeded_db.execute("""
        SELECT SUM(s.points) AS velocity
        FROM stories s
        JOIN sprint_stories ss ON ss.story_id = s.id
        WHERE ss.sprint_id = 1 AND s.status = 'done'
    """).fetchone()
    assert row["velocity"] == 1  # only Story C (1pt) is done

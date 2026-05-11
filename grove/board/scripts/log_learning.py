"""
Skill: log_learning
Domain: maintain
Purpose: Write a learning to the learnings table immediately when an insight is identified.
         Call this inline during any session — do not batch for end of session.

Inputs:
  --category   velocity | technical | process | collaboration
  --title      Short title (one line)
  --body       Full explanation — include root cause, fix, and how to avoid recurrence
  --source     session (default) | retro | manual
  --db         Path to grove.db (default: data/grove.db)

Output (stdout): JSON {id, category, title, created_at}

Example:
  python3 scripts/maintain/log_learning.py \\
    --category technical \\
    --title "Flask tojson + HTML attrs: use forceescape" \\
    --body "tojson returns Markup; | e no-ops on Markup. Use | forceescape in HTML attrs."

Design:
  - One concern: write a learning row. No embedding here — that runs nightly via embed_learnings.py.
  - Idempotency: no dedup at write time. Consolidation happens separately via consolidate_learnings.py.
  - is_canonical defaults to 1; consolidation may set it to 0 and point consolidated_into to the
    canonical row that absorbed this one.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from _project import project_root as ROOT, db_path as DB_PATH
VALID_CATEGORIES = {"velocity", "technical", "process", "collaboration"}
VALID_SOURCES    = {"session", "retro", "manual"}


def get_active_sprint_id(db: sqlite3.Connection) -> int | None:
    row = db.execute("SELECT id FROM sprints WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Log a learning to the learnings table.")
    parser.add_argument("--category", required=True, choices=sorted(VALID_CATEGORIES))
    parser.add_argument("--title",    required=True)
    parser.add_argument("--body",     required=True)
    parser.add_argument("--source",   default="session", choices=sorted(VALID_SOURCES))
    parser.add_argument("--db",       default=str(DB_PATH))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    sprint_id = get_active_sprint_id(db)

    cur = db.execute(
        """
        INSERT INTO learnings (category, title, body, source, sprint_id, is_canonical)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (args.category, args.title, args.body, args.source, sprint_id),
    )
    db.commit()

    row = db.execute(
        "SELECT id, category, title, created_at FROM learnings WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()

    print(json.dumps(dict(row)))
    db.close()


if __name__ == "__main__":
    main()

"""
Skill: update_story
Domain: maintain
Purpose: Update a story's status (and optionally branch/points) through the canonical
         transition path. All board mutations go through this script — not ad hoc SQL.

Inputs:
  --id        Story id (required)
  --status    backlog|ready|in-progress|review|blocked|done
  --branch    Git branch name (set when moving to in-progress)
  --points    Story points (set during refinement)
  --db        Path to grove.db (default: data/grove.db)

Output (stdout): JSON {id, title, old_status, new_status, branch, points}

Rules:
  - Moving to 'in-progress' requires --branch (warns if missing, does not block)
  - Moving to 'done' sets completed_at = datetime('now') automatically
  - Moving away from 'done' clears completed_at
  - Status must be a valid value; invalid status exits with code 1

Example:
  python3 scripts/maintain/update_story.py --id 3 --status in-progress --branch feat/testing-framework
  python3 scripts/maintain/update_story.py --id 3 --status done
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from _project import project_root as ROOT, db_path as DB_PATH
VALID_STATUSES = {"backlog", "ready", "in-progress", "review", "blocked", "done", "recurring"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a story's status on the board.")
    parser.add_argument("--id",     required=True, type=int)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--branch", default=None)
    parser.add_argument("--points", default=None, type=int)
    parser.add_argument("--db",     default=str(DB_PATH))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    story = db.execute("SELECT * FROM stories WHERE id=?", (args.id,)).fetchone()
    if not story:
        print(json.dumps({"error": f"Story {args.id} not found"}), file=sys.stderr)
        db.close()
        sys.exit(1)

    old_status = story["status"]

    # Warn if moving to in-progress without a branch
    if args.status == "in-progress" and not (args.branch or story["branch"]):
        print(
            json.dumps({"warning": "Moving to in-progress without a branch. "
                        "Set --branch feat/<slug> to enable git context recovery."}),
            file=sys.stderr,
        )

    # Build update
    fields: dict = {"status": args.status}
    if args.status == "done":
        fields["completed_at"] = "datetime('now')"
    elif old_status == "done":
        fields["completed_at"] = None
    if args.branch is not None:
        fields["branch"] = args.branch
    if args.points is not None:
        fields["points"] = args.points

    # Build SQL — completed_at uses SQLite datetime() function, not a bind param
    set_parts = []
    bind_vals = []
    for k, v in fields.items():
        if k == "completed_at" and v == "datetime('now')":
            set_parts.append(f"{k} = datetime('now')")
        elif k == "completed_at" and v is None:
            set_parts.append(f"{k} = NULL")
        else:
            set_parts.append(f"{k} = ?")
            bind_vals.append(v)
    bind_vals.append(args.id)

    db.execute(f"UPDATE stories SET {', '.join(set_parts)} WHERE id=?", bind_vals)
    db.commit()

    updated = db.execute("SELECT * FROM stories WHERE id=?", (args.id,)).fetchone()
    print(json.dumps({
        "id":         updated["id"],
        "title":      updated["title"],
        "old_status": old_status,
        "new_status": updated["status"],
        "branch":     updated["branch"],
        "points":     updated["points"],
    }))
    db.close()


if __name__ == "__main__":
    main()

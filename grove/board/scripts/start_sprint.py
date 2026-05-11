"""
Skill: start_sprint
Domain: maintain
Purpose: Create a new sprint, copy recurring ceremony stories into it, and pull in
         any ready/backlog stories nominated for the sprint. Runs after close_sprint.py.

Inputs:
  --name      Sprint name e.g. S02 (required)
  --goal      Sprint goal text (required)
  --start     Start date YYYY-MM-DD (default: today)
  --end       End date YYYY-MM-DD (default: today + 14 days)
  --stories   Comma-separated story IDs to commit to this sprint (optional)
  --db        Path to grove.db (default: data/grove.db)

Output (stdout): JSON {sprint_id, name, goal, start_date, end_date, stories_added}

Design:
  - Fails if an active sprint already exists (must close first).
  - Recurring stories (is_recurring=1) are always copied in — these are the ceremonies.
  - Additional story IDs passed via --stories are committed (committed=1).
  - Stories not yet pointed are warned but not blocked.
"""

import argparse
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from _project import project_root as ROOT, db_path as DB_PATH
def main() -> None:
    parser = argparse.ArgumentParser(description="Start a new sprint.")
    parser.add_argument("--name",    required=True)
    parser.add_argument("--goal",    required=True)
    parser.add_argument("--start",   default=date.today().isoformat())
    parser.add_argument("--end",     default=(date.today() + timedelta(days=14)).isoformat())
    parser.add_argument("--stories", default="")
    parser.add_argument("--db",      default=str(DB_PATH))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # Guard: no active sprint
    active = db.execute("SELECT id FROM sprints WHERE status='active'").fetchone()
    if active:
        print(json.dumps({"error": "Active sprint exists. Run close_sprint.py first."}),
              file=sys.stderr)
        db.close()
        sys.exit(1)

    # Create sprint
    cur = db.execute(
        "INSERT INTO sprints (name, goal, start_date, end_date, status) VALUES (?,?,?,?,'active')",
        (args.name, args.goal, args.start, args.end),
    )
    sprint_id = cur.lastrowid

    # Copy recurring stories
    recurring = db.execute(
        "SELECT id, points FROM stories WHERE is_recurring=1"
    ).fetchall()
    for s in recurring:
        db.execute(
            "INSERT OR IGNORE INTO sprint_stories (sprint_id, story_id, committed) VALUES (?,?,1)",
            (sprint_id, s["id"]),
        )

    # Add nominated stories
    warnings = []
    story_ids = [int(x.strip()) for x in args.stories.split(",") if x.strip()]
    added = list(recurring)
    for sid in story_ids:
        s = db.execute("SELECT id, title, points FROM stories WHERE id=?", (sid,)).fetchone()
        if not s:
            warnings.append(f"Story {sid} not found")
            continue
        if s["points"] is None:
            warnings.append(f"Story {sid} '{s['title']}' has no points — add before sprint")
        db.execute(
            "INSERT OR IGNORE INTO sprint_stories (sprint_id, story_id, committed) VALUES (?,?,1)",
            (sprint_id, sid),
        )
        added.append(s)

    db.execute(
        """INSERT INTO pipeline_runs (script, trigger, files_in, files_ok, status)
           VALUES ('start_sprint.py', 'manual', ?, ?, 'ok')""",
        (len(story_ids), len(story_ids)),
    )
    db.commit()
    db.close()

    result = {
        "sprint_id":     sprint_id,
        "name":          args.name,
        "goal":          args.goal,
        "start_date":    args.start,
        "end_date":      args.end,
        "stories_added": len(added),
    }
    if warnings:
        result["warnings"] = warnings
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

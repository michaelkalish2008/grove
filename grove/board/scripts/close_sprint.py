"""
Skill: close_sprint
Domain: maintain
Purpose: Close the active sprint. Archive done stories (they remain in sprint_stories
         with the closed sprint). Carry incomplete stories forward to backlog.
         Compute and write velocity. Run every Monday morning (cron) or manually
         at sprint close ceremony.

Inputs:
  --db        Path to grove.db (default: data/grove.db)
  --dry-run   Print what would happen without writing

Output (stdout): JSON {
  sprint_id, sprint_name, velocity,
  done: [story titles],
  carried: [story titles],
  status: "closed"
}

Schedule: Monday 06:00 (cron). Also called manually at retro.

Design:
  - Only one sprint can be active. Exits with error if none found.
  - Done stories stay in sprint_stories for the closed sprint (archive record).
  - Incomplete non-recurring stories: status reset to 'ready', removed from sprint_stories
    so they appear in backlog and can be pulled into next sprint during planning.
  - Recurring stories: left in sprint_stories (they get re-copied by start_sprint.py).
  - velocity = sum of points for done stories in the sprint.
  - Writes a pipeline_runs row on completion.
"""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from _project import project_root as ROOT, db_path as DB_PATH
INCOMPLETE = {"backlog", "ready", "in-progress", "review", "blocked"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Close the active sprint.")
    parser.add_argument("--db",      default=str(DB_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    sprint = db.execute(
        "SELECT * FROM sprints WHERE status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not sprint:
        print(json.dumps({"error": "No active sprint found."}), file=sys.stderr)
        db.close()
        sys.exit(1)

    sprint_stories = db.execute("""
        SELECT s.id, s.title, s.status, s.points, s.is_recurring
        FROM stories s
        JOIN sprint_stories ss ON ss.story_id = s.id
        WHERE ss.sprint_id = ?
    """, (sprint["id"],)).fetchall()

    done     = [s for s in sprint_stories if s["status"] == "done"]
    carried  = [s for s in sprint_stories if s["status"] in INCOMPLETE and not s["is_recurring"]]
    velocity = sum(s["points"] or 0 for s in done)

    result = {
        "sprint_id":   sprint["id"],
        "sprint_name": sprint["name"],
        "velocity":    velocity,
        "done":        [s["title"] for s in done],
        "carried":     [s["title"] for s in carried],
        "status":      "closed",
    }

    if args.dry_run:
        result["dry_run"] = True
        print(json.dumps(result, indent=2))
        db.close()
        return

    # Carry incomplete stories back to backlog
    for s in carried:
        db.execute("UPDATE stories SET status='ready' WHERE id=?", (s["id"],))
        db.execute(
            "DELETE FROM sprint_stories WHERE sprint_id=? AND story_id=?",
            (sprint["id"], s["id"]),
        )

    # Close sprint + write velocity
    db.execute(
        "UPDATE sprints SET status='closed', velocity=?, end_date=? WHERE id=?",
        (velocity, date.today().isoformat(), sprint["id"]),
    )

    db.execute(
        """INSERT INTO pipeline_runs (script, trigger, files_in, files_ok, status)
           VALUES ('close_sprint.py', 'scheduled', ?, ?, 'ok')""",
        (len(sprint_stories), len(done)),
    )
    db.commit()
    db.close()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

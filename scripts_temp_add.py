"""
Skill: add_story
Domain: maintain
Purpose: Create a new story (and optionally add it to the active sprint).
         Validates refs exist on disk before writing. Looks up epic by slug.

Inputs:
  --epic        Epic slug (required)
  --title       Story title (required)
  --points      Story points (integer, optional — warn if missing)
  --status      Initial status (default: ready)
  --desc        Description text
  --acceptance  Done-criteria text (markdown checklist)
  --output      Artifact produced: file path, table, route, etc.
  --refs        Comma-separated relative file paths to read before starting
  --branch      Git branch name
  --recurring   Flag: mark story as a recurring ceremony
  --sprint      Flag: add to active sprint after creation
  --db          Path to grove.db (default: data/grove.db)

Output (stdout): JSON {id, title, epic, status, points, refs, warnings}

Design:
  - Exits with code 1 if epic slug not found.
  - Warns (does not block) if a ref path does not exist on disk.
  - Warns if --sprint requested but no active sprint.
  - All inserts in a single transaction.
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
    parser = argparse.ArgumentParser(description="Add a new story to the board.")
    parser.add_argument("--epic",       required=True)
    parser.add_argument("--title",      required=True)
    parser.add_argument("--points",     type=int, default=None)
    parser.add_argument("--status",     default="ready", choices=sorted(VALID_STATUSES))
    parser.add_argument("--desc",       default=None)
    parser.add_argument("--acceptance", default=None)
    parser.add_argument("--output",     default=None)
    parser.add_argument("--refs",       default="")
    parser.add_argument("--branch",     default=None)
    parser.add_argument("--recurring",  action="store_true")
    parser.add_argument("--sprint",     action="store_true", help="Add to active sprint")
    parser.add_argument("--db",         default=str(DB_PATH))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    warnings: list[str] = []

    # Resolve epic
    epic = db.execute("SELECT id, slug FROM epics WHERE slug=?", (args.epic,)).fetchone()
    if not epic:
        slugs = [r["slug"] for r in db.execute("SELECT slug FROM epics ORDER BY slug").fetchall()]
        print(json.dumps({"error": f"Epic '{args.epic}' not found. Available: {slugs}"}),
              file=sys.stderr)
        db.close()
        sys.exit(1)

    # Validate refs
    ref_list: list[str] = [r.strip() for r in args.refs.split(",") if r.strip()]
    for ref in ref_list:
        if not (ROOT / ref).exists():
            warnings.append(f"Ref not found on disk: {ref}")

    if args.points is None:
        warnings.append("No points set — add before sprint planning")

    is_recurring = 1 if args.recurring else 0
    status = "recurring" if args.recurring else args.status

    # Insert story
    cur = db.execute("""
        INSERT INTO stories
            (epic_id, title, description, acceptance, output, refs,
             points, status, branch, is_recurring)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        epic["id"],
        args.title,
        args.desc,
        args.acceptance,
        args.output,
        json.dumps(ref_list),
        args.points,
        status,
        args.branch,
        is_recurring,
    ))
    story_id = cur.lastrowid

    # Optionally add to active sprint
    sprint_id = None
    if args.sprint:
        sprint = db.execute(
            "SELECT id FROM sprints WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if sprint:
            sprint_id = sprint["id"]
            db.execute(
                "INSERT OR IGNORE INTO sprint_stories (sprint_id, story_id, committed) VALUES (?,?,1)",
                (sprint_id, story_id),
            )
        else:
            warnings.append("--sprint requested but no active sprint found; story not added to sprint")

    db.execute(
        """INSERT INTO pipeline_runs (script, trigger, files_in, files_ok, status)
           VALUES ('add_story.py', 'manual', 1, 1, 'ok')"""
    )
    db.commit()
    db.close()

    result: dict = {
        "id":       story_id,
        "title":    args.title,
        "epic":     args.epic,
        "status":   status,
        "points":   args.points,
        "refs":     ref_list,
    }
    if sprint_id:
        result["sprint_id"] = sprint_id
    if warnings:
        result["warnings"] = warnings
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

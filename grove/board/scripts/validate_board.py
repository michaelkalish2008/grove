"""
Skill: validate_board
Domain: maintain
Purpose: Audit the board for common integrity problems and optionally fix them.
         Run at session start or after bulk edits to catch drift early.

Checks:
  1. Dead refs — story refs pointing to files that don't exist on disk
  2. Wrong path prefixes — legacy db/schema/, db/queries/, db/seeds/ prefixes
  3. Unpointed sprint stories — stories in active sprint with no points
  4. Schema coverage — tables in live DB not covered by any schema/*.sql file
  5. Orphaned sprint stories — sprint_stories rows for deleted stories/sprints

Inputs:
  --fix     Auto-fix what can be fixed deterministically:
              - Rewrite wrong path prefixes (db/schema/ → schema/, etc.)
  --db      Path to grove.db (default: data/grove.db)

Output (stdout): JSON {checks: {name: {status, count, items}}, fixed}

Design:
  - Default (no --fix): report only, no writes.
  - --fix: rewrite fixable issues; re-report to confirm clean.
  - Non-fixable issues (dead refs, unpointed stories) always report only.
"""

import argparse
import json
import sqlite3
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from _project import project_root as ROOT, db_path as DB_PATH
# Known wrong → correct prefix substitutions
PREFIX_FIXES = {
    "db/schema/":  "schema/",
    "db/queries/": "schema/queries/",
    "db/seeds/":   "schema/",
}


def check_dead_refs(db, fix: bool) -> dict:
    rows = db.execute(
        "SELECT id, title, refs FROM stories WHERE refs IS NOT NULL AND refs != '[]'"
    ).fetchall()
    dead, fixed = [], 0

    for row in rows:
        refs = json.loads(row["refs"])
        new_refs = list(refs)

        for i, ref in enumerate(refs):
            # Apply prefix fixes first if requested
            if fix:
                for wrong, right in PREFIX_FIXES.items():
                    if ref.startswith(wrong):
                        new_refs[i] = ref.replace(wrong, right, 1)
                        ref = new_refs[i]

            if not (ROOT / ref).exists():
                dead.append({"story_id": row["id"], "title": row["title"], "ref": ref})

        if fix and new_refs != refs:
            db.execute("UPDATE stories SET refs=? WHERE id=?",
                       (json.dumps(new_refs), row["id"]))
            fixed += 1

    if fix:
        db.commit()

    return {
        "status": "ok" if not dead else "warn",
        "count":  len(dead),
        "items":  dead,
        "fixed":  fixed,
    }


def check_prefix_drift(db) -> dict:
    """Report refs with legacy db/ prefixes (without fixing)."""
    rows = db.execute(
        "SELECT id, title, refs FROM stories WHERE refs IS NOT NULL AND refs != '[]'"
    ).fetchall()
    drifted = []
    for row in rows:
        for ref in json.loads(row["refs"]):
            for wrong in PREFIX_FIXES:
                if ref.startswith(wrong):
                    drifted.append({"story_id": row["id"], "title": row["title"], "ref": ref})
    return {
        "status": "ok" if not drifted else "warn",
        "count":  len(drifted),
        "items":  drifted,
    }


def check_unpointed(db) -> dict:
    rows = db.execute("""
        SELECT s.id, s.title, s.status
        FROM stories s
        JOIN sprint_stories ss ON ss.story_id = s.id
        JOIN sprints sp        ON sp.id = ss.sprint_id
        WHERE sp.status = 'active'
          AND s.is_recurring = 0
          AND (s.points IS NULL OR s.points = 0)
    """).fetchall()
    items = [{"id": r["id"], "title": r["title"], "status": r["status"]} for r in rows]
    return {
        "status": "ok" if not items else "warn",
        "count":  len(items),
        "items":  items,
    }


def check_schema_coverage(db) -> dict:
    live_tables = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    schema_dir = ROOT / "schema"
    covered = set()
    for sql_file in schema_dir.glob("*.sql"):
        if sql_file.name.startswith("seed_"):
            continue
        text = sql_file.read_text()
        for line in text.splitlines():
            stripped = line.strip().upper()
            if not stripped.startswith("CREATE TABLE"):
                continue
            parts = stripped.split()
            # CREATE TABLE name (          → name at [2]
            # CREATE TABLE IF NOT EXISTS name ( → name at [5]
            name_idx = 5 if len(parts) > 4 and parts[2] == "IF" else 2
            table = parts[name_idx].strip("(").lower()
            covered.add(table)

    gaps = sorted(live_tables - covered)
    return {
        "status": "ok" if not gaps else "warn",
        "count":  len(gaps),
        "items":  gaps,
    }


def check_orphans(db) -> dict:
    orphaned = db.execute("""
        SELECT ss.sprint_id, ss.story_id
        FROM sprint_stories ss
        LEFT JOIN stories s  ON s.id  = ss.story_id
        LEFT JOIN sprints sp ON sp.id = ss.sprint_id
        WHERE s.id IS NULL OR sp.id IS NULL
    """).fetchall()
    items = [{"sprint_id": r["sprint_id"], "story_id": r["story_id"]} for r in orphaned]
    return {
        "status": "ok" if not items else "error",
        "count":  len(items),
        "items":  items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the grove agile board.")
    parser.add_argument("--fix", action="store_true", help="Auto-fix prefix drift and other safe rewrites")
    parser.add_argument("--db",  default=str(DB_PATH))
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    results = {
        "dead_refs":       check_dead_refs(db, fix=args.fix),
        "unpointed":       check_unpointed(db),
        "schema_coverage": check_schema_coverage(db),
        "orphans":         check_orphans(db),
    }
    if not args.fix:
        results["prefix_drift"] = check_prefix_drift(db)

    db.close()

    overall = "ok"
    for name, check in results.items():
        if check["status"] == "error":
            overall = "error"
        elif check["status"] == "warn" and overall == "ok":
            overall = "warn"

    print(json.dumps({"status": overall, "checks": results}, indent=2))


if __name__ == "__main__":
    main()

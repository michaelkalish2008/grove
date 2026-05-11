"""
grove CLI — initialize and manage grove projects.

Commands:
  grove init [--modules board,swarm,index] [--db path/to/grove.db]
  grove status [--db path/to/grove.db]
  grove modules [--db path/to/grove.db]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import grove


def cmd_init(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    modules = [m.strip() for m in args.modules.split(",")]

    print(f"Initializing grove at {db_path} with modules: {modules}")
    conn = grove.init(db_path, modules=modules)
    conn.close()

    installed = grove.modules(db_path)
    print(f"✓ {db_path} ready — modules: {', '.join(installed)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"No grove database at {db_path}")
        print(f"  Run: grove init --db {db_path}")
        return 1

    installed = grove.modules(db_path)
    size_kb = db_path.stat().st_size // 1024
    print(f"grove database: {db_path} ({size_kb} KB)")
    print(f"Modules: {', '.join(installed) if installed else '(none)'}")
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    print("Available modules:")
    print("  board  — agile board: epics, stories, sprints, learnings")
    print("  index  — corpus index: files, chunks, tags, embeddings, clusters")
    print("  swarm  — local model swarm: Ollama workers + Claude orchestrator")
    print("  all    — install everything")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="grove",
        description="grove — local-first AI toolkit",
    )
    parser.add_argument("--db", default="data/grove.db",
                        help="Path to grove.db (default: data/grove.db, override: GROVE_DB env)")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize a grove database")
    p_init.add_argument("--modules", default="board",
                        help="Comma-separated modules to install (default: board)")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Show grove database status")
    p_status.set_defaults(func=cmd_status)

    p_modules = sub.add_parser("modules", help="List available modules")
    p_modules.set_defaults(func=cmd_modules)

    args = parser.parse_args()

    # GROVE_DB env override
    import os
    if "GROVE_DB" in os.environ and args.db == "data/grove.db":
        args.db = os.environ["GROVE_DB"]

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

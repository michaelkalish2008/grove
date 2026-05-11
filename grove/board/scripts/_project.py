"""
Shared project-root detection for board-plugin scripts.

Resolution order:
  1. $GROVE_DB env var  — absolute path to the .db file
  2. Walk up from cwd   — first directory containing data/grove.db or grove.db

Usage in scripts:
    from _project import project_root, db_path
"""

import os
import sys
from pathlib import Path


def _find() -> tuple[Path, Path]:
    # 1. Explicit env override
    env = os.getenv("GROVE_DB")
    if env:
        db = Path(env).resolve()
        if not db.exists():
            print(f"GROVE_DB={env} does not exist.", file=sys.stderr)
            sys.exit(1)
        return db.parent.parent if db.parent.name == "data" else db.parent, db

    # 2. Walk up from cwd
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        for rel in ("data/grove.db", "grove.db"):
            candidate = d / rel
            if candidate.exists():
                return d, candidate.resolve()

    print(
        "No grove.db found walking up from the current directory.\n"
        "Either run from within a board-enabled project, or set:\n"
        "  export GROVE_DB=/path/to/your/grove.db",
        file=sys.stderr,
    )
    sys.exit(1)


project_root, db_path = _find()

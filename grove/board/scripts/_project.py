"""
Shared project-root detection for grove board scripts.

Resolution order:
  1. $GROVE_DB env var  — absolute path to the .db file
  2. Walk up from cwd   — first directory containing data/grove.db or grove.db

Exposes:
  project_root : Path  — directory containing data/ (or the db file itself)
  db_path      : Path  — resolved path to grove.db

Usage in scripts:
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
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
        root = db.parent.parent if db.parent.name == "data" else db.parent
        return root, db

    # 2. Walk up from cwd — look for data/grove.db, then bare grove.db
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        for rel in ("data/grove.db", "grove.db"):
            candidate = d / rel
            if candidate.exists():
                return d, candidate.resolve()

    print(
        "No grove.db found walking up from the current directory.\n"
        "Options:\n"
        "  grove init --db data/grove.db   # create a new board\n"
        "  export GROVE_DB=/path/to/grove.db  # point to an existing one",
        file=sys.stderr,
    )
    sys.exit(1)


project_root, db_path = _find()

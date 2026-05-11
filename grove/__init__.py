"""
grove — local-first AI toolkit.

Modular components:
  grove[board]  — agile board: epics, stories, sprints, learnings
  grove[swarm]  — local model swarm: Ollama workers + Claude orchestrator
  grove[index]  — corpus index: files, chunks, tags, embeddings, clustering

Usage:
  import grove
  grove.init("my_project.db", modules=["board"])
  grove.init("my_project.db", modules=["board", "swarm", "index"])
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

__version__ = "0.1.0"

# Schema SQL files, keyed by module name
_SCHEMA_DIR = Path(__file__).parent.parent / "schema"

_MODULE_SCHEMAS: dict[str, list[Path]] = {
    "board": [
        _SCHEMA_DIR / "agile" / "agile.sql",
    ],
    "index": [
        _SCHEMA_DIR / "corpus" / "corpus.sql",
        _SCHEMA_DIR / "taxonomy" / "taxonomy.sql",
        _SCHEMA_DIR / "learnings" / "learnings.sql",
    ],
    "swarm": [
        _SCHEMA_DIR / "swarm" / "swarm.sql",   # judge_scores
    ],
}

# Dependency order: index requires corpus before taxonomy
_MODULE_DEPS: dict[str, list[str]] = {
    "board":  [],
    "index":  [],
    "swarm":  [],
}


def init(
    db_path: str | Path,
    modules: list[str] | None = None,
    exist_ok: bool = True,
) -> sqlite3.Connection:
    """
    Initialize a grove database, applying schema for the requested modules.

    Args:
        db_path:  Path to the SQLite database file (created if missing).
        modules:  List of modules to install: "board", "index", "swarm", or "all".
                  Defaults to ["board"].
        exist_ok: If True, skip schema steps that are already applied (idempotent).

    Returns:
        Open sqlite3.Connection to the initialized database.
    """
    if modules is None:
        modules = ["board"]
    if "all" in modules:
        modules = list(_MODULE_SCHEMAS.keys())

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    for module in modules:
        _apply_module(conn, module)

    conn.commit()
    _register_modules(conn, modules)
    conn.commit()

    return conn


def _apply_module(conn: sqlite3.Connection, module: str) -> None:
    """Apply a module's SQL schema files to the connection."""
    if module not in _MODULE_SCHEMAS:
        raise ValueError(f"Unknown grove module: {module!r}. Choose from: {list(_MODULE_SCHEMAS)}")

    # Apply deps first
    for dep in _MODULE_DEPS.get(module, []):
        _apply_module(conn, dep)

    for sql_path in _MODULE_SCHEMAS[module]:
        if not sql_path.exists():
            raise FileNotFoundError(f"Schema file not found: {sql_path}")
        conn.executescript(sql_path.read_text())


def _register_modules(conn: sqlite3.Connection, modules: list[str]) -> None:
    """Record installed modules in the grove_modules table (created if missing)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grove_modules (
            module      TEXT PRIMARY KEY,
            version     TEXT,
            installed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for module in modules:
        conn.execute("""
            INSERT OR IGNORE INTO grove_modules (module, version)
            VALUES (?, ?)
        """, (module, __version__))


def modules(db_path: str | Path) -> list[str]:
    """Return the list of modules installed in a grove database."""
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT module FROM grove_modules ORDER BY module").fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

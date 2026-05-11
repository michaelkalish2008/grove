---
name: update
description: Direct Claude to work on a specific story or task on any board-enabled project. Accepts a story ID, title fragment, sprint lifecycle command, or free-form task description.
---

# board:update

Jump directly to specific work. Auto-detects the project from the current directory.

## Parsing the input

| Input | Action |
|---|---|
| A number or `story 3` | Work on that story ID |
| A title fragment | Find matching story; confirm if ambiguous |
| `add story "<title>"` | Create and immediately start a new story |
| `close sprint` | Run close_sprint.py |
| `start sprint <name> "<goal>"` | Run start_sprint.py |
| `validate` / `check` | Run validate_board.py and report |
| Free-form description | Create story if needed, then work on it |

## Steps

### 1. Resolve the story

By ID:
```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import db_path
import sqlite3
db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row
s = db.execute("SELECT * FROM stories WHERE id=?", (STORY_ID,)).fetchone()
print(json.dumps(dict(s), indent=2))
EOF
```

By title fragment:
```bash
python3 - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import db_path
import sqlite3
db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row
rows = db.execute("SELECT id, title, status, points FROM stories WHERE title LIKE ?",
                  ("%FRAGMENT%",)).fetchall()
for r in rows:
    print(f"[{r['id']}] {r['status']:12s} {r['title']}")
EOF
```

To add a new story:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_story.py" \
  --epic <slug> --title "..." --points <n> \
  --desc "..." --output "..." --refs "schema/board.sql" \
  --sprint
```

### 2. Read the story's refs before starting

```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import project_root, db_path
import sqlite3
db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row
s = db.execute("SELECT refs FROM stories WHERE id=?", (STORY_ID,)).fetchone()
for ref in json.loads(s["refs"] or "[]"):
    p = project_root / ref
    print(f"--- {ref} ---")
    print(p.read_text() if p.exists() else "(file not yet created)")
EOF
```

### 3. Move to in-progress and do the work

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_story.py" \
  --id <id> --status in-progress --branch feat/<slug>
```

Execute the story. Check acceptance criteria before marking done.

### 4. Mark done

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_story.py" --id <id> --status done
```

### Sprint lifecycle

```bash
# Preview close
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/close_sprint.py" --dry-run

# Execute close
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/close_sprint.py"

# Start next sprint
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/start_sprint.py" \
  --name S02 --goal "goal text" --stories 3,4,10
```

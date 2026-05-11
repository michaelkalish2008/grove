---
name: run
description: Start a work session on any board-enabled project. Reads the active sprint, last standup, recent learnings, validates the board, then immediately begins on the highest-priority in-flight or ready story. Use at the start of every session.
---

# board:run

Cold-start the session and begin working without waiting for instructions.
Scripts auto-detect the project root by walking up from the current directory.

## Steps

### 1. Orient on the board

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_story.py" --help > /dev/null 2>&1 || true
python3 - <<'EOF'
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import project_root, db_path
import sqlite3

db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row

sprint = db.execute("SELECT * FROM sprints WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
if not sprint:
    print("NO ACTIVE SPRINT — run /board:update 'start sprint'")
    sys.exit(0)

print(f"Sprint : {sprint['name']}  {sprint['start_date']} → {sprint['end_date']}")
print(f"Goal   : {sprint['goal']}")
print(f"Project: {project_root}")
print()

rows = db.execute("""
    SELECT s.id, s.title, s.status, s.points, s.branch
    FROM stories s
    JOIN sprint_stories ss ON ss.story_id = s.id
    WHERE ss.sprint_id = ? AND s.is_recurring = 0
    ORDER BY CASE s.status
      WHEN 'in-progress' THEN 1 WHEN 'review' THEN 2 WHEN 'blocked' THEN 3
      WHEN 'ready' THEN 4 WHEN 'backlog' THEN 5 ELSE 9 END,
    s.points DESC
""", (sprint["id"],)).fetchall()

for r in rows:
    branch = f" [{r['branch']}]" if r["branch"] else ""
    print(f"  [{r['id']:2d}] {r['status']:12s} {str(r['points'] or '?'):>3}p  {r['title']}{branch}")

done  = sum(r["points"] or 0 for r in rows if r["status"] == "done")
total = sum(r["points"] or 0 for r in rows)
print(f"\nVelocity: {done}/{total}p")
EOF
```

### 2. Read recent context

```bash
python3 - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import db_path
import sqlite3

db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row

s = db.execute("SELECT did, next, blockers, created_at FROM standups ORDER BY id DESC LIMIT 1").fetchone()
if s:
    print(f"=== Last standup {s['created_at'][:10]} ===")
    print(f"DID    : {s['did']}")
    print(f"NEXT   : {s['next']}")
    if s["blockers"]: print(f"BLOCKER: {s['blockers']}")

ls = db.execute("SELECT category, title FROM learnings WHERE is_canonical=1 ORDER BY id DESC LIMIT 3").fetchall()
if ls:
    print("\n=== Recent learnings ===")
    for l in ls:
        print(f"  [{l['category']}] {l['title']}")
EOF
```

### 3. Run board validation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_board.py" 2>&1 | python3 -c "
import json,sys
d=json.load(sys.stdin)
issues=[f'{k}: {v[\"count\"]}' for k,v in d['checks'].items() if v['status']!='ok']
print('Board: ' + (', '.join(issues) if issues else 'clean'))
"
```

### 4. Pick up work

- If a story is `in-progress`, continue it — read its `refs`, branch is already cut.
- If nothing is `in-progress`, take the highest-point `ready` story.
  - Run: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_story.py" --id <id> --status in-progress --branch feat/<slug>`
  - Read the story's `refs` before writing any code.
- State what you're starting and why (1-2 sentences), then begin immediately.

### 5. End of session — mandatory writes

```bash
# Update story status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_story.py" --id <id> --status <status>

# Log any learnings that fired
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_learning.py" \
  --category <technical|velocity|process|collaboration> \
  --title "..." --body "root cause, fix, prevention"

# Write standup
python3 - <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import db_path
import sqlite3
db = sqlite3.connect(str(db_path))
sprint = db.execute("SELECT id FROM sprints WHERE status='active'").fetchone()
db.execute("INSERT INTO standups (sprint_id, did, next, blockers) VALUES (?,?,?,?)",
  (sprint["id"], "FILL_DID", "FILL_NEXT", None))
db.commit()
print("standup written")
PYEOF
```

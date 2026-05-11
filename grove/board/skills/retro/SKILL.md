---
name: retro
description: Run a sprint retrospective on any board-enabled project. Covers velocity, completion rate, learnings, honest assessment of what worked and what didn't (including tough feedback), action items, and sprint close. Run at sprint boundary.
---

# board:retro

Sprint retrospective. Honest, structured, no softening.

## Steps

### 1. Pull sprint data

```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import project_root, db_path
import sqlite3

db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row

sprint = db.execute("SELECT * FROM sprints WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
if not sprint:
    sprint = db.execute("SELECT * FROM sprints ORDER BY id DESC LIMIT 1").fetchone()

stories = db.execute("""
    SELECT s.id, s.title, s.status, s.points, s.completed_at, s.branch
    FROM stories s
    JOIN sprint_stories ss ON ss.story_id = s.id
    WHERE ss.sprint_id = ? AND s.is_recurring = 0
    ORDER BY s.status, s.points DESC
""", (sprint["id"],)).fetchall()

done     = [s for s in stories if s["status"] == "done"]
carry    = [s for s in stories if s["status"] != "done"]
velocity = sum(s["points"] or 0 for s in done)
planned  = sum(s["points"] or 0 for s in stories)

print(f"Project  : {project_root.name}")
print(f"Sprint   : {sprint['name']}  {sprint['start_date']} → {sprint['end_date']}")
print(f"Goal     : {sprint['goal']}")
print(f"Velocity : {velocity}/{planned}p  ({len(done)}/{len(stories)} stories done)")
print()
print("DONE:")
for s in done:
    print(f"  [{s['id']:2d}] {str(s['points'] or '?'):>3}p  {s['title']}")
print()
print("NOT DONE:")
for s in carry:
    print(f"  [{s['id']:2d}] {s['status']:12s} {str(s['points'] or '?'):>3}p  {s['title']}")

standups = db.execute("SELECT COUNT(*) AS n FROM standups WHERE sprint_id=?", (sprint["id"],)).fetchone()
print(f"\nSessions this sprint: {standups['n']}")

learnings = db.execute("""SELECT category, title, body FROM learnings
    WHERE sprint_id=? AND is_canonical=1 ORDER BY id""", (sprint["id"],)).fetchall()
print(f"Learnings logged: {len(learnings)}")
for l in learnings:
    print(f"  [{l['category']}] {l['title']}")
EOF
```

### 2. Write the retrospective

Be direct. The user asked for tough feedback.

#### Sprint summary
- Goal met? yes / partial / no — no hedging
- Velocity vs plan, trend vs prior sprints

#### What worked (2-3 items with evidence from this sprint)

#### What didn't work (2-4 items with root cause, not just symptoms)
- If Claude made repeated errors, name the pattern
- If stories were poorly sized or defined, say which ones
- If board discipline slipped (ad hoc SQL, stale refs, CLAUDE.md drift), note it
- If sessions ended without standup writes, say so

#### Learnings delta
Learnings already logged appear above. Log any that weren't captured:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_learning.py" \
  --category <technical|velocity|process|collaboration> \
  --title "..." \
  --body "root cause, fix, how to avoid recurrence"
```

#### Action items for next sprint (max 3, each testable)
Create stories for process changes:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_story.py" \
  --epic foundation --title "..." --points <n> --status ready
```

### 3. Close the sprint

```bash
# Preview
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/close_sprint.py" --dry-run

# Execute
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/close_sprint.py"
```

### 4. Write retrospective record to DB

```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("${CLAUDE_PLUGIN_ROOT}") / "scripts"))
from _project import db_path
import sqlite3

db = sqlite3.connect(str(db_path))
sprint = db.execute("SELECT id, name FROM sprints ORDER BY id DESC LIMIT 1").fetchone()
db.execute("""
    INSERT OR REPLACE INTO retrospectives (sprint_id, went_well, to_improve, action_items)
    VALUES (?,?,?,?)
""", (
    sprint["id"],
    "WENT_WELL",
    "TO_IMPROVE",
    json.dumps([{"owner": "claude", "item": "ACTION_ITEM", "due": "next-sprint"}]),
))
db.commit()
print(f"Retrospective written for {sprint['name']}")
EOF
```

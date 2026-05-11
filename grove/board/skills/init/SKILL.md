---
name: init
description: Initialize a new project with the board management system. Creates the SQLite database, applies schema, and sets up the required directory structure. Run once per project.
---

# board:init

Bootstrap a new project with the grow board system.

## Steps

### 1. Confirm the project root

The current working directory is the project root. Confirm with the user:
"I'll initialize the board system here: `<cwd>`. Correct?"

If wrong, ask them to `cd` to the right directory first.

### 2. Create directory structure

```bash
mkdir -p data logs
```

### 3. Apply schema

```bash
PLUGIN="${CLAUDE_PLUGIN_ROOT}"
DB="data/grove.db"

for schema in core board content catalog; do
  sqlite3 "$DB" < "${PLUGIN}/schema/${schema}.sql"
  echo "  ✓ ${schema}.sql"
done
```

### 4. Seed initial epic

Ask the user: "What's the name of this project? I'll create an initial epic for it."

Then insert:
```bash
sqlite3 data/grove.db "
INSERT INTO epics (slug, title, description, status, priority)
VALUES ('foundation', 'Foundation', 'Core infrastructure and setup', 'active', 10);
"
```

### 5. Create .env.board (optional)

If the DB is not at the default `data/grove.db` location:
```bash
echo "GROVE_DB=$(pwd)/data/grove.db" >> .env
```

### 6. Confirm

```bash
sqlite3 data/grove.db ".tables" | tr ' ' '\n' | sort | grep -v '^$'
```

Report how many tables were created and tell the user:
- Use `/board:update "add story <title>"` to add stories
- Use `/board:run` to start a work session
- Use `/board:retro` at sprint close

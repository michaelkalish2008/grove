#!/usr/bin/env bash
# grove/board/install.sh
# Install grove[board] Cowork skills into the active Claude Desktop session.
#
# Run after: pip install grove[board]
# Re-run after: pip install --upgrade grove
set -euo pipefail

SKILLS_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/skills" && pwd)"

# ── Find active Cowork session ────────────────────────────────────────────────
SESSIONS_ROOT="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"

MANIFEST=$(find "$SESSIONS_ROOT" -name "manifest.json" -path "*/rpm/manifest.json" \
  2>/dev/null | sort | tail -1)

if [[ -z "$MANIFEST" ]]; then
  echo "No Cowork session found. Open Claude Desktop and start a Cowork session first."
  exit 1
fi

RPM_DIR="$(dirname "$MANIFEST")"
PLUGIN_DEST="$RPM_DIR/plugin_grove_board"

echo "Installing grove[board] skills to: $PLUGIN_DEST"

# ── Copy skill files ──────────────────────────────────────────────────────────
rm -rf "$PLUGIN_DEST"
cp -r "$SKILLS_SRC" "$PLUGIN_DEST"

echo "  ✓ skills copied"

# ── Register in manifest ──────────────────────────────────────────────────────
python3 - "$MANIFEST" <<'PYEOF'
import json, sys, time

manifest_path = sys.argv[1]
with open(manifest_path) as f:
    manifest = json.load(f)

entry = {
    "id": "plugin_grove_board",
    "name": "board",
    "updatedAt": "2026-05-11T00:00:00.000Z",
    "marketplaceId": None,
    "marketplaceName": "local",
    "installedBy": "user",
    "installationPreference": "available"
}

manifest["plugins"] = [p for p in manifest["plugins"] if p["id"] != "plugin_grove_board"]
manifest["plugins"].insert(0, entry)
manifest["lastUpdated"] = int(time.time() * 1000)

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)

print("  ✓ manifest updated")
PYEOF

echo ""
echo "grove[board] skills installed. Restart Claude Desktop, then use:"
echo "  /board:run      — start a work session"
echo "  /board:update   — jump to specific work"
echo "  /board:retro    — sprint retrospective"
echo "  /board:grill-me — stress-test a plan"
echo "  /board:init     — set up a new project"

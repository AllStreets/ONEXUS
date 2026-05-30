#!/usr/bin/env bash
# Bundle ONEXUS state for migration to a new machine.
# Run this on the OLD machine. Outputs:
#   ~/Desktop/onexus-migration-bundle.tar.gz
#
# Contents:
#   - nexus.db                (memory, trust, chronicle, episodic state)
#   - state-snapshot.txt      (provider/agent/runtime info — no secrets)
#   - bundle-manifest.json    (versions + sizes for integrity check)
#
# API keys are NOT included — they're entered live via the dashboard.

set -euo pipefail

OUT_DIR="$(mktemp -d -t onexus-migration-XXXXXX)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nexus"
NEXUS_DB="$DATA_DIR/nexus.db"
BUNDLE_PATH="$HOME/Desktop/onexus-migration-bundle.tar.gz"

echo "→ Bundling ONEXUS state from $DATA_DIR"

if [[ ! -f "$NEXUS_DB" ]]; then
  echo "  ! nexus.db not found at $NEXUS_DB — was the server ever run?"
  exit 1
fi

# 1. Copy DB using sqlite3 .backup so it's safe even with a live server
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$NEXUS_DB" ".backup '$OUT_DIR/nexus.db'"
else
  cp "$NEXUS_DB" "$OUT_DIR/nexus.db"
fi
DB_BYTES=$(stat -f%z "$OUT_DIR/nexus.db" 2>/dev/null || stat -c%s "$OUT_DIR/nexus.db")
echo "  ✓ nexus.db copied ($DB_BYTES bytes)"

# 2. Capture provider state from the running server, if reachable
SERVER_URL="${ONEXUS_URL:-http://localhost:8600}"
if curl -sf --max-time 2 "$SERVER_URL/api/system/version" >/dev/null 2>&1; then
  {
    echo "# state snapshot — $(date)"
    echo "## providers"
    curl -s "$SERVER_URL/api/providers" || true
    echo
    echo "## modules"
    curl -s "$SERVER_URL/api/modules" || true
    echo
    echo "## trust"
    curl -s "$SERVER_URL/api/trust" || true
  } > "$OUT_DIR/state-snapshot.txt"
  echo "  ✓ live server snapshot captured"
else
  echo "  - server at $SERVER_URL not reachable, skipping live snapshot"
fi

# 3. Manifest
cat > "$OUT_DIR/bundle-manifest.json" <<EOF
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source_host": "$(hostname)",
  "source_user": "$USER",
  "nexus_db_bytes": $DB_BYTES,
  "data_dir": "$DATA_DIR"
}
EOF

# 4. Tar it
tar -czf "$BUNDLE_PATH" -C "$OUT_DIR" .
rm -rf "$OUT_DIR"

echo
echo "✓ Bundle ready: $BUNDLE_PATH"
echo "  Transfer this file to the new Mac (AirDrop / iCloud / scp)."
echo "  On the new Mac, run:  bash migrate/bootstrap-new-mac.sh"

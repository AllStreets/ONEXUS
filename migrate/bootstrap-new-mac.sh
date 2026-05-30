#!/usr/bin/env bash
# Bootstrap ONEXUS on a fresh Mac.
# Run AFTER cloning this repo: bash migrate/bootstrap-new-mac.sh
#
# Steps:
#   1. Verify the migration bundle exists on Desktop
#   2. Clone sibling ONEXUS-Agents repo if missing
#   3. Create a Python 3.12 venv and install deps
#   4. Restore nexus.db to ~/.local/share/nexus
#   5. Print remaining manual steps (macOS permissions, API keys)

set -euo pipefail

BUNDLE="$HOME/Desktop/onexus-migration-bundle.tar.gz"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIBLING_PARENT="$(dirname "$PROJECT_ROOT")"
SIBLING_DIR="$SIBLING_PARENT/ONEXUS-Agents"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nexus"
VENV="$PROJECT_ROOT/.venv"
RESTORE_DIR="$(mktemp -d -t onexus-restore-XXXXXX)"

step() { echo; echo "→ $1"; }
ok()   { echo "  ✓ $1"; }
warn() { echo "  ! $1"; }

# ── 1. Verify bundle ──────────────────────────────────────────────────────
step "Checking migration bundle"
if [[ ! -f "$BUNDLE" ]]; then
  warn "no bundle at $BUNDLE"
  echo "  Transfer onexus-migration-bundle.tar.gz to ~/Desktop on this Mac,"
  echo "  then rerun this script."
  exit 1
fi
tar -xzf "$BUNDLE" -C "$RESTORE_DIR"
ok "extracted bundle"
cat "$RESTORE_DIR/bundle-manifest.json"

# ── 2. Sibling repo ───────────────────────────────────────────────────────
step "ONEXUS-Agents catalog"
if [[ -d "$SIBLING_DIR/.git" ]]; then
  ok "already present at $SIBLING_DIR"
else
  echo "  cloning into $SIBLING_DIR"
  git clone https://github.com/AllStreets/ONEXUS-Agents.git "$SIBLING_DIR"
  ok "cloned"
fi

# ── 3. Python env ─────────────────────────────────────────────────────────
step "Python virtualenv"
if [[ -x "$VENV/bin/python" ]]; then
  ok "venv already exists at $VENV"
else
  PY=$(command -v python3.12 || command -v python3.11 || command -v python3 || true)
  if [[ -z "$PY" ]]; then
    warn "no python3 found — install Python 3.11+ first (brew install python@3.12)"
    exit 1
  fi
  "$PY" -m venv "$VENV"
  ok "created venv with $($PY --version)"
fi
"$VENV/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV/bin/pip" install -e "$PROJECT_ROOT[llm,api,tui]" >/dev/null
ok "dependencies installed"

# ── 4. Restore DB ─────────────────────────────────────────────────────────
step "Restoring nexus.db"
mkdir -p "$DATA_DIR"
if [[ -f "$DATA_DIR/nexus.db" ]]; then
  BACKUP="$DATA_DIR/nexus.db.pre-restore.$(date +%Y%m%d-%H%M%S)"
  mv "$DATA_DIR/nexus.db" "$BACKUP"
  ok "existing db backed up to $BACKUP"
fi
cp "$RESTORE_DIR/nexus.db" "$DATA_DIR/nexus.db"
ok "nexus.db placed at $DATA_DIR/nexus.db"

# ── 5. Cleanup + next steps ───────────────────────────────────────────────
rm -rf "$RESTORE_DIR"

cat <<'EOF'

✓ Migration complete.

REMAINING MANUAL STEPS:

1. Grant the python binary access to Downloads (so the ONEXUS-Agents catalog
   is readable):
     System Settings → Privacy & Security → Files and Folders →
     find your python3 entry → enable Downloads Folder
   (Or move ONEXUS-Agents out of Downloads to skip this.)

2. Start the server:
     source .venv/bin/activate
     onexus serve

3. Open http://localhost:8600/dashboard and re-enter your provider API keys
   (OpenAI / Anthropic) through the LLM Providers modal.

If you had a state snapshot in the bundle, it lives in:
  ~/Desktop/onexus-migration-bundle.tar.gz  (state-snapshot.txt inside)
for reference when re-entering provider configuration.

EOF

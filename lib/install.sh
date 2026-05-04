#!/usr/bin/env bash
# claude-team-toolkit — one-time setup
# Run once after cloning/installing the plugin to:
#   1. Copy lib/* to ~/.claude-team-toolkit/lib/ (stable path skills can source)
#   2. Verify dependencies (curl, jq, base64)
#   3. Set up audit log directory with proper permissions
#
# Usage: bash lib/install.sh

set -e

CTT_HOME="$HOME/.claude-team-toolkit"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "claude-team-toolkit installer"
echo "============================="
echo ""

# 1. Create stable home directory
echo "[1/3] Setting up $CTT_HOME ..."
mkdir -p "$CTT_HOME/lib"
chmod 700 "$CTT_HOME" 2>/dev/null || true
cp -f "$SCRIPT_DIR"/*.sh "$CTT_HOME/lib/"
# 644 — these are sourced helpers, not secret data files
chmod 644 "$CTT_HOME/lib"/*.sh 2>/dev/null || true
echo "  → installed lib to $CTT_HOME/lib/"

# 2. Check dependencies
echo ""
echo "[2/3] Checking dependencies ..."
missing=()
for cmd in curl jq base64 awk sed; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if [ ${#missing[@]} -gt 0 ]; then
  echo "  ✗ Missing: ${missing[*]}"
  echo ""
  echo "  Install:"
  echo "    Windows:  choco install jq curl  (or scoop install jq curl)"
  echo "    macOS:    brew install jq"
  echo "    Linux:    sudo apt install jq curl  (or dnf/yum equivalent)"
  exit 1
else
  echo "  ✓ curl jq base64 awk sed all present"
fi

# 3. Audit log
echo ""
echo "[3/3] Audit log directory ..."
touch "$CTT_HOME/audit.log"
chmod 600 "$CTT_HOME/audit.log" 2>/dev/null || true
echo "  → $CTT_HOME/audit.log (mode 600)"

echo ""
echo "Done. Next steps:"
echo "  1. Configure your first account:    /trello configure   (or any other skill)"
echo "  2. List available skills:           ls $CTT_HOME/../.claude/plugins/...  or /help"
echo "  3. Read the security model:         see README.md"
echo ""
echo "All credentials live in ~/.<service>/credentials (mode 600)."
echo "Run 'cat $CTT_HOME/audit.log' to see your mutation history."

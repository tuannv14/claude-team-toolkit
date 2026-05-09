#!/usr/bin/env bash
# claude-team-toolkit — one-time setup
# Run once after cloning/installing the plugin to:
#   1. Copy lib/* to ~/.claude-team-toolkit/lib/ (stable path skills can source)
#   2. Verify dependencies (curl, jq, base64)
#   3. Set up audit log directory with proper permissions
#   4. (Optional) Apply an install profile to disable unused skills
#      → bash lib/install.sh --profile mobile-team
#      → bash lib/install.sh --profile backend-ops
#      → bash lib/install.sh --list-profiles
#
# Usage:
#   bash lib/install.sh                          # full install (all 16 skills active)
#   bash lib/install.sh --profile <name>         # install + enable only profile's skills
#   bash lib/install.sh --list-profiles          # show available profiles + exit
#   bash lib/install.sh --reset-profile          # re-enable all skills (clear --profile)
#   bash lib/install.sh -h | --help              # print this help and exit

set -e

CTT_HOME="$HOME/.claude-team-toolkit"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
PROFILES_FILE="$PLUGIN_ROOT/.claude-plugin/install-profiles.json"
SKILLS_DIR="$PLUGIN_ROOT/skills"

PROFILE=""
LIST_ONLY=0
RESET_ONLY=0
ORIGINAL_ARGS="$*"

# --- Parse args ----------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --profile)
      if [ $# -lt 2 ]; then
        echo "✗ --profile requires a value. Run: bash lib/install.sh --list-profiles" >&2
        exit 2
      fi
      PROFILE="$2"; shift 2 ;;
    --profile=*)
      PROFILE="${1#--profile=}"; shift ;;
    --list-profiles)
      LIST_ONLY=1; shift ;;
    --reset-profile)
      RESET_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,19p' "$0"; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Reject empty/whitespace-only --profile value (typo guard).
if [ -n "${PROFILE+set}" ] && [ -z "$(echo "$PROFILE" | tr -d '[:space:]')" ] && [ "$LIST_ONLY" -eq 0 ] && [ "$RESET_ONLY" -eq 0 ]; then
  # Reset PROFILE if user passed --profile= or --profile " " — but only error if they
  # explicitly opted in to profile mode. For just `--profile=` we treat as typo.
  case "$ORIGINAL_ARGS" in
    *--profile*)
      echo "✗ --profile requires a value. Run: bash lib/install.sh --list-profiles" >&2
      exit 2 ;;
  esac
  PROFILE=""
fi

# --- --list-profiles -----------------------------------------------------
if [ "$LIST_ONLY" -eq 1 ]; then
  if [ ! -f "$PROFILES_FILE" ]; then
    echo "No install-profiles.json found at $PROFILES_FILE" >&2
    exit 1
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "jq required to list profiles. Install jq first." >&2
    exit 1
  fi
  echo "Available install profiles:"
  echo ""
  jq -r '.profiles | to_entries[] | "  \(.key)\n      \(.value.description)\n      Skills: \(.value.skills | join(", "))\n"' "$PROFILES_FILE"
  echo "Apply with:  bash lib/install.sh --profile <name>"
  exit 0
fi

# --- --reset-profile -----------------------------------------------------
if [ "$RESET_ONLY" -eq 1 ]; then
  echo "Re-enabling all skills (restoring SKILL.md from SKILL.md.disabled)..."
  count=0
  while IFS= read -r f; do
    mv "$f" "${f%.disabled}"
    count=$((count+1))
  done < <(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md.disabled" 2>/dev/null)
  echo "Done. Re-enabled $count skill(s). All skills are active."
  exit 0
fi

# --- Validate --profile if provided --------------------------------------
ENABLED_SKILLS=""
if [ -n "$PROFILE" ]; then
  if [ ! -f "$PROFILES_FILE" ]; then
    echo "✗ install-profiles.json not found." >&2
    exit 1
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "✗ jq required to apply --profile." >&2
    exit 1
  fi
  if ! jq -e ".profiles[\"$PROFILE\"]" "$PROFILES_FILE" >/dev/null 2>&1; then
    echo "✗ Unknown profile: $PROFILE" >&2
    echo "  Run: bash lib/install.sh --list-profiles" >&2
    exit 1
  fi
  # Collect enabled skills (always include 'shared' set + profile skills).
  # Note: strip CR (\r) — jq on Git-Bash for Windows emits CRLF, which would
  # otherwise leave embedded \r in the variable and break the grep match below.
  shared=$(jq -r '.shared[]?' "$PROFILES_FILE" 2>/dev/null | tr -d '\r' | tr '\n' ' ')
  selected=$(jq -r ".profiles[\"$PROFILE\"].skills[]" "$PROFILES_FILE" | tr -d '\r')
  if [ "$(echo "$selected" | tr -d '[:space:]')" = "*" ]; then
    ENABLED_SKILLS="*"
  else
    ENABLED_SKILLS="$shared $(echo "$selected" | tr '\n' ' ')"
  fi
fi

echo "claude-team-toolkit installer"
echo "============================="
[ -n "$PROFILE" ] && echo "Profile: $PROFILE"
echo ""

# --- 1. Stable home directory --------------------------------------------
echo "[1/4] Setting up $CTT_HOME ..."
mkdir -p "$CTT_HOME/lib"
chmod 700 "$CTT_HOME" 2>/dev/null || true
cp -f "$SCRIPT_DIR"/*.sh "$CTT_HOME/lib/"
chmod 644 "$CTT_HOME/lib"/*.sh 2>/dev/null || true
echo "  → installed lib to $CTT_HOME/lib/"

# --- 2. Dependencies -----------------------------------------------------
echo ""
echo "[2/4] Checking dependencies ..."
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

# --- 3. Audit log --------------------------------------------------------
echo ""
echo "[3/4] Audit log directory ..."
touch "$CTT_HOME/audit.log"
chmod 600 "$CTT_HOME/audit.log" 2>/dev/null || true
echo "  → $CTT_HOME/audit.log (mode 600)"

# --- 4. Profile application ---------------------------------------------
echo ""
echo "[4/4] Skill profile ..."
if [ -z "$PROFILE" ] || [ "$ENABLED_SKILLS" = "*" ]; then
  # Default: full install. Restore any previously disabled skills.
  restored=0
  while IFS= read -r f; do
    mv "$f" "${f%.disabled}"
    restored=$((restored+1))
  done < <(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md.disabled" 2>/dev/null)
  if [ "$restored" -gt 0 ]; then
    echo "  → restored $restored previously-disabled skills"
  fi
  echo "  → all 16 skills active (no profile filter)"
else
  # Disable every skill not in ENABLED_SKILLS by renaming SKILL.md → SKILL.md.disabled
  # (Claude Code's plugin loader scans for SKILL.md, so .disabled files are ignored.)
  count_enabled=0; count_disabled=0
  for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"
    skill_md_disabled="$skill_dir/SKILL.md.disabled"
    if echo " $ENABLED_SKILLS " | grep -q " $skill_name "; then
      # Should be enabled — restore if previously disabled
      [ -f "$skill_md_disabled" ] && mv "$skill_md_disabled" "$skill_md"
      count_enabled=$((count_enabled+1))
    else
      # Should be disabled — rename SKILL.md if present
      [ -f "$skill_md" ] && mv "$skill_md" "$skill_md_disabled"
      count_disabled=$((count_disabled+1))
    fi
  done
  echo "  → profile '$PROFILE' applied: $count_enabled enabled, $count_disabled disabled"
  echo "  → disabled skills have SKILL.md renamed to SKILL.md.disabled (loader skips them)"
  echo "  → run: bash lib/install.sh --reset-profile  to re-enable all"
fi

echo ""
echo "Done. Next steps:"
echo "  1. Configure your first account:    /trello configure   (or any other skill)"
echo "  2. List install profiles:            bash lib/install.sh --list-profiles"
echo "  3. Read the security model:          see README.md"
echo ""
echo "All credentials live in ~/.<service>/credentials (mode 600)."
echo "Run 'cat $CTT_HOME/audit.log' to see your mutation history."

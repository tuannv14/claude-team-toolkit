#!/usr/bin/env bash
# claude-team-toolkit — SessionStart hook
# Pre-warms credential discovery so the model knows which profiles are
# configured before any skill is invoked. Output goes to additionalContext
# (visible to the model, not blocking).
#
# Usage: invoked automatically by Claude Code via .claude-plugin/hooks/hooks.json
# Manual:  bash lib/session-start.sh
#
# Exits 0 always (advisory only — never block session).

set +e   # never block session start

CTT_HOME="$HOME/.claude-team-toolkit"
PLUGIN_VERSION_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude-plugin/plugin.json"
VERSION=""
if [ -f "$PLUGIN_VERSION_FILE" ] && command -v jq >/dev/null 2>&1; then
  VERSION=$(jq -r '.version // ""' "$PLUGIN_VERSION_FILE" 2>/dev/null)
fi

# Header
if [ -n "$VERSION" ]; then
  printf "[claude-team-toolkit v%s]\n" "$VERSION"
else
  printf "[claude-team-toolkit]\n"
fi

# Each line: "<service>: <profile1>, <profile2>* (active marked with *)" or "(none — run /<service> configure)"
# Services to probe — must match credential dirs under $HOME
SERVICES="trello azure-devops heroku sentry slack firebase shopify postgres maestro fastlane k6 rspec"

any_configured=0
for svc in $SERVICES; do
  cred_file="$HOME/.${svc}/credentials"
  active_file="$HOME/.${svc}/active_profile"

  if [ ! -f "$cred_file" ]; then
    continue   # not configured at all — skip silent line
  fi

  any_configured=1

  # Extract profile names = lines like "[name]" (skip [profile-name-with-space]; INI standard is alphanumeric+_-)
  profiles=$(grep -E '^\[[A-Za-z0-9_-]+\]$' "$cred_file" 2>/dev/null | tr -d '[]' | tr '\n' ' ')
  active=""
  [ -f "$active_file" ] && active=$(head -n1 "$active_file" 2>/dev/null | tr -d '[:space:]')

  # Format: mark active profile with *
  formatted=""
  for p in $profiles; do
    if [ "$p" = "$active" ]; then
      formatted="${formatted}${p}*, "
    else
      formatted="${formatted}${p}, "
    fi
  done
  formatted="${formatted%, }"   # trim trailing ", "

  if [ -z "$formatted" ]; then
    formatted="(file present but no [profile] sections found)"
  fi

  printf "  %-15s %s\n" "${svc}:" "$formatted"
done

if [ "$any_configured" -eq 0 ]; then
  echo "  (no profiles configured — run /<service> configure to add one)"
fi

# Audit log status
if [ -f "$CTT_HOME/audit.log" ]; then
  size=$(stat -c %s "$CTT_HOME/audit.log" 2>/dev/null || stat -f %z "$CTT_HOME/audit.log" 2>/dev/null || echo "?")
  if [ "$size" != "0" ] && [ "$size" != "?" ]; then
    last=$(tail -n1 "$CTT_HOME/audit.log" 2>/dev/null)
    if [ -n "$last" ]; then
      echo "  audit.log:      ${size} bytes — last: ${last:0:80}"
    fi
  fi
fi

exit 0

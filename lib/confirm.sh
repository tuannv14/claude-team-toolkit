#!/usr/bin/env bash
# claude-team-toolkit — destructive operation confirmation
# Sourced by skills before mutating ops.
#
#   ctt_confirm "Delete app foo on Heroku?" || return 1
#   ctt_confirm "Drop table users?" "DELETE" || return 1   # require typed confirmation
#
# Returns 0 if confirmed, 1 otherwise. Honors CTT_NONINTERACTIVE=1 (auto-deny).

ctt_confirm() {
  local prompt="$1"
  local require_phrase="${2:-}"

  # Non-interactive guardrail (CI, scripts) — refuse by default
  if [ "${CTT_NONINTERACTIVE:-0}" = "1" ]; then
    echo "Refusing destructive op (CTT_NONINTERACTIVE=1): $prompt" >&2
    return 1
  fi

  # If running under Claude Code, the AI must surface the prompt to the user
  # and only proceed if the user explicitly typed an approval. The skill body
  # is responsible for that — this helper just enforces a typed gate when
  # actually executed.
  if [ -n "$require_phrase" ]; then
    echo "$prompt" >&2
    echo "Type '$require_phrase' exactly to proceed:" >&2
    local answer
    read -r answer
    [ "$answer" = "$require_phrase" ] && return 0 || { echo "Aborted." >&2; return 1; }
  else
    echo "$prompt [y/N]" >&2
    local answer
    read -r answer
    case "$answer" in
      y|Y|yes|YES) return 0 ;;
      *) echo "Aborted." >&2; return 1 ;;
    esac
  fi
}

# ctt_warn_destructive <action> — log to stderr in a noticeable way
ctt_warn_destructive() {
  echo "" >&2
  echo "  !! DESTRUCTIVE: $1" >&2
  echo "" >&2
}

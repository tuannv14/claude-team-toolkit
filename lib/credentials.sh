#!/usr/bin/env bash
# claude-team-toolkit — shared credentials helper
# Sourced by every skill. Provides:
#   ctt_load_creds <service> [profile]   → populate CTT_<KEY> vars
#   ctt_mask <value>                     → "****<last4>"
#   ctt_save_profile <service> <profile> <key=value> ...
#   ctt_list_profiles <service>
#   ctt_use_profile <service> <profile>
#   ctt_active_profile <service>
#   ctt_remove_profile <service> <profile>
#   ctt_validate_perms <file>            → fail if world-readable on POSIX
#
# Credentials live at ~/.<service>/credentials (INI), mode 0600.
# Active profile pointer at ~/.<service>/active_profile.

set -o pipefail

# --- internals ---

_ctt_cred_file() { echo "$HOME/.${1}/credentials"; }
_ctt_active_file() { echo "$HOME/.${1}/active_profile"; }
_ctt_dir() { echo "$HOME/.${1}"; }

ctt_mask() { local v="$1"; [ ${#v} -le 4 ] && echo "****" || echo "****${v: -4}"; }

ctt_validate_perms() {
  local f="$1"
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;  # Windows: chmod is best-effort
  esac
  [ -f "$f" ] || return 0
  local mode
  mode=$(stat -c '%a' "$f" 2>/dev/null || stat -f '%A' "$f" 2>/dev/null)
  [ -z "$mode" ] && return 0
  case "$mode" in
    600|400) return 0 ;;
    *) echo "Refusing to load: $f is mode $mode (must be 600). Run: chmod 600 $f" >&2; return 1 ;;
  esac
}

# Parse one [section] from an INI file. Outputs key=value lines.
_ctt_section() {
  local file="$1" section="$2"
  awk -v s="[$section]" '
    /^[[:space:]]*[#;]/ {next}
    $0==s {found=1; next}
    /^\[/ {found=0}
    found && /=/ {
      sub(/^[[:space:]]+/,"")
      sub(/[[:space:]]+$/,"")
      print
    }
  ' "$file"
}

# Get a single field from a section.
_ctt_field() {
  local file="$1" section="$2" key="$3"
  _ctt_section "$file" "$section" | awk -F= -v k="$key" '
    {
      gsub(/[[:space:]]/,"",$1)
      if ($1==k) {
        sub(/^[^=]*=[[:space:]]*/,"")
        sub(/[[:space:]]+$/,"")
        print
        exit
      }
    }
  '
}

# Resolve which profile to use. Honors env vars in this order:
#   <UPPER_SVC>_PROFILE  (e.g. HEROKU_PROFILE, AWS_S3_PROFILE)
# Plus per-service short aliases for common cases (azure-devops → AZDO_PROFILE).
_ctt_resolve_profile() {
  local service="$1" explicit="$2"
  local active_file
  active_file=$(_ctt_active_file "$service")

  # Service name validation: lowercase letters, digits, hyphen only
  case "$service" in
    ''|*[!a-z0-9-]*) echo "Invalid service name: $service" >&2; echo "default"; return ;;
  esac

  # Primary env var: SVC_PROFILE (uppercased, hyphens → underscores)
  local primary_var
  primary_var="$(echo "$service" | tr '[:lower:]-' '[:upper:]_')_PROFILE"
  local from_env="${!primary_var:-}"

  # Aliases for backward-compat short names
  if [ -z "$from_env" ]; then
    case "$service" in
      azure-devops) from_env="${AZDO_PROFILE:-}" ;;
      bundler-audit) from_env="${BA_PROFILE:-}" ;;
      react-native) from_env="${RN_PROFILE:-}" ;;
      xlsx-testcases) from_env="${XTC_PROFILE:-}" ;;
    esac
  fi

  if [ -n "$explicit" ]; then echo "$explicit"
  elif [ -n "$from_env" ]; then echo "$from_env"
  elif [ -f "$active_file" ]; then cat "$active_file"
  else echo "default"
  fi
}

# --- public API ---

# ctt_load_creds <service> [profile]
# Populates env vars: CTT_PROFILE, CTT_<FIELD_UPPER> for each field in section.
# Example: ctt_load_creds trello work
#   → CTT_PROFILE=work, CTT_KEY=..., CTT_TOKEN=...
ctt_load_creds() {
  local service="$1" explicit_profile="${2:-}"
  [ -z "$service" ] && { echo "ctt_load_creds: missing service" >&2; return 2; }

  local cred_file
  cred_file=$(_ctt_cred_file "$service")
  if [ ! -f "$cred_file" ]; then
    echo "No credentials at $cred_file. Run: /$service configure" >&2
    return 1
  fi

  ctt_validate_perms "$cred_file" || return 1

  local profile
  profile=$(_ctt_resolve_profile "$service" "$explicit_profile")

  # Verify section exists
  if ! grep -q "^\[$profile\][[:space:]]*$" "$cred_file"; then
    echo "Profile [$profile] not found in $cred_file" >&2
    echo "Available profiles:" >&2
    ctt_list_profiles "$service" >&2
    return 1
  fi

  # Export each field as CTT_<UPPERCASE>
  CTT_PROFILE="$profile"
  export CTT_PROFILE
  while IFS='=' read -r key value; do
    [ -z "$key" ] && continue
    key=$(echo "$key" | tr -d '[:space:]')
    value=$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    [ -z "$key" ] && continue

    # Validate key shape: must be a valid shell var name component.
    # Accept letters/digits/underscore/hyphen. Reject anything else (defense
    # against tampered creds files trying to inject via key names).
    case "$key" in
      ''|[0-9]*|*[!a-zA-Z0-9_-]*) continue ;;
    esac

    local upper
    upper=$(echo "$key" | tr '[:lower:]-' '[:upper:]_')
    # Re-validate after transform (paranoia)
    case "$upper" in
      ''|[0-9]*|*[!A-Z0-9_]*) continue ;;
    esac

    # Use printf -v (POSIX-ish) instead of eval for safety
    printf -v "CTT_${upper}" '%s' "$value"
    export "CTT_${upper}"
  done < <(_ctt_section "$cred_file" "$profile")
}

# ctt_save_profile <service> <profile> <field1=value1> <field2=value2> ...
# Creates ~/.<service>/, sets perms, writes/replaces section atomically.
ctt_save_profile() {
  local service="$1" profile="$2"; shift 2
  [ -z "$service" ] || [ -z "$profile" ] && { echo "ctt_save_profile: usage <service> <profile> <kv>..." >&2; return 2; }

  local dir cred_file tmp
  dir=$(_ctt_dir "$service")
  cred_file=$(_ctt_cred_file "$service")
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  touch "$cred_file"
  chmod 600 "$cred_file" 2>/dev/null || true

  tmp=$(mktemp)
  # Copy all sections except the one we're replacing
  awk -v s="[$profile]" '
    /^\[/ { in_target=($0==s); print_section=!in_target }
    !/^\[/ { if (print_section) print }
    /^\[/ && !in_target { print }
  ' "$cred_file" > "$tmp" 2>/dev/null || true

  # Append the new section
  {
    echo ""
    echo "[$profile]"
    for kv in "$@"; do
      printf "%s\n" "$kv"
    done
  } >> "$tmp"

  # Clean up extra blank lines
  awk 'NF || prev_blank==0 { print; prev_blank=(NF==0) }' "$tmp" > "$cred_file"
  rm -f "$tmp"
  chmod 600 "$cred_file" 2>/dev/null || true
}

# ctt_list_profiles <service>
ctt_list_profiles() {
  local service="$1" cred_file active
  cred_file=$(_ctt_cred_file "$service")
  [ -f "$cred_file" ] || return 0
  active=$(_ctt_resolve_profile "$service" "")
  awk -F= '/^\[/ { gsub(/[\[\]]/,""); print }' "$cred_file" \
    | while read -r p; do
        if [ "$p" = "$active" ]; then echo "* $p"; else echo "  $p"; fi
      done
}

# ctt_use_profile <service> <profile> — set as active
ctt_use_profile() {
  local service="$1" profile="$2"
  local cred_file active_file
  cred_file=$(_ctt_cred_file "$service")
  active_file=$(_ctt_active_file "$service")
  if ! grep -q "^\[$profile\][[:space:]]*$" "$cred_file"; then
    echo "Profile [$profile] does not exist. Use 'profile list' to see options." >&2
    return 1
  fi
  echo "$profile" > "$active_file"
  chmod 600 "$active_file" 2>/dev/null || true
}

# ctt_active_profile <service>
ctt_active_profile() {
  local service="$1"
  _ctt_resolve_profile "$service" ""
}

# ctt_remove_profile <service> <profile>
ctt_remove_profile() {
  local service="$1" profile="$2"
  local cred_file tmp
  cred_file=$(_ctt_cred_file "$service")
  [ -f "$cred_file" ] || { echo "No credentials file" >&2; return 1; }

  local count
  count=$(grep -c "^\[" "$cred_file")
  if [ "$count" -le 1 ]; then
    echo "Refusing to remove the only profile. Add another first or delete $cred_file manually." >&2
    return 1
  fi

  tmp=$(mktemp)
  awk -v s="[$profile]" '
    /^\[/ { skip=($0==s) }
    !skip { print }
  ' "$cred_file" > "$tmp"
  mv "$tmp" "$cred_file"
  chmod 600 "$cred_file" 2>/dev/null || true
}

# ctt_audit_log <service> <action> — append to ~/.claude-team-toolkit/audit.log
# Records timestamp, profile, action. NEVER records credentials.
ctt_audit_log() {
  local service="$1" action="$2"
  local audit_dir="$HOME/.claude-team-toolkit"
  local audit_file="$audit_dir/audit.log"
  mkdir -p "$audit_dir"
  chmod 700 "$audit_dir" 2>/dev/null || true
  printf '%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$service" \
    "${CTT_PROFILE:-?}" \
    "$action" \
    >> "$audit_file"
  chmod 600 "$audit_file" 2>/dev/null || true
}

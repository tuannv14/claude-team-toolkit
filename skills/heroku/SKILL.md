---
name: heroku
description: Heroku apps/dynos/releases/config/logs via Platform API v3. Use for deploy, scale, restart, config-set, logs, rollback, pipeline promote. Auto-masks secrets. Multi-account via HEROKU_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /heroku — Platform API v3 (multi-account)

Direct REST against `https://api.heroku.com`. No Heroku CLI dependency.
Bearer auth with API key.

Profile resolution: `--profile` → `HEROKU_PROFILE` → `~/.heroku/active_profile` → `[default]`.

## Profile config

`~/.heroku/credentials` (mode 600):

```ini
[default]
api_key      = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
default_app  = my-staging-app

[work]
api_key      = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
default_app  = production-api
require_confirm = true                   # gate every mutation
```

**Get key:** `heroku authorizations:create` (CLI) OR Account Settings →
Authorizations. Use **scoped tokens** (read/write/deploy) — avoid global.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds heroku "$PROFILE"

heroku_api() {
  local method="$1" path="$2"; shift 2
  curl -s -X "$method" \
    -H "Authorization: Bearer $CTT_API_KEY" \
    -H "Accept: application/vnd.heroku+json; version=3" \
    -H "Content-Type: application/json" \
    "$@" "https://api.heroku.com$path"
}

heroku_app() {
  local app="${1:-$CTT_DEFAULT_APP}"
  [ -z "$app" ] && { echo "No app. Pass arg or set default_app." >&2; return 1; }
  echo "$app"
}
```

## Dispatch

### `apps` — list
```bash
heroku_api GET /apps | jq -r '.[] | "\(.name)\t\(.region.name)\t\(.stack.name)"'
```

### `info <app>` — app detail
```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP" | jq '{name, web_url, region:.region.name, stack:.stack.name, maintenance, dyno_count}'
```

### `config <app>` — list config vars (auto-mask secrets)
```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP/config-vars" | jq -r '
  to_entries[] | if (.key | test("KEY|SECRET|TOKEN|PASSWORD|PASS|DSN|URL"; "i"))
                 then "\(.key)=****\(.value[-4:])"
                 else "\(.key)=\(.value)" end
'
```
`--reveal` to show all in full (require explicit user request).

### `config-set <app> <KEY=value>...` — DESTRUCTIVE
```bash
APP=$(heroku_app "$1"); shift
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Set config on $APP ($CTT_PROFILE)?" || return 1

BODY=$(jq -n '$ARGS.positional | map(split("=")) | map({key:.[0], value:(.[1:]|join("="))}) | from_entries' --args "$@")
heroku_api PATCH "/apps/$APP/config-vars" -d "$BODY"

# Audit: key NAMES only, never values (handles JWT_KEY="x=y=z")
keys=$(printf '%s\n' "$@" | awk -F= '{print $1}' | tr '\n' ' ')
ctt_audit_log heroku "config-set $APP keys: $keys"
```

### `config-unset <app> <KEY>...`
```bash
APP=$(heroku_app "$1"); shift
ctt_confirm "Unset $* on $APP?" || return 1
BODY=$(jq -n '$ARGS.positional | map({(.):null}) | add' --args "$@")
heroku_api PATCH "/apps/$APP/config-vars" -d "$BODY"
ctt_audit_log heroku "config-unset $APP keys: $*"
```

### `dynos <app>` — list running dynos
```bash
heroku_api GET "/apps/$(heroku_app "$1")/dynos" | jq -r '.[] | "\(.type).\(.name)\t\(.state)\t\(.size)"'
```

### `scale <app> <type=count>...` — DESTRUCTIVE
```bash
APP=$(heroku_app "$1"); shift
ctt_confirm "Scale $APP ($CTT_PROFILE): $*?" || return 1
BODY=$(jq -n '{updates: ($ARGS.positional | map(split("=")) | map({type:.[0], quantity:(.[1]|tonumber)}))}' --args "$@")
heroku_api PATCH "/apps/$APP/formation" -d "$BODY"
ctt_audit_log heroku "scale $APP $*"
```

### `restart <app> [dyno-name]`
```bash
APP=$(heroku_app "$1")
ctt_confirm "Restart $APP ${2:-(all)}?" || return 1
[ -n "$2" ] && heroku_api DELETE "/apps/$APP/dynos/$2" || heroku_api DELETE "/apps/$APP/dynos"
ctt_audit_log heroku "restart $APP ${2:-all}"
```

### `releases <app> [--limit N]`
```bash
APP=$(heroku_app "$1")
case "$LIMIT" in ''|*[!0-9]*) LIMIT=20 ;; esac
heroku_api GET "/apps/$APP/releases" -H "Range: version ..; max=$LIMIT, order=desc" \
  | jq -r '.[] | "v\(.version)\t\(.created_at)\t\(.user.email)\t\(.description)"'
```

### `rollback <app> <version>` — DESTRUCTIVE
```bash
APP=$(heroku_app "$1")
ctt_warn_destructive "Rollback $APP to v$2"
ctt_confirm "Type ROLLBACK to confirm:" "ROLLBACK" || return 1
heroku_api POST "/apps/$APP/releases" -d "$(jq -n --arg v "$2" '{release:$v}')"
ctt_audit_log heroku "rollback $APP to v$2"
```

### `logs <app> [--tail] [--source app|heroku] [--lines N]`
```bash
APP=$(heroku_app "$1")
BODY=$(jq -n --arg src "${SOURCE:-app}" --argjson lines "${LINES:-100}" --argjson tail "${TAIL:-false}" \
  '{source:$src, lines:$lines, tail:$tail}')
URL=$(heroku_api POST "/apps/$APP/log-sessions" -d "$BODY" | jq -r '.logplex_url')
[ "$TAIL" = "true" ] && curl -s "$URL" || curl -s "$URL" | tail -n "${LINES:-100}"
```

### `pipelines` / `promote <pipeline-id>` — DESTRUCTIVE
```bash
heroku_api GET /pipelines | jq -r '.[] | "\(.id)\t\(.name)"'

# promote
ctt_warn_destructive "Pipeline promote: $1 ($CTT_PROFILE)"
ctt_confirm "Type PROMOTE to confirm:" "PROMOTE" || return 1
heroku_api POST /pipeline-promotions -d "$(jq -n --arg pid "$1" '{pipeline:{id:$pid}}')"
ctt_audit_log heroku "promote $1"
```

### `addons <app>` — installed add-ons
```bash
heroku_api GET "/apps/$(heroku_app "$1")/addons" | jq -r '.[] | "\(.addon_service.name)\t\(.plan.name)\t\(.state)"'
```

### `destroy <app>` — IRREVERSIBLE
```bash
APP=$(heroku_app "$1")
ctt_warn_destructive "DESTROY app $APP — irreversible"
ctt_confirm "Type the app name exactly:" "$APP" || return 1
heroku_api DELETE "/apps/$APP"
ctt_audit_log heroku "DESTROYED $APP"
```

## Safety

- All mutations require `ctt_confirm`; `destroy` requires typing app name.
- Profile-level `require_confirm=true` for prod adds extra gate.
- Config var output auto-masks `KEY|SECRET|TOKEN|PASSWORD|DSN|URL` matches.
- Audit log records action + key names, NEVER values.
- 401 → token revoked; 403 → scope missing; 404 → app name wrong.
- Use scoped tokens (`heroku authorizations:create -s read`) over global.

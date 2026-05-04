---
name: heroku
description: Manage Heroku apps, dynos, releases, config vars, logs, and pipelines via the Heroku Platform API v3 with multi-account profile support. Use when the user asks to deploy/scale/restart Heroku apps, view config vars, tail logs, promote between pipeline stages, manage add-ons, or rollback releases. Switch accounts with --profile <name> or HEROKU_PROFILE env var.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /heroku — Heroku Platform API (multi-account)

Direct REST against `https://api.heroku.com` (no Heroku CLI dependency).
Uses Bearer auth with API key. Profiles isolate accounts/teams.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `HEROKU_PROFILE` → `~/.heroku/active_profile` → `[default]`.

## Dependencies

`curl`, `jq`. No Heroku CLI needed.

## Profile config

`~/.heroku/credentials` (mode 600):

```ini
[default]
api_key = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional: pin a default app for this profile
default_app = my-staging-app

[work]
api_key = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
default_app = production-api
# Optional: enforce confirmation for ANY mutating op on this profile
require_confirm = true

[client_a]
api_key = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get an API key:
- `heroku authorizations:create` (CLI), or
- Account Settings → Applications → Authorizations → Create authorization
- Use **scoped tokens** when possible (read, write, deploy) — avoid global tokens.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"

heroku_api() {
  local method="$1" path="$2"; shift 2
  curl -s -X "$method" \
    -H "Authorization: Bearer $CTT_API_KEY" \
    -H "Accept: application/vnd.heroku+json; version=3" \
    -H "Content-Type: application/json" \
    "$@" \
    "https://api.heroku.com$path"
}

# Resolve app: explicit arg → profile default → fail
heroku_app() {
  local app="${1:-$CTT_DEFAULT_APP}"
  [ -z "$app" ] && { echo "No app. Pass arg or set default_app in profile." >&2; return 1; }
  echo "$app"
}
```

## Dispatch

### `apps` — list apps

```bash
ctt_load_creds heroku "$PROFILE"
heroku_api GET /apps | jq -r '.[] | "\(.name)\t\(.region.name)\t\(.stack.name)\t\(.web_url)"'
```

### `info <app>` — app detail

```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP" | jq '{name, web_url, region: .region.name, stack: .stack.name, maintenance, archived_at, released_at, dyno_count: .dyno_count}'
```

### `config <app>` — list config vars (REDACTED secrets)

```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP/config-vars" | jq -r '
  to_entries[]
  | if (.key | test("KEY|SECRET|TOKEN|PASSWORD|PASS|DSN|URL"; "i")) then
      "\(.key)=****\(.value[-4:])"
    else
      "\(.key)=\(.value)"
    end
'
```

By default, mask anything that looks like a secret. `--reveal` flag to show
all in full (require explicit user request).

### `config-set <app> <KEY=value> [KEY=value ...]` — set config vars

```bash
APP=$(heroku_app "$1"); shift
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Set config vars on $APP ($CTT_PROFILE)?" || return 1

BODY=$(jq -n '$ARGS.positional | map(split("=")) | map({key: .[0], value: (.[1:] | join("="))}) | from_entries' --args "$@")
heroku_api PATCH "/apps/$APP/config-vars" -d "$BODY"
# Audit: only key NAMES, never values (handles JWT_KEY="x=y=z" correctly)
keys=$(printf '%s\n' "$@" | awk -F= '{print $1}' | tr '\n' ' ')
ctt_audit_log heroku "config-set $APP keys: $keys"
```

Audit log records key names but NOT values.

### `config-unset <app> <KEY> [KEY ...]`

```bash
APP=$(heroku_app "$1"); shift
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Unset $* on $APP ($CTT_PROFILE)?" || return 1

BODY=$(jq -n '$ARGS.positional | map({(.): null}) | add' --args "$@")
heroku_api PATCH "/apps/$APP/config-vars" -d "$BODY"
ctt_audit_log heroku "config-unset $APP keys: $*"
```

### `dynos <app>` — list running dynos

```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP/dynos" | jq -r '.[] | "\(.type).\(.name)\t\(.state)\t\(.size)\t\(.command)"'
```

### `scale <app> <type=count> [type=count ...]`

```bash
APP=$(heroku_app "$1"); shift
ctt_confirm "Scale $APP ($CTT_PROFILE): $*?" || return 1

BODY=$(jq -n '{updates: ($ARGS.positional | map(split("=")) | map({type: .[0], quantity: (.[1] | tonumber)}))}' --args "$@")
heroku_api PATCH "/apps/$APP/formation" -d "$BODY"
ctt_audit_log heroku "scale $APP $*"
```

### `restart <app> [dyno-name]`

```bash
APP=$(heroku_app "$1")
ctt_confirm "Restart $APP ${2:-(all dynos)}?" || return 1
if [ -n "$2" ]; then
  heroku_api DELETE "/apps/$APP/dynos/$2"
else
  heroku_api DELETE "/apps/$APP/dynos"
fi
ctt_audit_log heroku "restart $APP ${2:-all}"
```

### `releases <app> [--limit N]`

```bash
APP=$(heroku_app "$1")
case "$LIMIT" in ''|*[!0-9]*) LIMIT=20 ;; esac
heroku_api GET "/apps/$APP/releases" \
  -H "Range: version ..; max=$LIMIT, order=desc" \
  | jq -r '.[] | "v\(.version)\t\(.created_at)\t\(.user.email)\t\(.description)"'
```

### `rollback <app> <version>` — DESTRUCTIVE

```bash
APP=$(heroku_app "$1")
ctt_warn_destructive "Rollback $APP to v$2"
ctt_confirm "Rollback $APP to v$2 on $CTT_PROFILE?" "ROLLBACK" || return 1

BODY=$(jq -n --arg v "$2" '{release: $v}')
heroku_api POST "/apps/$APP/releases" -d "$BODY"
ctt_audit_log heroku "rollback $APP to v$2"
```

### `logs <app> [--tail] [--source app|heroku] [--lines N]`

```bash
APP=$(heroku_app "$1")
BODY=$(jq -n \
  --arg src "${SOURCE:-app}" \
  --argjson lines "${LINES:-100}" \
  --argjson tail "${TAIL:-false}" \
  '{source: $src, lines: $lines, tail: $tail}')

URL=$(heroku_api POST "/apps/$APP/log-sessions" -d "$BODY" | jq -r '.logplex_url')
[ "$TAIL" = "true" ] && curl -s "$URL" || curl -s "$URL" | tail -n "${LINES:-100}"
```

### `pipelines` — list pipelines

```bash
heroku_api GET /pipelines | jq -r '.[] | "\(.id)\t\(.name)"'
```

### `promote <pipeline-id> [from-stage]` — promote to next stage

```bash
ctt_warn_destructive "Pipeline promote: $1 ($CTT_PROFILE)"
ctt_confirm "Promote pipeline $1 from ${2:-staging}?" "PROMOTE" || return 1

BODY=$(jq -n --arg pid "$1" '{pipeline: {id: $pid}}')
heroku_api POST /pipeline-promotions -d "$BODY"
ctt_audit_log heroku "promote $1 from ${2:-staging}"
```

### `addons <app>` — list installed add-ons

```bash
APP=$(heroku_app "$1")
heroku_api GET "/apps/$APP/addons" | jq -r '.[] | "\(.addon_service.name)\t\(.plan.name)\t\(.state)"'
```

### `destroy <app>` — DESTROY APP (NEVER without explicit phrase)

```bash
APP=$(heroku_app "$1")
ctt_warn_destructive "DESTROY app $APP — irreversible"
ctt_confirm "Type the app name to destroy:" "$APP" || return 1
heroku_api DELETE "/apps/$APP"
ctt_audit_log heroku "DESTROYED $APP"
```

## Safety

- **Mutating ops** (config-set, scale, restart, rollback, promote, destroy)
  always go through `ctt_confirm` — Claude must NOT proceed without an
  explicit user request typed in the terminal.
- **`destroy`** requires typing the app name exactly (matches Heroku CLI's UX).
- **Profile-level `require_confirm`**: set on prod/work profiles to add a
  layer for ALL mutations.
- **Config var redaction**: anything matching KEY|SECRET|TOKEN|PASSWORD|DSN|URL
  is masked by default. `--reveal` flag to show.
- **Audit log** at `~/.claude-team-toolkit/audit.log` records every mutation
  with timestamp + profile + action — but NEVER the actual values.
- **API errors**: 401 → token revoked. 403 → scope missing. 404 → app name
  wrong. 422 → validation (e.g., scale to non-integer).

## Token-saving tip

Use scoped tokens (`heroku authorizations:create -d "label" -s read`) to
limit blast radius. For CI/automation, create a separate machine user.

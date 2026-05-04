---
name: sentry
description: Query Sentry issues, events, releases, and projects via the Sentry API with multi-organization profile support. Use when the user asks to fetch Sentry issues, list errors, mark issues resolved, find recent crashes, look up release health, or correlate errors to deploys. Switch orgs/projects with --profile <name> or SENTRY_PROFILE env var.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /sentry — error monitoring (multi-org)

REST against `https://sentry.io/api/0/` (or self-hosted Sentry instance).
Bearer auth with API token. Profiles isolate org/project pairs.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `SENTRY_PROFILE` → `~/.sentry/active_profile` → `[default]`.

## Dependencies

`curl`, `jq`.

## Profile config

`~/.sentry/credentials` (mode 600):

```ini
[default]
api_url = https://sentry.io/api/0
auth_token = sntrys_xxxxxxxxxxxxxxxxxxxxxxxx
org = my-org-slug
project = backend

[work]
api_url = https://sentry.example.com/api/0    # self-hosted
auth_token = sntrys_xxxxxxxxxxxxxxxxxxxxxxxx
org = company-org
project = api

[client_a]
api_url = https://sentry.io/api/0
auth_token = sntrys_xxxxxxxxxxxxxxxxxxxxxxxx
org = client-a-org
project = mobile
```

**Token scopes** (least privilege):

| Operation | Required scope |
|---|---|
| Read issues, events | `event:read` + `project:read` |
| Resolve / assign issues | `event:write` + `project:read` |
| Read releases | `project:releases` |
| Manage members | `org:read` (avoid unless needed) |

Get token: User Settings → Auth Tokens → Create New Token.
Use **org-scoped** tokens (limits to one org) when possible.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds sentry "$PROFILE"

sentry_api() {
  local method="$1" path="$2"; shift 2
  curl -s -X "$method" \
    -H "Authorization: Bearer $CTT_AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    "$@" \
    "$CTT_API_URL$path"
}
```

## Dispatch

### `issues [--query <q>] [--limit N]` — list issues

```bash
Q="${QUERY:-is:unresolved}"
sentry_api GET "/projects/$CTT_ORG/$CTT_PROJECT/issues/?query=$(printf %s "$Q" | jq -sRr @uri)&limit=${LIMIT:-25}" \
  | jq -r '.[] | "\(.shortId)\t\(.level)\t\(.count)\t\(.title)\n  \(.permalink)"'
```

Common queries:
- `is:unresolved` — open issues
- `is:unresolved age:-24h` — last 24h
- `level:error` — errors only
- `release:1.2.3` — specific release
- `assigned:me` — yours

### `issue <issueId>` — full issue detail

```bash
sentry_api GET "/issues/$1/" | jq '{
  id: .shortId, title, level, status, count, userCount,
  firstSeen, lastSeen, assignedTo,
  release: .firstRelease.version,
  permalink
}'
```

### `events <issueId> [--limit N]` — recent events for an issue

```bash
sentry_api GET "/issues/$1/events/?limit=${LIMIT:-10}" \
  | jq -r '.[] | "\(.eventID)\t\(.dateCreated)\t\(.user.email // "—")"'
```

### `event <eventId>` — full event detail (stacktrace + context)

```bash
sentry_api GET "/projects/$CTT_ORG/$CTT_PROJECT/events/$1/" | jq '{
  id: .eventID, message, level, dateCreated,
  user, environment, release, dist,
  exception: (.entries[] | select(.type=="exception") | .data.values[0] | {type, value, frames: (.stacktrace.frames | map({function, filename, lineno}))})
}'
```

### `resolve <issueId>` — mark resolved

```bash
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_confirm "Resolve issue $1 on $CTT_PROFILE?" || return 1
sentry_api PUT "/issues/$1/" -d '{"status":"resolved"}'
ctt_audit_log sentry "resolved $1"
```

### `assign <issueId> <username>`

```bash
BODY=$(jq -n --arg u "$2" '{assignedTo: $u}')
sentry_api PUT "/issues/$1/" -d "$BODY"
ctt_audit_log sentry "assigned $1 → $2"
```

### `releases [--limit N]` — recent releases

```bash
sentry_api GET "/organizations/$CTT_ORG/releases/?per_page=${LIMIT:-20}" \
  | jq -r '.[] | "\(.version)\t\(.dateCreated)\t\(.newGroups // 0) new issues\t\(.commitCount) commits"'
```

### `release <version>` — release detail + health

```bash
sentry_api GET "/organizations/$CTT_ORG/releases/$1/" | jq '{
  version, dateCreated,
  newGroups, commitCount,
  authors: [.authors[].name],
  projects: [.projects[].slug]
}'
```

### `projects` — list projects in org

```bash
sentry_api GET "/organizations/$CTT_ORG/projects/" \
  | jq -r '.[] | "\(.slug)\t\(.platform)\t\(.id)"'
```

## Safety

- Issue/event content (stacktraces, user data, error messages) often contains
  **PII** — never paste raw output into public chats. The skill should
  default to summary view; `--full` flag opt-in for raw.
- `assignedTo` field can be a user OR a team — confirm with user which.
- Resolve is reversible (status:unresolved) but `delete` is not — there is
  intentionally NO `delete` command in this skill.
- Self-hosted Sentry: `api_url` includes path `/api/0`. Don't forget.
- 429 Too Many Requests: Sentry API rate limit (40 req/s default for free).

## Token-saving tip

Use **organization-scoped** tokens. They're limited to one org which limits
blast radius if leaked.

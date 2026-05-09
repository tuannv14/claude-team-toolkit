---
name: postgres
description: Use when querying PostgreSQL — ad-hoc SELECT, EXPLAIN plans, schema/index/lock inspection, or slow-query investigation. Read-only by default; mutations require --write + typed confirmation. Multi-database via PG_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /postgres — read-mostly DB ops (multi-database)

Wraps `psql`. Read-only by default; mutating SQL requires `--write` + typed confirm.

Profile resolution: `--profile` → `PG_PROFILE` → `~/.postgres/active_profile` → `[default]`.

## Overview

Wraps `psql` with read-only-by-default safety. Mutating SQL requires explicit `--write` flag plus typed database name confirmation. Profile-level `read_only=true` hard-refuses writes even with the flag (defense-in-depth).

## When to Use

- Ad-hoc SELECT queries against dev/staging/prod
- EXPLAIN plans for slow queries
- Schema / index / lock inspection during incidents
- Identifying slow queries via `pg_stat_statements`
- Killing stuck backends (with `--force` + typed `KILL`)

## When NOT to Use

- Application data writes → that's the app, not this skill
- Migrations → use Rails / Alembic / Flyway with version control
- Bulk data exports → `pg_dump` or `COPY` directly
- Cross-database queries → use FDW or app-side joins

## Profile config

`~/.postgres/credentials` (mode 600):

```ini
[default]
host = localhost
port = 5432
database = myapp_development
user = postgres
password = postgres
sslmode = prefer

[prod]
host = prod-db.example.com
database = myapp_production
user = readonly_user        # defense-in-depth: physical RO at DB level
password = xxxxxxxxxxxxxx
sslmode = verify-full       # min `require` for non-localhost
read_only = true            # hard refuse writes even with --write
require_confirm = true
```

**SSL modes:** `disable` (local only), `prefer`, `require` (min for remote), `verify-ca`, `verify-full` (strongest).

**Why readonly_user**: defense-in-depth. Skill is read-only by default but DB-level grants prevent accidents even if skill is bypassed.

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds postgres "$PROFILE"

pg_run() {
  PGPASSWORD="$CTT_PASSWORD" psql \
    --host "$CTT_HOST" --port "${CTT_PORT:-5432}" \
    --dbname "$CTT_DATABASE" --username "$CTT_USER" \
    --set "sslmode=${CTT_SSLMODE:-prefer}" --no-password "$@"
}

is_mutating_sql() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -s '[:space:]' ' ' \
    | grep -qE '\b(insert|update|delete|drop|truncate|alter|grant|revoke|create|copy|vacuum|reindex)\b'
}

# Identifier validation: prevent SQL injection in unquoted contexts
valid_ident() {
  case "$1" in ''|*[!a-zA-Z0-9_]*) return 1 ;; *) return 0 ;; esac
}
```

## Dispatch

### `query <sql>` — execute (read-only by default)
```bash
SQL="$1"; WRITE="${WRITE:-false}"

if is_mutating_sql "$SQL"; then
  [ "$WRITE" != "true" ] && { echo "Mutating SQL detected. Re-run with --write." >&2; return 1; }
  [ "$CTT_READ_ONLY" = "true" ] && { echo "Profile $CTT_PROFILE is read_only. Refusing." >&2; return 1; }
  ctt_warn_destructive "Mutating SQL on $CTT_DATABASE@$CTT_HOST ($CTT_PROFILE)"
  ctt_confirm "Type the database name '$CTT_DATABASE' to confirm:" "$CTT_DATABASE" || return 1
fi

pg_run -c "$SQL"
[ "$WRITE" = "true" ] && ctt_audit_log postgres "MUTATE: ${SQL:0:100}"
```

### `explain <sql>` — query plan
```bash
pg_run -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) $SQL"
```
Drop `ANALYZE` to see plan without running query.

### `schema <table>` — describe a table (validate identifier)
```bash
valid_ident "$TABLE" || { echo "Invalid table name: $TABLE" >&2; return 1; }
pg_run -v t="$TABLE" -c "\d+ :\"t\""
```

### `tables [--schema name]` — list tables with sizes
```bash
SCHEMA="${SCHEMA:-public}"
valid_ident "$SCHEMA" || { echo "Invalid schema: $SCHEMA" >&2; return 1; }

pg_run -v schema="$SCHEMA" -c "
SELECT c.relname AS table,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
  c.reltuples::bigint AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = :'schema'
ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 50;"
```

### `indexes <table>` — list indexes + usage stats
```bash
valid_ident "$TABLE" || return 1
pg_run -v t="$TABLE" -c "
SELECT i.relname AS index,
  pg_size_pretty(pg_relation_size(i.oid)) AS size,
  s.idx_scan AS scans, s.idx_tup_read AS reads
FROM pg_class i
JOIN pg_index ix ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
LEFT JOIN pg_stat_user_indexes s ON s.indexrelid = i.oid
WHERE t.relname = :'t' ORDER BY i.relname;"
```
`scans=0` after weeks = removal candidate.

### `locks` — current locks (debug hangs)
```bash
pg_run -c "
SELECT pid, usename, state, wait_event_type, wait_event,
  query_start, now() - query_start AS duration, left(query, 80) AS query
FROM pg_stat_activity
WHERE state != 'idle' AND pid != pg_backend_pid()
ORDER BY query_start;"
```

### `kill <pid>` — terminate backend (require --force)
```bash
[ "$FORCE" != "true" ] && { echo "Add --force flag" >&2; return 1; }
case "$PID" in ''|*[!0-9]*) echo "PID must be numeric" >&2; return 1 ;; esac
ctt_confirm "Type KILL to confirm:" "KILL" || return 1
pg_run -v pid="$PID" -c "SELECT pg_terminate_backend(:'pid'::int);"
ctt_audit_log postgres "killed pid $PID"
```

### `slow [--limit N]` — slowest queries (requires pg_stat_statements)
```bash
pg_run -c "
SELECT round(mean_exec_time::numeric, 2) AS avg_ms,
  calls, round((total_exec_time/1000)::numeric, 1) AS total_sec,
  left(query, 100) AS query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT ${LIMIT:-20};"
```

## Common Mistakes

- Using `EXPLAIN ANALYZE` on expensive queries → it actually runs them. Plain `EXPLAIN` first.
- `sslmode=disable` for non-localhost → MITM risk. Min `require` for remote.
- Connecting as superuser when `readonly_user` works → blast radius huge on accidents
- Running mutations without `--write` → skill refuses (this is correct behavior)
- Killing a backend without checking `pg_stat_activity` first → can break replication
- "connection refused" → check `host`, `port`, firewall, `sslmode` in profile

## Safety

- **Read-only by default**: mutating keywords need `--write` flag explicitly.
- **`read_only=true` profile flag**: hard refuse even with `--write`.
- **Use a readonly DB user** for staging/prod (defense-in-depth).
- **`PGPASSWORD` env**, not command line — process listing won't show password.
- **`sslmode=require` minimum** for non-localhost.
- **EXPLAIN ANALYZE runs the query** — use plain `EXPLAIN` first for expensive scans.
- Audit log truncates SQL to 100 chars to avoid logging sensitive payloads.

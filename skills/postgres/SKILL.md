---
name: postgres
description: Run safe read-only SQL queries, EXPLAIN plans, schema inspection, and admin checks against PostgreSQL databases with multi-database profile support. Use when the user asks to query a Postgres database, check a slow query plan, inspect schema/indexes/locks, or look up table sizes. By default refuses mutating SQL (UPDATE/DELETE/DROP/TRUNCATE) without explicit --write flag and confirmation. Switch DBs with --profile <name> or PG_PROFILE env var.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /postgres — read-mostly DB ops (multi-database)

Wrapper around `psql` with a SAFETY-FIRST default: read-only queries unless
the user explicitly opts into writes. Profiles isolate database connections.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `PG_PROFILE` env → `~/.postgres/active_profile` → `[default]`.

## Dependencies

`psql` (PostgreSQL client):

```bash
# Windows
choco install postgresql --params '/Password:postgres'   # or just installer
# macOS
brew install libpq && brew link --force libpq
# Linux
sudo apt install postgresql-client
```

Verify: `psql --version`.

## Profile config

`~/.postgres/credentials` (mode 600):

```ini
[default]
host     = localhost
port     = 5432
database = myapp_development
user     = postgres
password = postgres
sslmode  = prefer

[staging]
host     = staging-db.example.com
port     = 5432
database = myapp_production
user     = readonly_user
password = xxxxxxxxxxxxxxxx
sslmode  = require
# Mark this as production-ish — refuse writes even with --write flag
read_only = true

[prod]
host     = prod-db.example.com
port     = 5432
database = myapp_production
user     = readonly_user
password = xxxxxxxxxxxxxxxx
sslmode  = require
read_only = true
require_confirm = true
```

**SSL modes:**

| Mode | When |
|---|---|
| `disable` | local dev only |
| `prefer` | local; falls back if server doesn't support SSL |
| `require` | minimum for any non-localhost — **use this for staging/prod** |
| `verify-ca` | + verify cert is signed by trusted CA |
| `verify-full` | + verify hostname matches cert (strongest) |

**Why a separate readonly_user**: the skill defaults to read-only mode, but
defense-in-depth says use a database user that physically cannot write to
prod. Create one with: `CREATE ROLE readonly_user WITH LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE myapp_production TO readonly_user; GRANT USAGE ON
SCHEMA public TO readonly_user; GRANT SELECT ON ALL TABLES IN SCHEMA public
TO readonly_user;`.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds postgres "$PROFILE"

# Build connection string (password via PGPASSWORD env, never on command line)
pg_run() {
  PGPASSWORD="$CTT_PASSWORD" psql \
    --host "$CTT_HOST" \
    --port "${CTT_PORT:-5432}" \
    --dbname "$CTT_DATABASE" \
    --username "$CTT_USER" \
    --set "sslmode=${CTT_SSLMODE:-prefer}" \
    --no-password \
    "$@"
}

# Detect mutating SQL — refuse unless --write
is_mutating_sql() {
  local q
  q=$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr -s '[:space:]' ' ')
  echo "$q" | grep -qE '\b(insert|update|delete|drop|truncate|alter|grant|revoke|create|copy|vacuum|reindex)\b'
}
```

## Dispatch

### `query <sql>` — execute query (READ-ONLY by default)

```bash
SQL="$1"
WRITE="${WRITE:-false}"

if is_mutating_sql "$SQL"; then
  if [ "$WRITE" != "true" ]; then
    echo "Mutating SQL detected. Re-run with --write flag to proceed." >&2
    return 1
  fi
  if [ "$CTT_READ_ONLY" = "true" ]; then
    echo "Profile $CTT_PROFILE is marked read_only. Refusing." >&2
    return 1
  fi
  ctt_warn_destructive "Mutating SQL on $CTT_DATABASE@$CTT_HOST ($CTT_PROFILE)"
  ctt_confirm "Run mutating SQL? Type the database name '$CTT_DATABASE' to confirm:" "$CTT_DATABASE" || return 1
fi

pg_run -c "$SQL"
[ "$WRITE" = "true" ] && ctt_audit_log postgres "MUTATE: ${SQL:0:100}"
```

### `explain <sql>` — query plan (always read-only)

```bash
pg_run -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) $SQL"
```

For just the plan without running: drop `ANALYZE`.

### `schema <table>` — describe a table

Validate identifier first to prevent SQL injection:

```bash
# Identifier validation: letters, digits, underscore only (PostgreSQL identifier rules)
case "$TABLE" in
  ''|*[!a-zA-Z0-9_]*) echo "Invalid table name: $TABLE" >&2; return 1 ;;
esac
pg_run -v t="$TABLE" -c "\d+ :\"t\""
```

### `tables [--schema <name>]` — list tables with sizes

```bash
SCHEMA="${SCHEMA:-public}"
case "$SCHEMA" in
  ''|*[!a-zA-Z0-9_]*) echo "Invalid schema name: $SCHEMA" >&2; return 1 ;;
esac

# Use psql variable + quote_ident() inside SQL — never string-interpolate identifiers
pg_run -v schema="$SCHEMA" -c "
SELECT
  c.relname AS table,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
  pg_stat_get_tuples_inserted(c.oid) + pg_stat_get_tuples_updated(c.oid) AS writes,
  c.reltuples::bigint AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = :'schema'
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 50;
"
```

### `indexes <table>` — list indexes (with usage stats)

```bash
case "$TABLE" in
  ''|*[!a-zA-Z0-9_]*) echo "Invalid table name: $TABLE" >&2; return 1 ;;
esac
pg_run -v t="$TABLE" -c "
SELECT
  i.relname AS index,
  pg_size_pretty(pg_relation_size(i.oid)) AS size,
  s.idx_scan AS scans,
  s.idx_tup_read AS reads
FROM pg_class i
JOIN pg_index ix ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
LEFT JOIN pg_stat_user_indexes s ON s.indexrelid = i.oid
WHERE t.relname = :'t'
ORDER BY i.relname;
"
```

Indexes with `scans = 0` after weeks of traffic are candidates for removal.

### `locks` — current locks (debugging hangs)

```bash
pg_run -c "
SELECT
  pid, usename, state, wait_event_type, wait_event,
  query_start, now() - query_start AS duration,
  left(query, 80) AS query
FROM pg_stat_activity
WHERE state != 'idle' AND pid != pg_backend_pid()
ORDER BY query_start;
"
```

### `kill <pid>` — terminate a backend (requires --force)

```bash
[ "$FORCE" != "true" ] && { echo "Add --force flag" >&2; return 1; }
case "$PID" in
  ''|*[!0-9]*) echo "PID must be a positive integer" >&2; return 1 ;;
esac
ctt_confirm "Terminate Postgres backend pid $PID on $CTT_PROFILE?" "KILL" || return 1
pg_run -v pid="$PID" -c "SELECT pg_terminate_backend(:'pid'::int);"
ctt_audit_log postgres "killed pid $PID"
```

### `slow [--limit N]` — slowest queries (requires pg_stat_statements)

```bash
pg_run -c "
SELECT
  round(mean_exec_time::numeric, 2) AS avg_ms,
  calls,
  round((total_exec_time / 1000)::numeric, 1) AS total_sec,
  left(query, 100) AS query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT ${LIMIT:-20};
"
```

If `pg_stat_statements` extension isn't installed, surface that to the user.

## Safety

- **Read-only by default**: any mutating SQL keyword (INSERT/UPDATE/DELETE/
  DROP/TRUNCATE/ALTER/GRANT/REVOKE/CREATE/COPY/VACUUM/REINDEX) requires the
  `--write` flag explicitly.
- **`read_only = true`** profile flag: refuses writes even with `--write`.
  Set this on staging/prod profiles for defense-in-depth.
- **Use a readonly DB user** for staging/prod. Skill flags don't replace
  database-level permissions.
- **`PGPASSWORD` env**, not `-W` or password-in-URL — process listing
  shouldn't expose the password.
- **`sslmode=require` minimum** for non-localhost. The skill warns if a
  remote host is configured with `disable` or `prefer`.
- **EXPLAIN ANALYZE runs the query** — for slow/expensive reads, use plain
  `EXPLAIN` (no ANALYZE) first to see if it'll scan a billion rows.
- Audit log records mutating SQL but **truncates to 100 chars** to avoid
  logging full payloads with potentially sensitive data.

## Token-saving tip

Profile-level `read_only = true` makes the skill mathematically safer for
prod profiles. Combine with database-side readonly user — defense in depth.

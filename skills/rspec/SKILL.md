---
name: rspec
description: RSpec runner for Rails. Parse failures from JSON output, re-run only failed (--only-failures), --next-failure loop, parallel via parallel_tests, simplecov coverage, --bisect order-dependent failures. Multi-project profiles.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /rspec — Rails test runner

Wrapper around `bundle exec rspec` with structured output parsing and
selective retry. No external credentials needed — runs locally.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `RSPEC_PROFILE` env → `~/.rspec/active_profile` → `[default]`.

## Dependencies

- Ruby project with RSpec in Gemfile (`gem 'rspec-rails'` or similar).
- `bundle install` already done.
- Optional: `parallel_tests`, `simplecov` for coverage.

## Profile config

`~/.rspec/credentials` (mode 600 — though profiles rarely contain secrets, kept consistent with other skills):

```ini
[default]
project_path = .
rails_env = test
workers = 1
seed_strategy = random        # or fixed for repro: fixed:42

[ci]
project_path = .
rails_env = test
workers = 4                   # parallel via parallel_tests
seed_strategy = fixed:1234

[other_project]
project_path = /path/to/another/rails/app
rails_env = test
workers = 2
```

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds rspec "$PROFILE"

cd "$CTT_PROJECT_PATH" || { echo "No project at $CTT_PROJECT_PATH" >&2; return 1; }

# Build base RSpec command as an array — preserves quoting on args with spaces
build_rspec_cmd() {
  RSPEC_CMD=(bundle exec rspec)
  case "$CTT_SEED_STRATEGY" in
    fixed:*) RSPEC_CMD+=(--seed "${CTT_SEED_STRATEGY#fixed:}") ;;
    random|"") RSPEC_CMD+=(--order random) ;;
  esac
  RSPEC_CMD+=(--format documentation --format json --out /tmp/rspec.json)
}
```

## Dispatch

### `run [path] [--example "pattern"]` — run specs

```bash
TARGET="${1:-spec/}"
build_rspec_cmd
EXTRA=()
[ -n "$EXAMPLE" ] && EXTRA+=(--example "$EXAMPLE")
RAILS_ENV="$CTT_RAILS_ENV" "${RSPEC_CMD[@]}" "$TARGET" "${EXTRA[@]}"
```

After run, parse `/tmp/rspec.json`:

```bash
jq -r '
  "Examples:    \(.summary.example_count)
Failures:    \(.summary.failure_count)
Pending:     \(.summary.pending_count)
Duration:    \(.summary.duration)s

Failed:" + (
  if .summary.failure_count == 0 then "  none"
  else (.examples | map(select(.status=="failed")) | map("  \(.full_description)\n    \(.file_path):\(.line_number)\n    \(.exception.message // "" | sub("\n"; " "; "g")[:120])") | join("\n"))
  end
)
' /tmp/rspec.json
```

### `failed` — re-run only failures from last run

RSpec writes `.rspec_status` (or `~/.rspec-local`) with last failures:

```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --only-failures
```

### `next-failure` — run until first failure

```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --next-failure
```

Useful for iterating: fix → run → next failure → fix → ...

### `parallel [path]` — run with parallel_tests (workers > 1)

```bash
[ "$CTT_WORKERS" -gt 1 ] || { echo "Profile workers=$CTT_WORKERS — use 'run' instead" >&2; return 1; }
[ -x "$(command -v bundle)" ] || { echo "bundle not found" >&2; return 1; }

# Verify parallel_tests gem is in Gemfile
grep -q "parallel_tests" Gemfile.lock || {
  echo "parallel_tests not in Gemfile.lock — add: gem 'parallel_tests', group: :test" >&2
  return 1
}

# Setup parallel test databases (one-time per machine)
[ -f "config/database.yml" ] && {
  bundle exec rake parallel:create parallel:load_schema 2>/dev/null || true
}

bundle exec parallel_rspec -n "$CTT_WORKERS" "${1:-spec/}"
```

### `coverage [path]` — run with simplecov coverage

```bash
grep -q "simplecov" Gemfile.lock || {
  echo "simplecov not in Gemfile — add: gem 'simplecov', require: false, group: :test" >&2
  return 1
}

# Ensure spec_helper has SimpleCov.start at the top
grep -q "SimpleCov.start" spec/spec_helper.rb 2>/dev/null || \
grep -q "SimpleCov.start" spec/rails_helper.rb 2>/dev/null || {
  echo "Add 'require \"simplecov\"; SimpleCov.start \"rails\"' at the TOP of spec/spec_helper.rb" >&2
  return 1
}

COVERAGE=true RAILS_ENV="$CTT_RAILS_ENV" build_rspec_cmd; "${RSPEC_CMD[@]}" "${1:-spec/}"
echo ""
echo "Coverage report: file://$(pwd)/coverage/index.html"
[ -f coverage/.last_run.json ] && jq -r '"Line coverage: \(.result.line)%"' coverage/.last_run.json
```

### `summary` — last run summary (no re-run)

```bash
[ -f /tmp/rspec.json ] || { echo "No prior run found at /tmp/rspec.json" >&2; return 1; }
jq -r '"Examples: \(.summary.example_count)  Failed: \(.summary.failure_count)  Pending: \(.summary.pending_count)  Duration: \(.summary.duration)s"' /tmp/rspec.json
```

### `tag <tag-name> [path]` — run only specs tagged

```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --tag "$TAG" "${1:-spec/}"
```

Common tags: `:focus` (for dev), `:slow` (skip in fast loop), `:integration`.

### `bisect <description>` — find which spec causes failure when run together

When tests pass individually but fail in suite (order-dependent bug):

```bash
bundle exec rspec --bisect --example "$DESC"
```

## Implementation notes

- **`--format json`** is RSpec 3+. For RSpec 2 use a different approach.
- **`/tmp/rspec.json`** is overwritten each run — copy it if comparing runs.
- **`parallel_tests`** uses `RAILS_ENV=test` + `TEST_ENV_NUMBER` to isolate
  databases (e.g., `myapp_test1`, `myapp_test2`).
- For Rails system tests with browser, may need `chromedriver` or
  `playwright-ruby-client`.
- `--seed N` reproduces test order — important for debugging order-dependent
  failures.

## Safety

- Tests run **with full project access** — they can read any file, hit any
  service the test env points at. Never run untrusted spec files.
- `RAILS_ENV=test` should be enforced by the skill. NEVER let user pass
  `RAILS_ENV=production` here — refuse with error.
- If a profile points at a non-test env (`rails_env != test`), refuse to
  run — that's a misconfiguration.
- Test databases get **dropped/recreated**. Make sure the profile points to
  a TEST database, not staging or prod.

## Token-saving tip

Use `--example "pattern"` to run a focused subset during development, then
full suite via `parallel` only on commit / push.

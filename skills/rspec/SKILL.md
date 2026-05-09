---
name: rspec
description: Use when running RSpec on a Rails project — re-running only failed examples, parallelizing with parallel_tests, generating coverage, or bisecting test-order failures. Multi-project via RSPEC_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /rspec — Rails test runner

Wraps `bundle exec rspec` with structured output parsing and selective retry. No external credentials.

Profile resolution: `--profile` → `RSPEC_PROFILE` → `~/.rspec/active_profile` → `[default]`.

## Overview

Wraps `bundle exec rspec` with structured JSON output parsing and selective retry. No external credentials. Profiles isolate per-project test settings (parallel workers, seed strategy, rails_env).

## When to Use

- Running RSpec test suites with structured failure output
- Re-running only failed examples (after a fix attempt)
- Parallelizing with `parallel_tests` (multi-core machines, CI)
- Bisecting test-order failures (`--bisect`)
- Coverage reports via simplecov

## When NOT to Use

- Non-Rails Ruby tests → bare `rspec` works fine
- Minitest projects → use `rake test`, not this skill
- E2E / browser tests → not RSpec's job
- Production debugging → tests are not a debugger

## Profile config

`~/.rspec/credentials` (mode 600 — though profiles rarely contain secrets):

```ini
[default]
project_path = .
rails_env = test
workers = 1
seed_strategy = random        # or "fixed:42" for repro

[ci]
project_path = .
rails_env = test
workers = 4                   # parallel via parallel_tests
seed_strategy = fixed:1234
```

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds rspec "$PROFILE"

cd "$CTT_PROJECT_PATH" || { echo "No project at $CTT_PROJECT_PATH" >&2; return 1; }

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
build_rspec_cmd
RAILS_ENV="$CTT_RAILS_ENV" "${RSPEC_CMD[@]}" "${1:-spec/}" ${EXAMPLE:+--example "$EXAMPLE"}
```

After run, parse `/tmp/rspec.json`:
```bash
jq -r '
  "Examples: \(.summary.example_count)  Failed: \(.summary.failure_count)  Pending: \(.summary.pending_count)  Duration: \(.summary.duration)s\n\n" +
  "Failed:\n" + (
    if .summary.failure_count == 0 then "  none"
    else (.examples | map(select(.status=="failed")) | map("  \(.full_description)\n    \(.file_path):\(.line_number)") | join("\n"))
    end
  )
' /tmp/rspec.json
```

### `failed` — re-run only failures from last run
```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --only-failures
```

### `next-failure` — run until first failure
```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --next-failure
```
Iterate: fix → run → next failure → fix.

### `parallel [path]` — parallel_tests (workers > 1)
```bash
[ "$CTT_WORKERS" -gt 1 ] || { echo "Profile workers=$CTT_WORKERS — use 'run'" >&2; return 1; }
grep -q "parallel_tests" Gemfile.lock || {
  echo "parallel_tests not in Gemfile.lock — add: gem 'parallel_tests', group: :test" >&2
  return 1
}

# Setup parallel test databases (one-time per machine)
[ -f "config/database.yml" ] && bundle exec rake parallel:create parallel:load_schema 2>/dev/null || true

bundle exec parallel_rspec -n "$CTT_WORKERS" "${1:-spec/}"
```

### `coverage [path]` — simplecov coverage
```bash
grep -q "simplecov" Gemfile.lock || {
  echo "simplecov not in Gemfile — add: gem 'simplecov', require: false, group: :test" >&2
  return 1
}

# Verify spec_helper has SimpleCov.start at top
grep -q "SimpleCov.start" spec/spec_helper.rb 2>/dev/null || \
grep -q "SimpleCov.start" spec/rails_helper.rb 2>/dev/null || {
  echo "Add 'require \"simplecov\"; SimpleCov.start \"rails\"' at TOP of spec/spec_helper.rb" >&2
  return 1
}

build_rspec_cmd
COVERAGE=true RAILS_ENV="$CTT_RAILS_ENV" "${RSPEC_CMD[@]}" "${1:-spec/}"
echo "Coverage: file://$(pwd)/coverage/index.html"
[ -f coverage/.last_run.json ] && jq -r '"Line coverage: \(.result.line)%"' coverage/.last_run.json
```

### `summary` — last run summary (no re-run)
```bash
[ -f /tmp/rspec.json ] || { echo "No prior run found" >&2; return 1; }
jq -r '"Examples: \(.summary.example_count)  Failed: \(.summary.failure_count)  Pending: \(.summary.pending_count)  Duration: \(.summary.duration)s"' /tmp/rspec.json
```

### `tag <tag-name> [path]` — run only tagged
```bash
build_rspec_cmd; "${RSPEC_CMD[@]}" --tag "$TAG" "${1:-spec/}"
```
Common tags: `:focus`, `:slow`, `:integration`.

### `bisect <description>` — find order-dependent failure
```bash
bundle exec rspec --bisect --example "$DESC"
```

## Common Mistakes

- Forgetting `RAILS_ENV=test` → drops dev/prod data. Skill enforces this.
- `--seed random` then trying to reproduce → impossible. Set `fixed:N` for repro.
- Running `parallel` with workers=1 in profile → no speedup, use `run` instead
- `simplecov.start` AFTER `require 'rails'` → coverage misses framework load
- Re-running full suite when `--only-failures` would work → wastes minutes
- "Database is locked" → another test process holding it; kill stale `rspec` first

## Implementation notes

- `--format json` requires RSpec 3+.
- `/tmp/rspec.json` overwritten each run.
- `parallel_tests` uses `RAILS_ENV=test` + `TEST_ENV_NUMBER` to isolate DBs (`myapp_test1`, `myapp_test2`...).
- `--seed N` reproduces order — important for debugging order-dependent failures.

## Safety

- Tests run with full project access — never run untrusted spec files.
- **`RAILS_ENV=test` enforced** — refuse if profile has non-test rails_env.
- Test databases get dropped/recreated. Profile must point to TEST DB, not staging/prod.

## Token-saving tip

Use `--example "pattern"` for focused subset during dev, full `parallel` only on commit/push.

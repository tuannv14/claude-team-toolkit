---
name: brakeman
description: Run Brakeman static security scanner on a Ruby on Rails project. Use when the user asks to scan for Rails security vulnerabilities, run brakeman, check for SQL injection / XSS / mass assignment / CSRF / unsafe redirects, or audit a Rails app's security posture. Parses JSON output and surfaces high/medium issues with file:line references.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /brakeman — Rails security scanner

Wrapper around [Brakeman](https://brakemanscanner.org/) for Rails projects.
No credentials needed — purely local static analysis.

Arguments: `$ARGUMENTS`

## Dependencies

```bash
gem install brakeman                    # one-time, system-wide
# or in project Gemfile (development group):
#   gem 'brakeman', require: false
bundle exec brakeman --version          # if Gemfile-installed
```

If neither path works, tell the user and stop — do NOT try to scan without it.

## Dispatch

Default project: current working directory (`.`). Override with `--path <dir>`.

### `scan [path] [--severity high|medium|low|all]` — full scan

```bash
PATH_ARG="${1:-.}"
SEV="${SEV:-medium}"   # default: high+medium

# Use project's brakeman if Gemfile-pinned, else system gem
if [ -f "$PATH_ARG/Gemfile" ] && grep -q "brakeman" "$PATH_ARG/Gemfile" 2>/dev/null; then
  CMD="bundle exec brakeman"
else
  CMD="brakeman"
fi

$CMD -p "$PATH_ARG" -f json -o /tmp/brakeman.json --no-progress 2>/dev/null
```

Then parse `/tmp/brakeman.json` with jq:

```bash
jq -r --arg sev "$SEV" '
  .warnings[]
  | select(
      ($sev=="all") or
      ($sev=="high"   and .confidence=="High") or
      ($sev=="medium" and (.confidence=="High" or .confidence=="Medium")) or
      ($sev=="low"    and true)
    )
  | "[\(.confidence)] \(.warning_type): \(.message)\n  \(.file):\(.line)\n  \(.code // "")\n"
' /tmp/brakeman.json
```

Summary at the end:
```bash
jq -r '
  .scan_info | "Scanned \(.number_of_controllers) controllers, \(.number_of_models) models, \(.number_of_templates) templates in \(.duration)s"
' /tmp/brakeman.json
jq -r '.warnings | group_by(.confidence) | .[] | "\(.[0].confidence): \(length)"' /tmp/brakeman.json
```

### `diff [base-branch]` — only NEW issues vs base branch

```bash
git stash -u
git checkout "${BASE:-main}"
$CMD -f json -o /tmp/brakeman-base.json --no-progress
git checkout -
git stash pop || true
$CMD -f json -o /tmp/brakeman-head.json --no-progress

# Diff by fingerprint (brakeman's stable warning identifier)
jq -s '
  (.[0].warnings | map(.fingerprint)) as $base
  | .[1].warnings | map(select(.fingerprint as $f | $base | index($f) | not))
' /tmp/brakeman-base.json /tmp/brakeman-head.json
```

Only show warnings whose fingerprints don't exist on base — true regressions.

### `ignore <fingerprint>` — mark a warning as known/false-positive

Brakeman uses `config/brakeman.ignore`. Append a fingerprint:

```bash
mkdir -p config
[ -f config/brakeman.ignore ] || echo '{"ignored_warnings":[]}' > config/brakeman.ignore
jq --arg fp "$FINGERPRINT" --arg note "$NOTE" '
  .ignored_warnings += [{fingerprint: $fp, note: $note}]
' config/brakeman.ignore > config/brakeman.ignore.tmp \
  && mv config/brakeman.ignore.tmp config/brakeman.ignore
```

`<note>` should explain WHY it's being ignored (false positive, accepted risk, fix tracked at #issue).

## Implementation notes

- Brakeman output is verbose — always use `-f json` and parse, never raw stdout.
- Default severity threshold is **medium** (High + Medium confidence). Low has many false positives — only show on demand.
- `brakeman.ignore` MUST be committed — that's the audit trail of decisions.
- `--no-progress` suppresses TTY-only progress noise.
- For CI: exit non-zero if any High-confidence warnings exist:
  ```bash
  jq -e '.warnings | map(select(.confidence=="High")) | length == 0' /tmp/brakeman.json
  ```

## Security note

The scan results identify potential vulnerabilities — treat the output as
**sensitive information**. Don't paste it into public chats or PRs without
review. The fingerprints, file paths, and code snippets reveal attack surface.

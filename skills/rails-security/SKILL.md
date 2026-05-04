---
name: rails-security
description: Run Brakeman static security scanner + bundler-audit CVE check on a Ruby on Rails project. Use when the user asks to audit Rails security, scan for SQL injection / XSS / CSRF / mass assignment, check Gemfile.lock for known CVEs, run a pre-PR security gate, or generate a regression-only diff against the base branch. Combines two tools with shared output formatting.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /rails-security — Brakeman + bundler-audit (Rails-only)

Combined skill for the two Rails-focused security scanners. No credentials —
purely local static analysis.

| Tool | What it scans | Output |
|---|---|---|
| **Brakeman** | App code — SQL injection, XSS, CSRF, mass assignment, unsafe redirects, etc. | warnings with file:line |
| **bundler-audit** | `Gemfile.lock` — known CVEs in installed gem versions | advisories with upgrade path |

Arguments: `$ARGUMENTS`. First token = subcommand: `vulns`, `cves`, `audit`, `diff`, `ignore`, `update`.

## Dependencies

```bash
gem install brakeman bundler-audit
brakeman --version
bundle-audit --version          # binary is bundle-audit (with hyphen)
```

If either is missing, the corresponding subcommand will skip with a clear
message.

Running inside a Rails project (must contain `Gemfile.lock` for `cves`).

## Helpers

```bash
# Brakeman: prefer Gemfile-pinned version if available
brakeman_cmd() {
  local cmd=()
  if [ -f "${1:-.}/Gemfile" ] && grep -q "brakeman" "${1:-.}/Gemfile" 2>/dev/null; then
    cmd=(bundle exec brakeman)
  else
    cmd=(brakeman)
  fi
  printf '%s\n' "${cmd[@]}"
}
```

## Dispatch

### `vulns [path] [--severity high|medium|low|all]` — Brakeman scan

```bash
PATH_ARG="${1:-.}"
SEV="${SEV:-medium}"

mapfile -t CMD < <(brakeman_cmd "$PATH_ARG")
"${CMD[@]}" -p "$PATH_ARG" -f json -o /tmp/brakeman.json --no-progress 2>/dev/null

jq -r --arg sev "$SEV" '
  .warnings[]
  | select(
      ($sev=="all") or
      ($sev=="high"   and .confidence=="High") or
      ($sev=="medium" and (.confidence=="High" or .confidence=="Medium")) or
      ($sev=="low"    and true)
    )
  | "[\(.confidence)] \(.warning_type): \(.message)\n  \(.file):\(.line)\n"
' /tmp/brakeman.json

jq -r '"Scanned \(.scan_info.number_of_controllers) controllers, \(.scan_info.number_of_models) models in \(.scan_info.duration)s"' /tmp/brakeman.json
jq -r '.warnings | group_by(.confidence) | .[] | "\(.[0].confidence): \(length)"' /tmp/brakeman.json
```

### `cves [path]` — bundler-audit CVE scan

```bash
PROJ="${1:-.}"
[ -f "$PROJ/Gemfile.lock" ] || { echo "No Gemfile.lock at $PROJ" >&2; return 1; }

bundle-audit update --quiet 2>/dev/null || true
(cd "$PROJ" && bundle-audit check --format json) > /tmp/bundler-audit.json 2>/dev/null

jq -r '
  .results[]?
  | "[\(.advisory.criticality // "unknown" | ascii_upcase)] \(.gem.name) \(.gem.version)
  CVE: \(.advisory.cve // .advisory.id)
  Fix: upgrade to \(.advisory.patched_versions | join(", "))
  \(.advisory.title)
  \(.advisory.url)"
' /tmp/bundler-audit.json

jq -r '
  if (.results // []) | length == 0 then "No vulnerabilities."
  else "\(.results | length) vuln(s) found." end
' /tmp/bundler-audit.json
```

### `audit [path]` — both scanners + combined exit status

```bash
echo "=== Code (Brakeman) ==="
"$0" vulns "$1"
echo ""
echo "=== Dependencies (bundler-audit) ==="
"$0" cves "$1"

# Pre-PR gate: exit non-zero if HIGH-confidence Brakeman OR any CVE
HIGH_BR=$(jq -r '[.warnings[] | select(.confidence=="High")] | length' /tmp/brakeman.json 2>/dev/null || echo 0)
CVES=$(jq -r '(.results // []) | length' /tmp/bundler-audit.json 2>/dev/null || echo 0)

if [ "$HIGH_BR" -gt 0 ] || [ "$CVES" -gt 0 ]; then
  echo ""
  echo "GATE: ${HIGH_BR} high-confidence Brakeman warnings + ${CVES} CVEs"
  return 1
fi
```

### `diff [base-branch]` — only NEW issues vs base (non-destructive)

Uses `git worktree add` to a temp directory — your working tree is never touched.

```bash
BASE="${BASE:-main}"
WT="$(mktemp -d)/rails-security-base"
cleanup() { git worktree remove --force "$WT" 2>/dev/null; rm -rf "$WT"; }
trap cleanup EXIT INT TERM

git worktree add --quiet "$WT" "$BASE" || { echo "Cannot create worktree at $BASE" >&2; return 1; }

# Brakeman diff by fingerprint
mapfile -t CMD < <(brakeman_cmd ".")
(cd "$WT" && "${CMD[@]}" -f json -o /tmp/brakeman-base.json --no-progress 2>/dev/null) || true
"${CMD[@]}" -f json -o /tmp/brakeman-head.json --no-progress 2>/dev/null

echo "=== NEW Brakeman warnings ==="
jq -s '
  (.[0].warnings | map(.fingerprint)) as $base
  | .[1].warnings | map(select(.fingerprint as $f | $base | index($f) | not))
  | .[] | "[\(.confidence)] \(.warning_type) — \(.file):\(.line)\n  \(.message)"
' /tmp/brakeman-base.json /tmp/brakeman-head.json

# bundler-audit diff by advisory id
(cd "$WT" && bundle-audit check --format json) > /tmp/ba-base.json 2>/dev/null || echo '{}' > /tmp/ba-base.json
bundle-audit check --format json > /tmp/ba-head.json 2>/dev/null || echo '{}' > /tmp/ba-head.json

echo ""
echo "=== NEW CVEs ==="
jq -s '
  (.[0].results // [] | map(.advisory.id)) as $base
  | (.[1].results // []) | map(select(.advisory.id as $id | $base | index($id) | not))
  | .[] | "\(.gem.name) \(.gem.version) — \(.advisory.cve // .advisory.id) — \(.advisory.title)"
' /tmp/ba-base.json /tmp/ba-head.json
```

### `ignore brakeman <fingerprint> [note]`

Brakeman ignores via `config/brakeman.ignore`:

```bash
mkdir -p config
[ -f config/brakeman.ignore ] || echo '{"ignored_warnings":[]}' > config/brakeman.ignore
jq --arg fp "$FINGERPRINT" --arg note "${NOTE:-no reason given}" '
  .ignored_warnings += [{fingerprint: $fp, note: $note}]
' config/brakeman.ignore > config/brakeman.ignore.tmp \
  && mv config/brakeman.ignore.tmp config/brakeman.ignore
```

### `ignore cve <CVE-ID> [note]`

```bash
[ -f .bundler-audit.yml ] || echo "ignore: []" > .bundler-audit.yml
echo "Edit .bundler-audit.yml to add: $CVE_ID  # ${NOTE:-add reason}"
```

ALWAYS require a reason comment alongside an ignore — without it, future
maintainers can't audit the decision.

### `update` — refresh bundler-audit advisory DB

```bash
bundle-audit update
```

DB lives at `~/.local/share/ruby-advisory-db` (or similar per OS). Refresh
weekly minimum.

## Implementation notes

- Brakeman exit code 0 even with warnings — parse JSON, don't rely on exit.
- bundler-audit exit code 1 = vulns found. Don't treat as error in shell.
- `--no-progress` suppresses TTY-only progress noise.
- `bundle-audit update` hits GitHub — fallback `--no-update` for offline.
- Advisory `criticality` field is optional in older entries — handle missing
  with `// "unknown"`.

## Safety

- **Scan output reveals attack surface** — fingerprints, file paths, gem
  versions. Don't paste raw scan results into public chats/PRs without
  redaction.
- **`brakeman.ignore` and `.bundler-audit.yml` MUST be committed** — they're
  the audit trail of accepted-risk decisions. Each entry needs a human-readable
  reason.
- **Never bypass these scanners in CI** without an approved exception (PR
  comment + ignore entry with reason). Pre-PR gate via `audit` subcommand.

## Token-saving tip

Use `diff` mode for PR review — only see NEW issues, ignore existing
backlog. Drastically cuts output noise.

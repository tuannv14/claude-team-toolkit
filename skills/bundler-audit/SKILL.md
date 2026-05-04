---
name: bundler-audit
description: Run bundler-audit to scan Ruby project Gemfile.lock for known CVEs and insecure gem versions. Use when the user asks to audit Ruby gem vulnerabilities, check Gemfile.lock for CVEs, run bundler-audit, or verify dependency safety. Parses output and surfaces actionable upgrade paths.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /bundler-audit — Ruby gem CVE scanner

Wrapper around [bundler-audit](https://github.com/rubysec/bundler-audit). No
credentials — reads `Gemfile.lock` and the local advisory DB.

Arguments: `$ARGUMENTS`

## Dependencies

```bash
gem install bundler-audit               # one-time
bundle-audit --version                  # binary is bundle-audit (with hyphen)
```

If missing, stop and tell user to install.

## Dispatch

Default path: current dir (must contain `Gemfile.lock`).

### `check [path]` — scan and report

```bash
PROJ="${1:-.}"
[ -f "$PROJ/Gemfile.lock" ] || { echo "No Gemfile.lock at $PROJ" >&2; return 1; }

# Update advisory DB first (or rely on user's recent update)
bundle-audit update --quiet 2>/dev/null || true

# Scan — exit code 1 if vulns found, 0 if clean
cd "$PROJ" && bundle-audit check --format json 2>/dev/null > /tmp/bundler-audit.json
```

Parse with jq:

```bash
jq -r '
  .results[]?
  | "[\(.advisory.criticality // "unknown" | ascii_upcase)] \(.gem.name) \(.gem.version)
  CVE: \(.advisory.cve // .advisory.id)
  Fix: upgrade to \(.advisory.patched_versions | join(", "))
  Title: \(.advisory.title)
  URL: \(.advisory.url)
"
' /tmp/bundler-audit.json
```

Summary:
```bash
jq -r '
  if .results == null or (.results | length) == 0 then
    "No vulnerabilities."
  else
    "\(.results | length) vulnerabilit\(if .results|length==1 then "y" else "ies" end) found."
  end
' /tmp/bundler-audit.json
```

### `update` — refresh advisory DB

```bash
bundle-audit update
```

The DB lives at `~/.local/share/ruby-advisory-db` (or similar per OS). Refresh
weekly minimum, daily ideal for active projects.

### `ignore <CVE-ID>` — append to `.bundler-audit.yml`

```yaml
# .bundler-audit.yml — committed, audited
ignore:
  - CVE-2024-12345  # reason: false positive, gem usage doesn't trigger path
```

```bash
mkdir -p "$(dirname .bundler-audit.yml)"
if [ ! -f .bundler-audit.yml ]; then
  echo "ignore: []" > .bundler-audit.yml
fi
# Append (manual edit recommended — needs human-readable reason)
echo "  - $CVE_ID" >> .bundler-audit.yml
echo "Edit .bundler-audit.yml to add a reason comment for $CVE_ID" >&2
```

ALWAYS require a reason comment alongside an ignore — without it, future
maintainers can't audit the decision.

### `diff [base-branch]` — only NEW vulns vs base

Uses `git worktree add` — **non-destructive**.

```bash
BASE="${BASE:-main}"
WT="$(mktemp -d)/bundler-audit-base"
cleanup() { git worktree remove --force "$WT" 2>/dev/null; rm -rf "$WT"; }
trap cleanup EXIT INT TERM

git worktree add --quiet "$WT" "$BASE" || { echo "Cannot create worktree at $BASE" >&2; return 1; }

(cd "$WT" && bundle-audit check --format json > /tmp/ba-base.json 2>/dev/null) || true
bundle-audit check --format json > /tmp/ba-head.json 2>/dev/null

jq -s '
  (.[0].results // [] | map(.advisory.id)) as $base
  | (.[1].results // []) | map(select(.advisory.id as $id | $base | index($id) | not))
' /tmp/ba-base.json /tmp/ba-head.json
```

## Implementation notes

- Exit code 1 means vulns found — don't treat as error in shell, parse json.
- `bundle-audit update` hits GitHub — may fail in offline/firewalled envs.
  Fallback: `bundle-audit check --no-update`.
- Advisories include `criticality` (low/medium/high/critical) but it's
  optional in older entries — handle missing field with `// "unknown"`.

## Security note

Scan output reveals exact gem versions in use → attack surface info. Don't
paste raw scan results into public chats/PRs. Sanitize first or share only
the actionable upgrade list.

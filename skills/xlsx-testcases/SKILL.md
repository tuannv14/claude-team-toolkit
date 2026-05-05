---
name: xlsx-testcases
description: Convert XLSX test cases to Maestro YAML / Detox / Markdown + sync Azure DevOps Test Plans. Use when team has xlsx test cases needing runnable specs or ADO sync.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /xlsx-testcases — bridge tester xlsx ↔ runnable tests

Keeps xlsx as **source of truth** for test cases (testers' familiar tool),
generates runnable artifacts on demand, and syncs to Azure DevOps Test Plans.

Deps: `anthropic-skills:xlsx` (delegate parsing), `jq`, `python3`. ADO sync
uses `/azure-devops` skill (multi-profile).

## Schema mapping

Per-workbook schema at `<xlsx-folder>/.testcase-schema.yml` (committed):

```yaml
sheet: "Test Cases"           # or "*" for all sheets
header_row: 2
columns:
  id:         "TC ID"          # required, unique
  module:     "Module"
  title:      "Title"          # required
  steps:      "Steps"          # multi-line cell
  expected:   "Expected Result"
  priority:   "Priority"
  category:   "Category"       # smoke/regression/etc.
  status:     "Status"         # New/Updated/Stable
parsing:
  steps_separator: "newline"   # or "numbered"
  priority_map:
    P0: high
    P1: high
    P2: medium
    P3: low
```

If no schema file exists, prompt to infer from first sheet header row and
write file for review.

## Dispatch

### `parse <xlsx-path>` → `/tmp/xlsx-testcases-<hash>.json`
Delegates to `anthropic-skills:xlsx` for parsing. Cache key = SHA-256 of
xlsx mtime+size+schema content. Output array of testcase objects.

### `gen maestro <xlsx-path> [--out tests/maestro/]` — Maestro YAML

For each TC: `tests/maestro/<id>-<slug>.yaml`. Step translation heuristic:

| xlsx step pattern | Maestro action |
|---|---|
| "Open app" / "Launch" | `- launchApp` |
| "Tap [X]" | `- tapOn: "X"` |
| "Enter [X] in [field]" | `- tapOn: "field"` + `- inputText: "X"` |
| "Verify [X] visible" | `- assertVisible: "X"` |

Unmapped steps emit `# UNMAPPED:` comment and surface in run summary.

### `gen detox <xlsx-path> [--out e2e/]` — Detox `.test.ts`
Same flow as Maestro but JavaScript spec.

### `gen markdown <xlsx-path>` — manual QA checklist
```markdown
## TC001 — Title  [tags, priority]
**Precondition:** ...
**Steps:** 1. ... 2. ...
**Expected:** ...
[ ] Pass  [ ] Fail  [ ] Skip   Notes: ___
```

### `sync ado <xlsx-path> [--plan <id>] [--dry-run]`
Sync to Azure DevOps Test Plans (uses `/azure-devops` skill auth):
1. Search existing test cases by `TC ID`
2. Update if found (PATCH), else create (POST)
3. Track sync state in `<xlsx-folder>/.testcase-sync-state.json` (committed) —
   only sync TCs whose hash changed since last sync.

PAT scope required: `Test Plans (Read & Write)` + `Work Items (Read & Write)`.

`--dry-run` shows what would change without writing.

### `coverage <xlsx-path> --against <test-folder>` — gap report

```
Total TCs in xlsx:       142
Generated as Maestro:    98 (69%)
Synced to ADO:           120 (85%)

HIGH-priority untested TCs:
  TC047  IAP   Restore purchase across devices
  TC089  Push  Background notification handling
```

### `diff <xlsx-path>` — what changed since last sync
Compare current xlsx against `.testcase-sync-state.json`:
```
Added: 3 TCs    Modified: 12 TCs    Removed: 1 TC
```

## Implementation notes

- **Delegate parsing** to `anthropic-skills:xlsx`, don't reinvent.
- Step translation is heuristic — emit UNMAPPED comments, never silently drop.
- Cache key from input hash → no re-parse on repeated invocation.
- Per-TC sha256(title+steps+expected+priority) → ADO sync only delta.
- UTF-8 throughout (Vietnamese / Asian content must round-trip).

## Safety

- xlsx may contain sensitive test data (sample passwords, PII). Treat as
  **confidential**: cache to `/tmp/`, don't include verbatim in chat beyond
  what user asked.
- ADO sync is mutating → always run `--dry-run` first; require `ctt_confirm`
  before actual sync. Audit log records TC IDs only, not content.
- Generated runners are committed code — review before pushing public.
- `.testcase-schema.yml` and `.testcase-sync-state.json` are safe to commit
  (no test data, only mapping + hashes).

## Workflow for QA team

1. **Tester** writes test cases in xlsx (current habit, no change).
2. **Lead/Dev** runs `/xlsx-testcases gen maestro <xlsx>` to scaffold runners.
3. **Dev** edits scaffolded YAML to add real selectors / data refs.
4. **CI** runs Maestro on every PR.
5. **Weekly**: lead runs `sync ado` + `coverage` to identify gaps.

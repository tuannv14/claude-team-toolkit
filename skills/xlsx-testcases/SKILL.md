---
name: xlsx-testcases
description: Convert XLSX test case workbooks into runnable test specs (Maestro YAML, Detox JS, Cucumber feature, Markdown checklist) and sync them to Azure DevOps Test Plans. Use when the user has a test case spreadsheet (xlsx) and wants to generate runnable tests, sync to ADO Test Plans, audit coverage gaps, or maintain xlsx as source of truth while auto-generating runnable artifacts. Supports custom column mappings per workbook.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /xlsx-testcases — bridge tester xlsx ↔ runnable tests

Solves the common pattern: testers write test cases in xlsx (familiar tool),
devs need runnable specs (Maestro/Detox/Cucumber). This skill keeps xlsx as
**source of truth** and generates runnable artifacts on demand.

Arguments: `$ARGUMENTS`. No service profile — test data lives in the workbook
itself; ADO sync uses the existing `azure-devops` skill profile.

## How it works

```
        +--------+              +-------------------+
xlsx →  | parse  | → testcases → | generate runners |
        +--------+              +-------------------+
                                     ↓
                            ┌────────┼────────┬─────────┐
                            ↓        ↓        ↓         ↓
                       Maestro  Detox   Cucumber  Markdown
                       YAML     spec.ts feature   checklist

                                     ↓
                              + sync to Azure DevOps Test Plans
```

## Dependencies

- **`anthropic-skills:xlsx`** — for xlsx parsing (already available in
  Anthropic's official skills, no need to reimplement). The skill **delegates**
  parsing to that.
- `jq` — for JSON manipulation.
- `python3` — for generating runners (cleaner than awk for this).
- For ADO sync: `/azure-devops` skill must be configured (uses `lib/credentials.sh`).

## Schema mapping

Each workbook may have different column names. Skill reads a per-workbook
schema from `<xlsx-folder>/.testcase-schema.yml`:

```yaml
# .testcase-schema.yml — committed alongside the xlsx
sheet: "Test Cases"             # sheet name; "*" = all sheets
header_row: 2                    # 1-indexed
columns:
  id:        "TC ID"             # required, must be unique
  module:    "Module"            # optional
  title:     "Title"             # required
  steps:     "Steps"             # required (multi-line cell)
  expected:  "Expected Result"
  priority:  "Priority"          # High/Medium/Low or P0/P1/P2/P3
  precondition: "Precondition"
  data:      "Test Data"
  category:  "Category"          # for tagging (smoke/regression/etc.)
  status:    "Status"            # New/Updated/Stable - to track changes

# Optional: parser hints
parsing:
  steps_separator: "newline"     # or "numbered" (1. ... 2. ...)
  priority_map:
    P0: high
    P1: high
    P2: medium
    P3: low
```

If no schema file exists, the skill prompts to **infer** from the first sheet's
header row and writes the inferred file for review.

## Dispatch

### `parse <xlsx-path>` — extract testcases as JSON

```bash
XLSX="$1"
SCHEMA="$(dirname "$XLSX")/.testcase-schema.yml"

# Use anthropic-skills:xlsx to read the workbook
# (delegate to the xlsx skill — Claude invokes it as a subtask)
```

The skill produces `/tmp/xlsx-testcases-<hash>.json`:

```json
[
  {
    "id": "TC001",
    "module": "Login",
    "title": "Valid credentials",
    "steps": ["Open app", "Enter username", "Enter password", "Tap login"],
    "expected": "Home screen loads",
    "priority": "high",
    "category": "smoke",
    "data": null,
    "precondition": "App installed, network OK"
  }
]
```

Cache key: SHA-256 of `(xlsx mtime + size + schema content)` → re-parse only
when input changes.

### `gen maestro <xlsx-path> [--out tests/maestro/]` — generate Maestro YAML

For each testcase, write `tests/maestro/<id>-<slug>.yaml`:

```yaml
# Generated from <source-xlsx-name>.xlsx :: TC001
# DO NOT EDIT — regenerate with: /xlsx-testcases gen maestro <xlsx>
appId: com.example.app
name: TC001 - Valid credentials
tags:
  - smoke
  - login
---
- launchApp
- assertVisible: "Welcome"
- tapOn: "Username"
- inputText: "${TEST_USER}"
- tapOn: "Password"
- inputText: "${TEST_PASS}"
- tapOn: "Login"
- assertVisible: "Home"
```

Step translation rules (heuristic — log unmapped):

| xlsx step pattern | Maestro action |
|---|---|
| "Open app" / "Launch" | `- launchApp` |
| "Tap [X]" / "Click [X]" | `- tapOn: "X"` |
| "Enter [X] in [field]" | `- tapOn: "field"` + `- inputText: "X"` |
| "Verify [X] visible" | `- assertVisible: "X"` |
| "Wait [Ns]" | `- runFlow:\n    when: ...\n    file: wait.yaml` |
| "Scroll to [X]" | `- scrollUntilVisible:\n    element: "X"` |

Steps that don't match a rule: emit as `# UNMAPPED: <original step>` comment
and surface in the run summary so tester can refine.

### `gen detox <xlsx-path> [--out e2e/]` — generate Detox

Same flow, output `.test.ts`:

```typescript
describe('TC001 - Valid credentials', () => {
  it('logs in successfully', async () => {
    await element(by.id('username')).typeText(process.env.TEST_USER);
    await element(by.id('password')).typeText(process.env.TEST_PASS);
    await element(by.id('login-btn')).tap();
    await expect(element(by.text('Home'))).toBeVisible();
  });
});
```

### `gen markdown <xlsx-path>` — manual QA checklist

```markdown
## TC001 — Valid credentials  [smoke, high]

**Precondition:** App installed, network OK

**Steps:**
1. Open app
2. Enter username
3. Enter password
4. Tap login

**Expected:** Home screen loads

[ ] Pass  [ ] Fail  [ ] Skip   Notes: ___________
```

### `sync ado <xlsx-path> [--plan <test-plan-id>] [--dry-run]`

Sync test cases into Azure DevOps Test Plans. Uses `azure-devops` skill for
auth. For each testcase:

1. Search by `TC ID` in test case work items
2. If found → update title/steps/expected (PATCH)
3. If not → create new test case work item
4. Track `last_synced` hash per TC in `<xlsx-folder>/.testcase-sync-state.json`
   (committed) — only sync TCs whose hash changed since last sync.

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds azure-devops "${AZDO_PROFILE:-default}"

# Per testcase:
WIQL="SELECT [System.Id] FROM workitems WHERE [System.WorkItemType]='Test Case' AND [Custom.TestCaseExternalId]='$TC_ID'"
# ... PATCH or POST
```

Required PAT scope: `Test Plans (Read & Write)` + `Work Items (Read & Write)`.

`--dry-run` shows what would change without writing.

### `coverage <xlsx-path> --against <test-folder>` — gap report

Cross-reference TC IDs in xlsx against generated test files. Report:

```
Total TCs in xlsx:       142
Generated as Maestro:    98 (69%)
Generated as Detox:      0  (0%)
Manual-only (markdown):  44 (31%)
SYNCED to ADO:           120 (85%)

Untested TCs (in xlsx, not generated anywhere):
  TC047  IAP   Restore purchase across devices    [HIGH]
  TC089  Push  Background notification handling   [HIGH]
  ...

Orphan tests (generated, not in xlsx):
  tests/maestro/legacy-flow.yaml        # consider removing
```

Critical gap: HIGH-priority TCs without runner generation.

### `diff <xlsx-path>` — what changed since last sync

Compare current xlsx against `.testcase-sync-state.json` snapshot:

```
Added:    3 TCs
Modified: 12 TCs (steps or expected changed)
Removed:  1 TC
```

Helpful before sync to ADO — tester sees what they're about to push.

## Implementation notes

- **Delegate parsing** to `anthropic-skills:xlsx` — don't reinvent. Pass file
  path, ask for sheet/range as JSON, parse the result.
- **Heuristic step translation** is imperfect by design — this is a skeleton
  generator, not a perfect compiler. Always emit `UNMAPPED` comments so
  testers see what didn't translate.
- **Cache**: hash inputs (xlsx + schema) → only regenerate when changed.
  Skill can be invoked many times in a session without re-parsing the same
  workbook.
- **Per-TC hash for ADO sync**: `sha256(title + steps + expected + priority)`
  → ADO upload only delta; saves API calls and noise.
- **Workbook layout**: support multi-sheet workbooks via `sheet: "*"` and
  per-sheet schemas if needed.
- **Encoding**: UTF-8 throughout. Vietnamese / Asian characters must round-trip
  correctly.

## Safety

- **xlsx may contain sensitive test data** (sample passwords, API keys, PII
  for testing). Treat parsed content as **confidential**:
  - Never write parsed JSON to a public location.
  - Default cache path is `/tmp/...` (cleaned on reboot).
  - Don't include test data verbatim in chat output beyond what's needed —
    summarize.
- **ADO sync is mutating** — always run `--dry-run` first; require `ctt_confirm`
  before actual sync. Audit log records TC IDs synced (not content).
- **Schema file** can be committed safely (no test data, only column mapping).
- **State file** (`.testcase-sync-state.json`) contains hashes only — safe to
  commit; helps team see sync history.
- **Generated runners** (Maestro YAML, Detox TS) are committed code and may
  reflect TCs verbatim — review before pushing to public repos.
- **Generated markdown checklists** also reflect TCs — keep in private repo,
  not public docs site.

## Token-saving tips

- Use `coverage` and `diff` before regenerating — only regenerate what
  changed.
- Cache parsed xlsx (`/tmp/xlsx-testcases-<hash>.json`) so repeated invocations
  in the same session reuse it.
- Keep the schema file lean — only map columns you actually use.
- Don't include test data in skill responses beyond what the user asked for.

## Workflow recommendation for QA team

1. **Tester** writes test cases in xlsx (current habit, no change).
2. **Lead/Dev** runs `/xlsx-testcases gen maestro <xlsx>` to scaffold runners.
3. **Dev** edits scaffolded YAML to add real selectors / data references.
4. **CI** runs Maestro on every PR.
5. **Weekly**: lead runs `/xlsx-testcases sync ado <xlsx>` to push to Test Plans
   and `coverage` to identify gaps.

This keeps xlsx as one source of truth, eliminates manual YAML drudgery, and
gives leads a coverage view they didn't have before.

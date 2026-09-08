# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.1] - 2026-09-08

Patch release. A post-release audit of the README turned up one functional bug
in the shared credential resolver plus some accumulated rot. No skill behaviour
changed beyond the profile-resolution fix.

### Fixed — `PG_PROFILE` was silently ignored

The postgres skill's own frontmatter and body document `PG_PROFILE`, and the
README tells users to put `PG_PROFILE=staging-readonly` in a project `.env`.
`_ctt_resolve_profile` only derived `POSTGRES_PROFILE` from the service name and
had no `postgres` alias, so `PG_PROFILE` did nothing and the load fell through to
`[default]` — on a database skill, quietly the wrong database, with no warning.

Added the alias, plus a regression test asserting that `PG_PROFILE` resolves,
that `POSTGRES_PROFILE` still resolves, and that another service's alias does not
leak in.

Test 11 was also made idempotent: it asserts the audit log holds exactly one
line but `ctt_audit_log` appends, so it passed only on a pristine runner and
failed on a second local run.

### Removed — dead `bundler-audit` profile alias

The `bundler-audit` skill was removed in v0.4.0 when redundant skills were
trimmed, but its `BA_PROFILE` alias stayed in `_ctt_resolve_profile` and its
documentation line stayed in `examples/.env.example` — dead for eight releases.
Both are gone.

A new lib test asserts that every short alias names a skill directory that still
exists, so this kind of rot fails CI instead of accumulating.

`examples/.env.example` also gained the profile variables added since it was
written (`LINEAR_PROFILE`, `SHOPIFY_PROFILE`, `MAESTRO_PROFILE`,
`FASTLANE_PROFILE`, `RSPEC_PROFILE`, `PG_PROFILE`), and now says plainly that
`RN_PROFILE` and `XTC_PROFILE` are accepted but change nothing, because
react-native and xlsx-testcases hold no credentials of their own.

### Fixed — README claims that no longer matched the repo

Found by an audit of every checkable claim in the file.

- `bash lib/install.sh` was described as doing three things; it has four steps,
  and the install-profile step was undocumented there.
- The multi-account table omitted `require_confirm` for firebase and fastlane,
  and `project_path` for fastlane.
- "Frontmatter `description` ≤ 40 words" is the policy, but CI fails at 70. Both
  numbers are now stated.
- "each skill folder you delete drops ~70 always-loaded tokens" measured at ~65.

Verified as still correct and left alone: every example, reference and script
path the README names exists; the skill counts (16 user-invocable plus one
shared reference); the `.gitignore` claims; the body-table average; every verb
in the quick-start block; and the Shopify API version.

## [0.12.0] - 2026-09-08

### Added

- **`linear` skill** (`/linear`) — Linear issue tracking over the GraphQL API,
  the 16th integration. `SKILL.md` + `recipes.md` (loaded on demand), matching
  the heroku/slack reference-file shape.
  - Read verbs: `me`, `teams`, `states`, `issues`, `issue`, `search`,
    `projects`, `cycles`.
  - Write verbs: `create`, `comment`, `update`, `archive`. There is no
    `delete` — `issueArchive` is reversible, `issueDelete` is not.
  - Multi-workspace via `~/.linear/credentials` (`api_key`, `default_team`,
    `require_confirm`) and `LINEAR_PROFILE`, same resolution order as every
    other skill.
  - Triggers on the word Linear, a `linear.app/*/issue/` URL, or a bare issue
    key such as `ENG-123`.
- `examples/linear-credentials.example` — multi-workspace template.

### Notes on the Linear API (verified 2026-09-08)

Three behaviours differ from the other REST-based skills and are documented in
the skill body because they cost time otherwise:

- Personal API keys use `Authorization: <key>` with **no `Bearer` prefix**.
  `Bearer` is OAuth-only and a personal key sent that way is rejected.
- Linear maps errors to real HTTP statuses — **401** for `AUTHENTICATION_ERROR`,
  **400** for `GRAPHQL_VALIDATION_FAILED`, `INPUT_ERROR` and `RATELIMITED` — and
  puts the diagnosis in the body of those non-2xx responses. HTTP 200 with an
  `errors` array also occurs, for partial field-level failures. Either way the
  status settles nothing, so every recipe reads `.errors` before `.data`
  regardless of status.
- Rate limiting returns **HTTP 400** with error code `RATELIMITED`, not 429.
  Limits with an API key: 2,500 requests/hour and 3,000,000 complexity
  points/hour per user, 10,000 points maximum for a single query.

All 17 GraphQL documents in `recipes.md` were validated against the live schema
on 2026-09-08. Linear runs document validation **before** authentication, so an
unauthenticated request returns `AUTHENTICATION_ERROR` for a valid document and
`GRAPHQL_VALIDATION_FAILED` for a broken one — no key needed. That check caught
one mistake before release: `ProjectFilter` has no `team` input field, so
projects scope to a team through `accessibleTeams`. Introspection is likewise
open, so `recipes.md` documents how to check a doubtful field name — including
reading `isDeprecated`, since validation accepts deprecated fields. `Project.state`
is one: still valid, but superseded by `status { name }` and typed `String`, so
the recipes select `status { name }`.

Personal API keys are **scoped**, contrary to what a first reading of the
developer docs suggests. A key is created with explicit permissions (Read,
Write, Admin, Create issues, Create comments) and can be restricted to specific
teams. It is displayed once and never expires, so revocation is the only way one
stops working. The skill documents least privilege per verb, in the same shape
as the sentry and shopify skills, and the credentials file stays mode 600 with
the key masked as `****<last4>`.

### Fixed — recipe abort paths did not abort

Every verb body in `skills/linear/recipes.md` was a bare top-level shell block
whose failure paths used `return`. Outside a function `return` is a bash error:
it prints ``can only `return' from a function or sourced script`` and execution
**continues to the next line**. Confirmed by running it — a declined
`ctt_confirm` fell straight through to the mutation.

Consequences before the fix: `archive` ran after the user said no; `create` sent
`teamId: ""` after the team lookup failed and still wrote an audit line; and
`configure` printed "Key rejected — nothing saved", then printed
`Authenticated as null <null>` and persisted the rejected key to
`~/.linear/credentials`.

Every verb is now a named shell function that the recipe invokes, so `return` is
legal whether the snippet is pasted at top level or sourced. Audit calls moved
inside the function and after the response check, so a failed write cannot leave
a false audit record.

### Fixed — `linear_check` passed non-JSON responses as success

The guard tested `jq -e '.errors' … 2>/dev/null`, which cannot tell "no errors
key" from "jq could not parse this". `linear_gql` uses `curl -s` without `-f`,
so a proxy or CDN HTML error page, a truncated read, or an empty body all
arrived with curl exit 0 and were waved through; the next `jq -r '.data…'` then
died with a raw parse error instead of the intended message. It now rejects
non-JSON bodies and the non-GraphQL `{"error":…,"code":…}` envelope as well.
Verified against seven response shapes.

### Fixed — comment read-back could read the wrong comment

The mandatory verification step fetched `comments(last:1)`. The sort direction
of Linear's connections is not documented, so "last" is not reliably the comment
just written. It now reads back by the comment id the mutation returned,
captured before the response file is reused.

### Fixed — README stated token figures it could not reproduce

The 0.12.0 draft hand-bumped the v0.11.1 measurement (1,005 tokens / 15 skills)
to "~1,070 for 16" in two places while a third said "~1,170 for 17", and added a
char-scaled `~1,430` row for `linear` into a table of tiktoken output — which
also made the printed average unreproducible. `benchmark_tokens.py` needs
network access to fetch the tiktoken BPE file and could not run here, so rather
than publish numbers that cannot be checked, the section now states the single
v0.11.1 measurement, says plainly that nothing has been re-measured since
`linear` was added, and omits `linear` from the per-skill table instead of
estimating it.

Also corrected: "All skills support multiple accounts" (13 of the 16 do), the
xlsx-testcases body figure quoted in prose (1,372) contradicting the table
(1,172), and the architecture tree, which listed 15 of 17 skill directories and
omitted `marketplace.json`, `install-profiles.json`, `hooks/hooks.json`,
`session-start.sh`, and the per-skill reference files.

`benchmark_tokens.py` and `benchmark_cross_validate.py` hardcoded "15 skills" in
their labels while iterating every directory, so the tools the README points at
for verification contradicted it. Both now derive the count. `linear` was also
missing from `WITHOUT_SKILL_BASELINE`, silently falling back to the generic
default; it now has an entry.

### Fixed — CI credential scan skipped the credential templates

The leak scan's `--include` list covered `*.md`, `*.json`, `*.sh` and `*.yml`
but not `*.example` — the files a contributor is most likely to paste a real key
into while copying their working config. Added `*.example`, which also brings
the trello, azure-devops and shopify templates into scope.

### Fixed — cross-profile credential leak in the shared lib (affects every skill)

`ctt_load_creds` populated `CTT_<FIELD>` for each field in the new profile but
never cleared the previous load, so any field present in profile A and absent
from profile B kept A's value. Found while testing the new `read_only` flag:
loading `[default]` (with `default_team = ENG`) then `[work]` (without one) left
`CTT_DEFAULT_TEAM=ENG`, so `/linear --profile work create` would have created the
issue in the wrong team.

This is not linear-specific. The same silent carry-over applied to sentry's
`org`/`project`, heroku's `default_app`, postgres's `host`/`database`/`password`,
shopify's `api_version`, and the `read_only` / `require_confirm` flags — in a
toolkit whose whole premise is keeping accounts isolated. It also leaked across
services, since `CTT_API_KEY` from one service survived into the next.

`ctt_load_creds` now tracks what it set in `_CTT_LOADED_VARS` and unsets exactly
those before loading. Control variables the user or CI sets, such as
`CTT_NONINTERACTIVE`, are deliberately untouched. Two regression tests added to
CI (7 total for the lib): one asserting no field leaks across a profile switch,
one asserting `CTT_NONINTERACTIVE` survives.

Skill authors: read fields as `${CTT_FIELD:-}` and treat unset as "not set on
this profile". Documented in the profiles-and-credentials reference skill.

### Fixed — the documented placeholder was a validly-shaped Linear key

`lin_api_` followed by 40 `x` characters matches Linear's real key pattern,
because `x` is in the key charset. GitHub push protection rejected the push and
named four occurrences across `skills/linear/SKILL.md` and the design spec.

The repository's own leak scan could never have caught it: that scan drops any
line containing `xxx`, which is exactly what the placeholder contained.
Placeholders are now `lin_api_YOUR-KEY-HERE`, broken by a character outside the
charset, and a new CI step checks vendor token *shapes* with no `xxx`
exclusion, so a key-shaped placeholder fails locally instead of at the remote.

The five unpushed commits were rewritten so no blob in the pushed history
carries the key-shaped string.

### Fixed — inline comments silently disabled every gate flag (all skills)

The INI parser kept a trailing `# comment` as part of the value, so the
documented line

    read_only = true            # refuse every write verb on this profile

loaded as `true            # refuse every write verb...`, the
`[ "$CTT_READ_ONLY" = "true" ]` test failed, and the gate was a no-op. The same
applied to `require_confirm` in the documented blocks of heroku, shopify, slack,
fastlane and k6, and to postgres's `read_only`: nine shipped examples, all
failing open. Reproduced with the exact block from the linear skill.

`_ctt_section` now splits at the first `=` (so a value may contain `=`) and
strips a trailing whitespace-delimited `#`/`;` comment, while a value that
*starts* with `#` stays intact — slack's `default_channel = #general`. An
unrecognised gate value now fails **closed** with a warning instead of being
treated as off.

### Security — findings from an adversarial review of these commits

An adversarial pass (six attack surfaces, each finding re-run by two
independent refuters) produced these changes. Nineteen other candidate findings
were refuted and are not listed.

- **API key no longer passed in argv.** `linear_gql` sent
  `-H "Authorization: $CTT_API_KEY"`, and argv is readable by other local users
  (`/proc/<pid>/cmdline`, the Windows process list). The key now goes to curl on
  stdin via `-K -`.
- **Scratch files moved out of shared `/tmp`.** Fixed names such as `p.json` and
  `r.json` under `$TMPDIR` let another local account pre-create or read them.
  They now live in `~/.claude-team-toolkit/tmp/linear/`, mode 700, umask 077.
- **Text no longer travels through bash.** The comment recipe spliced the body
  into a `<<'BODY'` heredoc, so a line equal to `BODY` in text that often came
  *back from the API* would end the heredoc and execute the rest as shell. The
  title, description, comment body and search term are now written to files with
  the Write tool before the verb runs.
- **Listings are `@tsv`-escaped.** `jq -r '"\(.identifier)	..."'` emitted raw
  API strings, so a newline in a title forged a row indistinguishable from a real
  one — enough to steer a later `update`/`archive` onto the wrong issue id.
- **`lin_id` fails closed.** It passed through anything that did not match, so a
  crafted argument could pad the confirmation prompt and the audit line. It now
  requires `KEY-123` and refuses otherwise.
- **Credentials files cannot set control variables.** A field named
  `noninteractive` or `profile` overwrote `CTT_NONINTERACTIVE` / `CTT_PROFILE`;
  those names are now reserved and ignored with a warning.
- **The cross-profile clearing no longer trusts a tracking variable.** A
  pre-set `_CTT_LOADED_VARS=CTT_NONINTERACTIVE` made the next load unset the CI
  auto-deny gate. The list now comes from the shell (`compgen -v CTT_`), with
  `CTT_NONINTERACTIVE` and `CTT_HOME` excluded.
- **Profile names and field values are validated.** A name containing `]` and a
  newline could write a second `[default]` INI section that wins on the next
  load; the resolved name also reached a grep pattern. Both are now restricted
  to `[A-Za-z0-9_-]`, and newlines in values are refused.
- **Audit records cannot be forged.** `ctt_audit_log` wrote the action verbatim,
  so a newline in an id or team key appended a second, fake record. Newlines and
  tabs are now stripped.
- **CI leak scan covers `*.example`** and no longer whitelists lines containing
  `your-`, which could have hidden a real key on the same line.

Six lib regression tests added (13 total): env-poisoned clearing, gate-flag
spellings, inline comments, reserved field names, INI-section injection, and
audit forgery.

### Changed — skill trimmed for token cost

`SKILL.md` body and `recipes.md` were 33,021 characters together, roughly three
times the heroku or slack skill. Rationale moved to this changelog, verbs share
a `lin_run` helper, and the prose was cut to what the model needs at runtime:
22,634 characters, about 31% smaller, with every safety control kept. All 17
GraphQL documents re-validated against the live schema and all bash blocks
syntax-checked after the rewrite.

### Security

- Profiles accept **`read_only = true`**, which refuses every write verb locally
  even when the API key itself carries Write. Same defense-in-depth shape as the
  postgres skill's flag.
- All four write verbs now go through a single `lin_guard_write` helper:
  `read_only` refuses, `require_confirm` prompts, then the write proceeds.
  `archive` checks `read_only` first and always confirms.
- The helper is written as `if`/`fi` rather than `[ cond ] && { ...; }`. As the
  last line of a function the latter returns the failed test's exit status, so a
  correctly skipped gate reads as a failed command to the caller.
- `configure` asks whether the key is Read-only and records it. The API exposes
  no way to read a key's own permissions back — there is no `apiKeys` field on
  the query root — so a successful `viewer` validation proves the key is live,
  not that it can write.
- `examples/linear-credentials.example` now shows the recommended two-profile
  split: a Read-only key for queries, a separate narrower key with
  `require_confirm = true` for the rare mutation.

### Changed

- Every write carries its text as a **GraphQL variable** built with
  `jq -a --rawfile` and sent via `--data-binary @file`, never through argv.
  Same defence as trello v0.11.1 against the Windows Git Bash ANSI-codepage
  conversion that corrupts non-ASCII text before curl sees it. Verified: a
  title with Vietnamese diacritics and an em dash produces a payload with zero
  non-ASCII bytes and round-trips byte-identical.
- `pm` install profile now includes `linear` alongside trello, slack and
  azure-devops.
- SessionStart hook probes `~/.linear/credentials` and reports its profiles.
- CI credential-leak scan covers the `lin_api_` key pattern.
- README: skills badge 15 → 16, service table, multi-account table,
  `LINEAR_PROFILE` env var, auto-routing table, credential-revocation list,
  architecture tree. Linear removed from the roadmap.

### Token cost

Always-loaded frontmatter goes from ~1,005 to **~1,070 tokens** for 16 skills.
The `linear` line is scaled by character count at 3.66 chars/token, not
measured — `scripts/benchmark_tokens.py` needs network access to fetch the
tiktoken BPE file and could not run in this environment. The `linear` body
(~1,430 tokens, same method) loads only when the skill is invoked; `recipes.md`
loads only when a specific verb is used.

## [0.11.1] - 2026-08-18

### Fixed

- **`trello` — comments and card titles silently corrupted when the text contained
  any non-ASCII character.** A comment posted with an em dash came back as
  `Root cause identified%3A ... %2A%2Afirst%2A%2A ... %0A` — every punctuation mark
  and newline stored as its percent-escape, with a `200 OK` and a valid action id.

  Chain: on Windows Git Bash, non-ASCII argv is converted through the ANSI codepage
  before reaching the native `curl.exe`, so U+2014 arrives as the single byte `0x97`.
  `--data-urlencode` puts `%97` on the wire; that is not valid UTF-8, so Trello's
  form parser gives up and stores the still-escaped string verbatim. Pure-ASCII text
  is unaffected, which is why this went unnoticed.

  All write recipes now build a JSON body with `jq -a` (ASCII output, so every
  non-ASCII char becomes `\uXXXX`) and send it with `--data-binary @file`, which
  never touches argv. Covers `comment`, `create`, `move`, `archive`.

  Verified end to end on a throwaway private board: `--data-urlencode` + em dash
  reproduces the corruption; the JSON path round-trips em dash, curly apostrophe and
  Vietnamese diacritics intact.

### Added

- `trello` — new **Writing text (JSON body only)** section explaining the trap, and
  the in-place comment edit recipe
  (`PUT /1/cards/<idCard>/actions/<idAction>/comments`) so a bad comment is repaired
  rather than deleted and reposted.
- `trello` — mandatory read-back step after posting a comment: a mangled body still
  returns `200`, so the stored value must be fetched and inspected before reporting
  success.

### Changed

- `trello` — dependency note now states **jq 1.6+** (the write recipes need
  `--rawfile` and `-a`).
- `trello` — Implementation notes and Common Mistakes inverted: the old advice was
  "**Always** `--data-urlencode` for user-supplied strings", which is exactly what
  produced the bug. Reads still use the query string with `jq -sRr @uri`; only
  writes changed.

## [0.11.0] - 2026-05-09

### Added — Token efficiency & UX (informed by an audit against everything-claude-code patterns)

- **Install profiles** (`.claude-plugin/install-profiles.json`) — opt into a
  curated subset of skills (`mobile-team`, `backend-ops`, `qa-team`, `pm`,
  `ruby-dev`, `devops`, `ecommerce`, or `full`). A team that only needs
  three skills cuts always-loaded frontmatter cost by ~80%.
  - `bash lib/install.sh --list-profiles` — print the catalog
  - `bash lib/install.sh --profile <name>` — disable skills not in the profile
    (renames `SKILL.md` → `SKILL.md.disabled` so the loader skips them)
  - `bash lib/install.sh --reset-profile` — re-enable everything
- **SessionStart hook** (`.claude-plugin/hooks/hooks.json` +
  `lib/session-start.sh`) — pre-warms credential discovery on every session.
  Lists which services have a credentials file, which profiles are defined,
  and which is currently active. Advisory only (never blocks). Saves the
  model from probing per-skill.
- **Reference-file pattern (`recipes.md`) for the 5 heaviest skills**:
  heroku, slack, k6, azure-devops, firebase. SKILL.md keeps Overview /
  When-to-Use / Common-Mistakes / verb catalog only; full curl + jq
  implementations move to `recipes.md` and load only when the user invokes
  a specific dispatch verb.
- **README "Why curl + jq, not MCP?" section** — explicit positioning that
  this toolkit ships zero MCP servers, so it adds zero per-tool schema cost
  to your context window.

### Changed — Skill description URL hints (improved auto-routing accuracy)

Six descriptions now include explicit URL / host patterns so Claude routes
correctly when users paste links:

- `heroku`: + `*.herokuapp.com`, `dashboard.heroku.com`
- `sentry`: + `sentry.io`, `*.sentry.io/issues/`, "pastes a stack trace"
- `shopify`: + `*.myshopify.com`, `admin.shopify.com`
- `slack`: + `*.slack.com/archives/`, `#channel` mentions
- `firebase`: + `console.firebase.google.com`, `*.firebaseapp.com`, `*.web.app`
- `postgres`: + `postgres://` and `postgresql://` connection strings

trello and azure-devops already had URL hints from v0.10.0.

### Token cost (measured)

- Always-loaded base (16 frontmatters) is unchanged at ~1,102 tokens — the
  description rewrite kept length similar, just shifted content from
  features to triggers.
- 5 heaviest skills' SKILL.md bodies dropped 40–55%:
  - `heroku`: 937 → 487 words (-48%)
  - `slack`: 942 → 558 words (-41%)
  - `k6`: 962 → 565 words (-41%)
  - `azure-devops`: 873 → 510 words (-42%)
  - `firebase`: 791 → 620 words (-22%)
- Total bodies across 16 skills: 12,944 → ~10,500 words (~-19%) before
  loading any `recipes.md`. Recipes load on-demand only.

### Fixed (during pre-release testing of this version)

- `lib/install.sh --profile <name>` filtering broke on Windows (Git-Bash):
  jq emits CRLF line endings, and `tr '\n' ' '` left embedded `\r`
  characters that prevented the grep match for all but the last skill in a
  profile. Fix: pipe through `tr -d '\r'` before `tr '\n' ' '`. Verified
  with all 8 profiles end-to-end on Windows + macOS-style line endings.
- `lib/install.sh --profile=` (empty value) and `--profile` (no value at
  end of args) now error explicitly with exit code 2 instead of silently
  falling through to a full install. Helpful message points to
  `--list-profiles`.

### Notes

- 100% backward compatible: bash code in `lib/credentials.sh`,
  `lib/confirm.sh`, dispatch commands, INI format, and audit log format are
  unchanged. Existing profiles work without migration.
- Install profile is opt-in. `bash lib/install.sh` (no flag) keeps all 16
  skills active, exactly like v0.10.0.
- The `recipes.md` files use plain markdown link syntax that Claude follows
  when it needs the implementation — no special loader integration needed.
- SessionStart hook adds ~700–850ms of one-time bash exec on Git-Bash for
  Windows (faster on macOS / Linux with native bash). It is async and
  non-blocking; output goes to additionalContext, never to the user's
  terminal directly.

## [0.10.0] - 2026-05-09

### Changed (BREAKING for skill discovery — all descriptions reworked)
- **All 15 skill `description` fields rewritten** to start with "Use when..."
  per superpowers:writing-skills standard. Descriptions now focus on
  triggering conditions (symptoms, contexts) instead of feature lists.
  This significantly improves auto-invocation accuracy when users mention
  related topics (e.g., "Trello card abc" now reliably triggers /trello).
- **All 15 skills now have standardized sections**: `## Overview`,
  `## When to Use`, `## When NOT to Use`, `## Common Mistakes` — added
  for discoverability and to match writing-skills structural requirements.

### Added
- **New shared skill `profiles-and-credentials`** — reference for the
  INI/profile/`ctt_*` pattern used by all credential-bearing skills.
  Single source of truth; the 12 credential skills now link to it from
  their Helpers section instead of repeating the pattern inline.
- **Test scenarios for TDD workflow**:
  `skills/postgres/test-scenarios.md` (4 pressure scenarios for the
  discipline aspects: read-only enforcement, sslmode, kill confirmation,
  EXPLAIN ANALYZE) and `skills/shopify/test-scenarios.md` (5 application
  scenarios for the reference aspects: multi-store, mutations, bulk read,
  API version policy, token security).
- **`skills/shopify/commands.md`** — heavy GraphQL query reference
  extracted from SKILL.md (which was 1032 words, now 655 words after
  split per writing-skills "Skill with Heavy Reference" pattern).

### Improved
- Search keywords (error messages, symptoms like 401/403, "connection
  refused") added to Common Mistakes sections of azure-devops, firebase,
  heroku, postgres, sentry, slack, etc.
- `react-native` and `fastlane` "Common pitfalls" sections renamed to
  `Common Mistakes` for consistency across the suite.

### Notes
- This is a documentation/structure-only release. No behavior changes
  in skill bash code. Existing profiles, credentials, and dispatch
  commands work identically.
- Skill word counts increased (added sections) but skills are
  user-invocable (loaded on demand), not auto-loaded — size is fine.

## [0.9.3] - 2026-05-05

### Fixed (CRITICAL)
- **Missing `.claude-plugin/marketplace.json`** — without this file,
  `claude plugin marketplace add tuannv14/claude-team-toolkit` failed
  with "Marketplace file not found". This means **the documented install
  command in README never worked** for any version before 0.9.3.
- Discovered during local install verification immediately after
  fixing v0.9.2 schema bugs.

### Added
- `.claude-plugin/marketplace.json` — single-plugin marketplace manifest
  pointing to this repo as both the marketplace and the plugin source.
  Schema follows Anthropic's official marketplace.schema.json.
- Full keyword/tag/category metadata so the plugin is discoverable in
  marketplace UI.

### Verified
```bash
claude plugin validate .  # ✔ Validation passed
claude plugin marketplace add tuannv14/claude-team-toolkit  # works
claude plugin install claude-team-toolkit  # works
```

### How CI missed this
CI's lint.yml validates `plugin.json` schema and SKILL.md frontmatter,
but did not require a `marketplace.json`. Adding a CI step now to require
its presence so this can never happen again.

## [0.9.2] - 2026-05-05

### Fixed (CRITICAL)
- `plugin.json` schema: `author` field changed from string to object
  (`{name, email, url}`) — required by Claude's official `plugin validate`.
  String form was silently accepted by older Claude Code versions but
  newer versions reject the install.
- `plugin.json` schema: `repository` field changed from object
  (`{type, url}`) to plain URL string — same reason.
- `skills/fastlane/SKILL.md` frontmatter: description field had unquoted
  colon-space (`Fastlane lanes for iOS/Android release: TestFlight...`)
  which YAML parsers interpret as a key-value separator. Wrapped in
  double quotes. Without this fix, fastlane skill loaded with empty
  metadata and Claude couldn't route to it.
- `skills/react-native/SKILL.md` frontmatter: same issue. Wrapped in
  double quotes.

### Why this matters
Discovered during local install verification with `claude plugin validate`.
CI's lint.yml only ran a coarse frontmatter check (presence of `name:`
and `description:` lines), missing the structural YAML errors. This
release passes the official validator without errors or warnings.

### Verification
```bash
claude plugin validate /path/to/cloned/repo
# → ✔ Validation passed
```

Users who installed v0.8.x or v0.9.x where these bugs were latent should
update to v0.9.2 — fastlane and react-native skills will now route
correctly.

## [0.9.1] - 2026-05-05

### Changed
- **Radical honesty pass on token economics**: previous v0.9.0 numbers
  were measured correctly with tiktoken but the "without toolkit" baseline
  was a heuristic (`body × 1.5 + retry`). When measured against 18 actual
  sample responses Claude would generate ad-hoc, the realistic ad-hoc cost
  is ~163 tokens per task (median 167, range 104-232) — much lower than
  the heuristic predicted. This means **the toolkit costs MORE tokens than
  ad-hoc Claude for common APIs**, not less.
- **Reframed value proposition** from "~50% token savings" to honest
  positioning: the toolkit's value is multi-account profiles + audit
  logging + safety gates + standardization + xlsx-testcases unique
  workflow. Token cost is the price for these benefits, paid back only on
  specific workloads (multi-account, uncommon APIs, retry-heavy tasks).
- **README Token Economics section rewritten** with:
  - Measured baseline from 18 sample tasks (not heuristic)
  - Honest table showing toolkit costs 3-16× more on pure token comparison
  - Three real-world cost categories the comparison ignores (auth context
    repetition, retry overhead on uncommon APIs, impossible workflows)
  - When-to-use vs when-NOT-to-use checklist
  - Real value table (multi-account, audit, safety, etc.)

### Added
- `scripts/benchmark_realistic_baseline.py` — measures 18 sample ad-hoc
  Claude responses across 7 skills. Shows ~163 token mean per task.
- `scripts/benchmark_cross_validate.py` — cross-validates token counts
  across 3 methods (cl100k_base, o200k_base, char-based). Confirms ±3-7%
  spread, validating numbers within stated uncertainty.

### Notes
This release is functionally equivalent to v0.9.0 — same skills, same
APIs, same security model. Documentation only. The point is that being
**honest about when the toolkit pays off** is a competitive advantage:
users can verify our claims with `python3 scripts/benchmark_*.py` and
trust the rest of the README.

If you adopted v0.8.x or v0.9.0 expecting "74% token savings", read the
new Token Economics section. The toolkit's real value is workflow
consistency, not token reduction. Decide based on whether you actually
need multi-account / audit / safety / xlsx-testcases.

## [0.9.0] - 2026-05-05

### Changed
- **Honest token economics**: previous claims of ~74% token savings were
  based on a `words × 1.33` estimate that significantly underestimated
  real tokenization (markdown code blocks, special chars, URLs tokenize
  much denser than prose). Measured with tiktoken cl100k_base, real
  numbers are:
  - Always-loaded: 1,005 tokens (was claimed ~779, actual was 1,266)
  - Multi-step session (3 × 4): **48% savings** (was claimed 72%)
  - Heavy reuse (5 × 5): **57% savings** (was claimed 74%)
  - Break-even: ~3 invocations per skill (was claimed 2)
- **Token optimization pass**: trimmed 9 skills aggressively to compensate
  - shopify: 3,719 → 2,233 (-40%)
  - fastlane: 1,790 → 1,123 (-38%)
  - firebase: 2,027 → 1,314 (-36%)
  - postgres: 2,139 → 1,529 (-29%)
  - rails-security: 2,095 → 1,562 (-26%)
  - maestro: 1,714 → 1,290 (-25%)
  - rspec: 1,680 → 1,296 (-23%)
  - heroku: 2,258 → 1,864 (-18%)
  - All 15 frontmatter descriptions ultra-trimmed
- **Total reduction**: -21% always-loaded, -20% all-bodies sum
- **README Token economics section** rewritten with honest tiktoken numbers,
  exact methodology, when-it-doesn't-save disclosure

### Added
- `scripts/benchmark_tokens.py` — reproducible token benchmark using
  tiktoken. Run anytime with `python3 scripts/benchmark_tokens.py` to
  validate token claims for your stack.

### Notes
This release is functionally equivalent to v0.8.1 — same skills, same
APIs, same security model. Only documentation accuracy and token
efficiency changed. No breaking changes.

## [0.8.1] - 2026-05-05

### Documentation
- `shopify` skill: clarified multi-app support. The `(shop_domain,
  access_token)` profile pair naturally supports multi-app — multiple
  Custom Apps per store, each with least-privilege scopes, separate audit
  trail, and independent revocation.
- `examples/shopify-credentials.example`: rewrote with three patterns
  (multi-STORE, multi-APP on same store, MATRIX of stores × apps) and
  recommended naming convention `<store>-<app-purpose>`.
- `README.md`: noted multi-app support in shopify profile fields row.
- `skills/shopify/SKILL.md`: added "Why multi-app on the same store"
  rationale (least-privilege, audit separation, revocation granularity,
  team boundaries).

### Notes
No code changes. Pure documentation release.

## [0.8.0] - 2026-05-05

### Added
- New skill: **`shopify`** — Shopify Admin GraphQL API for products, orders,
  customers, inventory, draft orders. Multi-store profiles. Default API
  version 2026-04 (latest stable as of May 2026, supported until April 2027).
  GraphQL primary (Shopify's recommended API), REST fallback for legacy
  endpoints. Includes raw `gql` escape hatch and bulk operations support.
- `examples/shopify-credentials.example` — multi-store template with scope
  guidance per operation.

### Changed
- Skill count: 14 → **15**
- README: shopify added to all relevant sections (skill table, multi-account
  fields, env var list, auto-detect routing, install dependencies)

## [0.7.0] - 2026-05-05

### Added
- Community health files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `MAINTAINERS.md`, `SUPPORT.md`
- GitHub templates: `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md` + `config.yml`, `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/dependabot.yml` — weekly automated dependency checks for github-actions
- `.github/CODEOWNERS` — auto-assign reviews to project owner
- `.editorconfig` — consistent line endings and indentation across editors
- README: CI status badge

### Changed
- Bumped `plugin.json` version to 0.7.0

### Fixed
- Repository community profile completeness for ClaudePluginHub maintenance score (8 → 9 expected)

## [0.6.3] - 2026-05-04

### Fixed
- CI shellcheck SC2015 warning in `lib/confirm.sh` (replaced `A && B || C` with explicit `if/else`)
- Lowered shellcheck severity threshold from default to `warning` so style notes are advisory only

## [0.6.2] - 2026-05-04

### Added
- Comprehensive Multi-account workflow section in README so Claude auto-routes to skills correctly without users needing to memorize syntax
- "How Claude auto-detects which skill to use" routing table with 14 common user phrases
- "Adapting to your project" 5-step guide for new users
- Sanitized credential templates in `examples/` for trello and azure-devops

## [0.6.1] - 2026-05-04

### Added
- Token Economics section in README with concrete savings numbers (~74% on typical multi-step sessions)
- Methodology disclosure for the cost estimates

## [0.6.0] - 2026-05-04

### Added
- `CONTRIBUTING.md` with skill design rules and security checklist
- README badges (license, version, skills count, Claude Code)
- `.github/workflows/lint.yml` CI: validate plugin.json + SKILL.md frontmatter, shellcheck, lib tests, credential leak scan
- `examples/` folder with sanitized templates

### Security
- Final audit pass: zero internal info leaks, zero real credentials
- All commits authored by Nick Nguyen `<96.tuan.nv@gmail.com>` with consistent name across history

## [0.5.0] - 2026-05-04

### Changed
- Aggressive token optimization: -22% body, -39% always-loaded
- Trimmed top 4 token-heavy skills (azure-devops, xlsx-testcases, trello, react-native) by 50-64% each

## [0.4.0] - 2026-05-04

### Removed
- `aws-s3` skill (CLI passthrough; AWS CLI native multi-profile is sufficient)

### Changed
- Merged `brakeman` + `bundler-audit` into `rails-security` (combined Ruby security skill)
- Reduced from 16 to 14 skills

## [0.3.0] - 2026-05-04

### Fixed
- BLOCKER: `.gitignore` pattern `**/credentials.*` was excluding `lib/credentials.sh` — every install was effectively broken
- JSON injection in azure-devops wi-create (now uses `jq -n --arg`)
- SQL injection in postgres schema/tables/indexes/kill (added identifier validation + parameterized queries)
- aws-s3 sync unquoted variable expansion (replaced with bash array)
- slack history URL injection (URL-encode channel ID, validate shape)
- brakeman/rspec unquoted command expansion (replaced with arrays)
- brakeman/bundler-audit diff used destructive `git stash` (replaced with non-destructive `git worktree add`)
- Various: lib `eval` → `printf -v` + key shape validation, k6 import path, heroku LIMIT validation

### Added
- 9 new skills: heroku, sentry, slack, aws-s3, postgres, rspec, brakeman, bundler-audit, k6
- `lib/credentials.sh` shared helper with 16/16 unit tests passing
- `lib/confirm.sh`, `lib/install.sh`

## [0.2.0] - 2026-05-04

### Added
- Initial 9 skills batch
- Shared lib for token efficiency

## [0.1.0] - 2026-05-04

### Added
- Initial release with trello and azure-devops skills
- `plugin.json` manifest, README, `.gitignore`, MIT LICENSE

[Unreleased]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.11.1...HEAD
[0.11.1]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.10.0...v0.11.0
[0.9.3]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.8.1...v0.9.0
[0.8.1]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.6.3...v0.7.0
[0.6.3]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.1.0...v0.2.0

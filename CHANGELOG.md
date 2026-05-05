# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.9.3...HEAD
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

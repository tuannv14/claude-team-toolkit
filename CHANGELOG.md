# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/tuannv14/claude-team-toolkit/compare/v0.8.1...HEAD
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

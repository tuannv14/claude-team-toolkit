# Getting Support

Different channels exist for different kinds of questions.

## Bug reports
Open an issue using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include OS, shell version, plugin version, and redacted logs.

## Feature requests
Open an issue using the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md). Describe the workflow problem first, then your proposed solution.

## Questions and discussion
Use [GitHub Discussions](https://github.com/tuannv14/claude-team-toolkit/discussions) for:
- "How do I configure X for my team?"
- "Is there a skill for service Y?"
- "What's the right way to combine skills A and B?"

## Security vulnerabilities
**Do not open public issues.** See [SECURITY.md](SECURITY.md) for the private disclosure process.

## Documentation
- [README.md](README.md) — install, multi-account workflow, token economics, security model
- [CONTRIBUTING.md](CONTRIBUTING.md) — skill design rules, PR guidelines
- [examples/](examples/) — sanitized credential and config templates
- [CHANGELOG.md](CHANGELOG.md) — version history

## Response times

| Channel | Target response |
|---|---|
| Security email | 72 hours |
| Bug report | ~7 days |
| Feature request | ~14 days |
| Discussion | best-effort |

This is a single-maintainer project — response times depend on real-world bandwidth. Please be patient.

## Out of scope

We don't provide support for:
- Bugs in upstream tools we wrap (`curl`, `jq`, `psql`, `aws`, `firebase`, `gh`, `git`, `maestro`, `fastlane`, `bundle-audit`, `brakeman`, `k6`) — report those upstream
- Service-side issues with Trello, Azure DevOps, Heroku, Sentry, Slack, Firebase, Postgres servers, etc.
- General Claude Code questions unrelated to this plugin

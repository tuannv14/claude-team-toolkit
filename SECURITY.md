# Security Policy

## Supported Versions

The latest minor version receives security updates. Older versions are
unmaintained.

| Version | Supported          |
| ------- | ------------------ |
| 0.7.x   | :white_check_mark: |
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **96.tuan.nv@gmail.com** with the subject line
`[SECURITY] claude-team-toolkit: <short-description>`.

Include:
- Affected skill or shared lib file
- Reproduction steps (or proof-of-concept)
- Impact assessment (e.g. credential leak, shell injection, prompt injection)
- Your name/handle for credit (optional)

You will receive an acknowledgement within **72 hours**. After triage, a fix
plan will be shared back. Embargo until a patched release is published.

## Scope

In scope:
- Credential handling in `lib/credentials.sh` (load, save, mask, perms)
- Shell injection in any `skills/*/SKILL.md` bash snippet
- JSON injection (jq misuse, unescaped user input in API bodies)
- TLS misconfiguration (e.g. `insecure = true` defaults)
- Prompt injection paths where untrusted API content could trigger
  destructive operations
- Audit log integrity (`~/.claude-team-toolkit/audit.log`)
- `.gitignore` gaps that could lead to credential commits

Out of scope:
- Vulnerabilities in upstream tools we wrap (`curl`, `jq`, `psql`, `aws` CLI,
  `firebase` CLI, `gh`, `git`, `maestro`, `fastlane`, `bundle-audit`,
  `brakeman`, `k6`) — report to those projects.
- Network-level attacks against the services the skills call (Trello, ADO,
  Heroku, etc.) — those are the service operators' responsibility.
- Issues requiring physical access to the user's machine.

## Threat Model

This plugin assumes:
- The local user is trusted and has full filesystem access.
- `~/.<service>/credentials` files exist on the local machine with mode
  `0600`. They are NOT backed up to git — `.gitignore` blocks them.
- API content (cards, PR descriptions, work items, Slack messages, etc.)
  is **untrusted** and must not trigger automated actions.
- Claude Code itself is trusted to execute the dispatched bash snippets.

## Disclosure Timeline

Upon receiving a report:
1. **Day 0–3**: Acknowledge receipt + triage severity.
2. **Day 3–14**: Develop and test patch in private branch.
3. **Day 14**: Ship patched release + public CVE/advisory.
4. Embargo extension by mutual agreement if more time is needed.

## Hall of Fame

Reporters who responsibly disclose are credited in `CHANGELOG.md` and the
release notes (with permission).

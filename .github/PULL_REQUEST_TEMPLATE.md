# Pull Request

## Summary
<!-- One sentence on what this PR does and why. -->

## Type of change
<!-- Mark with x -->
- [ ] Bug fix (non-breaking)
- [ ] New skill
- [ ] Enhancement to existing skill
- [ ] Documentation
- [ ] CI / tooling
- [ ] Breaking change (describe migration in CHANGELOG)

## Affected
- Skill(s):
- Lib file(s):
- Other files:

## Checklist
- [ ] CI passes (`lint.yml` is green)
- [ ] No real credentials, internal hostnames, or project names in any committed file
- [ ] If adding a skill: sources `lib/credentials.sh` (no duplicated helpers)
- [ ] If adding a skill: frontmatter `description` is concise (≤ 60 words)
- [ ] If adding a skill: mutating operations use `ctt_confirm` + `ctt_audit_log`
- [ ] If adding a skill: documents required scopes/permissions
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] README.md updated if user-visible behavior changes
- [ ] Self-tested locally on at least one platform (note which: Windows / macOS / Linux)

## How to test
<!-- Steps for a reviewer to verify your change. -->

## Token cost
<!-- For new skills: paste output of `wc -w` on SKILL.md and brief justification of the size. -->

## Related issues
<!-- Closes #N, refs #M -->

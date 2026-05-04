# Contributing to claude-team-toolkit

Thanks for your interest. This toolkit is built for real teams — every PR
should make it safer, leaner, or more useful.

## Setup

```bash
git clone https://github.com/tuannv14/claude-team-toolkit.git
cd claude-team-toolkit
bash lib/install.sh         # one-time setup, copies lib/ to ~/.claude-team-toolkit/
```

## Adding a new skill

1. **Check if it's needed.** A skill should encode **non-obvious domain logic**:
   multi-account credential handling, custom safety gates, format conversion,
   etc. If it's just `cli --flag arg` that Claude already knows, skip the
   skill — Claude can run it via Bash directly.
2. **Reuse the shared lib.** Source `~/.claude-team-toolkit/lib/credentials.sh`
   and use `ctt_load_creds`, `ctt_mask`, `ctt_save_profile`, `ctt_audit_log`,
   `ctt_confirm`. Don't duplicate.
3. **Follow the structure** of an existing skill (see `skills/heroku/SKILL.md`
   as a reference):
   - Frontmatter: `name`, `description` (≤40 words, key terms only),
     `user-invocable`, `allowed-tools`.
   - Body: Profile config schema → Helpers → Dispatch → Safety.
4. **Document required scopes/permissions** for tokens at least-privilege.
5. **Run the security checklist** below before opening a PR.

## Security checklist (every PR)

- [ ] No real tokens / PATs / API keys in any file (use `xxx`/`yyy`
      placeholders).
- [ ] No internal hostnames, project names, or repo IDs from your employer.
- [ ] All user-supplied strings escaped (`jq -n --arg`, `--data-urlencode`,
      `psql -v` for identifiers, bash arrays for flags).
- [ ] Mutating operations gated by `ctt_confirm` (typed phrase) +
      `ctt_audit_log`.
- [ ] Tokens masked on display (`ctt_mask` → `****<last4>`).
- [ ] `chmod 600` enforced on credential files; refuse if world-readable.
- [ ] No new entries needed in `.gitignore` — but verify
      `git check-ignore <test-file>` blocks any common credential pattern.

## Trim policy (token efficiency)

- Frontmatter description: ≤40 words.
- SKILL.md body: aim for ≤200 lines. Move verbose API references to a
  per-skill `reference.md` if needed.
- No narrative ("Why X over Y") — that belongs in commit message or PR
  description. The skill body is for AI instructions, not human essays.

## Testing

- Lib tests: `bash` shell with `source lib/credentials.sh` + run synthetic
  test cases (see commit history for examples).
- Skill bash logic: hand-run with fake credentials in `/tmp/ctt-test/`
  before merging.

## Commit messages

```
<scope>: <imperative summary, ≤72 chars>

- bullet 1: what changed
- bullet 2: why (link to issue if applicable)
```

## Reporting security issues

Don't open a public issue. Email: 96.tuan.nv@gmail.com with subject
`[SECURITY] claude-team-toolkit`.

## License

By contributing you agree your code will be released under the [MIT License](LICENSE).

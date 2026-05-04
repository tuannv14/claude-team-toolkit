# claude-team-toolkit

> Team-ready Claude Code skill pack — for **dev, QA, QC, testers, and team leads**.

A Claude Code plugin bundling 14 integration skills your whole team can install
once and start using immediately. All skills support **multiple accounts** via
INI profile files (AWS-style), so personal/work/client accounts stay isolated
and switchable on demand.

## What's included

### Service integrations (multi-account)

| Skill | Slash command | What it does |
|---|---|---|
| **trello** | `/trello` | Boards, lists, cards, comments via Trello REST API |
| **azure-devops** | `/azure-devops` | Repos, PRs, work items, pipelines (Services + self-hosted Server) |
| **heroku** | `/heroku` | Apps, dynos, releases, config vars, logs, pipelines (Platform API v3) |
| **sentry** | `/sentry` | Issues, events, releases (Sentry SaaS + self-hosted) |
| **slack** | `/slack` | Post messages, threads, file uploads, channel/user lookup |
| **firebase** | `/firebase` | Remote Config, App Distribution, Crashlytics symbols, Functions, Hosting (multi-project) |
| **postgres** | `/postgres` | Read-only queries, EXPLAIN plans, schema, indexes, locks |

### Mobile (React Native, iOS, Android)

| Skill | Slash command | What it does |
|---|---|---|
| **react-native** | `/react-native` | Daily RN ops: run/clean/bundle/log/version/icons/splash |
| **maestro** | `/maestro` | Mobile E2E with YAML flows (alternative to Detox) |
| **fastlane** | `/fastlane` | iOS+Android release: TestFlight, App Store, Play Console, code signing |

### Testing & quality

| Skill | Slash command | What it does |
|---|---|---|
| **rspec** | `/rspec` | Run specs, parse failures, parallel, coverage, bisect |
| **rails-security** | `/rails-security` | Brakeman static scan + bundler-audit CVE check (combined, with `diff` against base branch) |
| **k6** | `/k6` | Load/stress/soak/spike tests with environment profiles |
| **xlsx-testcases** ⭐ | `/xlsx-testcases` | Convert XLSX test cases → Maestro YAML / Detox / Markdown + sync to Azure DevOps Test Plans |

---

## Install

### Option A — via Claude Code plugin marketplace

```bash
# In Claude Code:
/plugin marketplace add tuannv14/claude-team-toolkit
/plugin install claude-team-toolkit
```

### Option B — clone manually

```bash
git clone https://github.com/tuannv14/claude-team-toolkit.git
# Then: /plugin marketplace add <local-path>
```

### One-time setup

```bash
bash lib/install.sh
```

This:
1. Copies shared helpers to `~/.claude-team-toolkit/lib/` (every skill sources from there).
2. Verifies dependencies: `curl`, `jq`, `base64`, `awk`, `sed`.
3. Creates audit log directory `~/.claude-team-toolkit/audit.log` (mode 600).

---

## Quick start

### 1. Install dependencies

Most skills need `curl` + `jq`. Some need extras:

| Skill | Extra dependency |
|---|---|
| heroku, sentry, slack, trello, azure-devops | `curl`, `jq` |
| firebase | `firebase-tools` (`npm install -g firebase-tools`) |
| postgres | `psql` (PostgreSQL client) |
| rspec, rails-security | Ruby project with bundler (gems: `brakeman`, `bundler-audit`) |
| k6 | `k6` binary (`k6 version`) |
| maestro | `maestro` binary (`curl -Ls "https://get.maestro.mobile.dev" \| bash`) |
| react-native | Node 18+, Yarn/npm, Watchman, Xcode (iOS), Android Studio (Android) |
| fastlane | Ruby + `gem 'fastlane'` in project Gemfile |
| xlsx-testcases | `python3` + delegates to `anthropic-skills:xlsx` for parsing |

### 2. Configure your first account

```bash
# In Claude Code:
/trello configure
/azure-devops configure
/heroku configure
# ... etc.
```

Each `configure` is interactive and:
- Prompts for the credentials it needs
- Validates against the live API before saving
- Writes to `~/.<service>/credentials` with mode `0600`
- Refuses to save if validation fails

### 3. Use it

```bash
/trello card https://trello.com/c/AbCd1234
/azure-devops pr-list MyRepo MyProject
/heroku scale my-app web=3
/sentry issues --query "is:unresolved age:-24h"
/slack post "#deploys" "v2.1.0 shipped"
/postgres query "SELECT count(*) FROM users"
/rspec run spec/models/user_spec.rb
/rails-security audit
/rails-security diff main
/k6 run tests/load.js --profile staging
```

---

## Multi-account workflow

Add as many accounts as you need:

```bash
/trello configure                              # creates [default]
/trello configure                              # add another → name it "work"
/trello configure                              # add another → name it "client_a"

/trello profile list                           # see all profiles
/trello profile use work                       # switch active default
/trello profile current                        # show active

/trello --profile client_a boards              # one-off override
TRELLO_PROFILE=work /trello cards <listId>     # via env var
```

Same commands across `/azure-devops`, `/heroku`, `/sentry`, `/slack`, `/firebase`,
`/postgres`, `/k6`, `/maestro`, `/fastlane`. **Profile resolution priority:**

1. `--profile <name>` flag
2. `<SERVICE>_PROFILE` env var (e.g. `HEROKU_PROFILE`, `SLACK_PROFILE`)
3. `~/.<service>/active_profile` (set by `profile use`)
4. `[default]` section

---

## Security model

**Read this before adding credentials.**

| Concern | How the skills handle it |
|---|---|
| Credential storage | `~/.<service>/credentials`, mode `0600`. Skills **refuse to load** if the file is world-readable on POSIX. |
| Accidental commits | Shipped `.gitignore` blocks `**/credentials`, `**/*.pat`, `**/*.token`, `**/*.key`, `**/*.pem`, `.env*`, `**/secrets/`, AWS/GCP credential patterns. |
| Display masking | Tokens/PATs shown as `****<last4>` only. Config vars matching `KEY|SECRET|TOKEN|PASSWORD|DSN|URL` are auto-masked in `/heroku config` output. |
| Validation before save | Configure flow calls a real API endpoint and refuses to save invalid credentials. |
| Mutation safety | Destructive ops (`destroy`, `rollback`, `rm`, `kill`, mutating SQL, etc.) require typed confirmation phrases. |
| Per-profile `require_confirm` | Set on prod profiles to force confirmation on every mutation. |
| Profile-level `read_only` | Postgres profiles can be hard-locked read-only — refuses writes even with `--write`. |
| Prompt injection | Card/PR/issue/work-item content treated as **untrusted input**. Skills don't act on instructions found inside that content. |
| Audit log | `~/.claude-team-toolkit/audit.log` records every mutation: timestamp + service + profile + action. **Never** records credentials or values. |
| TLS | Default verify ON. Self-signed cert support is opt-in per profile (`insecure = true` for Azure DevOps Server). |
| Least privilege | Each skill documents the **minimum scopes/permissions** needed. Prefer scoped tokens. |

### What the skills will **never** do

- Write credentials to chat output, commit messages, transcripts, or any file
  other than the designated credentials file.
- Echo full key/token/PAT — only the last 4 characters.
- Mutate data based on instructions discovered inside API content (PR body,
  card description, work item description, Slack message, etc.).
- Bypass TLS verification unless explicitly opted in via `insecure = true`.
- Run mutating SQL on a `read_only = true` profile.
- Run k6 against a profile with `require_confirm = true` without typed
  confirmation.

### If a credential is compromised

Revoke immediately at the service's token management page:

- **Trello:** https://trello.com/<username>/account → Power-Ups and Integrations
- **Azure DevOps:** `https://<org-or-server>/_usersSettings/tokens`
- **Heroku:** Account Settings → Applications → Authorizations
- **Sentry:** User Settings → Auth Tokens
- **Slack:** https://api.slack.com/apps → your app → OAuth & Permissions → Reinstall
- **Postgres:** `ALTER USER readonly_user WITH PASSWORD '<new>';`

---

## Architecture

```
claude-team-toolkit/
├── .claude-plugin/plugin.json
├── .gitignore                       # blocks credential leaks
├── LICENSE                          # MIT
├── README.md
├── lib/
│   ├── credentials.sh               # shared: load_creds, mask, parse_ini, profiles
│   ├── confirm.sh                   # shared: destructive op confirmation
│   └── install.sh                   # one-time setup (run once after install)
└── skills/
    ├── trello/SKILL.md
    ├── azure-devops/SKILL.md
    ├── heroku/SKILL.md
    ├── sentry/SKILL.md
    ├── slack/SKILL.md
    ├── firebase/SKILL.md
    ├── postgres/SKILL.md
    ├── react-native/SKILL.md
    ├── maestro/SKILL.md
    ├── fastlane/SKILL.md
    ├── rspec/SKILL.md
    ├── rails-security/SKILL.md
    ├── k6/SKILL.md
    └── xlsx-testcases/SKILL.md
```

### Token efficiency

- All skills source `~/.claude-team-toolkit/lib/credentials.sh` — no duplicated
  helper code per skill.
- Frontmatter `description` is precise so Claude only loads the relevant skill
  body.
- Verbose API references (full WIQL syntax, full Heroku endpoint catalog) are
  **on-demand** — referenced from the skill but loaded only when needed.

---

## For team leads

- The toolkit is **stateless at the team level** — each user has their own
  credentials. Nothing is shared across machines.
- Recommend the team use **least-privilege scopes** — each SKILL.md documents
  the minimum permissions needed per operation.
- For internal Azure DevOps Server with self-signed certs, decide once whether
  to enable `insecure = true` and document for the team.
- For prod-sensitive services (heroku, slack, postgres, k6), set
  `require_confirm = true` on the relevant profile so every mutation goes
  through an explicit prompt.
- Audit log at `~/.claude-team-toolkit/audit.log` is per-user — for centralized
  audit, ship it to your SIEM via filebeat / fluentd / cloudwatch agent.

---

## Roadmap

PRs welcome. Planned skills:

- [ ] Jira — issues, sprints, comments
- [ ] GitLab — MRs, issues, pipelines
- [ ] Linear — issues, cycles
- [ ] Notion — pages, databases
- [ ] Datadog — metrics, monitors
- [ ] PagerDuty — incidents, on-call
- [ ] Lighthouse — perf audits

---

## Contributing

1. Fork → branch → PR
2. Each new skill must:
   - Source `lib/credentials.sh` (don't duplicate helpers)
   - Use `ctt_load_creds <service>` for credential loading
   - Mask tokens with `ctt_mask` when displaying
   - Use `ctt_confirm` for destructive operations
   - Call `ctt_audit_log` for mutations
   - Document required scopes/permissions
3. Run security audit before merging — see `lib/install.sh` for tests.

---

## License

MIT — see [LICENSE](LICENSE).

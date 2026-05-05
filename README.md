# claude-team-toolkit

[![CI](https://github.com/tuannv14/claude-team-toolkit/actions/workflows/lint.yml/badge.svg)](https://github.com/tuannv14/claude-team-toolkit/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.8.1-green.svg)](https://github.com/tuannv14/claude-team-toolkit/releases)
[![Skills](https://img.shields.io/badge/skills-15-orange.svg)](#whats-included)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-7a3aff.svg)](https://docs.claude.com/en/docs/claude-code/plugins)
[![ClaudePluginHub](https://img.shields.io/badge/ClaudePluginHub-listed-success.svg)](https://www.claudepluginhub.com/plugins/tuannv14-claude-team-toolkit)

> Team-ready Claude Code skill pack — for **dev, QA, QC, testers, and team leads**.

A Claude Code plugin bundling 15 integration skills your whole team can install
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
| **shopify** | `/shopify` | Shopify Admin GraphQL API — products/orders/customers/inventory/draft orders (multi-store, latest API 2026-04) |
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

All credential-based skills follow the same INI profile pattern (modeled
after AWS CLI). Add unlimited profiles per service: personal, work, multiple
clients, dev/staging/prod environments — each isolated.

### Which skills support multi-account

| Skill | Credentials file | Per-profile fields |
|---|---|---|
| **trello** | `~/.trello/credentials` | `key`, `token` |
| **azure-devops** | `~/.azure-devops/credentials` | `org_url`, `pat`, `api_version`, `project`, `insecure` |
| **heroku** | `~/.heroku/credentials` | `api_key`, `default_app`, `require_confirm` |
| **sentry** | `~/.sentry/credentials` | `api_url`, `auth_token`, `org`, `project` |
| **slack** | `~/.slack/credentials` | `bot_token`, `default_channel`, `require_confirm` |
| **firebase** | `~/.firebase/credentials` | `project_id`, `service_account`, `ios_app_id`, `android_app_id` |
| **shopify** | `~/.shopify/credentials` | `shop_domain`, `access_token`, `api_version`, `require_confirm` (supports multi-store **and** multi-app on the same store via separate profiles) |
| **postgres** | `~/.postgres/credentials` | `host`, `port`, `database`, `user`, `password`, `sslmode`, `read_only`, `require_confirm` |
| **maestro** | `~/.maestro/profiles.ini` | `platform`, `device`, `app_id`, `flows_dir`, `cloud_api_key` |
| **fastlane** | `~/.fastlane/credentials` | `appstore_api_*`, `google_play_json_key`, `match_*` |
| **k6** | `~/.k6/credentials` | `base_url`, `auth_header`, `vus`, `duration`, `require_confirm` |
| **rspec** | `~/.rspec/credentials` | `project_path`, `rails_env`, `workers`, `seed_strategy` |

**No multi-account** (purely local, no remote auth):
`react-native`, `rails-security`, `xlsx-testcases` (the latter reuses the
`/azure-devops` profile when syncing to Test Plans).

See [examples/](examples/) for sanitized credential templates.

### How to add and switch profiles

```bash
# 1) Add accounts interactively (skill validates against live API before saving)
/trello configure                              # creates [default]
/trello configure                              # add another → name it "work"
/trello configure                              # add another → name it "client_a"

# 2) Manage them
/trello profile list                           # show all profiles, * marks active
/trello profile current                        # show active + masked token
/trello profile use work                       # set "work" as active default
/trello profile remove client_a                # delete a profile

# 3) Use them
/trello --profile client_a boards              # one-off override (highest priority)
TRELLO_PROFILE=work /trello cards <listId>     # via env var (per-shell session)
/trello boards                                 # uses active profile or [default]
```

Same dispatch commands across **all 12 multi-account skills**. Replace
`trello` with `azure-devops`, `heroku`, `sentry`, `slack`, `firebase`,
`shopify`, `postgres`, `k6`, `maestro`, `fastlane`, or `rspec`.

### Profile resolution priority

When you call a skill, the active profile is resolved in this order
(first match wins):

1. **`--profile <name>` flag** — highest priority, per-call override
2. **`<SERVICE>_PROFILE` env var** — per-shell session
   - `TRELLO_PROFILE`, `HEROKU_PROFILE`, `SENTRY_PROFILE`, `SLACK_PROFILE`,
     `FIREBASE_PROFILE`, `SHOPIFY_PROFILE`, `PG_PROFILE`, `K6_PROFILE`,
     `MAESTRO_PROFILE`, `FASTLANE_PROFILE`, `RSPEC_PROFILE`
   - `azure-devops` accepts both `AZDO_PROFILE` and `AZURE_DEVOPS_PROFILE`
3. **`~/.<service>/active_profile`** — written by `profile use`, persists across sessions
4. **`[default]` section** — fallback if nothing else is set

### How Claude auto-detects which skill to use

Claude reads each skill's frontmatter `description` at session start
(~779 tokens total for all 14 skills) to route incoming requests:

| You say | Claude routes to |
|---|---|
| "fetch this trello card" / paste `https://trello.com/c/...` URL | `/trello card <id>` |
| "list azure devops PRs" / mention an ADO repo | `/azure-devops pr-list` |
| "scale my heroku app" / "promote staging to prod" | `/heroku scale` or `/heroku promote` |
| "any sentry errors today?" | `/sentry issues` |
| "post this to slack" | `/slack post` |
| "deploy firebase functions" | `/firebase fn-deploy` |
| "list shopify products" / "open orders this week" / paste myshopify URL | `/shopify products` or `/shopify orders` |
| "what's the slowest query?" | `/postgres slow` |
| "run e2e on this flow" | `/maestro run` |
| "release iOS to TestFlight" | `/fastlane beta-ios` |
| "load test the staging API" | `/k6 run` |
| "rerun only failed specs" | `/rspec failed` |
| "scan for SQL injection" / "any new CVEs?" | `/rails-security` |
| "convert these xlsx test cases to maestro" | `/xlsx-testcases gen maestro` |
| "clean RN build" / "bump app version" | `/react-native` |

Switching profiles in conversation works the same way: tell Claude *"on the
work account, list my Trello boards"* — Claude understands and runs
`/trello --profile work boards`.

### Adapting to your project

Nothing in this toolkit is tied to a specific project, organization, or
host. To use it for **your** project:

1. **Configure your accounts**: run `/<skill> configure` for each service
   you use. Pick profile names that match your own workflow
   (`personal`, `work`, `acme-corp`, `staging`, `prod`, etc.).
2. **Set per-project defaults** with env vars in your project's `.env`
   (which is `.gitignore`d):
   ```bash
   AZDO_PROFILE=acme-corp
   HEROKU_PROFILE=staging
   PG_PROFILE=staging-readonly
   ```
3. **Drop a `.testcase-schema.yml`** in your xlsx folder to tell
   `/xlsx-testcases` how to read your column layout (template in
   [examples/](examples/.testcase-schema.example.yml)).
4. **Mark prod profiles** with `require_confirm = true` and (for postgres)
   `read_only = true` so destructive ops require explicit typed
   confirmation.
5. **Audit log** at `~/.claude-team-toolkit/audit.log` records every
   mutation as `timestamp <TAB> service <TAB> profile <TAB> action`.
   Ship to your SIEM (filebeat / fluentd / cloudwatch agent) for
   centralized audit if needed.

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

## Token economics

This toolkit is designed to save tokens **across a typical multi-step
session**, not on a one-off ad-hoc task. Be honest about when it helps and
when it doesn't.

### Always-loaded cost (every session)

Frontmatter descriptions of all 14 skills load at session start so Claude
can route correctly to the right skill: **~779 tokens** total (avg 56
tokens per skill).

### Per-skill body cost (loaded only when invoked)

| Skill | Body tokens | Skill | Body tokens |
|---|---:|---|---:|
| postgres | 1,333 | k6 | 947 |
| heroku | 1,234 | slack | 930 |
| firebase | 1,222 | azure-devops | 845 |
| rails-security | 1,196 | xlsx-testcases | 799 |
| fastlane | 1,111 | sentry | 755 |
| maestro | 1,104 | react-native | 716 |
| rspec | 1,024 | trello | 584 |

Sum of all bodies (if you invoked every skill once): ~13,800 tokens.

### Comparison: with vs without the toolkit

| Scenario | Without toolkit | With toolkit | Saved |
|---|---:|---:|---:|
| 1 skill × 1 invocation | ~1,500 | ~1,680 | **-180** (toolkit costs more) |
| 3 skills × 4 invocations each | ~19,800 | ~5,500 | **+14,300 (~72%)** |
| 5 skills × 5 invocations each | ~37,500 | ~9,800 | **+27,700 (~74%)** |
| Per-skill, 5x reuse | ~5,000 | ~1,100 | **~75-81%** |

### When the toolkit saves tokens

- **Multi-step workflows that reuse the same skill** — skill body loads
  once per session, follow-up calls are cheap.
- **Multi-account operations** — the profile system saves re-explaining
  auth + safety patterns to Claude every call.
- **Less common APIs** — Azure DevOps Server, Heroku Platform API,
  Sentry/Trello REST patterns are non-trivial; without a skill, Claude
  often guesses wrong on the first try and needs a retry.

### When it doesn't

- **One-off ad-hoc tasks** — the 779 always-loaded tokens are wasted if
  you don't invoke any toolkit skill in that session.
- **Common tasks Claude knows well** — e.g., basic git, curl, npm scripts.
  No skill needed.

### Methodology

"Without toolkit" cost is estimated as: equivalent body content Claude
would generate (1.5× the skill body, accounting for verbose explanations)
+ retry overhead (35% probability of a retry on uncommon APIs, 50% of
original cost). Real-world numbers vary by API familiarity and how Claude
is prompted; these are best-effort estimates from observed token usage
patterns. The break-even point is at roughly **2 invocations of any single
skill in a session**.

### Tips for token efficiency

- Set `<SERVICE>_PROFILE` env var once at session start instead of
  `--profile foo` on every command.
- Use `profile use <name>` to set a default — the active profile pointer
  is read from disk, no env var needed.
- Don't run `configure` repeatedly — it's a one-time interactive setup
  per profile.
- For long-running scripts, prefer one skill invocation that does many
  things over many small ones.

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, skill design rules,
security checklist, and trim policy.

Quick rules:
- New skills must source `lib/credentials.sh` (no duplicated helpers)
- Frontmatter `description` ≤ 40 words
- Mutating ops must use `ctt_confirm` + `ctt_audit_log`
- No real credentials, internal hostnames, or project names anywhere

## Examples

Sanitized templates in [examples/](examples/) — copy to your config locations:
- `examples/trello-credentials.example` → `~/.trello/credentials`
- `examples/azure-devops-credentials.example` → `~/.azure-devops/credentials`
- `examples/.testcase-schema.example.yml` → your xlsx folder
- `examples/.env.example` → your project root

## Reporting security issues

Don't open a public issue. Email `96.tuan.nv@gmail.com` with subject
`[SECURITY] claude-team-toolkit`.

---

## License

MIT — see [LICENSE](LICENSE).

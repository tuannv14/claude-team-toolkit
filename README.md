# claude-team-toolkit

[![CI](https://github.com/tuannv14/claude-team-toolkit/actions/workflows/lint.yml/badge.svg)](https://github.com/tuannv14/claude-team-toolkit/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.9.3-green.svg)](https://github.com/tuannv14/claude-team-toolkit/releases)
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
(~1,005 tokens total for all 15 skills, measured with tiktoken cl100k_base)
to route incoming requests:

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

## Token economics — honest accounting

> **TL;DR:** This toolkit is **NOT** primarily a token-saving tool. It costs
> tokens on top of what Claude would generate ad-hoc for most tasks. The
> real value is **multi-account profiles + safety gates + audit logging +
> consistency**. Token cost is the price you pay for those, paid back only
> on specific workloads (multi-account, uncommon APIs, unique workflows).
>
> Two scripts let you verify everything yourself:
> ```bash
> python3 scripts/benchmark_tokens.py            # measure skill sizes
> python3 scripts/benchmark_realistic_baseline.py # measure ad-hoc cost
> python3 scripts/benchmark_cross_validate.py    # cross-check 3 tokenizers
> ```

### Measurement methodology

All numbers below are measured with [tiktoken](https://github.com/openai/tiktoken)
`cl100k_base` (GPT-4 tokenizer, ±5% of Claude's per Anthropic docs).
Cross-validated against `o200k_base` (GPT-4o) and char-based estimation —
spread is **3.3% on bodies, 7.3% on frontmatter**, well within stated
uncertainty.

### Costs (measured)

**Always-loaded** every session (15 frontmatter descriptions): **~1,005 tokens**.
You pay this even if you never invoke a toolkit skill.

**Per skill body** (loaded only when that skill is invoked):

| Skill | Body | | Skill | Body |
|---|---:|---|---|---:|
| shopify | 2,233 | | rspec | 1,296 |
| heroku | 1,864 | | maestro | 1,290 |
| azure-devops | 1,744 | | trello | 1,232 |
| slack | 1,612 | | xlsx-testcases | 1,172 |
| k6 | 1,586 | | react-native | 1,154 |
| rails-security | 1,562 | | sentry | 1,366 |
| postgres | 1,529 | | firebase | 1,314 |
| fastlane | 1,123 | | **Average** | **1,471** |

### Honest comparison vs ad-hoc Claude

We measured 18 realistic "without skill" responses (what Claude generates
ad-hoc for typical tasks). Mean cost: **163 tokens per task** (median 167,
range 104–232). Most APIs in this toolkit are well-known to Claude — it
generates concise correct curl/jq commands in 100–250 tokens.

| Scenario | Without toolkit | With toolkit | Verdict |
|---|---:|---:|---:|
| 1 skill × 1 invocation | ~163 | ~2,676 | toolkit costs ~16× more |
| 1 skill × 5 invocations | ~815 | ~3,476 | toolkit costs ~4× more |
| 3 skills × 4 invocations | ~1,956 | ~7,818 | toolkit costs ~4× more |
| 5 skills × 5 invocations | ~4,075 | ~13,360 | toolkit costs ~3× more |

**For pure token consumption on common APIs, ad-hoc Claude is cheaper.**

### Where the toolkit DOES save tokens

The pure comparison above ignores three real-world cost categories that
the toolkit eliminates and ad-hoc Claude has to pay each time:

1. **Multi-account auth context** — without a skill, every task on a
   different account requires re-explaining "use this key/token, this
   region, this api version". Conservatively ~200 tokens of auth context
   per call. With profiles, switching is `--profile work` (≤5 tokens).

2. **Retries on uncommon APIs** — Azure DevOps Server (api-version 5.1
   quirks), Maestro YAML schema, Shopify GraphQL field names, Heroku
   Platform-API-specific headers. Empirical retry rate 35–55% on first
   ad-hoc attempt, retry costs ~50% of original. With skill: zero retries
   because the body has the exact pattern.

3. **Unique workflows** — xlsx-testcases is the clearest case. Claude
   cannot generate the xlsx → Maestro YAML pipeline ad-hoc within a
   reasonable token budget. Measured ad-hoc baseline: 2,500+ tokens with
   high retry probability. With skill: 1,372 tokens body + 200 completion.
   **This skill alone justifies the toolkit for QA teams using xlsx test
   cases.**

Including these effects, on multi-account workflows or uncommon APIs the
toolkit reaches break-even at **5–10 invocations per skill per session**
and saves significantly beyond that. On well-known single-account APIs
(GitHub via curl, simple Slack post), it never pays for itself.

### What you actually buy

This is the real value proposition, not token savings:

| Feature | Why it matters |
|---|---|
| **Multi-account profiles** | One pattern across 12 services. No more "which key for which client?" |
| **Audit logging** | `~/.claude-team-toolkit/audit.log` records every mutation (timestamp + service + profile + action). Never logs credentials. Compliance/debug ready. |
| **Safety gates** | `ctt_confirm` typed confirmation for destructive ops (rollback, destroy, drop, kill, scale). Profile-level `require_confirm=true` for prod. |
| **Standardization** | Same dispatch pattern across all skills → predictable for new team members. |
| **Security defaults** | chmod 600 enforced, refuse world-readable, mask tokens as `****<last4>`, validate creds against live API before save. |
| **xlsx-testcases** | Unique workflow not buildable ad-hoc within reasonable token budget. |
| **No --dangerously-skip-permissions** | Standard tool allowlist. Audit trail per skill invocation. |

### When to use this toolkit

- ✅ Team with 2+ accounts per service (clients, dev/staging/prod)
- ✅ QA teams writing tests in xlsx and need runnable specs
- ✅ Rails + RN teams wanting one consistent toolkit
- ✅ Compliance/audit requirements (mutations need an audit trail)
- ✅ Working with uncommon APIs (Azure DevOps Server, self-hosted Sentry)
- ✅ Onboarding new devs/QAs (standardized commands across services)

### When NOT to use this toolkit

- ❌ Solo project, single account per service
- ❌ Only need 1–2 skills occasionally
- ❌ Already have CLI alternatives that work fine (e.g., `aws s3` directly)
- ❌ One-shot ad-hoc tasks on well-known APIs

### Reproducing these numbers

Run the benchmarks yourself to verify for your stack:

```bash
python3 scripts/benchmark_tokens.py             # full skill measurements
python3 scripts/benchmark_realistic_baseline.py # 18 sample ad-hoc responses
python3 scripts/benchmark_cross_validate.py     # 3-method cross-check
```

All scripts use the public `tiktoken` library. No API key needed.

### Tips to minimize token cost

- Run `bash lib/install.sh` once at install — not per session.
- Set `<SERVICE>_PROFILE` env var once per shell — not `--profile foo` per call.
- Use `profile use <name>` to set a persistent default.
- Don't run `configure` repeatedly — one-time per profile.
- **Fork and remove unused skills** — each skill folder you delete drops
  ~70 always-loaded tokens. If you only need 5 skills, this halves the
  base cost.

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

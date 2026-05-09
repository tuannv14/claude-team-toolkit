---
name: heroku
description: "Use when user references Heroku, *.herokuapp.com URLs, dashboard.heroku.com, or operations on apps/dynos/releases/config-vars/log-tails/rollbacks/pipeline-promotions. Multi-account via HEROKU_PROFILE."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /heroku — Platform API v3 (multi-account)

Direct REST against `https://api.heroku.com`. No Heroku CLI dependency.
Bearer auth with API key. Profile resolution: `--profile` → `HEROKU_PROFILE`
→ `~/.heroku/active_profile` → `[default]`.

## Overview

Direct REST against Platform API v3. Auto-masks secrets in config var output (`KEY|SECRET|TOKEN|PASSWORD|DSN|URL`). Multi-account via INI profile.

## When to Use

- Heroku app management: dynos, releases, config, logs
- Pipeline promotions (staging → prod)
- Rollback to a previous release
- Investigating prod via log streams or release history
- Investigating "why isn't my dyno running" issues

## When NOT to Use

- Heroku build/buildpack logic → that's a Procfile + buildpack thing
- One-off deploys → `git push heroku main` directly
- Add-on provisioning that needs interactive plan selection → admin UI
- Anything involving Dashboard 2FA flows

## Profile config

`~/.heroku/credentials` (mode 600):

```ini
[default]
api_key      = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
default_app  = my-staging-app

[work]
api_key      = HRKU-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
default_app  = production-api
require_confirm = true                   # gate every mutation
```

**Get key:** `heroku authorizations:create` (CLI) OR Account Settings →
Authorizations. Use **scoped tokens** (read/write/deploy) — avoid global.

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds heroku "$PROFILE"
```

`heroku_api()` wrapper and full dispatch implementations live in
**[recipes.md](recipes.md)** — load it when the user invokes a specific
verb. Brief verb catalog:

| Verb | Mutating? | Confirm |
|---|---|---|
| `apps`, `info`, `config`, `dynos`, `releases`, `logs`, `addons`, `pipelines` | no | — |
| `config-set`, `config-unset` | yes | `ctt_confirm` |
| `scale`, `restart` | yes | `ctt_confirm` |
| `rollback` | yes | typed `ROLLBACK` |
| `promote` | yes | typed `PROMOTE` |
| `destroy` | yes | typed app name (irreversible) |

## Reference files (load on demand)

- **`recipes.md`** — full curl + jq implementations for every dispatch verb above. Load when user invokes a specific verb (`/heroku scale my-app web=3` → load recipes for `scale`).

## Common Mistakes

- Pasting unmasked config output publicly → secrets leak. Use default masked view.
- Global API tokens vs scoped → prefer scoped (`-s read|write|deploy`)
- Forgetting `default_app` → every command needs explicit `<app>` arg
- 401 vs 403 confusion: 401 = token revoked, 403 = scope missing, 404 = wrong app name
- Pipeline promote without checking which apps are in the pipeline first
- Auditing `config-set` values instead of just key names → secrets land in audit log

## Safety

- All mutations require `ctt_confirm`; `destroy` requires typing app name.
- Profile-level `require_confirm=true` for prod adds extra gate.
- Config var output auto-masks `KEY|SECRET|TOKEN|PASSWORD|DSN|URL` matches.
- Audit log records action + key names, NEVER values.
- 401 → token revoked; 403 → scope missing; 404 → app name wrong.
- Use scoped tokens (`heroku authorizations:create -s read`) over global.

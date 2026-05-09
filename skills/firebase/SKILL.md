---
name: firebase
description: "Use when user references Firebase, console.firebase.google.com URLs, *.firebaseapp.com, *.web.app links, or asks for Remote-Config/App-Distribution/Crashlytics-dSYM/Cloud-Functions/Hosting ops. Multi-project via FIREBASE_PROFILE."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /firebase — Firebase CLI (multi-project)

Wraps `firebase` CLI with profile-based project switching. Each profile pins
project ID + service account JSON + default app IDs. Profile resolution:
`--profile` → `FIREBASE_PROFILE` → `~/.firebase/active_profile` → `[default]`.

## Overview

Profile-based project switching, so commands target the right env without
explicit flags. Service Account auth (least privilege per env), never
`firebase login` token (which carries Owner role).

## When to Use

- Push Remote Config (rollouts to production users)
- Distribute beta builds via App Distribution (testers groups)
- Upload Crashlytics dSYM / Proguard mapping (mandatory for readable prod stacks)
- Deploy Cloud Functions, manage Hosting channels (preview URLs)

## When NOT to Use

- Firebase web/mobile client SDK → that's the SDK in your app, not this skill
- Firestore data ops → use Firestore SDK or Admin SDK in code
- Auth flows → SDK in app, not CLI
- Project setup / billing → Firebase Console UI

## Profile config

`~/.firebase/credentials` (mode 600):

```ini
[default]
project_id     = my-app-dev
service_account = /Users/me/.firebase-keys/dev-sa.json
ios_app_id     = 1:123456789012:ios:abc123
android_app_id = 1:123456789012:android:def456

[prod]
project_id     = my-app-prod
service_account = /Users/me/.firebase-keys/prod-sa.json
ios_app_id     = 1:222222222222:ios:zzz
android_app_id = 1:222222222222:android:www
require_confirm = true
```

**Get SA key (least privilege):**

1. Firebase Console → ⚙ Project Settings → Service Accounts
2. Generate new private key → download JSON
3. Don't use default SA — create dedicated with only needed roles
   (e.g., `Firebase App Distribution Admin` for beta only)
4. Save to `~/.firebase-keys/<env>-sa.json`, `chmod 600`

**Why SA over `firebase login`:** SA scoped to roles, revocable, no human
auth flow. CI/automation always uses SA. `firebase login` writes a token
with full user permissions (often Owner role).

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds firebase "$PROFILE"
```

`firebase_run()` wrapper and full dispatch implementations live in
**[recipes.md](recipes.md)** — load when user invokes a specific verb.

| Verb area | Mutating? | Confirm |
|---|---|---|
| `projects`, `apps`, `current` | no | — |
| `rc-get` | no | — |
| `rc-set`, `rc-rollback` | yes | typed `PUSH` / `ROLLBACK` |
| `dist-upload`, `dist-testers add\|remove` | yes | `ctt_audit_log` |
| `crashlytics:symbols:upload`, `crashlytics:mappingfile:upload` | additive | — |
| `fn-deploy` | yes | `ctt_confirm` if profile `require_confirm` |
| `hosting deploy`, `hosting channel:deploy` | yes | `ctt_audit_log` |

## Reference files (load on demand)

- **`recipes.md`** — full firebase CLI invocations for every verb above (Remote Config push/rollback, App Distribution upload + tester management, Crashlytics symbol upload, Functions deploy + logs, Hosting deploy + preview channels). Load when user invokes a specific dispatch verb.

## Common Mistakes

- Using default service account → over-privileged. Create dedicated SA per role.
- Forgetting dSYM upload → crash stacks unreadable in prod
- `firebase login` token instead of SA → has Owner role, blast radius huge
- Wrong project (default vs prod) → check `--project` resolves correctly
- 401/403 → SA missing role; check IAM in GCP console
- Pushing Remote Config without checking current live version first → unintended user impact

## Safety

- **SA JSON is the most powerful credential** — never commit. `chmod 600`.
- **Per-environment SA** — dev/staging/prod must be SEPARATE SAs.
- **Least privilege roles**: avoid `Owner`/`Editor` for automation. Beta dist only → `Firebase App Distribution Admin`. RC only → `Firebase Remote Config Admin`.
- **`require_confirm=true`** on prod profiles for every deploy.
- **dSYM/mapping uploads non-destructive** — safe to automate.
- **Functions delete intentionally not in skill** — use Console (forces conscious action).
- 401/403 → SA missing role; check IAM in GCP console.

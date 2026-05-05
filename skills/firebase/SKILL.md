---
name: firebase
description: Firebase Remote Config, App Distribution, Crashlytics symbols, Functions, Hosting via CLI. Use to deploy, push config, distribute beta builds, upload dSYM. Multi-project via FIREBASE_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /firebase — Firebase CLI (multi-project)

Wraps `firebase` CLI with profile-based project switching. Each profile pins
project ID + service account JSON + default app IDs.

Profile resolution: `--profile` → `FIREBASE_PROFILE` → `~/.firebase/active_profile` → `[default]`.

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

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds firebase "$PROFILE"

firebase_run() {
  GOOGLE_APPLICATION_CREDENTIALS="$CTT_SERVICE_ACCOUNT" \
    firebase --project "$CTT_PROJECT_ID" "$@"
}
```

## Dispatch

### `projects` / `current` / `apps`
```bash
firebase_run projects:list
firebase_run apps:list
```

### Remote Config

#### `rc-get [--out file.json]`
```bash
firebase_run remoteconfig:get -o "${OUT:-/dev/stdout}"
```

#### `rc-set <file.json>` — DESTRUCTIVE
```bash
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Push RC to $CTT_PROJECT_ID? Type PUSH:" "PUSH" || return 1
ctt_warn_destructive "Pushing Remote Config to $CTT_PROJECT_ID — affects ALL users"
firebase_run remoteconfig:versions:list --limit 1     # show what's currently live
firebase_run deploy --only remoteconfig --json < "$FILE"
ctt_audit_log firebase "rc-set $FILE"
```

#### `rc-rollback <version>` — DESTRUCTIVE
```bash
ctt_warn_destructive "Rollback RC to v$VERSION"
ctt_confirm "Type ROLLBACK to confirm:" "ROLLBACK" || return 1
firebase_run remoteconfig:rollback --version "$VERSION"
ctt_audit_log firebase "rc-rollback v$VERSION"
```

### App Distribution (beta to testers)

#### `dist-upload <ipa-or-apk> [--release-notes "..."] [--groups "qa,internal"]`
```bash
case "${PLATFORM:-android}" in
  ios)     APP="$CTT_IOS_APP_ID" ;;
  android) APP="$CTT_ANDROID_APP_ID" ;;
esac

firebase_run appdistribution:distribute "$BUILD_FILE" \
  --app "$APP" \
  ${RELEASE_NOTES:+--release-notes "$RELEASE_NOTES"} \
  ${GROUPS:+--groups "$GROUPS"}

ctt_audit_log firebase "dist-upload ${PLATFORM:-android} groups:${GROUPS:-—}"
```

#### `dist-testers <list|add|remove> [email]`
```bash
case "$ACTION" in
  list)   firebase_run appdistribution:testers:list ;;
  add)    firebase_run appdistribution:testers:add "$EMAIL" ;;
  remove) firebase_run appdistribution:testers:remove "$EMAIL" ;;
esac
```

### Crashlytics symbols

```bash
# iOS dSYM
firebase_run crashlytics:symbols:upload --app "$CTT_IOS_APP_ID" "$DSYM_PATH"

# Android Proguard mapping
firebase_run crashlytics:mappingfile:upload \
  --app "$CTT_ANDROID_APP_ID" \
  --resource-file=android/app/src/main/AndroidManifest.xml \
  "$MAPPING"
```
**Required for prod builds** — without it, crash stacks are uninterpretable.

### Functions

```bash
# Deploy
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Deploy functions to $CTT_PROJECT_ID?" || return 1
firebase_run deploy --only "functions${FUNCTIONS:+:${FUNCTIONS}}"
ctt_audit_log firebase "fn-deploy ${FUNCTIONS:-all}"

# Logs
firebase_run functions:log ${FUNCTION:+--only "$FUNCTION"} --limit "${LIMIT:-50}"
```

### Hosting

```bash
# Deploy to production
firebase_run deploy --only "hosting${TARGET:+:$TARGET}"

# Preview channel (temporary URL, expires in 7d default)
firebase_run hosting:channel:deploy "$CHANNEL" --expires "${EXPIRES:-7d}"

# List channels
firebase_run hosting:channel:list
```

Preview channels = stakeholder review URLs without affecting prod.

## Safety

- **SA JSON is the most powerful credential** — never commit. `chmod 600`.
- **Per-environment SA** — dev/staging/prod must be SEPARATE SAs.
- **Least privilege roles**: avoid `Owner`/`Editor` for automation.
  Beta dist only → `Firebase App Distribution Admin`. RC only → `Firebase Remote Config Admin`.
- **`require_confirm=true`** on prod profiles for every deploy.
- **dSYM/mapping uploads non-destructive** — safe to automate.
- **Functions delete intentionally not in skill** — use Console (forces conscious action).
- 401/403 → SA missing role; check IAM in GCP console.

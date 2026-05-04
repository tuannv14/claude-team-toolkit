---
name: firebase
description: Firebase Remote Config, App Distribution, Crashlytics symbols, Functions, Hosting via Firebase CLI. Multi-project. Use to deploy functions, push remote config, distribute beta to testers, upload dSYM/mapping. Switch via --profile or FIREBASE_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /firebase — Firebase CLI (multi-project)

Wraps `firebase` CLI with profile-based project switching. Each profile pins a
project ID + service account JSON + default app IDs (iOS/Android).

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `FIREBASE_PROFILE` env → `~/.firebase/active_profile` → `[default]`.

## Dependencies

```bash
npm install -g firebase-tools           # or: yarn global add firebase-tools
firebase --version                      # 13+ recommended
```

## Profile config

`~/.firebase/credentials` (mode 600):

```ini
[default]
project_id = my-app-dev
service_account = /Users/me/.firebase-keys/dev-sa.json
ios_app_id = 1:123456789012:ios:abc123
android_app_id = 1:123456789012:android:def456

[staging]
project_id = my-app-staging
service_account = /Users/me/.firebase-keys/staging-sa.json
ios_app_id = 1:111111111111:ios:xxx
android_app_id = 1:111111111111:android:yyy

[prod]
project_id = my-app-prod
service_account = /Users/me/.firebase-keys/prod-sa.json
ios_app_id = 1:222222222222:ios:zzz
android_app_id = 1:222222222222:android:www
require_confirm = true
```

**Get a service account key (least privilege):**

1. https://console.firebase.google.com → ⚙ → Project Settings → Service Accounts
2. Generate new private key → download JSON
3. **Don't use the default service account** — create a dedicated one with only
   needed roles (e.g., `Firebase App Distribution Admin` for beta releases).
4. Save to `~/.firebase-keys/<env>-sa.json`, `chmod 600`.

**Why service account JSON over `firebase login`:**
- `firebase login` writes a token to `~/.config/configstore/firebase-tools.json`
  with full user permissions (often Owner role).
- Service account = scoped to specific roles, revocable, no human auth flow.
- CI/automation always uses service account.

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

### `projects` — list projects accessible to the SA

```bash
firebase_run projects:list
```

### `current` — show active profile + project

```bash
echo "Profile:    $CTT_PROFILE"
echo "Project ID: $CTT_PROJECT_ID"
echo "iOS app:    ${CTT_IOS_APP_ID:-—}"
echo "Android:    ${CTT_ANDROID_APP_ID:-—}"
echo "SA:         $CTT_SERVICE_ACCOUNT"
```

### `apps` — list apps in this project

```bash
firebase_run apps:list
```

---

### Remote Config

#### `rc-get [--out file.json]`

```bash
firebase_run remoteconfig:get -o "${OUT:-/dev/stdout}"
```

#### `rc-set <file.json> [--force]` — push template — DESTRUCTIVE

```bash
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Push Remote Config to $CTT_PROJECT_ID?" "PUSH" || return 1

firebase_run remoteconfig:versions:list --limit 1     # show what's currently live
ctt_warn_destructive "Pushing Remote Config to $CTT_PROJECT_ID — affects ALL users"
firebase_run deploy --only remoteconfig --json < "$FILE"
ctt_audit_log firebase "rc-set $FILE"
```

`force: true` flag in template overrides A/B test conflicts.

#### `rc-rollback <version>` — DESTRUCTIVE

```bash
ctt_warn_destructive "Rollback Remote Config to v$VERSION"
ctt_confirm "Rollback?" "ROLLBACK" || return 1
firebase_run remoteconfig:rollback --version "$VERSION"
ctt_audit_log firebase "rc-rollback v$VERSION"
```

---

### App Distribution (beta releases to testers)

#### `dist-upload <ipa-or-apk> [--release-notes "..."] [--groups "qa,internal"]`

```bash
APP_ID="${PLATFORM:-android}"
case "$APP_ID" in
  ios) APP="$CTT_IOS_APP_ID" ;;
  android) APP="$CTT_ANDROID_APP_ID" ;;
esac

firebase_run appdistribution:distribute "$BUILD_FILE" \
  --app "$APP" \
  ${RELEASE_NOTES:+--release-notes "$RELEASE_NOTES"} \
  ${GROUPS:+--groups "$GROUPS"}

ctt_audit_log firebase "dist-upload $APP_ID groups:${GROUPS:-—}"
```

#### `dist-testers <action>` — manage testers (add/remove/list)

```bash
case "$ACTION" in
  list)   firebase_run appdistribution:testers:list ;;
  add)    firebase_run appdistribution:testers:add "$EMAIL" ;;
  remove) firebase_run appdistribution:testers:remove "$EMAIL" ;;
esac
```

---

### Crashlytics symbols

#### `dsym-upload <dsym-path>` — iOS dSYM

```bash
firebase_run crashlytics:symbols:upload --app "$CTT_IOS_APP_ID" "$DSYM_PATH"
```

dSYMs are usually inside the .ipa or downloadable from App Store Connect.
**Required for prod builds** — without it, crash stacks are uninterpretable.

#### `mapping-upload <mapping.txt>` — Android Proguard mapping

```bash
firebase_run crashlytics:mappingfile:upload \
  --app "$CTT_ANDROID_APP_ID" \
  --resource-file=android/app/src/main/AndroidManifest.xml \
  "$MAPPING"
```

---

### Functions

#### `fn-deploy [function-names]` — deploy Cloud Functions

```bash
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Deploy functions to $CTT_PROJECT_ID?" || return 1

firebase_run deploy --only "functions${FUNCTIONS:+:${FUNCTIONS}}"
ctt_audit_log firebase "fn-deploy ${FUNCTIONS:-all}"
```

#### `fn-logs [--function name] [--limit N]`

```bash
firebase_run functions:log \
  ${FUNCTION:+--only "$FUNCTION"} \
  --limit "${LIMIT:-50}"
```

---

### Hosting

#### `hosting-deploy [--target site]`

```bash
firebase_run deploy --only "hosting${TARGET:+:$TARGET}"
ctt_audit_log firebase "hosting-deploy ${TARGET:-default}"
```

#### `hosting-channels` — list preview channels

```bash
firebase_run hosting:channel:list
```

#### `hosting-preview <channel-name> [--expires 7d]` — deploy to preview channel

```bash
firebase_run hosting:channel:deploy "$CHANNEL" --expires "${EXPIRES:-7d}"
```

Preview channels = temporary URLs for stakeholder review without affecting prod.

---

### Project-level

#### `use <profile>` — same as `profile use` but Firebase semantic

```bash
ctt_use_profile firebase "$1"
```

#### `whoami` — verify SA + show roles

```bash
firebase_run --debug projects:list 2>&1 | grep -E "Email|project_id" | head -5
```

## Safety

- **Service account JSON is the most powerful credential here**. Never commit
  to git. Store at `~/.firebase-keys/` with mode 600.
- **Per-environment SA**: dev/staging/prod should be **separate** SAs. Don't
  reuse a prod SA for dev convenience — leak risk multiplies.
- **Least privilege roles**:
  - Beta distribution only: `Firebase App Distribution Admin`
  - RC only: `Firebase Remote Config Admin`
  - Functions deploy: `Firebase Admin SDK Administrator Service Agent`
  - Avoid `Owner` / `Editor` for automation accounts.
- **Audit log** records actions but NOT credentials or RC content.
- **`require_confirm = true`** on prod: every deploy goes through typed
  confirmation. Add this layer for `prod` profiles always.
- **dSYM/mapping uploads are non-destructive** — safe to automate.
- **Functions delete** is intentionally not in this skill — to delete, use the
  Console (forces conscious action). Gradual rollout: deploy new version that
  no-ops, then delete from Console after metrics show no traffic.

## Token-saving tips

- Use `--only <product>` to scope deploy (don't redeploy hosting when only
  functions changed).
- Cache `firebase_run projects:list` once per session; profile config has
  the project ID anyway.
- For RC, use `force: true` only when needed — collisions are rare.

## Common pitfalls

- "Permission denied" on deploy → SA missing role; check IAM in GCP console.
- "Multiple projects in use" → CLI reads `.firebaserc` from cwd; explicit
  `--project` always wins (this skill always passes it).
- App Distribution upload silently fails with no testers → `--groups` or
  `--testers` is required, otherwise upload succeeds but no one gets notified.

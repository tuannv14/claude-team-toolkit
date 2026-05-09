# /firebase — recipes (load on demand)

> Loaded by SKILL.md only when user invokes a specific dispatch verb.

## Helpers (already loaded in SKILL.md)

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds firebase "$PROFILE"

firebase_run() {
  GOOGLE_APPLICATION_CREDENTIALS="$CTT_SERVICE_ACCOUNT" \
    firebase --project "$CTT_PROJECT_ID" "$@"
}
```

## Dispatch — projects / apps

### `projects` / `current` / `apps`
```bash
firebase_run projects:list
firebase_run apps:list
```

## Dispatch — Remote Config

### `rc-get [--out file.json]`
```bash
firebase_run remoteconfig:get -o "${OUT:-/dev/stdout}"
```

### `rc-set <file.json>` — DESTRUCTIVE
```bash
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Push RC to $CTT_PROJECT_ID? Type PUSH:" "PUSH" || return 1
ctt_warn_destructive "Pushing Remote Config to $CTT_PROJECT_ID — affects ALL users"
firebase_run remoteconfig:versions:list --limit 1     # show what's currently live
firebase_run deploy --only remoteconfig --json < "$FILE"
ctt_audit_log firebase "rc-set $FILE"
```

### `rc-rollback <version>` — DESTRUCTIVE
```bash
ctt_warn_destructive "Rollback RC to v$VERSION"
ctt_confirm "Type ROLLBACK to confirm:" "ROLLBACK" || return 1
firebase_run remoteconfig:rollback --version "$VERSION"
ctt_audit_log firebase "rc-rollback v$VERSION"
```

## Dispatch — App Distribution

### `dist-upload <ipa-or-apk> [--release-notes "..."] [--groups "qa,internal"]`
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

### `dist-testers <list|add|remove> [email]`
```bash
case "$ACTION" in
  list)   firebase_run appdistribution:testers:list ;;
  add)    firebase_run appdistribution:testers:add "$EMAIL" ;;
  remove) firebase_run appdistribution:testers:remove "$EMAIL" ;;
esac
```

## Dispatch — Crashlytics symbols

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

## Dispatch — Functions

```bash
# Deploy
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Deploy functions to $CTT_PROJECT_ID?" || return 1
firebase_run deploy --only "functions${FUNCTIONS:+:${FUNCTIONS}}"
ctt_audit_log firebase "fn-deploy ${FUNCTIONS:-all}"

# Logs
firebase_run functions:log ${FUNCTION:+--only "$FUNCTION"} --limit "${LIMIT:-50}"
```

## Dispatch — Hosting

```bash
# Deploy to production
firebase_run deploy --only "hosting${TARGET:+:$TARGET}"

# Preview channel (temporary URL, expires in 7d default)
firebase_run hosting:channel:deploy "$CHANNEL" --expires "${EXPIRES:-7d}"

# List channels
firebase_run hosting:channel:list
```

Preview channels = stakeholder review URLs without affecting prod.

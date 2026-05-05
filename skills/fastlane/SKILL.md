---
name: fastlane
description: "Fastlane lanes for iOS/Android release — TestFlight, App Store, Play Console, match code signing. Multi-app via FASTLANE_PROFILE."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /fastlane — mobile release automation (multi-app)

Wraps `bundle exec fastlane` for iOS/Android release workflows. Profiles
manage credentials per app/team. The `Fastfile` lives in the project repo.

Profile resolution: `--profile` → `FASTLANE_PROFILE` → `~/.fastlane/active_profile` → `[default]`.

## Profile config

`~/.fastlane/credentials` (mode 600):

```ini
[default]
project_path = .
# iOS — App Store Connect API key (preferred over Apple ID + 2FA)
appstore_api_key_id = ABCDEFGHIJ
appstore_api_issuer_id = 12345678-aaaa-bbbb-cccc-1234567890ab
appstore_api_key_path = /Users/me/.appstore-keys/AuthKey_ABCDEFGHIJ.p8
# Android — Google Play service account JSON
google_play_json_key = /Users/me/.gplay/service-account.json
# Match (signing) — repo + passphrase (also via MATCH_PASSWORD env)
match_git_url = git@github.com:org/certs.git
match_password = xxxxxxxxxxxx

[work]
project_path = /path/to/work/app
appstore_api_key_id = XYZWVU1234
require_confirm = true                 # gate every release
```

**Why API keys over Apple ID:** API key has no 2FA, scoped permissions,
revocable. CI breaks daily on Apple ID + phone-based 2FA codes.

**Match (recommended):** stores certs/profiles in encrypted git repo. Anyone
on team gets identical signing setup. Encrypted with `match_password`.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds fastlane "$PROFILE"

cd "$CTT_PROJECT_PATH" || { echo "No project at $CTT_PROJECT_PATH" >&2; return 1; }

fastlane_run() {
  APP_STORE_CONNECT_API_KEY_KEY_ID="$CTT_APPSTORE_API_KEY_ID" \
  APP_STORE_CONNECT_API_KEY_ISSUER_ID="$CTT_APPSTORE_API_ISSUER_ID" \
  APP_STORE_CONNECT_API_KEY_KEY_FILEPATH="$CTT_APPSTORE_API_KEY_PATH" \
  GOOGLE_PLAY_JSON_KEY="$CTT_GOOGLE_PLAY_JSON_KEY" \
  MATCH_PASSWORD="$CTT_MATCH_PASSWORD" \
    bundle exec fastlane "$@"
}
```

## Dispatch

### `lanes` — list available lanes from Fastfile
```bash
fastlane_run lanes
```

### `run <platform> <lane> [args...]`
```bash
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Run fastlane $PLATFORM $LANE on $CTT_PROFILE? Type RUN:" "RUN" || return 1
fastlane_run "$PLATFORM" "$LANE" "$@"
ctt_audit_log fastlane "$PLATFORM $LANE $*"
```

### `beta-ios [--changelog "..."]` — TestFlight
```bash
fastlane_run ios beta changelog:"$CHANGELOG"
```

### `beta-android [--track internal|alpha|beta]` — Play internal
```bash
fastlane_run android beta track:"${TRACK:-internal}"
```

### `release-ios` / `release-android` — DESTRUCTIVE
```bash
ctt_warn_destructive "Submit to ${PLATFORM} Store"
ctt_confirm "Type RELEASE to confirm:" "RELEASE" || return 1
fastlane_run "$PLATFORM" release ${TRACK:+track:$TRACK}
ctt_audit_log fastlane "$PLATFORM release"
```

### `match-sync` — sync code signing
```bash
fastlane_run match readonly:true     # readonly=true won't create new certs
```
For new device or initial setup: `readonly:false` (devs only, not CI).

### `screenshots [--device "iPhone 15 Pro"]`
```bash
fastlane_run snapshot ${DEVICE:+--devices "$DEVICE"}
```
Requires `Snapfile` + `SnapshotHelper.swift` in project.

### `pilot-list` — TestFlight builds + testers
```bash
fastlane_run pilot builds
fastlane_run pilot list
```

### `metadata-pull` — download App Store metadata to git
```bash
fastlane_run deliver download_metadata
fastlane_run supply --action download_metadata          # Android
```

## Safety

- **API keys are sensitive** — `.p8` file `chmod 600`, never commit.
- **`match_password`** decrypts certs — leak = full code signing capability.
  Long random passphrase, rotate yearly.
- **Service account JSON** for Play grants release power → `chmod 600`.
- **`require_confirm=true`** on prod profiles prevents accidental releases.
- **Symbols upload** mandatory for prod — without it, crash stacks are useless.
- iOS keystore lost = re-create with match. Android keystore lost = can't
  update app on Play. Back up encrypted to git.

## Common pitfalls

- "Bundle ID mismatch" → check `app_identifier` in Appfile vs Xcode.
- "Code signing failed" → 99% fixed by `match-sync`.
- "App Store rate limit" → use API key (much higher limit) not Apple ID.

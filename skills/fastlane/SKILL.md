---
name: fastlane
description: Fastlane lanes for iOS/Android release — TestFlight, App Store, Play Console, match code signing, screenshots. Multi-app profiles. Use to beta-distribute, sign, submit, or invoke a lane. Apple App Store API key + Play service account JSON.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /fastlane — mobile release automation (multi-app)

Wraps `bundle exec fastlane` for iOS/Android release workflows. Profiles
manage credentials per app/team; the `Fastfile` itself stays in the project
repo (committed, no secrets).

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `FASTLANE_PROFILE` env → `~/.fastlane/active_profile` → `[default]`.

## Dependencies

- Ruby ≥ 2.7 (Fastlane is a Ruby gem)
- Project's `Gemfile` includes `gem 'fastlane'`
- iOS: Xcode CLI tools, optionally `match` for code signing
- Android: Java JDK, Android SDK, `google-play-developer-api` JSON key

```bash
bundle install              # in project root
bundle exec fastlane --version
```

## Profile config

`~/.fastlane/credentials` (mode 600 — contains api keys):

```ini
[default]
project_path = .
# iOS — App Store Connect API key (preferred over Apple ID + 2FA)
appstore_api_key_id = ABCDEFGHIJ
appstore_api_issuer_id = 12345678-aaaa-bbbb-cccc-1234567890ab
appstore_api_key_path = /Users/me/.appstore-keys/AuthKey_ABCDEFGHIJ.p8
# Android — Google Play service account JSON
google_play_json_key = /Users/me/.gplay/service-account.json
# Match (signing) — repo + passphrase
match_git_url = git@github.com:org/certs.git
match_password = xxxxxxxxxxxx                    # also via MATCH_PASSWORD env

[work-ios-only]
project_path = /path/to/work/app
appstore_api_key_id = XYZWVU1234
appstore_api_issuer_id = 87654321-xxxx-yyyy-zzzz-098765432100
appstore_api_key_path = /Users/me/.appstore-keys/AuthKey_XYZWVU1234.p8
# require confirmation for any release
require_confirm = true

[client-android-only]
project_path = /path/to/client/app
google_play_json_key = /Users/me/.gplay/client-sa.json
```

**Why API keys over Apple ID:**
- Apple ID + 2FA → CI breaks daily; phone-based codes can't be automated
- App Store Connect API key → no 2FA; scoped to specific permissions; revocable
- Generate at: https://appstoreconnect.apple.com → Users and Access → Keys

**Match (recommended for iOS teams):**
- Stores certs/profiles in encrypted git repo
- Anyone on team gets identical signing setup with one command
- Encrypted with `match_password` — never commit the password

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds fastlane "$PROFILE"

cd "$CTT_PROJECT_PATH" || { echo "No project at $CTT_PROJECT_PATH" >&2; return 1; }

fastlane_run() {
  # Inject credentials as env (Fastlane reads ENV)
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
PLATFORM="$1" LANE="$2"; shift 2

[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Run fastlane $PLATFORM $LANE on profile $CTT_PROFILE?" "RUN" || return 1

fastlane_run "$PLATFORM" "$LANE" "$@"
ctt_audit_log fastlane "$PLATFORM $LANE $*"
```

### `beta-ios [--changelog "..."]` — TestFlight build

Common Fastlane lane name. Skill assumes lane exists in Fastfile:

```ruby
# Fastfile (committed in project)
platform :ios do
  desc "Build & upload to TestFlight"
  lane :beta do |options|
    setup_ci if ENV['CI']
    match(type: 'appstore', readonly: ENV['CI'])
    increment_build_number(xcodeproj: 'MyApp.xcodeproj')
    build_app(scheme: 'MyApp', export_method: 'app-store')
    upload_to_testflight(
      changelog: options[:changelog],
      skip_waiting_for_build_processing: true
    )
  end
end
```

Then:
```bash
fastlane_run ios beta changelog:"$CHANGELOG"
```

### `beta-android [--track internal|alpha|beta]` — Play Console internal

```bash
fastlane_run android beta track:"${TRACK:-internal}"
```

### `release-ios` — App Store submission — DESTRUCTIVE

```bash
ctt_warn_destructive "App Store submission for $CTT_PROFILE"
ctt_confirm "Submit to App Store review?" "RELEASE" || return 1
fastlane_run ios release
ctt_audit_log fastlane "ios release"
```

### `release-android [--track production]`

```bash
ctt_warn_destructive "Play Store production rollout"
ctt_confirm "Promote to production?" "PROMOTE" || return 1
fastlane_run android release track:production
ctt_audit_log fastlane "android release production"
```

### `match-sync` — sync code signing certs/profiles

```bash
fastlane_run match readonly:true     # readonly = won't create new certs
```

For initial setup or new device: `readonly:false` (devs only, not CI).

### `screenshots [--device "iPhone 15 Pro"]` — generate App Store screenshots

```bash
fastlane_run snapshot ${DEVICE:+--devices "$DEVICE"}
```

Requires `Snapfile` + `SnapshotHelper.swift` in project.

### `pilot-list` — list TestFlight builds + testers

```bash
fastlane_run pilot builds
fastlane_run pilot list
```

### `metadata-pull` — download App Store metadata to git

```bash
fastlane_run deliver download_metadata
fastlane_run supply --action download_metadata          # Android equivalent
```

Useful for keeping store listing under version control.

## Safety

- **API keys are sensitive** — `appstore_api_key_path` points to a `.p8` file
  on disk; protect with `chmod 600`.
- **`match_password`** decrypts certs — leak = full code signing capability.
  Use a long random passphrase; rotate yearly.
- **Service account JSON** for Play Console grants release power — store at
  `~/.gplay/` (mode 600) or use OS keychain.
- **`require_confirm = true`** on prod profiles prevents accidental
  TestFlight/release runs.
- **Never log credentials** — Fastlane is mostly safe but custom lanes can
  print env. Audit Fastfile for `puts ENV[...]` patterns.
- **Symbols upload** (Crashlytics, Sentry) for production builds is mandatory
  — without it, prod stack traces are useless. Add to release lane.

## Token-saving tips

- Use **App Store Connect API key** instead of Apple ID + 2FA (no manual
  intervention).
- Use `setup_ci` action in CI lanes to manage keychain temporary files.
- For Android: prefer **AAB (Android App Bundle)** over APK — smaller download
  for users.
- Use `--skip-waiting-for-build-processing` for TestFlight to avoid 10-min
  hangs.

## Common pitfalls

- iOS code signing failures: 99% of the time `match-sync` fixes it.
- Android: keystore lost = can't update app on Play. Back up to encrypted
  storage AND match-style git repo.
- "App Store Connect API rate limit" — use API key (much higher limit) not
  Apple ID auth.
- "Bundle ID mismatch" — check `app_identifier` in Appfile vs Xcode.

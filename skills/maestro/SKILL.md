---
name: maestro
description: Maestro mobile E2E (YAML) for RN/iOS/Android. Use to run flows, record, inspect hierarchy, detect flaky tests. Multi-environment via MAESTRO_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /maestro — mobile E2E (YAML, multi-env)

Wraps `maestro test`. Profiles = device + app build per environment.

Profile resolution: `--profile` → `MAESTRO_PROFILE` → `~/.maestro/active_profile` → `[default]`.

## Dependencies

```bash
curl -Ls "https://get.maestro.mobile.dev" | bash    # macOS / Linux
# Windows: scoop install maestro  (or use WSL)
maestro --version
```
iOS: Xcode + simulator. Android: Android Studio + emulator.

## Profile config

`~/.maestro/profiles.ini` (mode 600 — may contain Cloud key):

```ini
[default]
platform = ios                        # ios | android
device = iPhone 15
app_id = com.example.app
flows_dir = .maestro

[android-emu]
platform = android
device = Pixel_7_API_34               # AVD name
app_id = com.example.app
flows_dir = .maestro

[staging-cloud]
platform = android
device = R5XY...                      # serial of physical device
app_id = com.example.app.staging
flows_dir = .maestro
cloud_api_key = xxxxxxxxxxxxxxxxxxxxxxxx     # Maestro Cloud
```

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds maestro "$PROFILE"

# Verify device reachable
case "$CTT_PLATFORM" in
  ios) xcrun simctl list devices "$CTT_DEVICE" | grep -q Booted || xcrun simctl boot "$CTT_DEVICE" ;;
  android) adb devices | grep -q "$CTT_DEVICE" || { echo "Device not connected" >&2; return 1; } ;;
esac
```

## Dispatch

### `run <flow.yaml> [--continuous]`
```bash
ARGS=()
[ "$CONTINUOUS" = "true" ] && ARGS+=(--continuous)
maestro test "${ARGS[@]}" "$FLOW"
```
`--continuous` re-runs on file changes — great for authoring.

### `run-all [--tags smoke,critical]`
```bash
maestro test "$CTT_FLOWS_DIR/" \
  ${TAGS:+--include-tags "$TAGS"} \
  --format junit --output /tmp/maestro-results/
```

### `record <flow.yaml>` — interactive flow recorder
```bash
maestro record "$FLOW"
```
Point/tap to record actions → save as YAML. Tester-friendly (no coding).

### `studio` — visual flow editor (browser-based)
```bash
maestro studio
```

### `inspect [--app <bundle-id>]` — view hierarchy
```bash
maestro hierarchy --app "${APP_ID:-$CTT_APP_ID}"
```
Find element selectors / accessibility IDs.

### `tags` — list all tags used in flows
```bash
grep -h "^tags:" -A 20 "$CTT_FLOWS_DIR"/*.yaml | grep "^- " | sort -u
```

### `flaky-report [--last N]` — detect flaky tests from JUnit results
```bash
LAST="${LAST:-10}"
ls -t /tmp/maestro-results/*.xml | head -n "$LAST" | xargs python3 -c '
import sys, xml.etree.ElementTree as ET
from collections import defaultdict
results = defaultdict(list)
for f in sys.argv[1:]:
  for tc in ET.parse(f).iter("testcase"):
    failed = tc.find("failure") is not None or tc.find("error") is not None
    results[tc.get("name")].append(failed)
print("Flaky tests (passed AND failed across runs):")
for n, runs in results.items():
  if any(runs) and not all(runs):
    print(f"  {n}: {sum(runs)}/{len(runs)} fail rate")
'
```

### `cloud upload <flow-or-folder> [--name <run-name>]` — Maestro Cloud
```bash
[ -z "$CTT_CLOUD_API_KEY" ] && { echo "Set cloud_api_key in profile" >&2; return 1; }
maestro cloud --apiKey "$CTT_CLOUD_API_KEY" \
  ${NAME:+--name "$NAME"} \
  "$APP" "$FLOW_OR_FOLDER"
```
`<app>` for cloud is the build artifact (`.app`/`.ipa`/`.apk`), not bundle ID.

### `from-xlsx <xlsx-path>` — scaffold from xlsx test cases
Delegates to `xlsx-testcases gen maestro` — see that skill.

## Flow patterns (cheat sheet)

```yaml
# Common actions
- launchApp
- tapOn: "Submit"             # by text
- tapOn:
    id: "submit-btn"          # by accessibility id
- inputText: "${EMAIL}"
- assertVisible: "Welcome"
- assertNotVisible: "Login"
- waitForAnimationToEnd
- extendedWaitUntil: { visible: "Loaded", timeout: 30000 }
- scrollUntilVisible: { element: "Footer", direction: DOWN }
- runFlow: { file: ../subflows/login.yaml }
```

Variables via env: `EMAIL=test@example.com maestro test flow.yaml`. Inside YAML: `${EMAIL}`.

## Safety

- **Never commit credentials** in flow YAML. Use `${ENV_VAR}` + document required vars in flow comment.
- **Cloud API key** per-account — limited blast radius. Prefer CI-scoped key.
- **Physical devices**: Maestro can interact with anything on screen including OS dialogs.
  Run only on dedicated test devices, never personal phones.
- **Recordings** capture screen — don't record flows with real user data / prod accounts.

## Layout

```
.maestro/
├── config.yaml                  # global config
├── subflows/{login,grant-perms}.yaml
├── smoke/{launch,home-tabs}.yaml
├── regression/...
└── iap/...
```

---
name: maestro
description: Maestro mobile E2E (YAML flows) for RN/iOS/Android. Multi-environment. Use to run flows, record interactively, inspect view hierarchy, detect flaky tests, run on Maestro Cloud. Profiles select device + app build.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /maestro — mobile E2E (YAML, multi-env)

[Maestro](https://maestro.mobile.dev) is a YAML-based mobile E2E framework
that's simpler than Detox/Appium. This skill wraps `maestro test`, manages
flow files, and integrates with `xlsx-testcases` for scaffolding.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `MAESTRO_PROFILE` → `~/.maestro/active_profile` → `[default]`.

## Dependencies

```bash
# Maestro CLI
curl -Ls "https://get.maestro.mobile.dev" | bash    # macOS / Linux
# Windows: scoop install maestro  (or use WSL)

maestro --version
```

For iOS: Xcode + simulator. For Android: Android Studio / SDK + emulator.

## Profile config

`~/.maestro/profiles.ini` (mode 600):

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

[staging-physical]
platform = android
device = R5XY...                      # serial of physical device
app_id = com.example.app.staging
flows_dir = .maestro
# Maestro Cloud — for parallel cloud runs
cloud_api_key = xxxxxxxxxxxxxxxxxxxxxxxx
```

Profiles let you run the **same flow** against different devices/builds with
one flag — useful for CI matrix testing.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds maestro "$PROFILE"

# Verify device is reachable
case "$CTT_PLATFORM" in
  ios) xcrun simctl list devices "$CTT_DEVICE" | grep -q Booted || xcrun simctl boot "$CTT_DEVICE" ;;
  android) adb devices | grep -q "$CTT_DEVICE" || { echo "Device not connected" >&2; return 1; } ;;
esac
```

## Dispatch

### `run <flow.yaml> [--continuous]`

```bash
ctt_load_creds maestro "$PROFILE"

ARGS=()
[ "$CONTINUOUS" = "true" ] && ARGS+=(--continuous)

maestro test "${ARGS[@]}" "$FLOW"
```

`--continuous` re-runs on file changes — great for authoring flows.

### `run-all [--tags smoke,critical]`

```bash
maestro test "$CTT_FLOWS_DIR/" \
  ${TAGS:+--include-tags "$TAGS"} \
  --format junit \
  --output /tmp/maestro-results/
```

`--format junit` lets CI ingest results in standard format.

### `record <flow.yaml>` — interactive flow recorder

```bash
maestro record "$FLOW"
```

Opens an inspector — point/tap to record actions → save as YAML. Great for
testers without coding background.

### `studio` — launch visual flow editor

```bash
maestro studio
```

Browser-based UI to author flows by tapping the live device screen.

### `inspect [--app <bundle-id>]`

```bash
maestro hierarchy --app "${APP_ID:-$CTT_APP_ID}"
```

Dumps the current view hierarchy — find element selectors / IDs.

### `tags` — list all tags used in flows

```bash
grep -h "^tags:" -A 20 "$CTT_FLOWS_DIR"/*.yaml \
  | grep "^- " | sort -u
```

### `flaky-report [--last N]` — detect flaky tests from N recent runs

Maestro doesn't ship a built-in flaky tracker, but JUnit XML output lets us
build one:

```bash
LAST="${LAST:-10}"
ls -t /tmp/maestro-results/*.xml | head -n "$LAST" \
  | xargs python3 -c '
import sys, xml.etree.ElementTree as ET
from collections import defaultdict
results = defaultdict(list)
for f in sys.argv[1:]:
  for tc in ET.parse(f).iter("testcase"):
    failed = tc.find("failure") is not None or tc.find("error") is not None
    results[tc.get("name")].append(failed)
print("Flaky tests (passed AND failed across runs):")
for name, runs in results.items():
  if any(runs) and not all(runs):
    print(f"  {name}: {sum(runs)}/{len(runs)} fail rate")
'
```

### `cloud upload <flow-or-folder> [--name <run-name>]`

Run on Maestro Cloud (parallel devices, CI integration):

```bash
[ -z "$CTT_CLOUD_API_KEY" ] && { echo "Set cloud_api_key in profile" >&2; return 1; }

maestro cloud --apiKey "$CTT_CLOUD_API_KEY" \
  ${NAME:+--name "$NAME"} \
  "$APP" "$FLOW_OR_FOLDER"
```

`<app>` for cloud is the `.app`/`.ipa`/`.apk` build artifact, not bundle ID.

### `from-xlsx <xlsx-path>` — scaffold flows from xlsx test cases

Delegates to `xlsx-testcases gen maestro` — see that skill.

## Flow patterns (cheat sheet)

### Common actions

```yaml
# Navigation
- launchApp
- launchApp:
    arguments:
      deeplink: "myapp://product/123"

# Tapping
- tapOn: "Submit"             # by visible text
- tapOn:
    id: "submit-btn"          # by accessibility id
- tapOn:
    point: "50%, 80%"         # by screen percent

# Input
- tapOn: "Email"
- inputText: "${EMAIL}"
- pressKey: enter

# Assertions
- assertVisible: "Welcome"
- assertNotVisible: "Login"
- assertTrue: ${TOTAL > 0}

# Waiting
- waitForAnimationToEnd
- extendedWaitUntil:
    visible: "Loaded"
    timeout: 30000

# Scrolling
- scrollUntilVisible:
    element: "Footer"
    direction: DOWN

# Subroutines
- runFlow:
    file: ../subflows/login.yaml
```

### Variables / parameters

Pass via env:
```bash
EMAIL=test@example.com PASSWORD=xxx maestro test flow.yaml
```

Inside YAML: `${EMAIL}`, `${PASSWORD}`.

## Safety

- **Never commit credentials** in flow YAML. Use `${ENV_VAR}` and document
  required vars in a comment at top.
- **Maestro Cloud API key** is per-account — limited blast radius. Prefer
  CI-scoped key over personal.
- **Physical device runs**: Maestro can interact with anything on screen
  including OS dialogs, banking apps, etc. Run only on **dedicated test
  devices**, never on personal phones.
- **Permissions**: iOS — pre-grant via simctl: `xcrun simctl privacy <device>
  grant location <bundle-id>`. Don't rely on Maestro to dismiss permission
  dialogs — flaky.
- **Recordings** (`maestro record`) capture screen activity. Don't record
  flows that involve real user data / production accounts.

## Token-saving tip

Group flows by feature folder (`.maestro/login/`, `.maestro/iap/`). Use tags
(`smoke`, `regression`, `iap-only`) to run subsets — faster feedback in dev.

## Recommended layout for RN projects

```
.maestro/
├── config.yaml                  # global config
├── subflows/
│   ├── login.yaml
│   └── grant-perms.yaml
├── smoke/
│   ├── launch.yaml
│   └── home-tabs.yaml
├── regression/
│   └── ...
└── iap/
    └── ...
```

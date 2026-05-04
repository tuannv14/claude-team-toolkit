---
name: react-native
description: Daily React Native development operations - run iOS/Android, install/upgrade pods, link native modules, clean build caches, analyze bundle size, tail device logs, generate icons/splash, and patch native code. Use when the user is working on a React Native project and needs CLI helpers beyond raw npm scripts. No credentials needed - operates on the local project.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /react-native — RN dev ops

Wrapper around common RN day-to-day commands with safer defaults and faster
recovery from common breakage. No credentials — runs locally on the project.

Arguments: `$ARGUMENTS`. Default project: cwd. Override with `--path <dir>`.

## Dependencies

- Node ≥ 18 (RN 0.74+) or 20 (RN 0.77+)
- Yarn (Berry / 4.x is fine) or npm
- Watchman (`brew install watchman` on macOS — major flakiness reduction)
- iOS: Xcode + CocoaPods (`sudo gem install cocoapods` or `brew install cocoapods`)
- Android: Android Studio + JDK 17 (RN 0.73+)

## Dispatch

### `doctor` — environment health check

```bash
npx react-native doctor
```

Reports JDK/SDK/Xcode versions, common misconfigurations.

### `info` — project metadata

```bash
node -e "
const p = require('./package.json');
console.log('Name:', p.name);
console.log('RN:', p.dependencies['react-native']);
console.log('Hermes:', require('./android/app/build.gradle').toString().includes('enableHermes'));
" 2>/dev/null

# iOS pods version
[ -f ios/Podfile.lock ] && grep -m1 "react-native" ios/Podfile.lock
```

### `run-ios [--device "iPhone 15"] [--scheme <name>] [--config Debug|Release]`

```bash
npx react-native run-ios \
  ${DEVICE:+--simulator "$DEVICE"} \
  ${SCHEME:+--scheme "$SCHEME"} \
  ${CONFIG:+--mode "$CONFIG"}
```

Common scheme: same as project name. For RN with multiple schemes (staging/prod):

```bash
npx react-native run-ios --scheme MyApp-Staging --mode Release
```

### `run-android [--device <serial>] [--variant <flavor>Debug>]`

```bash
npx react-native run-android \
  ${DEVICE:+--deviceId "$DEVICE"} \
  ${VARIANT:+--variant "$VARIANT"}
```

`--variant` matches Gradle build variants (e.g., `stagingDebug`, `productionRelease`).

### `pods` — install/update CocoaPods

```bash
cd ios
# RN 0.71+ uses bundle exec for consistent CocoaPods version
[ -f Gemfile ] && bundle install --quiet && bundle exec pod install \
  || pod install
cd -
```

If pods are seriously broken: `pod deintegrate && pod install`.

### `clean [--ios] [--android] [--metro] [--all]`

```bash
if [ "$ALL" = "true" ] || [ "$IOS" = "true" ]; then
  rm -rf ios/Pods ios/build ios/DerivedData
  rm -rf "$HOME/Library/Developer/Xcode/DerivedData"
fi
if [ "$ALL" = "true" ] || [ "$ANDROID" = "true" ]; then
  cd android && ./gradlew clean && cd -
  rm -rf android/app/build android/build android/.gradle
fi
if [ "$ALL" = "true" ] || [ "$METRO" = "true" ]; then
  watchman watch-del-all 2>/dev/null
  rm -rf "$TMPDIR/metro-"* "$TMPDIR/haste-map-"*
  rm -rf node_modules/.cache
fi
```

`--all` is the "nuclear option" — fixes 90% of "why doesn't this build" issues.

### `start [--reset]` — start Metro bundler

```bash
ARGS=()
[ "$RESET" = "true" ] && ARGS+=(--reset-cache)
npx react-native start "${ARGS[@]}"
```

`--reset` after dependency changes or weird module-not-found errors.

### `bundle-android [--variant productionRelease]` — manual JS bundle build

```bash
mkdir -p android/app/src/main/assets
npx react-native bundle \
  --platform android \
  --dev false \
  --entry-file index.js \
  --bundle-output android/app/src/main/assets/index.android.bundle \
  --assets-dest android/app/src/main/res
```

Useful when Hermes / OTA build pipelines need a pre-built JS bundle.

### `bundle-ios` — manual JS bundle for iOS

```bash
npx react-native bundle \
  --platform ios \
  --dev false \
  --entry-file index.js \
  --bundle-output ios/main.jsbundle \
  --assets-dest ios
```

### `bundle-size [--platform ios|android]` — analyze bundle size

```bash
PLATFORM="${PLATFORM:-android}"
case "$PLATFORM" in
  android) BUNDLE=android/app/src/main/assets/index.android.bundle ;;
  ios) BUNDLE=ios/main.jsbundle ;;
esac

[ -f "$BUNDLE" ] || { echo "Build bundle first: /react-native bundle-$PLATFORM" >&2; return 1; }

echo "Total: $(du -h "$BUNDLE" | cut -f1)"
echo ""
echo "Top 20 modules by size (requires source-map):"
npx source-map-explorer "$BUNDLE" --html /tmp/rn-bundle.html 2>/dev/null \
  || echo "Install: npm i -D source-map-explorer"
echo "Open: file:///tmp/rn-bundle.html"
```

### `logs <ios|android> [--filter pattern]` — tail device logs

```bash
case "$PLATFORM" in
  ios)
    xcrun simctl spawn booted log stream \
      --level debug \
      --predicate "subsystem CONTAINS 'com.example.app' OR processImagePath CONTAINS 'MyApp'" \
      ${FILTER:+| grep -i "$FILTER"}
    ;;
  android)
    adb logcat \
      -v color \
      ReactNativeJS:V ReactNative:V "*:E" \
      ${FILTER:+| grep -i "$FILTER"}
    ;;
esac
```

### `link <module>` — link a native module (RN ≥ 0.60 = autolink)

RN 0.60+ uses **autolinking** — usually no manual step. If a module isn't
linking:

```bash
# Force re-evaluation
cd ios && bundle exec pod install && cd -
# Android: usually nothing needed; if broken, check android/settings.gradle
```

For iOS, sometimes need to add to `Podfile`:
```ruby
pod 'YourModule', :path => '../node_modules/your-module'
```

### `patch <package> [--rebuild]` — apply / regenerate patch-package patches

```bash
[ -d patches ] || mkdir patches

# After editing node_modules/<pkg>/...
npx patch-package "$PACKAGE"
echo "Patch saved to patches/"
echo "Commit it. Re-applies on every yarn install via postinstall."
```

Make sure `package.json` has:
```json
"scripts": {
  "postinstall": "patch-package"
}
```

### `icons <source.png>` — generate app icons (uses `react-native-icon-changer`)

```bash
npx react-native-icon-changer "$SOURCE"
```

Or with `app-icon` package for full icon set:
```bash
npx app-icon generate --icon "$SOURCE"
```

### `splash <source.png>` — generate splash screen assets

```bash
npx react-native-bootsplash "$SOURCE" \
  --background-color "#FFFFFF" \
  --logo-width 200 \
  --assets-output assets/bootsplash
```

### `version <new-version> [--skip-android] [--skip-ios]` — bump app version

```bash
# package.json
npm version "$NEW_VERSION" --no-git-tag-version

# iOS
[ -z "$SKIP_IOS" ] && {
  cd ios
  agvtool new-marketing-version "$NEW_VERSION"
  agvtool next-version -all
  cd -
}

# Android
[ -z "$SKIP_ANDROID" ] && {
  CURRENT_CODE=$(grep -oE 'versionCode\s+[0-9]+' android/app/build.gradle | grep -oE '[0-9]+')
  NEW_CODE=$((CURRENT_CODE + 1))
  sed -i.bak -E "s/versionName\s+\".*\"/versionName \"$NEW_VERSION\"/; s/versionCode\s+[0-9]+/versionCode $NEW_CODE/" android/app/build.gradle
  rm android/app/build.gradle.bak
}

echo "Bumped to $NEW_VERSION (Android code: $NEW_CODE)"
```

### `check-deprecated` — find deprecated APIs

```bash
# RN 0.74+ removed many APIs. Check codebase:
grep -rn "AsyncStorage\b" src --include="*.ts" --include="*.tsx" 2>/dev/null \
  | head -20 \
  | sed 's|^|deprecated AsyncStorage: |'
# More patterns:
grep -rn "ImageBackground\.\|StatusBar\.setBackgroundColor\|YellowBox\b\|ProgressBarAndroid\|MaskedViewIOS" src --include="*.ts" --include="*.tsx" 2>/dev/null
```

## Safety

- **Don't run `clean --all` mid-PR** — wipes `Pods`, `node_modules`, Gradle
  cache. Recovery takes 5-15 min on first build after.
- **`patch-package`** files are committed and reapplied on every install.
  Review patches in PRs — they're a security surface (modifying third-party
  code).
- **iOS keychain** issues during build: usually solved by Fastlane match,
  not by deleting keychain.
- **Hermes vs JSC**: Hermes is now default in RN 0.70+ — don't disable
  unless you have a specific reason; bundle size and startup time differ.
- **Android signing**: `android/app/build.gradle` references a keystore.
  If `release` keystore path is in repo, ensure it's `.gitignored` or
  encrypted (e.g., via Fastlane match-style git repo).

## Token-saving tips

- For UI iteration use **Fast Refresh** (built-in) — no full rebuild needed.
- Use `--variant` to skip flavor-specific builds you don't need.
- Bundle analysis (`bundle-size`) only when investigating perf — not every PR.

## Common pitfalls

- "Unable to resolve module ..." after install → `start --reset` + `clean --metro`.
- "Pod install fails" → check Ruby version; RN often needs Ruby 3.0+ now.
- "Duplicate symbols" iOS → check for `use_frameworks!` mismatch in Podfile.
- "Gradle daemon disappeared" → `cd android && ./gradlew --stop && ./gradlew clean`.
- "Metro can't find Watchman" → `brew install watchman` (macOS) — fixes
  countless flakiness issues.

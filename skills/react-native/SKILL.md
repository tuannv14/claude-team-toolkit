---
name: react-native
description: "Use when troubleshooting React Native local dev — stale Metro/Watchman caches, pod install issues, bundle size analysis, device logs, version bumps, icon/splash regen, or patch-package."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /react-native — RN dev ops

Local commands for RN projects. No credentials. Works in cwd or `--path <dir>`.

Deps: Node 18+, Yarn/npm, Watchman, Xcode (iOS), Android Studio + JDK 17 (Android).

## Overview

Local dev ops for React Native projects. No credentials needed — operates on the project tree. Solves the "won't build" mysteries (cache pollution, pod sync, version drift) that consume most of RN dev frustration.

## When to Use

- Build errors after dependency changes ("Module not found", stale Metro/Watchman caches)
- CocoaPods install / Gradle issues
- Bundle size analysis with source-map-explorer
- Tailing device logs (`xcrun simctl` / `adb logcat`) with filter
- Bumping version (package.json + iOS Info.plist + Android `build.gradle` in sync)
- Generating icons / splash from a source PNG

## When NOT to Use

- Code signing / store releases → use `fastlane` skill
- E2E tests → use `maestro` skill
- Backend / API issues → wrong scope
- Anything requiring Apple Developer account credentials

## Dispatch

### `doctor` — environment health check
```bash
npx react-native doctor
```

### `clean [--ios] [--android] [--metro] [--all]` — recovery from "won't build"
```bash
[ "$ALL" = "true" ] || [ "$IOS" = "true" ] && \
  rm -rf ios/Pods ios/build ios/DerivedData "$HOME/Library/Developer/Xcode/DerivedData"
[ "$ALL" = "true" ] || [ "$ANDROID" = "true" ] && \
  (cd android && ./gradlew clean) && rm -rf android/app/build android/build android/.gradle
[ "$ALL" = "true" ] || [ "$METRO" = "true" ] && \
  watchman watch-del-all 2>/dev/null; rm -rf "$TMPDIR/metro-"* "$TMPDIR/haste-map-"* node_modules/.cache
```
`--all` = nuclear option, fixes 90% of build mysteries.

### `pods` — install/update CocoaPods
```bash
cd ios
[ -f Gemfile ] && bundle install --quiet && bundle exec pod install || pod install
cd -
```
If broken: `pod deintegrate && pod install`.

### `bundle-size [--platform ios|android]` — analyze bundle
```bash
PLATFORM="${PLATFORM:-android}"
case "$PLATFORM" in
  android) BUNDLE=android/app/src/main/assets/index.android.bundle ;;
  ios) BUNDLE=ios/main.jsbundle ;;
esac
[ -f "$BUNDLE" ] || { echo "Run: npx react-native bundle --platform $PLATFORM ..." >&2; return 1; }
echo "Total: $(du -h "$BUNDLE" | cut -f1)"
npx source-map-explorer "$BUNDLE" --html /tmp/rn-bundle.html 2>/dev/null && \
  echo "Open: file:///tmp/rn-bundle.html"
```

### `version <new-version>` — bump app version (package.json + iOS + Android)
```bash
npm version "$NEW_VERSION" --no-git-tag-version

# iOS
(cd ios && agvtool new-marketing-version "$NEW_VERSION" && agvtool next-version -all) 2>/dev/null

# Android (auto-increment versionCode)
CURRENT_CODE=$(grep -oE 'versionCode\s+[0-9]+' android/app/build.gradle | grep -oE '[0-9]+')
NEW_CODE=$((CURRENT_CODE + 1))
sed -i.bak -E "s/versionName\s+\".*\"/versionName \"$NEW_VERSION\"/; s/versionCode\s+[0-9]+/versionCode $NEW_CODE/" android/app/build.gradle
rm android/app/build.gradle.bak

echo "Bumped to $NEW_VERSION (Android code: $NEW_CODE)"
```

### `logs <ios|android> [--filter pattern]` — tail device logs
```bash
case "$PLATFORM" in
  ios)
    xcrun simctl spawn booted log stream --level debug \
      --predicate "subsystem CONTAINS '$BUNDLE_ID'" \
      ${FILTER:+| grep -i "$FILTER"}
    ;;
  android)
    adb logcat -v color ReactNativeJS:V ReactNative:V "*:E" \
      ${FILTER:+| grep -i "$FILTER"}
    ;;
esac
```

### `patch <package>` — save patch-package patch
```bash
npx patch-package "$PACKAGE"
echo "Add to package.json scripts: \"postinstall\": \"patch-package\""
```

### `icons <source.png>` / `splash <source.png>` — asset generators
```bash
npx app-icon generate --icon "$SOURCE"
npx react-native-bootsplash "$SOURCE" --background-color "#FFFFFF" --logo-width 200
```

### Other RN commands (use Bash directly)

These are simple enough to run as native commands:
- Run iOS: `npx react-native run-ios [--simulator "iPhone 15"] [--scheme MyApp-Staging]`
- Run Android: `npx react-native run-android [--variant stagingDebug]`
- Start Metro: `npx react-native start [--reset-cache]`
- Bundle: `npx react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res`

## Common Mistakes

- "Module not found" after install → `start --reset-cache` + `clean --metro`
- Gradle daemon stuck → `cd android && ./gradlew --stop && ./gradlew clean`
- iOS keychain issues → use Fastlane match (don't manually delete certs)
- Pod install fails → check Ruby version (RN often needs 3.0+)
- `clean --all` before checking what specifically broke → 5-15 min wasted on every run

## Safety

- `clean --all` wipes Pods + Gradle cache + node_modules/.cache → 5-15 min recovery on first build
- `patch-package` patches modify third-party code — review patches in PRs (security surface)
- iOS keychain → use Fastlane match, not manual deletion
- Android signing keystore lost = can't update app on Play Store; back up encrypted

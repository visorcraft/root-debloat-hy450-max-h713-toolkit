#!/usr/bin/env bash
# Build the Settings launcher APK with only the Android SDK (no gradle).
# Signs with ~/.android/debug.keystore, same as tools/settings-shim.
set -euo pipefail
cd "$(dirname "$0")"

SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
PLATFORM="$SDK/platforms/android-34/android.jar"
BT="$SDK/build-tools/35.0.0"
OUT="$PWD/build"
rm -rf "$OUT"
mkdir -p "$OUT/classes"

"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -o "$OUT/unsigned.apk" \
  -I "$PLATFORM" \
  --manifest AndroidManifest.xml \
  --min-sdk-version 21 \
  --target-sdk-version 34 \
  "$OUT/res.zip"

javac -source 8 -target 8 -cp "$PLATFORM" -d "$OUT/classes" \
  src/com/visorcraft/settingslauncher/MainActivity.java

"$BT/d8" --min-api 21 --lib "$PLATFORM" --output "$OUT" \
  "$OUT/classes"/com/visorcraft/settingslauncher/*.class

mkdir -p "$OUT/dex"
cp "$OUT/classes.dex" "$OUT/dex/classes.dex"
(cd "$OUT/dex" && zip -0 "$OUT/unsigned.apk" classes.dex >/dev/null)

"$BT/apksigner" sign --ks "$HOME/.android/debug.keystore" \
  --ks-pass pass:android --out settings-launcher.apk "$OUT/unsigned.apk"

echo "built: settings-launcher.apk"

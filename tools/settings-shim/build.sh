#!/usr/bin/env bash
# Build the settings shim APK with only the Android SDK (no gradle).
set -euo pipefail
cd "$(dirname "$0")"

SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
PLATFORM="$SDK/platforms/android-33/android.jar"
BT="$SDK/build-tools/35.0.0"
OUT="$PWD/build"
rm -rf "$OUT"
mkdir -p "$OUT/classes"

javac -source 8 -target 8 -cp "$PLATFORM" -d "$OUT/classes" \
  src/com/visorcraft/settingsshim/MainActivity.java

"$BT/d8" --min-api 26 --output "$OUT" "$OUT/classes"/com/visorcraft/settingsshim/*.class

"$BT/aapt2" link -o "$OUT/shim-unsigned.apk" \
  -I "$PLATFORM" \
  --manifest AndroidManifest.xml \
  --min-sdk-version 26 --target-sdk-version 33

# aapt2 link output is a zip; add classes.dex under its proper name
mkdir -p "$OUT/dex"
cp "$OUT/classes.dex" "$OUT/dex/classes.dex"
(cd "$OUT/dex" && zip -0 "$OUT/shim-unsigned.apk" classes.dex >/dev/null)

"$BT/apksigner" sign --ks "$HOME/.android/debug.keystore" \
  --ks-pass pass:android --out settings-shim.apk "$OUT/shim-unsigned.apk"

echo "built: settings-shim.apk"

# RUNBOOK: Root + Magisk on a fresh HY450 Max

Verified end-to-end on a retail unit (firmware `Projector_20260821.111618`).
Assumes: Linux laptop with adb + python3 + pyusb, this repo's `tools/`, and a
USB-A male-to-male cable (insurance only - not needed for the happy path).

Time: ~15 minutes per unit. Near-zero brick risk if the order is followed
(backups BEFORE any flash; readback hash BEFORE reboot; FEL recovery lane if
something still goes wrong).

## Prerequisites

```bash
# official Magisk APK (do not use mirrors):
wget https://github.com/topjohnwu/Magisk/releases/download/v31.1/Magisk-v31.1.apk -O tools/Magisk-v31.1.apk
```

## 0. Connect + firmware note

```bash
adb connect <projector-ip>:5555        # adb over TCP is open out of the box
adb -s <projector-ip>:5555 shell getprop ro.build.version.incremental
adb -s <projector-ip>:5555 shell getprop ro.boot.slot_suffix   # we saw _b
```

This procedure patches the unit's OWN init_boot image, so it tolerates other
firmware builds - but if the build differs, re-read NOTES.md and be extra
careful; the partition layout could theoretically differ.

## 1. Root shell via the OEM qw daemon

```bash
adb -s <ip>:5555 push tools/qwc4 /data/local/tmp/qwc4
adb -s <ip>:5555 shell 'chmod 755 /data/local/tmp/qwc4; /data/local/tmp/qwc4 -c "id"'
# expect: uid=0(root) ...
```

(qwc4 source is `tools/qwc4.c`; a prebuilt armv7 binary is in `tools/`.
To rebuild: NDK `armv7a-linux-androideabi34-clang -O2 -o qwc4 qwc4.c`.)

## 2. Backups BEFORE touching anything

```bash
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "
mkdir -p /sdcard/backup
for p in boot_a boot_b init_boot_a init_boot_b dtbo_a dtbo_b vbmeta_a vbmeta_b vbmeta_system_a vbmeta_system_b vbmeta_vendor_a vbmeta_vendor_b env_a env_b misc bootloader_a bootloader_b treadahead; do
  dd if=/dev/block/by-name/\$p of=/sdcard/backup/\$p.img; done"'
mkdir -p backup && adb -s <ip>:5555 pull /sdcard/backup backup/
```

Keep `backup/` - it is this unit's only factory-state lifeline, and
`tools/fel_mmc.py restore` reads from it (override path with `HY450_BACKUP`).

## 3. Patch init_boot on-device

```bash
adb -s <ip>:5555 push tools/Magisk-v31.1.apk /data/local/tmp/
adb -s <ip>:5555 push tools/mgk_setup.sh tools/mgk_patch.sh tools/mgk_verify.sh /data/local/tmp/
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "sh /data/local/tmp/mgk_setup.sh"'   # stage armv7 libs from the APK
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "sh /data/local/tmp/mgk_patch.sh"'   # writes /data/local/tmp/mgk/new-boot.img
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "sh /data/local/tmp/mgk_verify.sh"'  # structural proof of the patch
```

`mgk_verify.sh` must show: new `init` == staged `magiskinit`; stock init
preserved as `.backup/init`; no kernel in either image (init_boot is
ramdisk-only on this platform - the kernel stays untouched in `boot_b`).

Which partition to flash: the image patches `init_boot_<activeslot>` (step 0).
Everything below assumes `_b`; substitute if yours differs.

## 4. Flash + verify + reboot

```bash
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "
cp /data/local/tmp/mgk/new-boot.img /data/local/tmp/ibp.img
sha256sum /data/local/tmp/ibp.img
dd if=/data/local/tmp/ibp.img of=/dev/block/by-name/init_boot_b bs=4096; sync
sha256sum /dev/block/by-name/init_boot_b"'
# the two hashes MUST match. Only then:
adb -s <ip>:5555 shell 'reboot'
```

If it hangs at the boot logo after this (should not - hash was verified):
FEL recovery with `tools/fel_mmc.py` (see docs/MANAGEMENT.md "Recovery
lane"): re-enter FEL (pinhole + power), restore `backup/init_boot_b.img`
(extend `ALLOWED_WRITE` to LBA 615424..631807 first - only on a unit whose
GPT you have re-verified against `backup/bootarea32.img`... dump order and
offsets are in NOTES.md).

## 5. Magisk app finalize + shell su

```bash
adb -s <ip>:5555 install tools/Magisk-v31.1.apk
adb -s <ip>:5555 shell 'am start -n com.topjohnwu.magisk/.ui.MainActivity'
# on screen: OK to "additional setup" -> it reboots (or reboot it yourself)
adb -s <ip>:5555 push tools/fixpolicy.sh /data/local/tmp/
adb -s <ip>:5555 shell '/data/local/tmp/qwc4 -c "sh /data/local/tmp/fixpolicy.sh"'
adb -s <ip>:5555 shell 'su -c id'   # expect uid=0(root) context=u:r:magisk:s0
```

`fixpolicy.sh` pre-authorizes the adb shell in Magisk's DB. Two quirks that
cost us an hour: the `policies` table has NO `package_name` column, and
policy `2` = Allow (`1` = Deny). Apps still prompt on screen as usual.

## 6. Debloat (reversible)

```bash
adb -s <ip>:5555 push tools/debloat1.sh /data/local/tmp/
adb -s <ip>:5555 shell 'su -c "sh /data/local/tmp/debloat1.sh"'
```

12 OEM bloat/telemetry packages are `disable-user`ed (both OTA updaters,
factory test, memory cleaner, OEM store, OfficeSuite, HTC Music, cast
stack). Re-enable any with `pm enable <pkg>`. Smoke-test launcher / HDMI
input / keystone / remote / playback, then reboot and confirm
`pm list packages -d` still shows them.

## 7. If you sideload apps that need accessibility / notification access

Android 13 blocks this for sideloaded apps ("Restricted settings") and on TV
the block is silent: the Settings toggle flips straight back off. Fix per app:

```bash
adb -s <ip>:5555 shell 'appops set <package> ACCESS_RESTRICTED_SETTINGS allow'
```

or lift it for all user-installed apps with `tools/lift-restricted.sh`
(edit its list first). Then the Settings toggle works normally.

## Never-do list (bricking causes, proven the hard way)

1. Never raw-write env_a/env_b without a valid env CRC32 (format: CRC32 +
   flag byte + text). Bad CRC on BOTH copies = hang at the boot logo.
2. Never "power-cycle" with the FEL cable in - laptop VBUS backfeed keeps
   the SoC alive and it will sit in FEL forever. Cable out + 15s.
3. Never flash before backups exist on both device and laptop.
4. Never skip the post-flash readback hash.
5. Never accept an OEM OTA afterward (undoes the patch; both updaters are
   disabled by debloat1.sh).
6. Never abort a FEL USB transaction mid-flight; if wedged, fel_mmc.py's
   resync() heals it - worst case re-enter FEL (pinhole + power).

## 8. Optional: fix the OEM accessibility wipe (Magisk framework patch)

Symptom without it: accessibility services (e.g. Projectivy Launcher) die the
moment focus moves to any app that isn't Netflix/YouTube - this ROM's
`DisplayContent` focus hook writes `accessibility_enabled=0` and wipes
`enabled_accessibility_services` on every such focus change, and
`AccessibilityManagerService.isAccessibilityTargetAllowed` hard-denies
third-party services behind a fake "device admin policy".

Fix = patch services.jar (Magisk module overlay, no partition writes):
1. `adb pull /system/framework/services.jar`, unzip classes.dex + classes3.dex,
   disassemble with baksmali.
2. classes3.dex `com/android/server/wm/DisplayContent.smali`: in
   `enableNfxAccessibility(Z)V` and `enableYtbAccessibility(Z)V`, insert
   `return-void` at the top of the false branch (`:cond_27`). The Netflix/YT
   enable path stays intact.
3. classes.dex `com/android/server/accessibility/AccessibilityManagerService.smali`:
   replace `isAccessibilityTargetAllowed(Ljava/lang/String;II)Z` body with
   `const/4 v0, 0x1; return v0` (`.registers 4`).
4. Reassemble, update the jar with `zip -0 -X` (dex entries MUST stay stored),
   drop it into a Magisk module at `system/framework/services.jar`, reboot.
   First boot is slower (dex2oat recompiles; cached after).
Full rationale + verification steps: docs/NOTES.md (2026-10-28 entry).

## 9. Optional: "android.settings.SETTINGS is not installed"

This ROM's TvSettings never registers the generic `android.settings.SETTINGS`
action, so apps like Projectivy error out when opening "Android settings".
Fix: build + install `tools/settings-shim` (`bash build.sh`, needs only the
Android SDK - javac/d8/aapt2/apksigner). It registers the action and forwards
to the TV settings root. One install, permanent.

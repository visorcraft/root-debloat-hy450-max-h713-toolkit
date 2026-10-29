# HY450 Max - Management Guide

Rooted, debloated, and recoverable. Everything you need to operate this device
long-term lives here. Machine-readable details and the full incident log are in
`NOTES.md`; this is the operator's doc.

## What this device actually is

- "HY450 Max" projector (Magcubic/Hotack family), Allwinner **H713** SoC
  (sun50iw15p1), kernel 5.15.167, 32-bit ARM userspace, **Android 14 (SDK 34)**
  - the rockchip/rk3566 Android 13 build fingerprint is an OEM spoof, ignore it.
- Firmware `Projector_20260821.111618`. Real A/B slots (active `_b`),
  bootloader unlocked, SELinux Permissive (set via U-Boot env).
- Serial <your-unit-serial>. IP `192.168.1.x` (adb on port 5555).

## Root access (two independent ways)

1. **Magisk 31.1 (persistent, app-level)** - patched `init_boot_b` flashed;
   magiskd starts at boot. `adb shell su -c id` works (shell uid 2000 is
   pre-allowed in `/data/adb/magisk.db`; policy value 2 = Allow - **1 means
   Deny**, careful if hand-editing). Magisk app installed.
2. **qw daemon (OEM backdoor, always present)** - `/data/local/tmp/qwc4`
   client (source+binary in `tools/`) talks to the OEM superuser daemon:
   ```bash
   adb connect 192.168.1.x:5555
   adb -s 192.168.1.x:5555 shell '/data/local/tmp/qwc4 -c "id"'
   ```

## Recovery lane (BRICK INSURANCE): FEL eMMC editing

If the device ever hangs at the MAGCUBIC logo again, the boot ROM's FEL mode
lets the laptop read/write the **entire eMMC** over the male-to-male USB-A
cable. No device-side code needed. Driver: `tools/fel_mmc.py` (pyusb).

1. Cable laptop↔projector. Hold the **pinhole reset** (near HDMI), apply wall
   power, hold ~5s. Screen stays black; `lsusb` shows `1f3a:efe8`.
2. `sudo chmod 666 /dev/bus/usb/<bus>/<dev>` (new number each time).
3. Use it:
   ```bash
   python3 tools/fel_mmc.py probe                      # register dump
   python3 tools/fel_mmc.py read <lba> <nblk> out.img  # read any region
   python3 tools/fel_mmc.py restore                    # writes STOCK env_a/env_b + sha256 verify
   ```
   `restore` is bounds-checked to the env partitions only. To write anything
   else, extend `ALLOWED_WRITE` deliberately.
4. **CRITICAL - USB backfeed trap:** with the cable attached, the SoC never
   fully loses power (laptop VBUS keeps it alive), so "power-cycling" with
   the cable in does NOT reset it - it will sit in FEL forever. To truly
   reboot: **cable out**, wall power out 15s, then power in.

### Key device facts for FEL work (all proven)

- env_a = LBA 204800, env_b = LBA 205312, 512 sectors each. GPT in
  `backup/bootarea32.img`. Stock env hashes: env_a `2bbfc0d6…`, env_b
  `90941dfc…`, init_boot_b stock `748114f0…`, Magisk-patched `53d96bc2…`.
- SMHC2 (eMMC) @ `0x04022000`; needs GCTRL bit31 (AHB access) for PIO FIFO.
- PIO @ `0x02000000`, port stride 0x30; PC0–PC11 mux value **2** = sdc2.
- CCU SMHC2_CLK @ `0x02001838`, SMHC_BGR @ `0x0200184C` (bit2 gate, bit18 reset).
- FEL wire quirks: ≤8-byte reads come back as 16-byte packets (read 64,
  truncate); BROM FEL is stateful - an aborted USB transaction wedges the
  next session (the script's `resync()` auto-heals).
- U-Boot env MUST keep a valid CRC - editing env bytes without fixing CRC
  boots into the compiled-in stub env (`bootcmd=run distro_bootcmd`,
  undefined) → hang at logo. That was the 2026-10-28 brick; FEL restored it.

## Debloat state

`tools/debloat1.sh` `disable-user`s 12 OEM packages (both OTA updaters,
factory test, memory cleaner, OEM store, OfficeSuite, HTC Music, cast stack).
On the development unit, 3 cast packages (`com.toofifi.lineserver`,
`com.mphotool.dlna`, `com.mphotool.usbcastserver`) were later re-enabled to
stop idle watchdog log spam, and `com.htc.btremote.receiver` (luminago
phone-remote telemetry) was additionally disabled - final disabled set: **10
packages**, listed in `packages-disabled.txt`. All survive reboot; APKs stay
on flash. Re-enable any with: `adb shell su -c "pm enable <pkg>"`.
Google services kept per user choice. With the OTA updaters off, no official
updates arrive - that's intentional (an OTA would undo the Magisk patch).

## Backups

`backup/` holds full partition dumps of both slots (boot, init_boot, dtbo,
vendor_boot, vbmeta*, env, bootloader splash, misc, treadahead) plus the
verified Magisk-patched init_boot. Also mirrored on-device at
`/sdcard/backup/`. The eMMC boot0 SPL region is not exposed as a block
node; `backup/boot0.bin` came from the FEL-era dump work.

## If you ever want to undo everything

1. `adb shell su -c "pm enable <pkg>"` for each package in
   `packages-disabled.txt` (or factory reset re-enables all).
2. Flash stock init_boot back:
   `adb push backup/init_boot_b.img /data/local/tmp/` then as root
   `dd if=/data/local/tmp/init_boot_b.img of=/dev/block/by-name/init_boot_b bs=4096; sync; reboot`
3. Uninstall Magisk APK. qw root remains (it's OEM-built-in).

## Later additions (2026-10-28, post-recovery)

- **Magisk module `a11ywipefix`** (in /data/adb/modules/): overlays a patched
  /system/framework/services.jar that (a) neutralizes the OEM focus-change
  hook that wiped accessibility services for non-Netflix/YouTube apps, and
  (b) removes the fake device-admin gate on accessibility. Without it,
  Projectivy Launcher's accessibility service dies on every app switch.
  Remove the module dir + reboot to revert. Patched jar archived at
  backup/services-patched-a11yfix.jar; recipe in NOTES.md.
- **`tools/lift-restricted.sh`**: run after sideloading apps that need
  accessibility/notification access (Android 13 restricted-settings block).
  Note this ROM re-derives the block at boot - the durable path for
  accessibility is the a11ywipefix module above.
- **`com.visorcraft.settingsshim`** installed: handles the generic
  android.settings.SETTINGS intent the OEM TvSettings never registered
  (Projectivy "Android settings" entry point). Source: tools/settings-shim/.
- Projectivy a11y: enabled + bound; enabled_accessibility_services must use
  the fully-qualified component form or the app misreports "Enabled: No".

## OTA updates (deliberately disabled)

Both updaters are off (`com.hy.hyotaupdate`, `com.softwinner.update`), so no
official updates can arrive. Two hazards if one were applied: (1) the A/B slot
switch boots an unpatched init_boot = Magisk gone; (2) WORSE - the a11ywipefix
module would overlay the OLD patched services.jar onto the NEW framework =
version skew, likely bootloop. Recovering from that state means a factory
reset or FEL block surgery on /data/adb/modules/a11ywipefix - avoid it
entirely.

Safe update procedure if ever needed: pm enable both updaters → take OTA →
re-dump partitions → re-patch init_boot (runbook step 3-4) → rebuild the
a11yfix jar FROM THE NEW services.jar (NOTES.md recipe) → replace module file.

## AFWall+ firewall policy (2026-10-28)

Mode: **blacklist** (everything allowed unless explicitly blocked). Config lives
in AFWall's shared_prefs, applied by its own engine; verified persistent across
reboot (BootReceiver re-applies on every boot).

Blocked UIDs (AFWall rejects all WAN traffic - wifi, mobile, roaming, VPN):

| UID | Package | Why |
|---|---|---|
| 10001 | com.google.android.apps.searchlite.overlay | Stock launcher search overlay, unused under Projectivy |
| 10040 | com.google.android.katniss | Stock "Google" TV search/voice app, unused under Projectivy |
| 10057 | com.google.android.backdrop | Chromecast ambient/backdrop, unused |
| 10088 | cm.aptoidetv.pt | Preinstalled Aptoide TV store, telemetry-heavy, superseded by Aurora Store |

Separately, `com.htc.btremote.receiver` (luminago phone-remote beacon to
Cloudflare:443) is **pm disable-user**ed instead of firewalled: it runs under
shared system uid 1000 along with ~26 core packages, so a UID firewall rule
would have knocked out Android system networking entirely. Re-enable with
`pm enable com.htc.btremote.receiver` (physical BT remote is unaffected -
that's `com.htc.htcbluetoothremotecontrol`, still enabled).

Undo AFWall policy: open AFWall+ and uncheck apps / toggle firewall off, or
delete the `AllowedPKG*_UIDS` strings from
/data/data/dev.ukanth.ufirewall/shared_prefs/AFWallPrefs.xml and broadcast
BOOT_COMPLETED to dev.ukanth.ufirewall/.broadcast.OnBootReceiver as root.

Verified: ping as blocked UIDs fails, ping as Sinema (10094) / Syncler (10090)
UIDs succeeds; general internet + LAN unaffected. Sinema was never launched
during configuration.

## Apps installed (2026-10-28, anonymous Play-signed APKs)

| App | Package | Version | Status |
|---|---|---|---|
| Aurora Store | com.aurora.store | 4.8.4 (F-Droid build) | installed; use anonymous login on first open |
| YouTube (Android TV) | com.google.android.youtube.tv | 7.28.300 | launches to main UI |
| Netflix (Android TV) | com.netflix.ninja | 10.3.1 | launches; playback subject to DRM (below) |
| Disney+ | com.disney.disneyplus | 26.19.0 | launches |
| Hulu | com.hulu.plus | latest single-APK | launches to welcome screen |
| Chrome | com.android.chrome | 155.0.8059.84 | launches to first-run |

Notes:
- Sources pulled anonymously; Google apps + Netflix + Disney+ carry Google's
  Play source stamp (cert 3257d599… = provably authentic Play bytes);
  signatures verified with apksigner before install. Hulu is a single APK
  signed directly by Hulu.
- Device userspace is 32-bit (armeabi-v7a). Netflix *mobile*
  (com.netflix.mediaclient) is arm64-only now - that's why the Android TV
  build (com.netflix.ninja) was installed instead.
- Chrome required its `on_demand` split; install-multiple with base+chrome+
  config.en+on_demand.
- DRM reality check: `ro.boot.drmkey=false` suggests weak Widevine
  provisioning and the device is not Play-certified, so Netflix/Disney+/Hulu
  may refuse playback or cap at low resolution. They launch fine; check actual
  playback by eye and report.
- GMS (vending 34.1.09, gms 22.36.16) shipped on-device and stays enabled -
  app logins depend on it. Play Store is present but unused; no Google account
  was signed in.

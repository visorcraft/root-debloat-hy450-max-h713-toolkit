# HY450 Max Projector - Root & Management Notes

Device: Hotack/Magcubic-family **HY450 Max** (Amazon ASIN B0G64GMYH9)
SoC: Allwinner H713 (`sun50iw15p1`, platform `hermes`), quad Cortex-A53, 32-bit userspace (armeabi-v7a)
Serial: `<your-unit-serial>` · Firmware: `Projector_20260821.111618` (VERIFIED Android 14, SDK 34; the rockchip/rk3566 :13 fingerprint is an OEM forgery for app compat) · SPL 2024-06-05
Kernel: 5.15.167 armv7l · A/B slots (active: `_b`) · **SELinux Permissive** (`selinux=0` in U-Boot env) · bootloader reports unlocked/orange

## Root access (persistent, no exploit, no flashing)

OEM ships a hidden superuser daemon: `service qw /system/bin/qw --daemon` (`/system/etc/init/qw.rc`,
root, class core → starts every boot). Policy patched to auto-allow uid 2000 (adb shell): string
`Allowing shell.` in the binary. Socket: `/dev/com.koushikdutta.superuser.daemon/server`.

The OEM's own client is gated; our client is `tools/qwc4` (source `tools/qwc4.c`, NDK armv7, API34).
It is installed on-device at `/data/local/tmp/qwc4` (survives reboots).

Protocol (reverse-engineered from qw daemon_accept @ 0x1fe70; NOT stock koush):
connect fs socket → 6 ints: pid, tty_flag(0), uid, ppid, mount_storage(0), argc → argv strings
("su" + args) → daemon mkfifos `/dev/com.koushikdutta.superuser.daemon/<pid>.{stdin,stdout,stderr}`
(0660, chown to caller uid) → ack int(1) → client opens 3 fifos O_RDWR → client sends ready int →
daemon forks, child dup2s fifos, runs su_main → root. I/O via fifos; exit code returns on socket.

Usage:
```
adb connect 192.168.1.x:5555
adb -s 192.168.1.x:5555 shell '/data/local/tmp/qwc4 -c "id"'
adb -s 192.168.1.x:5555 shell '/data/local/tmp/qwc4 -c "pm list packages"'
```
(If adb refuses after a projector reboot, rediscover port: `avahi-browse -rt _adb-tls-connect._tcp`)

Rebuilt client: `armv7a-linux-androideabi34-clang -O2 -o qwc4 qwc4.c` (NDK 29).

## Other findings

- `hotacksu` (/system/xbin, setuid root:shell 6755) is broken-by-design: kernel ignores its setuid
  (setgid EPERM); toybox-style su clone. Decorative.
- `wletd`/`wletc`: root factory RF-test daemon (BT/WiFi test modes via `/vendor/lib/libwlet-xr.so`). Not a shell.
- `dbgserver` (`/vendor/bin/dbgserver`, root, TCP :65528): started via `setprop persist.vendor.dbgserver 1`
  (works as shell because SELinux permissive → property_service allows). Binary protocol; **left OFF**
  (`setprop persist.vendor.dbgserver 0` already done).
- OTA: server `https://ota.hanychx.com/api/ota/check` (HanYing Innovation). Leftover incremental OTA on
  device `/sdcard/update.zip` (0425→0821, applied already; copy in `reference/ota/`).
- Local update app `com.softwinner.update`: exported `AbUpdate` activity accepts `update_path` extra and
  calls `UpdateEngine.applyPayload` with NO app-level signature check - but `update_engine` itself
  enforces OEM payload signatures (otacerts.zip) → crafted-OTA path is dead. Online updater
  `com.hy.hyotaupdate` has exported DownloadService taking arbitrary `newUrl` extra (downloader only).
- U-Boot env: `ab_partition_list=bootloader,env,boot,vendor_boot,dtbo,vbmeta,vbmeta_system,vbmeta_vendor,init_boot,Reserve0`;
  `slot_suffix=_a` stored in both env copies (stale); `force_normal_boot=1`; no try-counters found →
  assume NO automatic A/B fallback. `bootloader_a/b` partitions are FAT16 with splash BMPs only.
- Community context: Hotack shipped signed malware on HY300 siblings (`com.hotack.silentsdk`,
  `com.hotack.writesn`) - NOT present in this build's package list; verify again at debloat time.
  Refs: probonopd HY300 gist, gniax/magcubic-hy300-root, XDA H713 thread (all target Android 11 builds -
  do NOT flash their images here).

## Backups (`backup/`, also on-device `/sdcard/backup/`)

Both slots: boot, init_boot, dtbo, vendor_boot, vbmeta(+_system/_vendor), env, bootloader(FAT16 splash),
misc, treadahead. sha256 (init_boot_b stock): `748114f01e2a9666c3137b5153f222fb3b36e22498ca71f4ddf581d459d9b5c6`
eMMC boot0/boot1 (SPL) not exposed as block nodes - not dumped.

## Magisk v31.1 patch (verified, not yet flashed)

Patched on-device with the APK's own `boot_patch.sh` (armv7 libs staged from APK).
Image: `backup/magisk-patched-init_boot_b.img` (sha256 `53d96bc2267ebf403d34717885a59d0d83d3a5bf209a29bb5e944d2056d5b747`).
Verification: new `init` == magiskinit (sha256 match); stock init preserved as `.backup/init.xz`;
adds `.backup/.magisk`, `.rmlist`, `overlay.d/sbin/{magisk.xz,init-ld.xz}`; fstab untouched
(KEEPVERITY=true); init_boot has no kernel (header v4, KERNEL_SZ=0) → kernel/dtb never touched.

## Plan status (user-approved)

- [x] Recon + root via qw
- [x] Backups
- [x] Reboot persistence rehearsal (adb+qw return in ~30s; port 5555)
- [x] Magisk patch + verification
- [ ] Recovery-stick no-op test (user plugs FAT32 stick; we write update/init_boot_b.img stock +
      auto_update.txt via adb; cold power-cycle; expect green auto-update bar; proves boot0 sprite update)
- [ ] Flash patched init_boot_b via dd + readback sha256 + reboot
- [ ] Magisk app install/finalize + app-level su test
- [ ] Debloat batches (pm as root; verify keystone/HDMI/remote after each)
- [ ] This file becomes MANAGEMENT.md handoff

## INCIDENT 2026-10-28: env probe edit → boot hang at MAGCUBIC logo

Cause: edited env_a/env_b in place (loglevel 3→7) via root dd without fixing the env CRC.
U-Boot rejects both copies ("bad CRC... using default environment") and falls back to its
compiled-in default env: `bootcmd=run distro_bootcmd` with distro_bootcmd undefined → hang
at bootlogo. Upside-down MAGCUBIC image is NORMAL bootloader-stage orientation (not a symptom).
Stick-out repro confirmed hang is env-only, unrelated to stick contents.

### Recovery channels (ranked)

1. **Boot-time stick auto-update (PRIMARY, in progress)** - U-Boot contains
   `auto_update_check`/`sunxi_auto_update_gpadc_key_check`; format:
   `sunxi_flash write <file path> <load partition>`, one per line in `update/auto_update.txt`,
   and requires `update/update.img` present on stick. Payload staged in `recovery-stick/update/`
   and written to the FAT32 stick from laptop (stick UUID 8616-12F2, label RECOVERY):
   - `sunxi_flash write update/env_a.img env_a`   (env_a.img = stock sha 2bbfc0d6...)
   - `sunxi_flash write update/env_b.img env_b`   (env_b.img = stock sha 90941dfc...)
   - `sunxi_flash write update/init_boot_b.img init_boot` (stock, canary/no-op content)
   - `update.img` = stock init_boot_b.img (gate file only)
   Open risk: whether explicit slotted names (env_a/env_b) resolve in sunxi_flash, and whether
   the check runs unconditional (`select_mode=1`) even with broken env.
2. **FEL mode (PROVEN to BROM level)** - reset pinhole (near HDMI) + USB-A male-to-male →
   `1f3a:efe8`. Fork `/tmp/sunxi-fork` (Fiooodooor + local patches: soc 0x1911 spl_addr 0x104000,
   scratch 0x127a00, thunk 0x123a00; SCTLR check relaxed; MMU path disabled). Raw ver/sid/read/
   write/exe WORK (0xdeadbeef sentinel verified). `sunxi-fel spl boot0_spl.bin` FAILS: vendor
   boot0 SPL is one-way (never returns to FEL thunk; usb_bulk_send timeout kills link).
   Fallback deep plan: patch vendor SPL final jump → bx lr, then FEL-patch DRAM-resident U-Boot
   default env. No cross-compiler on PC for mainline U-Boot.
3. **UART lane (if user has 3.3V USB-TTL)** - open case (3 screws), T/R/G pads → U-Boot console
   → fatload/env write directly. Adapter availability: UNANSWERED.

### Watch-items

- Stick "mystery reformat" happened once before (serial EBF6-5DCC → 8616-12F2, files vanished);
  old Phase-2 `update/` payload (treadahead write) was found on stick afterward. Watch recurrence.
- After recovery: verify env sha256 vs stock dumps BEFORE any new writes; re-do Phase 2 properly
  (no-op treadahead write test, self-verifying, recorded treadahead head sha d69b3985f08b...).

### Lane 2 build-out: FEL host-driven eMMC (2026-10-28)

Stick auto-update FAILED (booted with stick, still hung) → U-Boot C-flow never ran the
payload (stock env bootcmd = `run setargs_nand boot_normal`, no auto_update ref; trigger
is C-side but gated - likely select_mode semantics or key-gated; not investigated further
because a better lane exists).

Key facts established:
- Default env block in U-Boot = only `bootcmd=run distro_bootcmd / bootdelay=2 /
  baudrate=115200` at file offset 0xc6deb4 in bootarea32.img (DRAM addr 0x4a06d074,
  ~60 bytes of slack). U-Boot link base 0x4a000000 CONFIRMED via vector table at image
  start (0xEA0000AE branch + ldr pc vectors pointing to 0x4a0006a0...).
- GPT: env_a LBA 204800 (0x6400000), env_b LBA 205312 (0x6440000), 512 sectors each.
- eMMC = SMHC2 @ 0x04022000 (8-bit, sunxi-mmc-v4p6x). CCU window 0x02001000+0x2000
  (SMHC2_CLK @ +0x838, SMHC_BGR @ +0x84C bit2 gate / bit18 reset). Pins PC0-PC11
  (mux value unverified; runtime-probed). PIO port C CFG @ 0x0300B048/0x4C.
- FEL protocol reimplemented in python (pyusb): AWUC/AWUS framing, req 0x001/0x101/
  0x102/0x103. Script: tools/fel_mmc.py (probe/init/read/readtest/restore).
  Read-validate-first design: readtest byte-compares env_a/env_b block0 vs backups
  before any write; restore writes then sha256-verifies readback.
- sunxi-fel spl failure root cause (hypothesis): vendor SPL image spans
  0x104000-0x112000 which covers FEL's IRQ stack (sp_irq=0x105400) → upload kills
  the handler mid-transfer (usb_bulk_send -7). Swap-buffer table in the fork only
  covers 0x121000. If the MMIO lane fails, fix = CPSID-i stub first, chunked upload,
  or widen swap buffers.

Pending: user re-enters FEL (pinhole + power), then: ver → probe → init → readtest
→ restore → power-cycle.

### FEL lane WORKING DETAILS (2026-10-28, proven on device)

Wire protocol (pyusb, tools/fel_mmc.py):
- AWUC 32-byte request header (sig "AWUC"+pad4, len, 0x0c000000, u16 type
  (0x11=read/0x12=write), len again, pad10). FEL request = 16 bytes
  (u32 req 0x001 ver/0x101 write/0x102 exec/0x103 read, addr, len, pad).
- H713 BROM quirk: small data reads (<=8B) come back as a 16-byte padded
  packet; always read with 64B buffer and truncate. Read AWUS as 64B too.
- BROM FEL is STATEFUL: an aborted transaction wedges the next session
  (no AWUS answer). resync(): try ver; on fail send dangling AWUC READ(8),
  consume 2 packets, drain, ver again. Never crash mid-transaction.

Device register facts (sun50iw15 differs from H616!):
- PIO pinctrl @ 0x02000000 (NOT 0x0300b000), port stride 0x30 (NOT 0x24).
  PC_CFG0=0x02000060 (PC0-7), PC_CFG1=0x02000064 (PC8-11). Post-FEL default:
  PC pins = 0xF (disabled). sdc2 mux value = 2 (NOT 3). PC0-PC11 all mux 2.
- CCU window 0x02001000..0x02003000. SMHC2_CLK @ 0x02001838 (wrote
  0x8000020E = enable, OSC24M src, N=2,M=14 -> 400kHz), SMHC_BGR @
  0x0200184C (bit2 gate, bit18 reset deassert -> 0x00040004).
- SMHC2 @ 0x04022000 (SDXC/v4.6). CRITICAL: PIO FIFO only works with
  GCTRL bit31 (ACCESS_BY_AHB) set; without it FIFO reads return the first
  word (the CRC) forever. FIFO @ +0x200. Card init at 400kHz 1-bit:
  CMD0(init seq) -> CMD1(0x40FF8080, poll bit31) -> CMD2 -> CMD3(RCA=1)
  -> CMD7 -> CMD16(512). CMDR = START|flags|idx; RINTR: CMD_DONE bit2,
  DATA_OVER bit3, errors bits1/6/7/8/9/11/15. Between block ops must wait
  !(STAS bit9 CARD_BUSY | bit10 FSM_BUSY) else next transfer corrupts.
- eMMC alive: OCR=0xc0ff8080 (sector mode), CID cc0c53f1-3200865f-
  31364737-11010030 ("16GS" 16GB-class).

Root-cause of the hang (fully confirmed by FEL reads):
- env_a on device = stock except my probe byte (loglevel '3'->'7' at env
  offset 0x299, stable across reads) -> CRC invalid.
- env_b on device = structurally corrupted by my bad patch write (text
  shifted, no flag byte) -> CRC invalid.
- Both copies bad -> U-Boot "bad CRC, using default environment" ->
  default bootcmd `run distro_bootcmd` (undefined) -> hang at bootlogo.
- Stock env header format: CRC32(4) + 0x00 flag byte + text @ offset 5.

Restore in progress: write backup env_a.img->LBA204800, env_b.img->
LBA205312, then sha256 readback verify. Then wall power-cycle (stick OUT).

### RESTORE COMPLETE (2026-10-28)

fel_mmc.py restore: env_a + env_b written block-by-block over FEL PIO and
read-back sha256-verified (env_a 2bbfc0d6..., env_b 90941dfc..., both MATCH
stock backups). ~5 min total. Awaiting user power-cycle to confirm normal boot.

FEL lane is now a fully proven recovery/flash primitive for this device:
arbitrary eMMC read/write via MMIO pokes, no device-side code needed.

### RECOVERY CONFIRMED (2026-10-28)

Root cause of "no boot after restore": USB VBUS backfeed - with the
male-to-male cable attached, the SoC never lost power during wall
power-cycles and stayed in FEL (same USB device number persisted).
Fix: cable OUT + stick OUT + 15s wall-power removal → true cold boot →
normal Android. Post-boot on-device check: sha256 of
/dev/block/by-name/env_{a,b} via qw root = stock hashes. adb@5555 + qw OK.

LESSON: any FEL session must end with the cable physically removed before
power-cycling, or the SoC never resets. FEL remains the primary recovery
lane (stick auto-update path closed: never triggers on this build).

### PROJECT COMPLETE (2026-10-28)

- Magisk 31.1 patched init_boot_b flashed (dd, sha256-verified 53d96bc2...),
  booted, app finalized, shell su verified (uid=0, context u:r:magisk:s0).
- Magisk su lessons: policies schema has NO package_name column
  (uid,policy,until,logging,notification); SuPolicy repr: 0=Query 1=Deny
  2=Allow 3=Restrict; default policy with no row = instant Deny; shell was
  fixed via `INSERT ... VALUES (2000,2,0,1,0)` + settings root_access=3.
  su injection lands in /vendor/xbin (magisk bind-overlay).
- Debloat: 12 pkgs disable-usered (see packages-disabled.txt; 3 of them were
  already disabled pre-incident). Smoke test + reboot persistence PASSED.
- MANAGEMENT.md written (operator doc: root, FEL recovery, debloat, undo).

### Public repo assembled (2026-10-28)

Sanitized publishable copy at /work/repos/visorcraft/hy450-max-root/ (git,
main, initial commit). Contains: README/LICENSE/.gitignore, docs/{NOTES,
MANAGEMENT,RUNBOOK-fresh-unit}.md (sanitized of serial/IP), tools/ (qwc4.c +
prebuilt qwc4, fel_mmc.py [BACKUP_DIR now env-overridable], fixpolicy.sh,
debloat1.sh, mgk_setup/patch/verify.sh). EXCLUDED (copyright/privacy):
backup/, reference/, *.img, *.apk, OTA zip, patch_env.py (the brick-causer,
lesson documented instead). Runbook rewritten to be self-contained without
bundled binaries (Magisk APK from official releases; always patch on-device).

### Accessibility "toggle flips back off" - root cause + fix (2026-10-28)

Symptom: enabling an accessibility service in Settings instantly toggles back
off. Cause: Android 13+ "Restricted settings" (APP_OPS ACCESS_RESTRICTED_SETTINGS)
blocks accessibility/notification-listener for apps installed by untrusted
installers (sideloads). Evidence: `appops get <pkg> ACCESS_RESTRICTED_SETTINGS`
-> `deny; rejectTime=<matches the toggle attempt>`; installer was
com.android.packageinstaller (sideload), not a store. On TV the block dialog
never renders, so the toggle just reverts silently.

Fix (per app, no root needed): `appops set <pkg> ACCESS_RESTRICTED_SETTINGS allow`
then enable normally (UI toggle, or
`settings put secure enabled_accessibility_services <pkg>/<.ServiceClass>` +
`settings put secure accessibility_enabled 1`). Verified: Projectivy service
(com.spocky.projengmenu/.services.ProjectivyAccessibilityService) bound and live.

`tools/lift-restricted.sh` lifts the block for all user-installed apps.

### Accessibility "service died" - full root cause + permanent fix (2026-10-28)

THREE stacked OEM behaviors, all proven:

1. Android 13+ restricted settings (appops ACCESS_RESTRICTED_SETTINGS=deny for
   sideloaded apps) - fixed per-app via `appops set <pkg> ... allow`, BUT this
   ROM re-derives the op at every boot (non-persistent) → not durable.
2. OEM framework hook in services.jar: DisplayContent focus-change handler calls
   enableNfxAccessibility(false)/enableYtbAccessibility(false) whenever the newly
   focused package is not com.netflix.mediaclient / com.google.android.youtube.
   The false path does Settings.Secure putInt(accessibility_enabled,0) AND
   putString(enabled_accessibility_services,"") - i.e. ANY focus change to any
   other app nukes global accessibility. (True path enables the OEM Netflix/YT
   remote-key services - left intact.)
3. OEM-added AMS.isAccessibilityTargetAllowed(pkg,uid,user): denies unless the
   DPM permitted-services list contains the pkg (list is EMPTY with no admin)
   AND appop 119 allows. Logs "Skipping enabling service disallowed by device
   admin policy". Second caller: sendRestrictedDialogIntent (the dialog TV
   can't render anyway).

FIX (both in services.jar, shipped as Magisk module a11ywipefix):
- DisplayContent.enableNfxAccessibility/enableYtbAccessibility: inserted
  `return-void` at the top of the false branch (wipe code now unreachable;
  Netflix/YT enable path untouched).
- AccessibilityManagerService.isAccessibilityTargetAllowed: body replaced with
  `const/4 v0, 0x1; return v0` (.registers 4).
Rebuild procedure: baksmali 3.0.10 disassemble classes.dex + classes3.dex from
/system/framework/services.jar → edit → smali assemble → `zip -0 -X` update the
two entries (MUST stay stored/uncompressed). Result: backup/services-patched-
a11yfix.jar (sha256 ca7f31869268...). Module: /data/adb/modules/a11ywipefix/
{module.prop, system/framework/services.jar}. Remove dir + reboot = unpatched.

Verified: enable Projectivy a11y → Settings open/close/home → stays enabled;
reboot → persists, service bound. First boot after install is slower
(dex2oat recompiles services.jar; cached afterward).

### Follow-up fixes (2026-10-28, evening)

1. Projectivy showed a11y "Enabled: No" while system said bound: the app
   string-matches the raw enabled_accessibility_services value with the
   FULLY-QUALIFIED component. My earlier `settings put` used the short form
   (`pkg/.Class`); rewriting with the long form (`pkg/pkg.Class`) fixes the
   display. System accepts both; UI writes long form.
2. "android.settings.SETTINGS is not installed": this ROM's TvSettings does
   NOT register for the generic android.settings.SETTINGS action (many other
   android.settings.* exist, just not that one). Fixed with
   tools/settings-shim: a 1-activity app (no UI) with the SETTINGS
   intent-filter that forwards to com.android.tv.settings/.MainSettings.
   Hand-built with SDK tools only (build.sh: javac+d8+aapt2+apksigner,
   no gradle). Verified: resolve-activity finds it, am start opens TvSettings.
3. Launcher tiles rebuilt from the 2026-10-16 installs
   (`com.visorcraft.settingslauncher`, `com.visorcraft.adbwifi`): source in
   tools/settings-launcher and tools/adb-wifi, same SDK-only build.sh.
   Behavior matches those installs: Settings tries the generic settings
   action, then the TV settings launch intent, then MainSettings. Wireless
   ADB writes adb_enabled + adb_wifi_enabled, toasts the IPv4, and retries
   20s after BOOT_COMPLETED. The built APKs are checked in. Other *.apk
   files stay gitignored. Signed with the local debug keystore.

### Privacy audit (2026-10-28)

Camera: /dev/video0/1 exist (V4L2, world-rw perms - sloppy) but NO camera HAL,
no android.hardware.camera feature, zero CAMERA permission grants in OEM stack,
no process holds the nodes open. = auto-focus/keystone sensor only, faces the
wall. Mic: capture PCMs exist (HDMI-in, BT remote); RECORD_AUDIO grants only in
5 user-visible apps (katniss, mphotool.airplay, vending, aptoide, syncler).
Network snapshot: only non-obvious outbound = com.htc.btremote.receiver →
Cloudflare 443 (luminago phone-remote pairing). No rogue listeners
(dbgserver :65528 confirmed off). OTA channels disabled = vendor can't push
new code. Verdict: no eavesdropping path present or wired up.

### Improvements applied (2026-10-28)

1. Private DNS = dns.adguard-dns.com (settings global private_dns_specifier).
   Verified: google.com resolves, ads.doubleclick.net NXDOMAIN. System-wide
   tracker/ad DNS blocking, incl. future apps. Undo: settings delete global
   private_dns_specifier.
2. AFWall+ v5.0.0 installed (dev.ukanth.ufirewall, uid 10099), Magisk policy
   pre-authorized (policy=2). User configures rules in its UI. APK kept in
   tools/ (do not commit to public repo - link upstream releases instead).
3. Anti-suspension: VERIFIED DORMANT - PersonalAppsSuspensionHelper's list
   never applies (single Owner user, no work profile, no device admin,
   mAppsSuspended=false). No patch needed.
4. Cast chatter: re-enabled com.toofifi.lineserver + com.mphotool.dlna +
   com.mphotool.usbcastserver (all idle unless a cast client connects; they
   were watchdogged by toofifi and spammed logcat when disabled). lineserver
   loop now satisfied. NOTE: storeos CheckUpdateService ~1/s start failures
   remain - caller unidentified (silent OEM retry loop), impact = logcat
   lines only, no network/CPU cost. Benign; left as-is.

### Aurora Store "Required permissions were denied" (2026-10-28)

Symptom: Aurora 4.8.4 permissions screen toasts "Required permissions were
denied" on Grant for Background Downloads and for App links. Same toast
(`R.string.permissions_denied`) for every row whose Settings screen returns
without the check passing.

There is no `com.android.settings` on this ROM. TvSettings either stubs the
phone Settings intent or does not register it.

**Background Downloads** is `PermissionType.DOZE_WHITELIST`. Grant launches
`Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` for
`package:com.aurora.store`. `cmd package resolve-activity` returns
`com.android.tv.settings/.EmptyStubActivity` (intent-filter priority 1,
scheme `package`). The stub finishes without calling
`IDeviceIdleController.addPowerSaveWhitelistApp`. Aurora then checks
`PowerManager.isIgnoringBatteryOptimizations`.
`IGNORE_BATTERY_OPTIMIZATION_SETTINGS` is the same stub.

Fix: `cmd deviceidle whitelist +com.aurora.store` (shell, no root).
Verified: `user,com.aurora.store,10100` and `/data/system/deviceidle.xml`
contains `<wl n="com.aurora.store" />`. Same user whitelist already used
for Projectivy and Sinema. Uninstall drops the entry.

**App links** is `PermissionType.APP_LINKS`. Grant launches
`Settings.ACTION_APP_OPEN_BY_DEFAULT_SETTINGS` with the same package URI.
`cmd package resolve-activity` returns no activity. Aurora's check
(`Context.isDomainVerified`) is user selection, not auto-verify:

```
domainMap.values.first() == DomainVerificationUserState.DOMAIN_STATE_SELECTED
```

for both `play.google.com` and `market.android.com`. Before the fix,
`pm get-app-links --user 0 com.aurora.store` showed both hosts under
`Selection state / Disabled`. `STATE_APPROVED` from `pm set-app-links`
would record verification state, which this check does not accept.

Fix (shell, no root):

```
pm set-app-links-user-selection --user 0 --package com.aurora.store true \
  play.google.com market.android.com
pm set-app-links-allowed --user 0 --package com.aurora.store true
```

Verified after: both hosts under `Selection state / Enabled`, and
`Verification link handling allowed: true`. Enabled user selection is
`DOMAIN_STATE_SELECTED`. Link-handling allowed must stay true or the
platform reports the hosts as not selected.

Installer permission resolves to
`com.android.tv.settings/.device.apps.specialaccess.ExternalSourcesActivity`.
All-files access resolves to `AllFilesAccessActivity`. Those two Grant
buttons have a real screen.

Script for the two broken rows: `tools/aurora-perms.sh`. For another
package, same commands; list its hosts with `pm get-app-links --user 0 <pkg>`.

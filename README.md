<h1 align="center">Guide for Rooting &amp; Debloating the HY450 Max</h1>

<p align="center">
  <b>Root it. Clean it. Unbrick it.</b>
  <br />
  The complete root &amp; recovery toolkit for the <b>HY450 Max</b> Android projector (Allwinner H713).
  <br />
  Magisk in ~15 minutes · reversible debloat · full un-brick with nothing but a USB-A male-to-male cable.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Android%2014%20(SDK%2034)-3DDC84?logo=android&logoColor=white" alt="Platform: Android 14" />
  <img src="https://img.shields.io/badge/SoC-Allwinner%20H713-orange" alt="SoC: Allwinner H713" />
  <img src="https://img.shields.io/badge/root-Magisk%2031.1-00A86B" alt="Root: Magisk 31.1" />
  <img src="https://img.shields.io/badge/recovery-FEL%20%2B%20USB-critical" alt="Recovery: FEL over USB" />
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT" />
</p>

---

Developed and verified end-to-end on a retail unit - including a **full
un-brick** after a bad U-Boot environment write left it hung at the boot
logo. Every procedure is backup-first and hash-verified.

> **Warning / disclaimer:** For devices you own. Rooting and flashing void
> your warranty and can brick the device if you deviate from the order of
> operations. No warranty is provided; see LICENSE. The authors are not
> affiliated with the device vendor. See [LEGAL.md](LEGAL.md) for why
> publishing and using this documentation is lawful and for the deliberate
> boundaries of this repository (no copyrighted binaries, no DRM
> circumvention).

---

## Device specifications

Verified on the retail development unit (Android 14 build
`Projector_20260821.111618`):

| Component | Specification |
|---|---|
| **SoC** | Allwinner H713 (`sun50iw15p1`, platform `hermes`) |
| **CPU** | Quad-core ARM Cortex-A53 |
| **GPU** | ARM Mali-G31 (OpenGL ES 3.2) |
| **RAM** | 2 GB |
| **Storage** | 16 GB-class eMMC (SMHC2 @ `0x04022000`) |
| **Wireless** | AIC8800 family (Wi-Fi + Bluetooth) |
| **Operating System** | **Android 14 (SDK 34)** - the `rk3566`/Android 13 build fingerprint is an OEM spoof |
| **Kernel** | Linux 5.15.167 (`armv7l`) |
| **Userspace ABI** | 32-bit (`armeabi-v7a`) - arm64-only apps will not install |
| **Partition layout** | Real A/B - **both slots populated** (development unit boots slot `_b`) |
| **SELinux** | Permissive (set via U-Boot env) |
| **Factory root** | OEM `qw` superuser daemon, reachable out of the box (see `tools/qwc4.c`) |
| **Recovery entry** | BootROM FEL (`1f3a:efe8`): pinhole-reset + power, USB-A↔A cable |

> **Not the HY300.** This is a newer generation than the well-documented
> Android 11 / kernel 4.9 / 1 GB / 8 GB / fake-A/B HY300 family. Partition
> maps, firmware images, and bootloader patches from that generation are
> **not compatible** - do not flash them here.

---

## Quick start

### Prerequisites
- An **HY450 Max** (or closely related H713 sibling) that you own
- ADB access - adb/TCP is open from the factory
- A **USB-A male-to-male cable** (only needed for the FEL recovery lane)
- Python 3 + `pyusb` on your computer (FEL recovery only)
- [Magisk](https://github.com/topjohnwu/Magisk/releases) APK - official releases only

### Root a fresh unit
```bash
# Connect to your projector
adb connect <projector-ip>:5555

# Then follow the runbook, top to bottom:
#   docs/RUNBOOK-fresh-unit.md
# backups → on-device Magisk patch → verified flash → app finalize → debloat
```

### Recover a hung unit
```bash
# Device hangs at the MAGCUBIC logo? Boot into FEL (pinhole-reset + power),
# then rewrite the stock env partitions from your own backups:
python3 tools/fel_mmc.py restore
```

## The two things that will brick you

1. **Writing U-Boot env partitions** (`env_a`/`env_b`) without a valid env
   CRC32 → hang at the MAGCUBIC logo. (Recovery: `tools/fel_mmc.py`.)
2. **"Power-cycling" with the FEL USB cable attached** - laptop VBUS
   backfeed keeps the SoC alive; it never resets and looks dead.
   Cable out, wait 15 seconds, then power on.

---

## What you get

- **🔓 Magisk root** - patched `init_boot`, structural verification before flashing, working `su` for adb shell and apps.
- **🧹 Reversible debloat** - 12 OEM bloat/telemetry packages disabled, every step undoable.
- **🧯 A real recovery lane** - host-driven eMMC read/write over the BootROM FEL protocol, no device-side code needed. If it hangs at the logo, you can fix it.
- **♿ Accessibility that sticks** - Magisk module fixing the OEM focus hook that silently killed accessibility services (e.g. Projectivy Launcher) on every app switch.
- **⚙️ Settings shim** - restores the `android.settings.SETTINGS` entry point missing from the OEM TvSettings.
- **📺 Settings tile & wireless ADB** - two home-screen apps so TV settings and wireless adb are one click away, and wireless adb comes back on at boot.
- **🛡️ Privacy hardening** - private-DNS and AFWall+ blocklist policy, plus a privacy audit of what the stock firmware talks to.
- **📚 Full forensics** - register maps, FEL wire-protocol quirks, GPT layout, hashes, and the incident log from a real un-brick.

## Documentation

| Document | Contents |
|---|---|
| [`docs/RUNBOOK-fresh-unit.md`](docs/RUNBOOK-fresh-unit.md) | **Start here.** The exact ~15-minute fresh-unit rooting procedure. |
| [`docs/MANAGEMENT.md`](docs/MANAGEMENT.md) | Operating a rooted unit: root access, FEL recovery, debloat undo, OTA hazards, returning to stock. |
| [`docs/NOTES.md`](docs/NOTES.md) | The full technical knowledge base: hardware facts, register maps, FEL protocol quirks, hashes, incident log. |

## Tools

| Tool | Purpose |
|---|---|
| `tools/qwc4.c` (+ prebuilt `qwc4`) | Root client for the OEM's `qw` superuser daemon - the always-present root shell on these units. |
| `tools/fel_mmc.py` | Host-driven eMMC reader/writer over BROM FEL (pyusb). Includes the H713 wire-protocol quirks. |
| `tools/mgk_setup.sh` / `mgk_patch.sh` / `mgk_verify.sh` | On-device Magisk boot-image patching with structural verification. |
| `tools/fixpolicy.sh` | Authorizes adb shell in Magisk's policy DB. |
| `tools/debloat1.sh` | Reversible debloat (12 OEM bloat/telemetry apps). |
| `tools/lift-restricted.sh` | Lifts Android 13's "Restricted settings" block so sideloaded apps can use accessibility services / notification listeners. |
| `tools/settings-shim/` | Tiny app (source + build script) that handles the missing `android.settings.SETTINGS` intent. |
| `tools/settings-launcher/` | Home-screen **Settings** tile (`com.visorcraft.settingslauncher`). Opens TV settings. Source, `build.sh`, and `settings-launcher.apk`. |
| `tools/adb-wifi/` | Home-screen **Wireless ADB** tile (`com.visorcraft.adbwifi`). Turns wireless adb on, and again 20s after boot. Source, `build.sh`, and `adb-wifi.apk`. |

---

## Credits / upstream

- [Magisk](https://github.com/topjohnwu/Magisk) (GPL-3.0) - get the APK only
  from the official releases page.
- [sunxi-tools](https://github.com/linux-sunxi/sunxi-tools) (GPL) - the FEL
  protocol implementation here is an independent reimplementation informed
  by that project (and by the H713 research fork by Fiooodooor); no code is
  vendored.
- Community H713/Magcubic research ([probonopd's HY300 gist](https://gist.github.com/probonopd/3ad6b7777caea1503f00d5fe7710ad06),
  [gniax/magcubic-hy300-root](https://github.com/gniax/magcubic-hy300-root),
  [YuujiLab/HY300-H713-Research](https://github.com/YuujiLab/HY300-H713-Research),
  XDA H713 thread) for prior art - note their images target **Android 11**
  builds; do **not** flash them here.

## Contribute

Tested on one retail HY450 Max. Reports from other units, batches, and
sibling H713 projectors are very welcome - especially partition-layout or
boot-flow differences. Issues and PRs are open.

---

## License

Licensed under the **MIT License** - see [`LICENSE`](LICENSE) for the full text.

© 2026 visorcraft. This repository contains original documentation, original
source, and two small original helper APKs (Settings launcher and Wireless
ADB). It ships **no** firmware dumps, no device-pulled binaries, and no
pre-patched boot images - those are the vendor's copyrighted property and you
must dump/patch your own unit (the runbook covers exactly how). See
[`LEGAL.md`](LEGAL.md) for the lawful-use rationale. Not affiliated with or
endorsed by Magcubic, Allwinner, Google, or any other vendor mentioned.

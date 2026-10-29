# Legal notes

This repository contains documentation and original tooling for rooting,
debloating, and recovering Android devices **that you own** - specifically
the HY450 Max (Magcubic-family, Allwinner H713) projector.

This is not legal advice. If you need legal advice, consult a lawyer in
your jurisdiction.

## Why this is published

- **You may modify devices you own.** In the United States, the DMCA
  anti-circumvention rule (17 U.S.C. §1201) is subject to Copyright Office
  exemptions that have long covered "jailbreaking" personal computing
  devices for software interoperability, and the 2021+ exemptions broadly
  cover diagnosis, maintenance, and repair - which includes the un-bricking
  procedures documented here. Other jurisdictions (e.g. the EU under
  Directive 2001/29/EC art. 6) similarly tolerate circumvention for
  interoperability on your own hardware.
- **Instructions are speech.** Step-by-step guides, register maps, and
  patch *recipes* are knowledge, not circumvention devices. The Allwinner
  FEL protocol used by `tools/fel_mmc.py` has been publicly documented by
  the linux-sunxi community for over a decade.
- **Nothing here bypasses DRM or content protection.** Widevine, Play
  Integrity, and streaming-service protections are explicitly out of scope
  and untouched.

## What this repository deliberately does NOT contain

- **No copyrighted binaries.** No firmware dumps, boot/init_boot images,
  partition images, or patched OEM/Google binaries (e.g. no patched
  `services.jar`). Every procedure here instructs you to extract the files
  from *your own device* and patch *your own copies*. Keep personal backups
  of your own device for your own use; do not upload them anywhere.
- **No personal data.** Serial numbers, MAC addresses, and network
  identifiers from the development unit have been removed.

## Terms of use

- For devices you own, for educational and repair purposes.
- Rooting and flashing **void your warranty** and can permanently damage
  the device if instructions are not followed.
- Using the techniques here may violate vendor or app-store terms of
  service (a civil/contract matter); that is your decision to make.
- The authors are not affiliated with Magcubic, Allwinner, Google,
  Netflix, or any other vendor mentioned. Trademarks belong to their
  owners and are used nominatively.
- All original content in this repository is provided under the
  [MIT License](LICENSE), as-is, without warranty.

## Responsible disclosure

The qw superuser daemon described in `docs/NOTES.md` is a pre-installed
OEM component, documented here in the interest of device owners'
security. It is present on retail units as shipped.

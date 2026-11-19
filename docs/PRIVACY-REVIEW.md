# Public release privacy review

Publication requires the project owner's review of the exact staged source and rendered documentation. This document records the checks to perform, not a claim that every check has already passed.

## Keep local

- Household Wi-Fi names, BSSIDs, signal surveys, room names, device names, network exports, event history and utility-meter troubleshooting records.
- Device MAC addresses, adapter serial identifiers, LAN addressing and personal filesystem paths.
- Upload tokens, dashboard access codes, provisioning proof of possession, real provisioning QR codes and Wi-Fi credentials.
- Compiled ESP32 firmware: this project embeds its receiver token and provisioning identity in the image.
- Original radio firmware downloads and flash dumps. Build from source or download directly from the original publisher when needed.

`.gitignore` excludes runtime `data/`, local environments, private configuration headers, logs, captures, archives and firmware build products. Ignore rules do not remove an already tracked file or purge Git history. Review the indexed files and all existing commits separately before making any repository public.

## Source and documentation

Use generated per-installation identities and command-line or environment configuration. Documentation should use generic paths and reserved documentation addresses. Fixtures must be synthetic and labeled. Household observations should be replaced by general troubleshooting guidance; do not copy logs or exports into issues, examples or release notes.

Run from the repository root:

```sh
python scripts/audit_release.py
# After selecting the public files:
python scripts/audit_release.py --staged
git diff --cached --stat
```

The audit prints file locations and finding categories without printing matched values. It checks common identifiers and credential literals, but it cannot prove the absence of all personal information. Human review remains necessary, particularly for free-form text, images, SVG metadata, unusual credentials and Git author metadata.

## Screenshots and photographs

Create dashboard screenshots using an explicitly labeled demonstration dataset in an isolated demo instance. Do not capture the live setup page or its QR, access code, device IP, household network names, actual device identifiers or imported device lists. Check each image visually at its full resolution and inspect image metadata before staging.

Use only hardware photographs with a documented reuse basis. Record the author, source URL, license and required attribution. A photograph's appearance on a public website does not establish an open license. The project's software license does not automatically cover third-party images, trademarks or firmware.

## Dependency and attribution checks

`pyboard.py` is vendored from MicroPython under its MIT license; retain its complete existing copyright and license header and document local modifications. Arduino ESP32, ESP-IDF, ArduinoJson, PlatformIO and Python packages retain their own licenses. Do not present the project license as replacing them. Keep dependency build artifacts outside the public source tree.

The downloaded CC2652P reference image is not needed for this project's normal operation. Its redistribution terms must be reviewed before including it; it is excluded by default.

## Approval boundary

Prepare the local commit, sanitized archive and documentation for owner review. Do not create a public GitHub repository, push public commits or upload release artifacts until the owner approves that concrete result.

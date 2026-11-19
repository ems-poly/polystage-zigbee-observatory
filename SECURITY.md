# Security and privacy

This is a local survey tool intended for a trusted private LAN. The receiver is not designed for direct exposure to the public internet. Device uploads use a shared token over local HTTP; the dashboard uses a separate login code and an HttpOnly session cookie. These controls do not encrypt LAN traffic.

BLE provisioning uses Espressif Security 1 with a per-device proof of possession. The generated provisioning QR is a setup credential: share it only with someone authorized to configure the unit. Wi-Fi credentials are stored on the ESP32 rather than in the repository.

## Reporting a vulnerability

Do not put secrets, exploitable private deployment details, or unredacted network captures in a public issue. If GitHub private vulnerability reporting is enabled on the published repository, use **Security → Report a vulnerability**. If that option is unavailable, open a minimal issue asking the maintainers for a private reporting channel without including the vulnerability details.

A private reporting channel and response service level are not guaranteed during this project's initial development.

## Before sharing a checkout or screenshot

Review the publication checklist and privacy review in the documentation. Keep generated device headers, runtime databases, raw scans, original hub exports, provisioning QR images, and build outputs out of Git. Ignoring a path does not remove it from existing commits; inspect the staged files and history before publishing.

If a credential is accidentally disclosed, rotate it and reprovision affected devices. Removing the visible file or rewriting Git history alone does not invalidate the disclosed credential.

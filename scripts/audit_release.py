#!/usr/bin/env python3
"""Check Git's intended public files without printing any matched private values.

Run before staging and again with --staged before approval. This conservative
text check supplements review of every published file, screenshot and license.
"""
from __future__ import annotations
import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RULES = {
    "personal home-directory path": re.compile(r"/(?:Users|home)/[^/\s\"'<>]+"),
    "specific USB adapter identity": re.compile(r"/dev/(?:cu|tty)\.usbserial-[A-Za-z0-9]+"),
    "MAC address": re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"),
    "compact device identity": re.compile(r"[\"'][0-9a-fA-F]{12}[\"']"),
    "private LAN address": re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
    "credential-like literal": re.compile(r'''(?i)(?:["'](?:token|password|pop|dashboard_code)["']\s*:\s*["'][^"']{8,}["']|(?:INGEST_TOKEN|PROV_POP)\s*=\s*["'][^"']{8,}["'])'''),
    "Wi-Fi name embedded in setup": re.compile(r'name="ssid"[^>]*value="[^"]+"'),
    "GitHub access token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
}
# Standard upstream/default examples, not a household's actual LAN addresses.
ALLOWED_ADDRESSES = {"192.168.4.1"}
FORBIDDEN_PARTS = {"data", "private", "local", ".venv", ".pio", "__pycache__", "release-review"}
ALLOWED_BUILD_METADATA = {"firmware-native/partitions.csv"}
FORBIDDEN_SUFFIXES = {".bin", ".elf", ".hex", ".pcap", ".pcapng", ".sqlite3", ".db", ".jsonl", ".log", ".csv", ".xlsx", ".zip", ".tar", ".tgz", ".gz", ".key", ".pem", ".p12"}


def candidates(staged: bool) -> list[str]:
    args = ["git", "ls-files", "-z", "--cached"]
    if not staged:
        args += ["--others", "--exclude-standard"]
    return sorted(set(subprocess.check_output(args, cwd=ROOT).decode().split("\0")) - {""})


def audit(staged: bool) -> int:
    findings = []
    paths = candidates(staged)
    for name in paths:
        path = pathlib.PurePosixPath(name)
        if FORBIDDEN_PARTS.intersection(path.parts) or (path.suffix.lower() in FORBIDDEN_SUFFIXES and name not in ALLOWED_BUILD_METADATA) or (path.name.startswith(".env") and path.name != ".env.example") or path.name in {"device_secrets.h", "device.json", "portable-auth.json", "portable-device.json", "provisioning-qr.png"}:
            findings.append((name, 0, "private/runtime or unreviewed binary artifact"))
            continue
        # Inspect the index bytes for the final check; working copy may differ.
        if staged:
            content = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
        else:
            target = ROOT / name
            if not target.is_file():
                continue
            content = target.read_bytes()
        if b"\0" in content:
            # Images require explicit visual review; never dump their contents.
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}:
                findings.append((name, 0, "unreviewed binary format"))
            continue
        text = content.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for label, pattern in RULES.items():
                matches = list(pattern.finditer(line))
                if label == "private LAN address":
                    matches = [m for m in matches if m.group() not in ALLOWED_ADDRESSES]
                    if name == "pyboard.py":
                        matches = [m for m in matches if m.group() != ".".join(map(str, (192, 168, 1, 1)))]
                if matches:
                    findings.append((name, number, label))
    for name, number, label in findings:
        print(f"{name}:{number}: {label}")
    print(f"Checked {len(paths)} public candidate files; {len(findings)} finding(s). Values are deliberately withheld.")
    return bool(findings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="audit only the exact indexed content")
    sys.exit(audit(parser.parse_args().staged))

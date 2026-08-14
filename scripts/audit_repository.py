#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BLOCKED_SUFFIXES = {".dcm", ".dicom", ".p12", ".pfx", ".key", ".pem"}
BLOCKED_PUBLIC_CONTENT_SUFFIXES = {
    ".7z", ".azw3", ".docx", ".epub", ".jpeg", ".jpg", ".mobi", ".pdf", ".png",
    ".pptx", ".rar", ".tif", ".tiff", ".webp", ".xlsx", ".zip",
}
BLOCKED_NAMES = {".env", "credentials.json", "secrets.json"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "dist", "build"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
)
PATIENT_PATTERNS = (
    re.compile(r"(?i)medical\s*record\s*(?:number|no\.?|#)\s*[:=]\s*\w+"),
    re.compile(r"(?i)civil\s*(?:id|number)\s*[:=]\s*\d{6,}"),
)


def audit(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
            continue
        relative = path.relative_to(root)
        name = path.name.casefold()
        suffix = path.suffix.casefold()
        if name in BLOCKED_NAMES or name.startswith(".env.") or suffix in BLOCKED_SUFFIXES:
            findings.append(f"blocked file type/name: {relative}")
            continue
        if suffix in BLOCKED_PUBLIC_CONTENT_SUFFIXES:
            findings.append(f"binary/publication asset requires explicit provenance allowlist: {relative}")
            continue
        if path.stat().st_size > 5_000_000:
            findings.append(f"large file requires rights and sensitivity review: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"possible secret: {relative}")
                break
        for pattern in PATIENT_PATTERNS:
            if pattern.search(text):
                findings.append(f"possible patient identifier: {relative}")
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    findings = audit(args.root.resolve())
    if findings:
        print("\n".join(findings))
        return 1
    print("repository audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

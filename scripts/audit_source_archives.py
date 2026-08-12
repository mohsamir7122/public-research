#!/usr/bin/env python3
"""Audit ZIP sources and optionally extract only archives that pass every safety gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_research.source_archives import ArchiveLimits, UnsafeArchiveError, audit_zip, extract_zip_safely


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Write the JSON audit report here")
    parser.add_argument("--extract-root", type=Path, help="Extract each safe archive into a distinct directory")
    parser.add_argument("--max-members", type=int, default=10_000)
    parser.add_argument("--max-single-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=10 * 1024 * 1024 * 1024)
    parser.add_argument("--max-ratio", type=float, default=200.0)
    args = parser.parse_args()
    limits = ArchiveLimits(
        max_members=args.max_members,
        max_single_uncompressed=args.max_single_bytes,
        max_total_uncompressed=args.max_total_bytes,
        max_compression_ratio=args.max_ratio,
    )
    reports: list[dict[str, object]] = []
    exit_code = 0
    for archive_path in args.archives:
        audit = audit_zip(archive_path, limits)
        report = audit.to_dict()
        if args.extract_root and audit.safe_to_extract:
            destination = args.extract_root / archive_path.stem
            try:
                extract_zip_safely(archive_path, destination, limits)
                report["extracted_to"] = str(destination.resolve())
            except (OSError, UnsafeArchiveError) as exc:
                report["extraction_error"] = str(exc)
                exit_code = 1
        elif not audit.safe_to_extract:
            exit_code = 1
        reports.append(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"archives": reports}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

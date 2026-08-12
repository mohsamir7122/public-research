#!/usr/bin/env python3
"""Validate the historical journal discovery snapshot and its verification gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_REQUIREMENT_STATUS = {"verified", "stale", "conflicting", "pending_live_verification"}
ALLOWED_CURRENT_STATUS = {"active", "ceased", "transferred", "unverified"}


def validate(path: Path, expected_count: int | None = None) -> list[str]:
    errors: list[str] = []
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: expected an object")
            continue
        records.append(value)

    if expected_count is not None and len(records) != expected_count:
        errors.append(f"expected {expected_count} records, found {len(records)}")

    ranks: set[object] = set()
    source_ids: set[object] = set()
    for index, record in enumerate(records, start=1):
        prefix = f"record {index}"
        for field in ("rank_2023", "scopus_source_id", "title", "metric_role", "current_journal_status", "author_requirements_status"):
            if record.get(field) in (None, ""):
                errors.append(f"{prefix}: missing {field}")
        if record.get("rank_2023") in ranks:
            errors.append(f"{prefix}: duplicate rank {record.get('rank_2023')}")
        ranks.add(record.get("rank_2023"))
        if record.get("scopus_source_id") in source_ids:
            errors.append(f"{prefix}: duplicate scopus_source_id {record.get('scopus_source_id')}")
        source_ids.add(record.get("scopus_source_id"))
        if record.get("metric_role") != "historical_discovery_only":
            errors.append(f"{prefix}: 2023 metric must be historical_discovery_only")
        if record.get("current_journal_status") not in ALLOWED_CURRENT_STATUS:
            errors.append(f"{prefix}: invalid current_journal_status")
        if record.get("author_requirements_status") not in ALLOWED_REQUIREMENT_STATUS:
            errors.append(f"{prefix}: invalid author_requirements_status")
        if record.get("author_requirements_status") == "verified":
            for field in ("official_url", "verified_at", "evidence_locations"):
                if not record.get(field):
                    errors.append(f"{prefix}: verified requirements require {field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    errors = validate(args.registry, args.expected_count)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create derived title/style/statistical markers from a rights-gated PDF inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from medical_research.manuscript_audit import aggregate_by_journal, profile_text, profile_title, stable_text_hash


ANALYSIS_LICENSES = {"cc-by", "cc-by-nc", "public-domain"}


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_text(path: Path, timeout_seconds: int) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", "extraction_failed"
    if result.returncode != 0:
        return "", "extraction_failed"
    text = result.stdout.decode("utf-8", errors="replace")
    if len(text.strip()) < 200:
        return text, "insufficient_extracted_text"
    return text, "analyzed"


def _profile_record(record: dict[str, Any], pdf_root: Path, verify_hash: bool, timeout_seconds: int) -> dict[str, Any]:
    title = str(record.get("title", ""))
    title_profile = profile_title(title)
    source_sha256 = str(record.get("sha256", ""))
    output: dict[str, Any] = {
        "doi": record.get("doi", ""),
        "journal": record.get("journal", ""),
        "year": record.get("year", ""),
        "license": record.get("license", ""),
        "oa_status": record.get("oa_status", ""),
        "document_kind": record.get("document_kind", ""),
        "pages": record.get("pages"),
        "source_sha256": source_sha256,
        "source_path_sha256": stable_text_hash(str(record.get("relative_path", ""))),
        "title": title,
        "title_sha256": stable_text_hash(title),
        "title_profile": {
            "word_count": title_profile.word_count,
            "has_colon": title_profile.has_colon,
            "has_question_mark": title_profile.has_question_mark,
            "design_labels": list(title_profile.design_labels),
        },
        "full_text_status": "not_analyzed_rights_gate",
        "text_profile": None,
    }
    if str(record.get("license", "")).casefold() not in ANALYSIS_LICENSES:
        return output
    resolved_root = pdf_root.resolve()
    path = (resolved_root / str(record.get("relative_path", ""))).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError:
        output["full_text_status"] = "invalid_source_path"
        return output
    if not path.is_file():
        output["full_text_status"] = "missing_file"
        return output
    if verify_hash and _sha256_file(path) != source_sha256:
        output["full_text_status"] = "checksum_mismatch"
        return output
    text, status = _extract_text(path, timeout_seconds)
    output["full_text_status"] = status
    if status == "analyzed":
        output["text_profile"] = profile_text(text).to_dict()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--pdf-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--skip-hash-verification", action="store_true")
    args = parser.parse_args()
    if shutil.which("pdftotext") is None:
        raise SystemExit("pdftotext is required for full-text marker extraction")
    records = [json.loads(line) for line in args.inventory.read_text(encoding="utf-8").splitlines() if line.strip()]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        profiles = list(
            executor.map(
                lambda record: _profile_record(
                    record,
                    args.pdf_root,
                    not args.skip_hash_verification,
                    args.timeout_seconds,
                ),
                records,
            )
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    document_path = args.output_dir / "document_profiles.jsonl"
    document_path.write_text(
        "".join(json.dumps(profile, ensure_ascii=False, sort_keys=True) + "\n" for profile in profiles),
        encoding="utf-8",
    )
    journals = aggregate_by_journal(profiles)
    journal_path = args.output_dir / "journal_profiles.json"
    journal_path.write_text(json.dumps(journals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses: dict[str, int] = {}
    license_counts: dict[str, int] = {}
    for profile in profiles:
        status = str(profile["full_text_status"])
        statuses[status] = statuses.get(status, 0) + 1
        license_name = str(profile["license"] or "unrecorded")
        license_counts[license_name] = license_counts.get(license_name, 0) + 1
    journal_evidence_status_counts: dict[str, int] = {}
    for journal in journals:
        status = str(journal["style_evidence_status"])
        journal_evidence_status_counts[status] = journal_evidence_status_counts.get(status, 0) + 1
    version_result = subprocess.run(
        ["pdftotext", "-v"], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    extractor_version = version_result.stdout.decode("utf-8", errors="replace").splitlines()[0]
    summary = {
        "snapshot_date": args.snapshot_date,
        "source_inventory_sha256": _sha256_file(args.inventory),
        "records": len(profiles),
        "journals": len(journals),
        "license_labels_allowed_for_internal_analysis": sorted(ANALYSIS_LICENSES),
        "license_verification_status": "labels_inherited_from_supplied_inventory_not_independently_reverified",
        "license_counts": dict(sorted(license_counts.items())),
        "full_text_status_counts": dict(sorted(statuses.items())),
        "journal_evidence_status_counts": dict(sorted(journal_evidence_status_counts.items())),
        "extractor": extractor_version,
        "raw_full_text_persisted": False,
        "interpretation": "Derived text-marker observations only; not official journal requirements, methodological quality judgments, reasons for acceptance, or evidence of acceptance probability.",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    fatal_statuses = {"checksum_mismatch", "missing_file", "invalid_source_path", "extraction_failed"}
    return 0 if fatal_statuses.isdisjoint(statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .dedupe import deduplicate
from .models import StudyRecord
from .search_strategy import build_queries


RECORD_FIELDS = {"title", "doi", "year", "journal", "abstract", "source", "source_id", "url", "provenance"}


def _record_from_payload(value: Any, index: int) -> StudyRecord:
    if not isinstance(value, dict):
        raise ValueError(f"record {index} must be an object")
    unknown = sorted(set(value) - RECORD_FIELDS)
    if unknown:
        raise ValueError(f"record {index} has unknown fields: {', '.join(unknown)}")
    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"record {index} requires a non-empty title")
    year = value.get("year")
    if year is not None and (not isinstance(year, int) or year < 1800 or year > 2200):
        raise ValueError(f"record {index} has an invalid year")
    provenance = value.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError(f"record {index} provenance must be an object")
    return StudyRecord(**{field: value[field] for field in RECORD_FIELDS if field in value})


def run_pilot(config: dict[str, Any], records_payload: Any) -> dict[str, Any]:
    """Run the repository's implemented search and deduplication stages on frozen metadata.

    The function deliberately does not infer novelty, eligibility, Risk of Bias,
    or clinical conclusions. Those remain accountable human decisions.
    """

    if not isinstance(config, dict):
        raise ValueError("pilot config must be an object")
    if not isinstance(records_payload, list) or not records_payload:
        raise ValueError("records must be a non-empty array")
    records = [_record_from_payload(value, index) for index, value in enumerate(records_payload)]
    kept, decisions = deduplicate(records)
    return {
        "project_id": config.get("project_id", ""),
        "search_date": config.get("search_date"),
        "queries": build_queries(config),
        "counts": {
            "input_records": len(records),
            "deduplicated_records": len(kept),
            "duplicates_removed": len(decisions),
        },
        "records": [record.to_dict() for record in kept],
        "deduplication_decisions": [asdict(decision) for decision in decisions],
        "human_review_required": [
            "novelty and overlap with recent reviews",
            "study eligibility",
            "clinical interpretation",
            "risk of bias",
        ],
    }

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from .models import StudyRecord


DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class DedupeDecision:
    kept_index: int
    removed_index: int
    reason: str
    score: float


def normalize_doi(value: str) -> str:
    match = DOI_RE.search(value or "")
    return match.group(0).rstrip(". ,;)").casefold() if match else ""


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    return " ".join(NON_WORD_RE.sub(" ", normalized).split())


def title_similarity(left: str, right: str) -> float:
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio() * 100


def _record_snapshot(record: StudyRecord) -> dict[str, object]:
    return {
        "source": record.source,
        "source_id": record.source_id,
        "url": record.url,
        "provenance": record.provenance,
    }


def _merge_records(existing: StudyRecord, candidate: StudyRecord) -> StudyRecord:
    existing_score = sum(bool(getattr(existing, field)) for field in ("doi", "journal", "abstract", "url", "source_id"))
    candidate_score = sum(bool(getattr(candidate, field)) for field in ("doi", "journal", "abstract", "url", "source_id"))
    primary, secondary = (candidate, existing) if candidate_score > existing_score else (existing, candidate)
    payload = primary.to_dict()
    for field in ("title", "doi", "year", "journal", "abstract", "source", "source_id", "url"):
        if not payload[field] and getattr(secondary, field):
            payload[field] = getattr(secondary, field)
    provenance = dict(primary.provenance)
    merged_records = list(provenance.get("merged_records", [])) if isinstance(provenance.get("merged_records"), list) else []
    for record in (existing, candidate):
        snapshot = _record_snapshot(record)
        if snapshot not in merged_records:
            merged_records.append(snapshot)
    provenance["merged_records"] = merged_records
    payload["provenance"] = provenance
    return StudyRecord(**payload)


def deduplicate(records: Iterable[StudyRecord], title_threshold: float = 94.0) -> tuple[list[StudyRecord], list[DedupeDecision]]:
    """Deduplicate conservatively.

    Matching normalized DOI is decisive. Title/year fallback is allowed only
    when both records lack a DOI. Different non-empty DOIs are never merged.
    """

    kept: list[StudyRecord] = []
    original_indexes: list[int] = []
    decisions: list[DedupeDecision] = []
    doi_index: dict[str, int] = {}

    for candidate_index, candidate in enumerate(records):
        candidate_doi = normalize_doi(candidate.doi)
        if candidate_doi and candidate_doi in doi_index:
            kept_index = doi_index[candidate_doi]
            kept[kept_index] = _merge_records(kept[kept_index], candidate)
            decisions.append(DedupeDecision(original_indexes[kept_index], candidate_index, "doi", 100.0))
            continue

        match_index: int | None = None
        match_score = 0.0
        if not candidate_doi and candidate.year is not None:
            for index, existing in enumerate(kept):
                if normalize_doi(existing.doi) or existing.year != candidate.year:
                    continue
                score = title_similarity(existing.title, candidate.title)
                if score >= title_threshold and score > match_score:
                    match_index, match_score = index, score

        if match_index is not None:
            kept[match_index] = _merge_records(kept[match_index], candidate)
            decisions.append(DedupeDecision(original_indexes[match_index], candidate_index, "normalized_title_year", round(match_score, 2)))
            continue

        kept.append(candidate)
        original_indexes.append(candidate_index)
        if candidate_doi:
            doi_index[candidate_doi] = len(kept) - 1

    return kept, decisions

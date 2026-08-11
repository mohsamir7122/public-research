from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from .models import StudyRecord


DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[^a-z0-9]+")


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
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio() * 100


def _prefer(existing: StudyRecord, candidate: StudyRecord) -> StudyRecord:
    existing_score = sum(bool(getattr(existing, field)) for field in ("doi", "journal", "abstract", "url", "source_id"))
    candidate_score = sum(bool(getattr(candidate, field)) for field in ("doi", "journal", "abstract", "url", "source_id"))
    return candidate if candidate_score > existing_score else existing


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
            kept[kept_index] = _prefer(kept[kept_index], candidate)
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
            kept[match_index] = _prefer(kept[match_index], candidate)
            decisions.append(DedupeDecision(original_indexes[match_index], candidate_index, "normalized_title_year", round(match_score, 2)))
            continue

        kept.append(candidate)
        original_indexes.append(candidate_index)
        if candidate_doi:
            doi_index[candidate_doi] = len(kept) - 1

    return kept, decisions

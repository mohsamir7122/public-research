from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Iterable


WORD = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")

DESIGN_LABELS: dict[str, re.Pattern[str]] = {
    "randomized_trial": re.compile(r"\brandomi[sz]ed(?: controlled)? trial\b", re.I),
    "cohort": re.compile(r"\b(?:prospective|retrospective)?\s*cohort study\b", re.I),
    "case_control": re.compile(r"\bcase[- ]control study\b", re.I),
    "cross_sectional": re.compile(r"\bcross[- ]sectional study\b", re.I),
    "systematic_review": re.compile(r"\bsystematic review\b", re.I),
    "meta_analysis": re.compile(r"\bmeta[- ]analysis\b", re.I),
    "case_report": re.compile(r"\bcase report\b", re.I),
    "case_series": re.compile(r"\bcase series\b", re.I),
    "diagnostic_accuracy": re.compile(r"\bdiagnostic accuracy\b", re.I),
    "study_protocol": re.compile(r"\b(?:study |trial )?protocol\b", re.I),
    "prospective": re.compile(r"\bprospective\b", re.I),
    "retrospective": re.compile(r"\bretrospective\b", re.I),
    "scoping_review": re.compile(r"\bscoping review\b", re.I),
    "narrative_review": re.compile(r"\bnarrative review\b", re.I),
    "qualitative": re.compile(r"\bqualitative(?: study| research)?\b", re.I),
    "registry_or_database": re.compile(r"\b(?:registry|database|administrative data)\b", re.I),
    "biomechanical_or_preclinical": re.compile(
        r"\b(?:biomechanical|cadaveric|finite element|animal model|in vitro|in vivo)\b", re.I
    ),
    "consensus_or_guideline": re.compile(
        r"\b(?:consensus statement|clinical practice guideline)\b", re.I
    ),
}

LATE_REFERENCES_HEADING = re.compile(
    r"(?im)^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?:references|bibliography)\s*(?:[:.]\s*)?$"
)

SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "introduction": re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:introduction|background)\s*$"),
    "methods": re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:methods?|materials and methods|patients and methods)\s*$"),
    "results": re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?results?\s*$"),
    "discussion": re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?discussion\s*$"),
    "conclusion": re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?conclusions?\s*$"),
    "data_availability": re.compile(r"(?im)^\s*(?:data availability|availability of data and materials)\s*$"),
}

ABSTRACT_HEADING_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(rf"(?im)^\s*{pattern}\s*[:.]?\s+")
    for name, pattern in {
        "background": "(?:background|introduction|purpose|objective)",
        "methods": "(?:methods?|design)",
        "results": "results?",
        "conclusion": "conclusions?",
    }.items()
}

STATISTICAL_MARKERS: dict[str, re.Pattern[str]] = {
    "confidence_interval": re.compile(r"\b(?:95\s*%\s*CI|confidence intervals?)\b", re.I),
    "effect_estimate": re.compile(
        r"\b(?:effect sizes?|mean differences?|standardi[sz]ed mean differences?|risk ratios?|relative risks?|odds ratios?|hazard ratios?|rate ratios?)\b",
        re.I,
    ),
    "exact_or_threshold_p_value": re.compile(r"(?<![A-Za-z])p\s*(?:=|<|>)\s*(?:0?\.\d+|\d+(?:\.\d+)?)", re.I),
    "sample_size_or_power": re.compile(r"\b(?:sample size|power (?:analysis|calculation)|powered to detect)\b", re.I),
    "missing_data": re.compile(r"\b(?:missing data|missing values?|loss to follow[- ]up|complete[- ]case)\b", re.I),
    "multiple_imputation": re.compile(r"\b(?:multiple imputation|chained equations|MICE)\b", re.I),
    "multivariable_regression": re.compile(r"\b(?:multivaria(?:ble|te)|multiple (?:linear|logistic) regression|adjusted regression)\b", re.I),
    "mixed_or_repeated_model": re.compile(r"\b(?:mixed[- ]effects?|mixed model|generalized estimating equations?|GEE|repeated measures?)\b", re.I),
    "survival_analysis": re.compile(r"\b(?:Kaplan[-– ]Meier|Cox (?:proportional hazards? )?regression|time[- ]to[- ]event|survival analysis)\b", re.I),
    "propensity_method": re.compile(r"\b(?:propensity score|inverse probability weight|IPTW|overlap weight)\b", re.I),
    "diagnostic_accuracy": re.compile(r"\b(?:sensitivity and specificity|receiver operating characteristic|ROC curve|area under the curve|AUC)\b", re.I),
    "meta_analysis": re.compile(r"\b(?:meta[- ]analysis|pooled effect|random[- ]effects model|fixed[- ]effect model)\b", re.I),
    "heterogeneity": re.compile(r"\b(?:heterogeneity|I\s*[²2]|tau\s*[²2]|prediction interval)\b", re.I),
    "multiplicity": re.compile(r"\b(?:multiplicity|multiple comparisons?|Bonferroni|false discovery rate|family[- ]wise error)\b", re.I),
    "sensitivity_analysis": re.compile(r"\bsensitivity analys(?:is|es)\b", re.I),
    "model_diagnostics": re.compile(r"\b(?:model diagnostics?|goodness[- ]of[- ]fit|residuals?|proportional hazards assumption|collinearity|variance inflation factor)\b", re.I),
}

SOFTWARE_PATTERNS: dict[str, re.Pattern[str]] = {
    "R": re.compile(r"\bR (?:software|version|Foundation for Statistical Computing)\b", re.I),
    "SPSS": re.compile(r"\bSPSS\b", re.I),
    "Stata": re.compile(r"\bStata(?:Corp)?\b", re.I),
    "SAS": re.compile(r"\bSAS(?: Institute)?\b", re.I),
    "GraphPad Prism": re.compile(r"\b(?:GraphPad )?Prism\b", re.I),
    "RevMan": re.compile(r"\bRevMan\b", re.I),
    "MATLAB": re.compile(r"\bMATLAB\b", re.I),
    "jamovi": re.compile(r"\bjamovi\b", re.I),
}

GUIDELINE_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])")
    for name in (
        "CONSORT",
        "SPIRIT",
        "STROBE",
        "RECORD",
        "PRISMA",
        "STARD",
        "TRIPOD+AI",
        "TRIPOD",
        "ARRIVE",
        "CARE",
        "PROCESS",
    )
}
GUIDELINE_CONTEXT = re.compile(
    r"\b(?:accord(?:ing|ance)|adher(?:e|ed|ence)|checklist|compli(?:ant|ance)|extension|"
    r"follow(?:ed|ing)|guidelines?|recommendations?|reporting|statement)\b",
    re.I,
)


def _has_contextual_guideline_mention(text: str, pattern: re.Pattern[str]) -> bool:
    """Require an uppercase acronym plus nearby reporting-guideline language.

    Several guideline acronyms (CARE, PROCESS, RECORD, ARRIVE, and SPIRIT)
    are also ordinary English words. Case-insensitive keyword counting produces
    severe false positives, so every candidate mention is context checked.
    """

    for match in pattern.finditer(text):
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        if GUIDELINE_CONTEXT.search(text[start:end]):
            return True
    return False


@dataclass(frozen=True, slots=True)
class TitleProfile:
    word_count: int
    has_colon: bool
    has_question_mark: bool
    design_labels: tuple[str, ...]


@dataclass(slots=True)
class TextProfile:
    characters: int
    marker_characters: int
    late_references_boundary_detected: bool
    sections: dict[str, bool]
    abstract_headings: dict[str, bool]
    structured_abstract_marker: bool
    statistical_markers: dict[str, bool]
    software_mentions: tuple[str, ...]
    reporting_guideline_mentions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def profile_title(title: str) -> TitleProfile:
    return TitleProfile(
        word_count=len(WORD.findall(title)),
        has_colon=":" in title,
        has_question_mark="?" in title,
        design_labels=tuple(name for name, pattern in DESIGN_LABELS.items() if pattern.search(title)),
    )


def profile_text(text: str) -> TextProfile:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    front = normalized[:30_000]
    minimum_boundary = max(5_000, int(len(normalized) * 0.4))
    late_reference_matches = [
        match for match in LATE_REFERENCES_HEADING.finditer(normalized) if match.start() >= minimum_boundary
    ]
    marker_text = normalized[: late_reference_matches[0].start()] if late_reference_matches else normalized
    abstract_headings = {name: bool(pattern.search(front)) for name, pattern in ABSTRACT_HEADING_PATTERNS.items()}
    return TextProfile(
        characters=len(normalized),
        marker_characters=len(marker_text),
        late_references_boundary_detected=bool(late_reference_matches),
        sections={name: bool(pattern.search(normalized)) for name, pattern in SECTION_PATTERNS.items()},
        abstract_headings=abstract_headings,
        structured_abstract_marker=sum(abstract_headings.values()) >= 3,
        statistical_markers={name: bool(pattern.search(marker_text)) for name, pattern in STATISTICAL_MARKERS.items()},
        software_mentions=tuple(name for name, pattern in SOFTWARE_PATTERNS.items() if pattern.search(marker_text)),
        reporting_guideline_mentions=tuple(
            name
            for name, pattern in GUIDELINE_PATTERNS.items()
            if _has_contextual_guideline_mention(marker_text, pattern)
        ),
    )


def stable_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def aggregate_by_journal(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("journal", ""))].append(record)

    output: list[dict[str, object]] = []
    for journal, rows in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        title_rows = [row for row in rows if isinstance(row.get("title_profile"), dict)]
        text_rows = [row for row in rows if row.get("full_text_status") == "analyzed"]
        unique_text_sources = {
            str(row.get("source_sha256", "")) for row in text_rows if row.get("source_sha256")
        }
        title_counts = Counter()
        design_counts = Counter()
        for row in title_rows:
            title_profile = row["title_profile"]
            title_counts["colon"] += bool(title_profile.get("has_colon"))
            title_counts["question"] += bool(title_profile.get("has_question_mark"))
            for label in title_profile.get("design_labels", []):
                design_counts[str(label)] += 1
        marker_counts = Counter()
        section_counts = Counter()
        abstract_counts = Counter()
        software_counts = Counter()
        guideline_counts = Counter()
        all_kind_counts = Counter(str(row.get("document_kind", "unknown")) for row in rows)
        text_kind_counts = Counter(str(row.get("document_kind", "unknown")) for row in text_rows)
        for row in text_rows:
            profile = row.get("text_profile", {})
            for name, present in profile.get("statistical_markers", {}).items():
                marker_counts[name] += bool(present)
            for name, present in profile.get("sections", {}).items():
                section_counts[name] += bool(present)
            for name, present in profile.get("abstract_headings", {}).items():
                abstract_counts[name] += bool(present)
            for name in profile.get("software_mentions", []):
                software_counts[name] += 1
            for name in profile.get("reporting_guideline_mentions", []):
                guideline_counts[name] += 1
        n_titles = len(title_rows)
        n_text = len(text_rows)
        if len(unique_text_sources) >= 5:
            style_evidence_status = "descriptive_sample_minimum_met"
        elif unique_text_sources:
            style_evidence_status = "insufficient_sample_below_five"
        else:
            style_evidence_status = "no_license_compatible_full_text_sample"
        word_counts = [int(row["title_profile"]["word_count"]) for row in title_rows]
        output.append(
            {
                "journal": journal,
                "title_records": n_titles,
                "full_text_license_compatible_and_analyzed": n_text,
                "distinct_full_text_sources": len(unique_text_sources),
                "style_evidence_status": style_evidence_status,
                "full_text_coverage_fraction": round(n_text / n_titles, 4) if n_titles else 0,
                "title_word_count_mean": round(sum(word_counts) / n_titles, 2) if n_titles else None,
                "title_colon_fraction": round(title_counts["colon"] / n_titles, 4) if n_titles else None,
                "title_question_fraction": round(title_counts["question"] / n_titles, 4) if n_titles else None,
                "title_design_label_counts": dict(sorted(design_counts.items())),
                "statistical_marker_counts": dict(sorted(marker_counts.items())),
                "section_marker_counts": dict(sorted(section_counts.items())),
                "abstract_heading_counts": dict(sorted(abstract_counts.items())),
                "software_mention_counts": dict(sorted(software_counts.items())),
                "reporting_guideline_mention_counts": dict(sorted(guideline_counts.items())),
                "document_kind_counts_all": dict(sorted(all_kind_counts.items())),
                "document_kind_counts_full_text": dict(sorted(text_kind_counts.items())),
            }
        )
    return output

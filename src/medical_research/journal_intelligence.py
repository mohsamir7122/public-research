from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Literal


VerificationStatus = Literal["verified", "stale", "conflicting", "pending_live_verification"]
FitStatus = Literal["eligible", "not_eligible", "pending_verification"]


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
HYPE = {
    "breakthrough",
    "game-changing",
    "groundbreaking",
    "innovative",
    "novel",
    "promising",
    "revolutionary",
    "successful",
}
CAUSAL = {"causes", "effect", "effects", "efficacy", "improves", "prevents", "reduces"}
RESULT_LANGUAGE = {"associated", "improved", "improves", "increased", "reduced", "superior", "worse"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}

DESIGN_LABELS: dict[str, tuple[str, ...]] = {
    "randomized_trial": ("randomized trial", "randomised trial", "randomized controlled trial", "randomised controlled trial"),
    "retrospective_cohort": ("retrospective cohort", "retrospective study"),
    "prospective_cohort": ("prospective cohort", "prospective study"),
    "cross_sectional": ("cross-sectional", "cross sectional"),
    "case_control": ("case-control", "case control"),
    "diagnostic_accuracy": ("diagnostic accuracy",),
    "systematic_review": ("systematic review",),
    "meta_analysis": ("meta-analysis", "meta analysis"),
    "case_report": ("case report",),
    "case_series": ("case series",),
}

OBSERVATIONAL_DESIGNS = {
    "retrospective_cohort",
    "prospective_cohort",
    "cross_sectional",
    "case_control",
}


def _words(text: str) -> list[str]:
    return [word.lower() for word in WORD_RE.findall(text)]


def _content_words(text: str) -> list[str]:
    return [word for word in _words(text) if word not in STOPWORDS]


@dataclass(frozen=True, slots=True)
class StudyProfile:
    study_design: str
    stage: Literal["planning", "completed"]
    topic_terms: tuple[str, ...]
    article_type: str = "original_research"


@dataclass(frozen=True, slots=True)
class JournalProfile:
    journal_id: str
    name: str
    requirements_status: VerificationStatus
    verified_at: str = ""
    official_url: str = ""
    scope_terms: tuple[str, ...] = ()
    article_types: tuple[str, ...] = ()
    title_word_limit: int | None = None
    title_requires_design_label: bool = False
    evidence_locations: tuple[str, ...] = ()


@dataclass(slots=True)
class TitleAssessment:
    title: str
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    word_count: int = 0

    @property
    def quality_status(self) -> str:
        if self.hard_failures:
            return "not_usable"
        if self.warnings:
            return "revise"
        return "clear"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["quality_status"] = self.quality_status
        return payload


@dataclass(slots=True)
class JournalFitAssessment:
    journal_id: str
    journal_name: str
    fit_status: FitStatus
    hard_gates: list[str] = field(default_factory=list)
    verified_matches: list[str] = field(default_factory=list)
    pending_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_title(title: str, study: StudyProfile, journal: JournalProfile | None = None) -> TitleAssessment:
    """Assess title quality and verified title constraints without predicting acceptance."""

    assessment = TitleAssessment(title=title.strip())
    words = _words(title)
    content = _content_words(title)
    assessment.word_count = len(words)
    lowered = " ".join(words)

    if not title.strip():
        assessment.hard_failures.append("title is blank")
        return assessment
    if len(words) < 5:
        assessment.warnings.append("title may be too short to identify the question")
    if journal and journal.requirements_status == "verified" and journal.title_word_limit is not None:
        if len(words) > journal.title_word_limit:
            assessment.hard_failures.append(f"exceeds verified {journal.title_word_limit}-word journal limit")
    elif len(words) > 25:
        assessment.warnings.append("title is longer than 25 words; verify the target-journal limit")

    hype_found = sorted(set(content) & HYPE)
    if hype_found:
        assessment.warnings.append(f"promotional or unsubstantiated wording: {', '.join(hype_found)}")

    if study.study_design in OBSERVATIONAL_DESIGNS:
        causal_found = sorted(set(content) & CAUSAL)
        if causal_found:
            assessment.hard_failures.append(
                f"causal language is not justified by the stated observational design: {', '.join(causal_found)}"
            )

    if study.stage == "planning":
        result_words = sorted(set(content) & RESULT_LANGUAGE)
        if result_words:
            assessment.hard_failures.append(f"a planned-study title cannot assert results: {', '.join(result_words)}")

    expected_labels = DESIGN_LABELS.get(study.study_design, ())
    has_design_label = not expected_labels or any(label in title.lower() for label in expected_labels)
    design_required = bool(journal and journal.requirements_status == "verified" and journal.title_requires_design_label)
    if design_required and not has_design_label:
        assessment.hard_failures.append("missing a design label required by the verified journal instructions")
    elif expected_labels and not has_design_label:
        assessment.warnings.append(f"consider an accurate design label such as {expected_labels[0]!r}")
    else:
        assessment.strengths.append("study design is identifiable")

    duplicate_terms = sorted({word for word in content if content.count(word) > 1 and len(word) > 3})
    if duplicate_terms:
        assessment.warnings.append(f"repeated content words: {', '.join(duplicate_terms)}")

    topic_vocabulary = {word for term in study.topic_terms for word in _content_words(term)}
    if topic_vocabulary and not topic_vocabulary.intersection(content):
        assessment.hard_failures.append("title does not contain any supplied topic term")
    elif topic_vocabulary:
        assessment.strengths.append("title contains a supplied topic term")

    if ":" in title or "—" in title:
        assessment.strengths.append("title separates the clinical question from the design")
    return assessment


def assess_journal_fit(study: StudyProfile, journal: JournalProfile, title: str = "") -> JournalFitAssessment:
    """Apply verified eligibility gates; unverified requirements can never produce an eligible label."""

    result = JournalFitAssessment(
        journal_id=journal.journal_id,
        journal_name=journal.name,
        fit_status="pending_verification",
    )
    if journal.requirements_status != "verified":
        result.pending_checks.append("journal requirements are not currently verified from the official source")
        return result
    if not journal.official_url or not journal.verified_at or not journal.evidence_locations:
        result.pending_checks.append("verified label lacks URL, date, or evidence location")
        return result

    topic_words = {word for term in study.topic_terms for word in _content_words(term)}
    scope_words = {word for term in journal.scope_terms for word in _content_words(term)}
    if not scope_words:
        result.pending_checks.append("scope terms were not extracted from the official source")
    elif not topic_words.intersection(scope_words):
        result.hard_gates.append("study topic does not match the verified scope terms")
    else:
        result.verified_matches.append("topic overlaps verified scope")

    if not journal.article_types:
        result.pending_checks.append("accepted article types were not extracted from the official source")
    elif study.article_type not in journal.article_types:
        result.hard_gates.append(f"article type {study.article_type!r} is not in the verified accepted types")
    else:
        result.verified_matches.append("article type is accepted")

    if title and journal.title_word_limit is not None and len(_words(title)) > journal.title_word_limit:
        result.hard_gates.append(f"title exceeds the verified {journal.title_word_limit}-word limit")

    if result.hard_gates:
        result.fit_status = "not_eligible"
    elif result.pending_checks:
        result.fit_status = "pending_verification"
    else:
        result.fit_status = "eligible"
    return result


def rank_title_quality(titles: Iterable[str], study: StudyProfile, journal: JournalProfile | None = None) -> list[TitleAssessment]:
    """Rank only title quality; journal fit and editorial outcome remain separate."""

    assessments = [assess_title(title, study, journal) for title in titles]
    return sorted(
        assessments,
        key=lambda item: (
            len(item.hard_failures),
            len(item.warnings),
            abs(item.word_count - 14),
            item.title.casefold(),
        ),
    )

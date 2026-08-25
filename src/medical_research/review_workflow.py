"""Auditable topic-to-completion workflow primitives for evidence reviews.

This module deliberately performs workflow validation and arithmetic only.  It
does not infer study eligibility, extract outcomes, judge risk of bias, or make
clinical claims.  Those decisions must be supplied as auditable records and
remain the responsibility of accountable reviewers.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


SUPPORTED_REVIEW_TYPES = (
    "systematic_review",
    "systematic_review_with_meta_analysis",
    "umbrella_review",
)

_REVIEW_TYPE_ALIASES = {
    "systematic_review": "systematic_review",
    "systematic_review_with_meta_analysis": "systematic_review_with_meta_analysis",
    "systematic_review_and_meta_analysis": "systematic_review_with_meta_analysis",
    "meta_analysis": "systematic_review_with_meta_analysis",
    "umbrella_review": "umbrella_review",
    "overview_of_reviews": "umbrella_review",
    "meta_meta_analysis": "umbrella_review",
}


class IntakeValidationError(ValueError):
    """Raised when a topic intake is incomplete or internally inconsistent."""

    def __init__(self, errors: Sequence[str]):
        self.errors = tuple(errors)
        super().__init__("invalid topic intake: " + "; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class TopicIntake:
    """Normalized starting description of a proposed evidence review."""

    review_type: str
    working_title: str
    research_question: str
    rationale: str
    objective: str
    population: str
    intervention_or_exposure: str
    comparator: str
    primary_outcome: str
    secondary_outcomes: tuple[str, ...]
    eligible_evidence_types: tuple[str, ...]
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    databases: tuple[str, ...]
    accountable_reviewers: tuple[str, ...]
    effect_measure: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "secondary_outcomes",
            "eligible_evidence_types",
            "inclusion_criteria",
            "exclusion_criteria",
            "databases",
            "accountable_reviewers",
        ):
            value[key] = list(value[key])
        return value


_INTAKE_FIELDS = {
    "review_type",
    "working_title",
    "research_question",
    "rationale",
    "objective",
    "population",
    "intervention_or_exposure",
    "comparator",
    "primary_outcome",
    "secondary_outcomes",
    "eligible_evidence_types",
    "inclusion_criteria",
    "exclusion_criteria",
    "databases",
    "accountable_reviewers",
    "effect_measure",
}

_REQUIRED_TEXT_FIELDS = (
    "working_title",
    "research_question",
    "rationale",
    "objective",
    "population",
    "intervention_or_exposure",
    "primary_outcome",
)

_PLACEHOLDERS = {
    "n/a",
    "na",
    "none",
    "not applicable",
    "tbd",
    "to be decided",
    "to be determined",
    "unknown",
}

_MACHINE_ACTOR_PATTERN = re.compile(
    r"(?:\bai\b|\bbot\b|\bgpt(?:-?\d+)?\b|chatgpt|openai|codex|"
    r"artificial intelligence|large language model|language model|ai assistant|"
    r"claude ai|gemini ai)",
    flags=re.IGNORECASE,
)

_GENERIC_REVIEWER_LABELS = {
    "reviewer one",
    "reviewer two",
    "researcher one",
    "researcher two",
    "investigator one",
    "investigator two",
    "methodologist",
    "statistician",
}


def _looks_like_machine_actor(value: str) -> bool:
    return bool(_MACHINE_ACTOR_PATTERN.search(value))


def _looks_like_named_human(value: str) -> bool:
    if value.casefold() in _GENERIC_REVIEWER_LABELS or _looks_like_machine_actor(value):
        return False
    words = re.findall(r"[^\W\d_]+", value, flags=re.UNICODE)
    return len(words) >= 2


def _normalize_review_type(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", value.strip().casefold())
    return _REVIEW_TYPE_ALIASES.get(key, value)


def _clean_text(value: Any, field_name: str, errors: list[str], *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        errors.append(f"{field_name} must be a string")
        return ""
    cleaned = " ".join(value.split())
    if required and not cleaned:
        errors.append(f"{field_name} is required")
    elif cleaned.casefold() in _PLACEHOLDERS:
        errors.append(f"{field_name} contains a placeholder")
    return cleaned


def _clean_text_list(
    value: Any,
    field_name: str,
    errors: list[str],
    *,
    minimum: int,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        errors.append(f"{field_name} must be an array")
        return ()
    cleaned: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _clean_text(item, f"{field_name}[{index}]", errors)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            errors.append(f"{field_name} contains a duplicate value: {text}")
            continue
        seen.add(key)
        cleaned.append(text)
    if len(cleaned) < minimum:
        errors.append(f"{field_name} requires at least {minimum} distinct value(s)")
    return tuple(cleaned)


def validate_topic_intake(payload: Mapping[str, Any]) -> TopicIntake:
    """Validate and normalize the topic supplied before a review is opened.

    The intake intentionally requires two named accountable reviewers.  An AI
    tool may assist them, but it is not an accountable reviewer or an author.
    """

    if not isinstance(payload, Mapping):
        raise IntakeValidationError(("topic intake must be an object",))

    errors: list[str] = []
    unknown = sorted(set(payload) - _INTAKE_FIELDS)
    if unknown:
        errors.append("unknown fields: " + ", ".join(unknown))

    review_type = _clean_text(payload.get("review_type"), "review_type", errors)
    if review_type:
        review_type = _normalize_review_type(review_type)
    if review_type and review_type not in SUPPORTED_REVIEW_TYPES:
        errors.append(
            "review_type must be one of: " + ", ".join(SUPPORTED_REVIEW_TYPES)
        )

    texts = {
        field_name: _clean_text(payload.get(field_name), field_name, errors)
        for field_name in _REQUIRED_TEXT_FIELDS
    }
    comparator = _clean_text(payload.get("comparator", ""), "comparator", errors, required=False)
    effect_measure = _clean_text(
        payload.get("effect_measure", ""), "effect_measure", errors, required=False
    )

    if texts["working_title"] and not 12 <= len(texts["working_title"]) <= 300:
        errors.append("working_title must contain 12 to 300 characters")
    for field_name in ("research_question", "rationale", "objective"):
        if texts[field_name] and len(texts[field_name]) < 20:
            errors.append(f"{field_name} must contain at least 20 characters")

    secondary_outcomes = _clean_text_list(
        payload.get("secondary_outcomes", []),
        "secondary_outcomes",
        errors,
        minimum=0,
    )
    eligible_evidence_types = _clean_text_list(
        payload.get("eligible_evidence_types"),
        "eligible_evidence_types",
        errors,
        minimum=1,
    )
    inclusion_criteria = _clean_text_list(
        payload.get("inclusion_criteria"), "inclusion_criteria", errors, minimum=1
    )
    exclusion_criteria = _clean_text_list(
        payload.get("exclusion_criteria"), "exclusion_criteria", errors, minimum=1
    )
    databases = _clean_text_list(payload.get("databases"), "databases", errors, minimum=2)
    accountable_reviewers = _clean_text_list(
        payload.get("accountable_reviewers"),
        "accountable_reviewers",
        errors,
        minimum=2,
    )
    for reviewer in accountable_reviewers:
        if not _looks_like_named_human(reviewer):
            errors.append(
                f"accountable_reviewers must contain named humans, not roles or AI/tool identities: {reviewer}"
            )

    primary_key = texts["primary_outcome"].casefold()
    if primary_key and primary_key in {value.casefold() for value in secondary_outcomes}:
        errors.append("primary_outcome must not be repeated in secondary_outcomes")
    criteria_overlap = {value.casefold() for value in inclusion_criteria} & {
        value.casefold() for value in exclusion_criteria
    }
    if criteria_overlap:
        errors.append("the same criterion cannot be both included and excluded")

    if review_type == "systematic_review_with_meta_analysis" and not effect_measure:
        errors.append("effect_measure is required when meta-analysis is planned")

    if review_type == "umbrella_review":
        invalid_types = [
            value
            for value in eligible_evidence_types
            if "systematic review" not in value.casefold()
            and "meta-analysis" not in value.casefold()
            and "meta analysis" not in value.casefold()
        ]
        if invalid_types:
            errors.append(
                "umbrella_review eligible_evidence_types must be review-level evidence: "
                + ", ".join(invalid_types)
            )

    if errors:
        raise IntakeValidationError(errors)

    return TopicIntake(
        review_type=review_type,
        working_title=texts["working_title"],
        research_question=texts["research_question"],
        rationale=texts["rationale"],
        objective=texts["objective"],
        population=texts["population"],
        intervention_or_exposure=texts["intervention_or_exposure"],
        comparator=comparator,
        primary_outcome=texts["primary_outcome"],
        secondary_outcomes=secondary_outcomes,
        eligible_evidence_types=eligible_evidence_types,
        inclusion_criteria=inclusion_criteria,
        exclusion_criteria=exclusion_criteria,
        databases=databases,
        accountable_reviewers=accountable_reviewers,
        effect_measure=effect_measure,
    )


_COMMON_PIPELINE = (
    "topic_intake",
    "protocol",
    "registration",
    "search_strategy",
    "search_execution",
    "deduplication",
    "title_abstract_screening",
    "full_text_screening",
    "data_extraction",
    "risk_of_bias",
)

_PIPELINES = {
    "systematic_review": _COMMON_PIPELINE
    + (
        "narrative_synthesis",
        "certainty_assessment",
        "reporting",
        "quality_assurance",
        "completed",
    ),
    "systematic_review_with_meta_analysis": _COMMON_PIPELINE
    + (
        "effect_size_harmonization",
        "meta_analysis",
        "certainty_assessment",
        "reporting",
        "quality_assurance",
        "completed",
    ),
    "umbrella_review": _COMMON_PIPELINE
    + (
        "overlap_assessment",
        "umbrella_synthesis",
        "certainty_assessment",
        "reporting",
        "quality_assurance",
        "completed",
    ),
}

_STAGE_GATES = {
    "topic_intake": ("intake_validated",),
    "protocol": (
        "protocol_frozen",
        "eligibility_criteria_frozen",
        "outcome_definitions_frozen",
    ),
    "registration": ("registration_status_recorded",),
    "search_strategy": (
        "database_specific_queries_complete",
        "peer_review_recorded",
    ),
    "search_execution": (
        "raw_exports_preserved",
        "search_log_complete",
        "checksums_recorded",
    ),
    "deduplication": ("deduplication_decisions_auditable",),
    "title_abstract_screening": (
        "final_decisions_recorded",
        "conflicts_resolved",
    ),
    "full_text_screening": (
        "retrieval_status_recorded",
        "exclusion_reasons_recorded",
        "final_decisions_recorded",
    ),
    "data_extraction": (
        "source_locations_recorded",
        "decisive_fields_verified",
    ),
    "risk_of_bias": (
        "design_appropriate_tool_used",
        "judgments_verified",
    ),
    "narrative_synthesis": (
        "synthesis_uses_verified_data",
        "protocol_deviations_recorded",
    ),
    "effect_size_harmonization": (
        "effect_measure_prespecified",
        "unit_of_analysis_checked",
        "extracted_effects_verified",
    ),
    "meta_analysis": (
        "analysis_reproducible",
        "heterogeneity_assessed",
        "sensitivity_analyses_complete",
        "protocol_deviations_recorded",
    ),
    "overlap_assessment": ("citation_matrix_verified", "cca_calculated"),
    "umbrella_synthesis": (
        "review_quality_appraised",
        "overlap_incorporated",
        "synthesis_uses_verified_data",
    ),
    "certainty_assessment": (
        "outcome_level_certainty_complete",
        "certainty_rationales_verified",
    ),
    "reporting": (
        "selection_flow_derived",
        "claims_traceable_to_evidence",
        "reporting_checklist_complete",
    ),
    "quality_assurance": (
        "methods_review_signed",
        "clinical_review_signed",
        "citation_audit_passed",
        "release_approved",
    ),
}


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be JSON-serializable") from exc


def _slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return (slug or fallback)[:64].rstrip("-")


def _manifest_files(review_type: str) -> list[dict[str, Any]]:
    files: list[tuple[str, str, bool]] = [
        ("manifest.json", "Frozen scaffold and topic fingerprint", False),
        ("project-state.json", "Serializable integrity-checked workflow state", True),
        ("audit/gate-transitions.jsonl", "Derived evidence-gate transition log", True),
        ("protocol/topic_intake.json", "Validated topic intake", False),
        ("protocol/protocol.md", "Dated review protocol", True),
        ("protocol/amendments.jsonl", "Prospective protocol deviations", True),
        ("registration/registration.json", "Registration status and identifier", True),
        ("search/strategies.json", "Database-specific search strategies", True),
        ("search/search_log.csv", "Queries, filters, dates, hit counts, and checksums", True),
        ("search/raw_exports/README.md", "Immutable raw-export handling instructions", False),
        ("screening/decisions.jsonl", "Reviewer and consensus screening decisions", True),
        ("screening/conflicts.jsonl", "Conflict resolution audit trail", True),
        ("retrieval/full_text_inventory.csv", "Retrieval and rights status", True),
        ("extraction/data_extraction.csv", "Extracted values with source locations", True),
        ("extraction/verification.jsonl", "Independent verification decisions", True),
        ("risk_of_bias/judgments.csv", "Design-appropriate judgments and support", True),
        ("certainty/judgments.csv", "Outcome-level certainty judgments and rationale", True),
        ("certainty/evidence_profiles.csv", "Outcome-level evidence profiles", True),
        ("synthesis/protocol_deviations.jsonl", "Analysis deviations and rationale", True),
        ("reporting/reporting_checklist.csv", "Applicable reporting checklist", True),
        ("manuscript/manuscript.md", "Evidence-traceable manuscript source", True),
        ("qa/release_gate.json", "Methods, clinical, citation, and release sign-off", True),
    ]
    if review_type == "systematic_review":
        files.extend(
            (
                ("reporting/prisma_counts.json", "PRISMA counts derived from final records", True),
                ("synthesis/narrative_synthesis.md", "Structured evidence synthesis", True),
            )
        )
    elif review_type == "systematic_review_with_meta_analysis":
        files.extend(
            (
                ("reporting/prisma_counts.json", "PRISMA counts derived from final records", True),
                ("analysis/effect_sizes.csv", "Verified harmonized effect sizes", True),
                ("analysis/model_specification.json", "Prespecified quantitative model", True),
                ("analysis/results.json", "Reproducible quantitative results", True),
                ("analysis/sensitivity_analyses.json", "Prespecified sensitivity analyses", True),
            )
        )
    else:
        files.extend(
            (
                ("reporting/prior_flow_counts.json", "PRIOR flow counts derived from final review records", True),
                ("overlap/citation_matrix.csv", "Review-by-primary-study citation matrix", True),
                ("overlap/corrected_covered_area.json", "Corrected covered area calculation", True),
                ("synthesis/umbrella_synthesis.md", "Overlap-aware review-level synthesis", True),
            )
        )
    return [
        {"path": path, "purpose": purpose, "mutable": mutable}
        for path, purpose, mutable in sorted(files, key=lambda item: item[0])
    ]


def build_project_manifest(intake: TopicIntake | Mapping[str, Any]) -> dict[str, Any]:
    """Return the same scaffold manifest for the same normalized intake."""

    normalized = validate_topic_intake(
        intake.to_dict() if isinstance(intake, TopicIntake) else intake
    )
    intake_dict = normalized.to_dict()
    fingerprint = sha256(_canonical_json(intake_dict).encode("utf-8")).hexdigest()
    prefix = {
        "systematic_review": "SR",
        "systematic_review_with_meta_analysis": "SRMA",
        "umbrella_review": "UR",
    }[normalized.review_type]
    files = _manifest_files(normalized.review_type)
    directories = sorted(
        {
            path.rsplit("/", 1)[0]
            for path in (item["path"] for item in files)
            if "/" in path
        }
    )
    return {
        "schema_version": "1.0",
        "project_id": f"{prefix}-{fingerprint[:12].upper()}",
        "topic_fingerprint_sha256": fingerprint,
        "slug": _slugify(normalized.working_title, normalized.review_type.replace("_", "-")),
        "review_type": normalized.review_type,
        "pipeline": list(_PIPELINES[normalized.review_type]),
        "directories": directories,
        "files": files,
        "integrity_rules": [
            "raw inputs are immutable and checksummed",
            "screening counts are derived from final auditable decisions",
            "extracted values retain source locations and verification status",
            "protocol deviations are logged prospectively",
            "clinical and methodological conclusions require accountable review",
        ],
        "truth_boundary": (
            "The manifest and state machine validate structure, references, checksums, and "
            "sequencing. They do not authenticate source content or replace accountable "
            "clinical, methodological, statistical, or publication review."
        ),
    }


def required_evidence_for_stage(stage: str) -> tuple[str, ...]:
    """Return the gate keys required to complete a workflow stage."""

    if stage not in _STAGE_GATES:
        raise ValueError(f"stage has no completion gate: {stage}")
    return _STAGE_GATES[stage]


_EVIDENCE_REFERENCE_FIELDS = {
    "artifact",
    "sha256",
    "verified_by",
    "verified_on",
    "note",
}

_DUAL_VERIFIER_GATES = {
    "protocol_frozen",
    "eligibility_criteria_frozen",
    "outcome_definitions_frozen",
    "peer_review_recorded",
    "final_decisions_recorded",
    "conflicts_resolved",
    "decisive_fields_verified",
    "judgments_verified",
    "extracted_effects_verified",
    "citation_matrix_verified",
    "review_quality_appraised",
    "synthesis_uses_verified_data",
    "outcome_level_certainty_complete",
    "certainty_rationales_verified",
    "selection_flow_derived",
    "claims_traceable_to_evidence",
    "release_approved",
}


def _normalize_reviewer_names(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("accountable_reviewers must be an array")
    normalized = tuple(
        _validated_nonempty_string(value, "accountable_reviewer") for value in values
    )
    if len(normalized) < 2:
        raise ValueError("at least two accountable human reviewers are required")
    keys = [value.casefold() for value in normalized]
    if len(set(keys)) != len(keys):
        raise ValueError("accountable reviewer names must be distinct")
    invalid_labels = [value for value in normalized if not _looks_like_named_human(value)]
    if invalid_labels:
        raise ValueError(
            "accountable reviewers must be named humans, not roles or AI/tool identities: "
            + ", ".join(invalid_labels)
        )
    return normalized


def _normalize_gate_evidence(
    evidence: Mapping[str, Any],
    *,
    required: Sequence[str],
    accountable_reviewers: Sequence[str],
    decision_date: str,
) -> dict[str, dict[str, Any]]:
    required_set = set(required)
    supplied_set = set(evidence)
    if supplied_set != required_set:
        missing = sorted(required_set - supplied_set)
        unexpected = sorted(supplied_set - required_set)
        details: list[str] = []
        if missing:
            details.append("missing evidence: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected evidence keys: " + ", ".join(unexpected))
        raise ValueError("; ".join(details))

    reviewer_lookup = {value.casefold(): value for value in accountable_reviewers}
    normalized: dict[str, dict[str, Any]] = {}
    for gate in required:
        value = evidence[gate]
        if not isinstance(value, Mapping):
            raise ValueError(
                f"{gate} evidence must be an object with artifact, sha256, verified_by, and verified_on"
            )
        unknown = sorted(set(value) - _EVIDENCE_REFERENCE_FIELDS)
        if unknown:
            raise ValueError(f"{gate} evidence has unknown fields: " + ", ".join(unknown))

        artifact = _validated_nonempty_string(value.get("artifact"), f"{gate}.artifact")
        artifact_path = PurePosixPath(artifact)
        if artifact_path.is_absolute() or ".." in artifact_path.parts or artifact in {".", ""}:
            raise ValueError(f"{gate}.artifact must be a safe project-relative path")

        checksum = _validated_nonempty_string(value.get("sha256"), f"{gate}.sha256").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError(f"{gate}.sha256 must be a 64-character SHA-256 digest")

        raw_verifiers = value.get("verified_by")
        if isinstance(raw_verifiers, (str, bytes)) or not isinstance(raw_verifiers, Sequence):
            raise ValueError(f"{gate}.verified_by must be an array")
        verifiers = tuple(
            _validated_nonempty_string(item, f"{gate}.verified_by")
            for item in raw_verifiers
        )
        verifier_keys = [item.casefold() for item in verifiers]
        if len(set(verifier_keys)) != len(verifier_keys):
            raise ValueError(f"{gate}.verified_by must contain distinct reviewers")
        unknown_verifiers = [
            item for item in verifiers if item.casefold() not in reviewer_lookup
        ]
        if unknown_verifiers:
            raise ValueError(
                f"{gate}.verified_by contains unaccountable reviewers: "
                + ", ".join(unknown_verifiers)
            )
        minimum = 2 if gate in _DUAL_VERIFIER_GATES else 1
        if len(verifiers) < minimum:
            raise ValueError(f"{gate} requires at least {minimum} accountable verifier(s)")

        verified_on = _validated_iso_date(value.get("verified_on"), f"{gate}.verified_on")
        if verified_on > decision_date:
            raise ValueError(f"{gate}.verified_on cannot be after decision_date")
        note_value = value.get("note", "")
        if not isinstance(note_value, str):
            raise ValueError(f"{gate}.note must be a string")
        normalized[gate] = {
            "artifact": artifact,
            "sha256": checksum,
            "verified_by": [reviewer_lookup[item.casefold()] for item in verifiers],
            "verified_on": verified_on,
            "note": " ".join(note_value.split()),
        }
    return normalized


class ReviewWorkflow:
    """Strict forward-only state machine with deterministic transition logs."""

    def __init__(self, review_type: str, accountable_reviewers: Sequence[str]):
        if review_type not in SUPPORTED_REVIEW_TYPES:
            raise ValueError(
                "unsupported review_type; expected one of: "
                + ", ".join(SUPPORTED_REVIEW_TYPES)
            )
        self.review_type = review_type
        self.accountable_reviewers = _normalize_reviewer_names(accountable_reviewers)
        self._pipeline = _PIPELINES[review_type]
        self._position = 0
        self._transitions: list[dict[str, Any]] = []

    @property
    def current_stage(self) -> str:
        return self._pipeline[self._position]

    @property
    def next_stage(self) -> str | None:
        if self._position + 1 >= len(self._pipeline):
            return None
        return self._pipeline[self._position + 1]

    @property
    def completed(self) -> bool:
        return self.current_stage == "completed"

    def advance(
        self,
        evidence: Mapping[str, Any],
        *,
        reviewer: str,
        decision_date: str,
        to_stage: str | None = None,
    ) -> dict[str, Any]:
        """Complete the current stage and move exactly one stage forward."""

        if self.completed:
            raise RuntimeError("completed workflow cannot be advanced")
        expected = self.next_stage
        if to_stage is not None and to_stage != expected:
            raise ValueError(f"invalid transition: expected {expected}, received {to_stage}")
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence must be an object")
        if any(not isinstance(key, str) or not key for key in evidence):
            raise ValueError("evidence keys must be non-empty strings")
        reviewer = _validated_nonempty_string(reviewer, "reviewer")
        reviewer_lookup = {
            value.casefold(): value for value in self.accountable_reviewers
        }
        if reviewer.casefold() not in reviewer_lookup:
            raise ValueError("reviewer must be one of the accountable human reviewers")
        reviewer = reviewer_lookup[reviewer.casefold()]
        decision_date = _validated_iso_date(decision_date, "decision_date")
        if self._transitions and decision_date < self._transitions[-1]["decision_date"]:
            raise ValueError("decision_date cannot precede the previous transition")

        required = required_evidence_for_stage(self.current_stage)
        try:
            normalized_evidence = _normalize_gate_evidence(
                evidence,
                required=required,
                accountable_reviewers=self.accountable_reviewers,
                decision_date=decision_date,
            )
        except ValueError as exc:
            raise ValueError(f"cannot complete {self.current_stage}; {exc}") from exc
        if self.current_stage == "quality_assurance":
            methods = set(normalized_evidence["methods_review_signed"]["verified_by"])
            clinical = set(normalized_evidence["clinical_review_signed"]["verified_by"])
            if methods == clinical:
                raise ValueError(
                    "cannot complete quality_assurance; methods and clinical sign-offs require distinct accountable roles"
                )
        evidence_json = _canonical_json(normalized_evidence)
        transition = {
            "from_stage": self.current_stage,
            "to_stage": expected,
            "reviewer": reviewer,
            "decision_date": decision_date,
            "evidence_keys": sorted(evidence),
            "evidence_fingerprint_sha256": sha256(evidence_json.encode("utf-8")).hexdigest(),
            "evidence": normalized_evidence,
            "previous_transition_sha256": (
                self._transitions[-1]["transition_sha256"]
                if self._transitions
                else "0" * 64
            ),
        }
        transition["transition_sha256"] = sha256(
            _canonical_json(transition).encode("utf-8")
        ).hexdigest()
        self._transitions.append(transition)
        self._position += 1
        return deepcopy(transition)

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "ReviewWorkflow":
        """Restore a workflow only when its pipeline and transition hash chain verify."""

        if not isinstance(snapshot, Mapping):
            raise ValueError("workflow snapshot must be an object")
        review_type = snapshot.get("review_type")
        reviewers = snapshot.get("accountable_reviewers")
        workflow = cls(review_type, reviewers)
        if snapshot.get("pipeline") != list(workflow._pipeline):
            raise ValueError("workflow snapshot pipeline does not match review_type")
        transitions = snapshot.get("transitions")
        if not isinstance(transitions, list):
            raise ValueError("workflow snapshot transitions must be an array")
        if len(transitions) >= len(workflow._pipeline):
            raise ValueError("workflow snapshot contains too many transitions")

        restored: list[dict[str, Any]] = []
        previous_hash = "0" * 64
        previous_date = ""
        transition_fields = {
            "from_stage",
            "to_stage",
            "reviewer",
            "decision_date",
            "evidence_keys",
            "evidence_fingerprint_sha256",
            "evidence",
            "previous_transition_sha256",
            "transition_sha256",
        }
        reviewer_lookup = {
            value.casefold(): value for value in workflow.accountable_reviewers
        }
        for index, raw_transition in enumerate(transitions):
            if not isinstance(raw_transition, Mapping):
                raise ValueError(f"workflow transition {index} must be an object")
            if set(raw_transition) != transition_fields:
                raise ValueError(f"workflow transition {index} has invalid fields")
            expected_from = workflow._pipeline[index]
            expected_to = workflow._pipeline[index + 1]
            if raw_transition.get("from_stage") != expected_from:
                raise ValueError(f"workflow transition {index} has invalid from_stage")
            if raw_transition.get("to_stage") != expected_to:
                raise ValueError(f"workflow transition {index} has invalid to_stage")
            reviewer = _validated_nonempty_string(
                raw_transition.get("reviewer"), "reviewer"
            )
            if reviewer.casefold() not in reviewer_lookup:
                raise ValueError(f"workflow transition {index} has an unaccountable reviewer")
            reviewer = reviewer_lookup[reviewer.casefold()]
            decision_date = _validated_iso_date(
                raw_transition.get("decision_date"), "decision_date"
            )
            if previous_date and decision_date < previous_date:
                raise ValueError("workflow transition dates are not monotonic")
            required = required_evidence_for_stage(expected_from)
            raw_evidence = raw_transition.get("evidence")
            if not isinstance(raw_evidence, Mapping):
                raise ValueError(f"workflow transition {index} evidence must be an object")
            evidence = _normalize_gate_evidence(
                raw_evidence,
                required=required,
                accountable_reviewers=workflow.accountable_reviewers,
                decision_date=decision_date,
            )
            if expected_from == "quality_assurance":
                methods = set(evidence["methods_review_signed"]["verified_by"])
                clinical = set(evidence["clinical_review_signed"]["verified_by"])
                if methods == clinical:
                    raise ValueError(
                        "workflow quality assurance has non-distinct methods and clinical sign-offs"
                    )
            evidence_keys = sorted(evidence)
            if raw_transition.get("evidence_keys") != evidence_keys:
                raise ValueError(f"workflow transition {index} evidence_keys do not reconcile")
            evidence_fingerprint = sha256(
                _canonical_json(evidence).encode("utf-8")
            ).hexdigest()
            if raw_transition.get("evidence_fingerprint_sha256") != evidence_fingerprint:
                raise ValueError(f"workflow transition {index} evidence fingerprint is invalid")
            if raw_transition.get("previous_transition_sha256") != previous_hash:
                raise ValueError(f"workflow transition {index} breaks the hash chain")
            normalized_transition = {
                "from_stage": expected_from,
                "to_stage": expected_to,
                "reviewer": reviewer,
                "decision_date": decision_date,
                "evidence_keys": evidence_keys,
                "evidence_fingerprint_sha256": evidence_fingerprint,
                "evidence": evidence,
                "previous_transition_sha256": previous_hash,
            }
            transition_hash = sha256(
                _canonical_json(normalized_transition).encode("utf-8")
            ).hexdigest()
            if raw_transition.get("transition_sha256") != transition_hash:
                raise ValueError(f"workflow transition {index} hash is invalid")
            normalized_transition["transition_sha256"] = transition_hash
            restored.append(normalized_transition)
            previous_hash = transition_hash
            previous_date = decision_date

        workflow._position = len(restored)
        workflow._transitions = restored
        expected_snapshot = workflow.snapshot()
        for key in ("current_stage", "next_stage", "completed", "completed_stages"):
            if snapshot.get(key) != expected_snapshot[key]:
                raise ValueError(f"workflow snapshot {key} does not reconcile")
        return workflow

    def snapshot(self) -> dict[str, Any]:
        return {
            "review_type": self.review_type,
            "accountable_reviewers": list(self.accountable_reviewers),
            "pipeline": list(self._pipeline),
            "current_stage": self.current_stage,
            "next_stage": self.next_stage,
            "completed": self.completed,
            "completed_stages": list(self._pipeline[: self._position]),
            "transitions": deepcopy(self._transitions),
        }


_SCREENING_FIELDS = {
    "record_id",
    "stage",
    "decision",
    "reviewer",
    "decision_date",
    "is_final",
    "source_type",
    "source_name",
    "reason",
    "duplicate_of",
    "study_id",
}

_SCREENING_DECISIONS = {
    "identification": {"identified"},
    "deduplication": {
        "retained",
        "duplicate",
        "removed_by_automation",
        "removed_other",
    },
    "title_abstract": {"include", "exclude"},
    "retrieval": {"retrieved", "not_retrieved"},
    "full_text": {"include", "exclude"},
}

_SOURCE_TYPES = {"database", "register", "other_method"}


@dataclass(frozen=True, slots=True)
class ScreeningEvent:
    """One reviewer event; PRISMA uses only uniquely adjudicated final events."""

    record_id: str
    stage: str
    decision: str
    reviewer: str
    decision_date: str
    is_final: bool
    source_type: str = ""
    source_name: str = ""
    reason: str = ""
    duplicate_of: str = ""
    study_id: str = ""


def _validated_nonempty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return " ".join(value.split())


def _validated_iso_date(value: Any, field_name: str) -> str:
    text = _validated_nonempty_string(value, field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc
    if parsed > date.today():
        raise ValueError(f"{field_name} cannot be in the future")
    return parsed.isoformat()


def _screening_event_from_mapping(value: Any, index: int) -> ScreeningEvent:
    if not isinstance(value, Mapping):
        raise ValueError(f"screening record {index} must be an object")
    unknown = sorted(set(value) - _SCREENING_FIELDS)
    if unknown:
        raise ValueError(
            f"screening record {index} has unknown fields: " + ", ".join(unknown)
        )
    record_id = _validated_nonempty_string(value.get("record_id"), "record_id")
    stage = _validated_nonempty_string(value.get("stage"), "stage")
    decision = _validated_nonempty_string(value.get("decision"), "decision")
    reviewer = _validated_nonempty_string(value.get("reviewer"), "reviewer")
    decision_date = _validated_iso_date(value.get("decision_date"), "decision_date")
    is_final = value.get("is_final")
    if not isinstance(is_final, bool):
        raise ValueError("is_final must be a boolean")
    if stage not in _SCREENING_DECISIONS:
        raise ValueError(f"unsupported screening stage: {stage}")
    if decision not in _SCREENING_DECISIONS[stage]:
        raise ValueError(f"decision {decision} is invalid for stage {stage}")

    optional = {
        field: _clean_optional_event_text(value.get(field, ""), field)
        for field in ("source_type", "source_name", "reason", "duplicate_of", "study_id")
    }
    if stage == "identification":
        if optional["source_type"] not in _SOURCE_TYPES:
            raise ValueError(
                "identification source_type must be database, register, or other_method"
            )
        if not optional["source_name"]:
            raise ValueError("identification requires source_name")
    if stage == "deduplication" and decision == "duplicate" and not optional["duplicate_of"]:
        raise ValueError("duplicate decision requires duplicate_of")
    if stage == "deduplication" and decision == "removed_other" and not optional["reason"]:
        raise ValueError("removed_other decision requires reason")
    if stage == "retrieval" and decision == "not_retrieved" and not optional["reason"]:
        raise ValueError("not_retrieved decision requires reason")
    if stage == "full_text" and decision == "exclude" and not optional["reason"]:
        raise ValueError("full_text exclusion requires reason")
    if stage == "full_text" and decision == "include" and not optional["study_id"]:
        raise ValueError("full_text inclusion requires study_id")

    return ScreeningEvent(
        record_id=record_id,
        stage=stage,
        decision=decision,
        reviewer=reviewer,
        decision_date=decision_date,
        is_final=is_final,
        **optional,
    )


def _clean_optional_event_text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return " ".join(value.split())


def derive_prisma_counts(
    records: Iterable[ScreeningEvent | Mapping[str, Any]],
    *,
    accountable_reviewers: Sequence[str],
    require_complete: bool = True,
    require_independent_humans: bool = True,
) -> dict[str, Any]:
    """Derive PRISMA 2020 flow counts from final, record-level decisions.

    Non-final reviewer rows are retained for audit purposes but ignored for
    counting.  Each record and stage must have at most one final/adjudicated row.
    With ``require_complete=True``, every retained record must reach the next
    applicable stage, so omissions cannot silently make the diagram balance.
    """

    reviewer_names = _normalize_reviewer_names(accountable_reviewers)
    reviewer_lookup = {value.casefold(): value for value in reviewer_names}
    if not isinstance(records, Iterable) or isinstance(records, (str, bytes, Mapping)):
        raise ValueError("screening records must be an iterable of record objects")
    events: list[ScreeningEvent] = []
    for index, value in enumerate(records):
        if isinstance(value, ScreeningEvent):
            event = _screening_event_from_mapping(asdict(value), index)
        else:
            event = _screening_event_from_mapping(value, index)
        if event.reviewer.casefold() not in reviewer_lookup:
            raise ValueError(
                f"screening reviewer must be an accountable human: {event.reviewer}"
            )
        events.append(event)
    if not events:
        raise ValueError("screening records must not be empty")

    final: dict[tuple[str, str], ScreeningEvent] = {}
    for event in events:
        if not event.is_final:
            continue
        key = (event.record_id.casefold(), event.stage)
        if key in final:
            raise ValueError(
                f"multiple final decisions for record {event.record_id} at stage {event.stage}"
            )
        final[key] = event

    if require_independent_humans:
        independent: dict[tuple[str, str], dict[str, ScreeningEvent]] = {}
        for event in events:
            if event.is_final or event.stage not in {"title_abstract", "full_text"}:
                continue
            key = (event.record_id.casefold(), event.stage)
            reviewer_key = event.reviewer.casefold()
            decisions = independent.setdefault(key, {})
            if reviewer_key in decisions:
                raise ValueError(
                    f"multiple independent decisions by {event.reviewer} for "
                    f"record {event.record_id} at stage {event.stage}"
                )
            decisions[reviewer_key] = event
        for key, final_event in final.items():
            if final_event.stage not in {"title_abstract", "full_text"}:
                continue
            decisions = independent.get(key, {})
            if len(decisions) < 2:
                raise ValueError(
                    f"record {final_event.record_id} at {final_event.stage} lacks two independent human decisions"
                )
            unique_decisions = {value.decision for value in decisions.values()}
            if len(unique_decisions) == 1 and final_event.decision not in unique_decisions:
                raise ValueError(
                    f"final decision for record {final_event.record_id} at {final_event.stage} "
                    "contradicts unanimous independent decisions"
                )

    by_stage: dict[str, dict[str, ScreeningEvent]] = {
        stage: {} for stage in _SCREENING_DECISIONS
    }
    for (record_key, stage), event in final.items():
        by_stage[stage][record_key] = event

    identified = by_stage["identification"]
    if not identified:
        raise ValueError("at least one final identification event is required")
    identified_ids = set(identified)
    for stage, stage_events in by_stage.items():
        unknown_ids = set(stage_events) - identified_ids
        if unknown_ids:
            raise ValueError(
                f"{stage} contains records without identification events: "
                + ", ".join(sorted(unknown_ids))
            )

    deduplication = by_stage["deduplication"]
    if require_complete and set(deduplication) != identified_ids:
        _raise_stage_coverage_error("deduplication", identified_ids, set(deduplication))
    retained_ids = {
        key for key, event in deduplication.items() if event.decision == "retained"
    }
    removed_ids = set(deduplication) - retained_ids
    for record_key, event in deduplication.items():
        if event.decision != "duplicate":
            continue
        duplicate_target = event.duplicate_of.casefold()
        if duplicate_target == record_key:
            raise ValueError(f"record {event.record_id} cannot be a duplicate of itself")
        if duplicate_target not in identified_ids:
            raise ValueError(
                f"duplicate target {event.duplicate_of} has no identification event"
            )
        target_decision = deduplication.get(duplicate_target)
        if target_decision is None or target_decision.decision != "retained":
            raise ValueError(
                f"duplicate target {event.duplicate_of} must have a retained decision"
            )

    downstream_stages = ("title_abstract", "retrieval", "full_text")
    for stage in downstream_stages:
        invalid = set(by_stage[stage]) & removed_ids
        if invalid:
            raise ValueError(
                f"removed records cannot proceed to {stage}: " + ", ".join(sorted(invalid))
            )

    title_abstract = by_stage["title_abstract"]
    invalid_title_abstract = set(title_abstract) - retained_ids
    if invalid_title_abstract:
        raise ValueError(
            "only retained records may proceed to title_abstract: "
            + ", ".join(sorted(invalid_title_abstract))
        )
    if require_complete and set(title_abstract) != retained_ids:
        _raise_stage_coverage_error("title_abstract", retained_ids, set(title_abstract))
    screened_ids = set(title_abstract)
    title_included = {
        key for key, event in title_abstract.items() if event.decision == "include"
    }
    title_excluded = screened_ids - title_included

    retrieval = by_stage["retrieval"]
    invalid_retrieval = set(retrieval) - title_included
    if invalid_retrieval:
        raise ValueError(
            "only title/abstract inclusions may proceed to retrieval: "
            + ", ".join(sorted(invalid_retrieval))
        )
    if require_complete and set(retrieval) != title_included:
        _raise_stage_coverage_error("retrieval", title_included, set(retrieval))
    retrieved = {key for key, event in retrieval.items() if event.decision == "retrieved"}
    not_retrieved = set(retrieval) - retrieved

    full_text = by_stage["full_text"]
    invalid_full_text = set(full_text) - retrieved
    if invalid_full_text:
        raise ValueError(
            "only retrieved reports may proceed to full_text: "
            + ", ".join(sorted(invalid_full_text))
        )
    if require_complete and set(full_text) != retrieved:
        _raise_stage_coverage_error("full_text", retrieved, set(full_text))
    full_text_included = {
        key for key, event in full_text.items() if event.decision == "include"
    }
    full_text_excluded = set(full_text) - full_text_included

    exclusion_reasons: dict[str, int] = {}
    for key in full_text_excluded:
        reason = full_text[key].reason
        exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
    studies = {full_text[key].study_id.casefold() for key in full_text_included}

    source_type_counts = {
        source_type: sum(
            1 for event in identified.values() if event.source_type == source_type
        )
        for source_type in sorted(_SOURCE_TYPES)
    }
    source_name_counts: dict[str, int] = {}
    for event in identified.values():
        source_name_counts[event.source_name] = source_name_counts.get(event.source_name, 0) + 1

    decision_counts = {
        decision: sum(1 for event in deduplication.values() if event.decision == decision)
        for decision in _SCREENING_DECISIONS["deduplication"]
    }
    flow_complete = (
        set(deduplication) == identified_ids
        and set(title_abstract) == retained_ids
        and set(retrieval) == title_included
        and set(full_text) == retrieved
    )
    return {
        "records_identified_from_databases": source_type_counts["database"],
        "records_identified_from_registers": source_type_counts["register"],
        "records_identified_via_other_methods": source_type_counts["other_method"],
        "total_records_identified": len(identified),
        "records_removed_before_screening_as_duplicates": decision_counts["duplicate"],
        "records_removed_before_screening_by_automation_tools": decision_counts[
            "removed_by_automation"
        ],
        "records_removed_before_screening_for_other_reasons": decision_counts[
            "removed_other"
        ],
        "records_after_removals": len(retained_ids),
        "records_screened": len(screened_ids),
        "records_excluded": len(title_excluded),
        "reports_sought_for_retrieval": len(title_included),
        "reports_not_retrieved": len(not_retrieved),
        "reports_assessed_for_eligibility": len(full_text),
        "reports_excluded": len(full_text_excluded),
        "reports_excluded_by_reason": {
            key: exclusion_reasons[key]
            for key in sorted(exclusion_reasons, key=str.casefold)
        },
        "reports_of_included_studies": len(full_text_included),
        "studies_included_in_review": len(studies),
        "identification_by_source": {
            key: source_name_counts[key] for key in sorted(source_name_counts, key=str.casefold)
        },
        "nonfinal_decisions_ignored": sum(1 for event in events if not event.is_final),
        "complete": flow_complete,
        "completion_required": require_complete,
        "independent_human_screening_validated": require_independent_humans,
    }


def _raise_stage_coverage_error(stage: str, expected: set[str], actual: set[str]) -> None:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    details = []
    if missing:
        details.append("missing " + ", ".join(missing))
    if extra:
        details.append("unexpected " + ", ".join(extra))
    raise ValueError(f"incomplete {stage} coverage: " + "; ".join(details))


def derive_prior_counts(
    records: Iterable[Mapping[str, Any]],
    *,
    accountable_reviewers: Sequence[str],
    require_complete: bool = True,
    require_independent_humans: bool = True,
) -> dict[str, Any]:
    """Derive an overview-of-reviews selection flow from review-level events.

    Full-text inclusions use ``review_id`` rather than ``study_id``.  The
    underlying record/report arithmetic is shared with the tested PRISMA flow,
    while the included evidence-unit labels and reporting truth boundary are
    specific to PRIOR/umbrella reviews.
    """

    if not isinstance(records, Iterable) or isinstance(records, (str, bytes, Mapping)):
        raise ValueError("review screening records must be an iterable of objects")
    transformed: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, Mapping):
            raise ValueError(f"review screening record {index} must be an object")
        value = dict(raw)
        review_id = value.pop("review_id", "")
        if "study_id" in value and value.get("study_id"):
            raise ValueError("PRIOR review-level events must use review_id, not study_id")
        if value.get("stage") == "full_text" and value.get("decision") == "include":
            if not isinstance(review_id, str) or not review_id.strip():
                raise ValueError("full_text review inclusion requires review_id")
            value["study_id"] = review_id
        elif review_id:
            raise ValueError("review_id is allowed only on included full_text events")
        transformed.append(value)

    result = derive_prisma_counts(
        transformed,
        accountable_reviewers=accountable_reviewers,
        require_complete=require_complete,
        require_independent_humans=require_independent_humans,
    )
    result["reports_of_included_reviews"] = result.pop(
        "reports_of_included_studies"
    )
    result["systematic_reviews_included_in_overview"] = result.pop(
        "studies_included_in_review"
    )
    result["reporting_framework"] = "PRIOR"
    result["truth_boundary"] = (
        "Flow counts describe review selection only; they do not establish review quality, "
        "primary-study independence, certainty, or permission to pool review estimates."
    )
    return result


def corrected_covered_area(
    review_to_primary_studies: Mapping[str, Iterable[str]],
    *,
    comparison: str,
    outcome: str,
    time_point: str,
) -> dict[str, Any]:
    """Build a citation matrix and calculate corrected covered area (CCA).

    CCA = (N - r) / (r * c - r), where N is the total number of primary-study
    occurrences, r is the number of unique primary studies, and c is the number
    of included reviews.  Duplicate study identifiers inside one review are
    rejected because they make the citation matrix invalid.
    """

    scope = {
        "comparison": _validated_nonempty_string(comparison, "comparison"),
        "outcome": _validated_nonempty_string(outcome, "outcome"),
        "time_point": _validated_nonempty_string(time_point, "time_point"),
    }
    if not isinstance(review_to_primary_studies, Mapping):
        raise ValueError("review_to_primary_studies must be an object")
    if len(review_to_primary_studies) < 2:
        raise ValueError("corrected covered area requires at least two reviews")

    normalized_reviews: dict[str, set[str]] = {}
    review_labels: dict[str, str] = {}
    study_labels: dict[str, str] = {}
    for raw_review_id, raw_studies in review_to_primary_studies.items():
        review_id = _validated_nonempty_string(raw_review_id, "review_id")
        review_key = review_id.casefold()
        if review_key in normalized_reviews:
            raise ValueError(f"duplicate review identifier: {review_id}")
        if isinstance(raw_studies, (str, bytes, Mapping)) or not isinstance(
            raw_studies, Iterable
        ):
            raise ValueError(f"primary studies for {review_id} must be an iterable")
        study_keys: set[str] = set()
        for raw_study_id in raw_studies:
            study_id = _validated_nonempty_string(raw_study_id, "primary_study_id")
            study_key = study_id.casefold()
            if study_key in study_keys:
                raise ValueError(
                    f"review {review_id} contains duplicate primary study {study_id}"
                )
            study_keys.add(study_key)
            study_labels.setdefault(study_key, study_id)
        if not study_keys:
            raise ValueError(f"review {review_id} must contain at least one primary study")
        normalized_reviews[review_key] = study_keys
        review_labels[review_key] = review_id

    review_keys = sorted(normalized_reviews, key=lambda key: review_labels[key].casefold())
    study_keys = sorted(study_labels, key=lambda key: study_labels[key].casefold())
    review_count = len(review_keys)
    unique_studies = len(study_keys)
    total_occurrences = sum(len(value) for value in normalized_reviews.values())
    overlap_excess = total_occurrences - unique_studies
    maximum_overlap_excess = unique_studies * review_count - unique_studies
    if maximum_overlap_excess <= 0:
        raise ValueError("corrected covered area denominator must be positive")
    cca = overlap_excess / maximum_overlap_excess
    percent = cca * 100

    if percent <= 5:
        interpretation = "slight"
    elif percent <= 10:
        interpretation = "moderate"
    elif percent <= 15:
        interpretation = "high"
    else:
        interpretation = "very_high"

    matrix = [
        [1 if study_key in normalized_reviews[review_key] else 0 for review_key in review_keys]
        for study_key in study_keys
    ]
    return {
        "scope": scope,
        "review_count": review_count,
        "unique_primary_studies": unique_studies,
        "total_study_occurrences": total_occurrences,
        "overlap_excess": overlap_excess,
        "maximum_overlap_excess": maximum_overlap_excess,
        "corrected_covered_area": cca,
        "corrected_covered_area_percent": percent,
        "interpretation": interpretation,
        "review_ids": [review_labels[key] for key in review_keys],
        "primary_study_ids": [study_labels[key] for key in study_keys],
        "citation_matrix": matrix,
        "caution": "CCA measures structural overlap, not evidence quality or certainty.",
    }


__all__ = [
    "IntakeValidationError",
    "ReviewWorkflow",
    "SUPPORTED_REVIEW_TYPES",
    "ScreeningEvent",
    "TopicIntake",
    "build_project_manifest",
    "corrected_covered_area",
    "derive_prisma_counts",
    "derive_prior_counts",
    "required_evidence_for_stage",
    "validate_topic_intake",
]

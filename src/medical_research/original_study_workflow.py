"""Auditable workflow primitives for an original clinical study or thesis.

This module validates intake, builds a deterministic scaffold, and enforces
human, evidence-gated transitions.  It never infers regulatory decisions,
creates approvals, collects data, or interprets results.  An evidence reference
only proves that a caller supplied a traceable reference; it does not prove the
referenced record is authentic or sufficient.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
import unicodedata
from typing import Any


SUPPORTED_STUDY_FAMILIES = ("observational", "interventional")
REGISTRATION_OPTIONS = ("required", "not_required")


class OriginalStudyIntakeError(ValueError):
    """Raised when an original-study intake is incomplete or inconsistent."""

    def __init__(self, errors: Sequence[str]):
        self.errors = tuple(errors)
        super().__init__("invalid original-study intake: " + "; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class OriginalStudyIntake:
    """Normalized professional intake; no approval or result fields belong here."""

    study_family: str
    working_title: str
    research_question: str
    rationale: str
    primary_objective: str
    secondary_objectives: tuple[str, ...]
    study_design: str
    design_rationale: str
    population: str
    setting: str
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    intervention_or_exposure: str
    comparison_strategy: str
    primary_outcome: str
    secondary_outcomes: tuple[str, ...]
    data_source_and_recruitment: str
    sample_size_basis: str
    feasibility_summary: str
    analysis_overview: str
    reporting_framework: str
    ethics_jurisdiction: str
    registration_applicability: str
    registration_basis: str
    sponsor_or_institution: str
    accountable_humans: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "secondary_objectives",
            "inclusion_criteria",
            "exclusion_criteria",
            "secondary_outcomes",
            "accountable_humans",
        ):
            value[key] = list(value[key])
        return value


_INTAKE_FIELDS = {
    "study_family",
    "working_title",
    "research_question",
    "rationale",
    "primary_objective",
    "secondary_objectives",
    "study_design",
    "design_rationale",
    "population",
    "setting",
    "inclusion_criteria",
    "exclusion_criteria",
    "intervention_or_exposure",
    "comparison_strategy",
    "primary_outcome",
    "secondary_outcomes",
    "data_source_and_recruitment",
    "sample_size_basis",
    "feasibility_summary",
    "analysis_overview",
    "reporting_framework",
    "ethics_jurisdiction",
    "registration_applicability",
    "registration_basis",
    "sponsor_or_institution",
    "accountable_humans",
}

_REQUIRED_TEXT_FIELDS = (
    "working_title",
    "research_question",
    "rationale",
    "primary_objective",
    "study_design",
    "design_rationale",
    "population",
    "setting",
    "intervention_or_exposure",
    "comparison_strategy",
    "primary_outcome",
    "data_source_and_recruitment",
    "sample_size_basis",
    "feasibility_summary",
    "analysis_overview",
    "reporting_framework",
    "ethics_jurisdiction",
    "registration_basis",
    "sponsor_or_institution",
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

_NONHUMAN_NAME_PATTERN = re.compile(
    r"(?:\bai\b|\bbot\b|\bgpt(?:-?\d+)?\b|chatgpt|openai|codex|"
    r"artificial intelligence|large language model|language model|ai assistant|"
    r"claude ai|gemini ai)",
    flags=re.IGNORECASE,
)

_GENERIC_HUMAN_LABELS = {
    "investigator one",
    "investigator two",
    "person one",
    "person two",
    "researcher one",
    "researcher two",
    "reviewer one",
    "reviewer two",
    "supervisor one",
    "supervisor two",
}


def _clean_text(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str):
        errors.append(f"{field} must be a string")
        return ""
    cleaned = " ".join(value.split())
    if not cleaned:
        errors.append(f"{field} is required")
    elif cleaned.casefold() in _PLACEHOLDERS:
        errors.append(f"{field} contains a placeholder")
    return cleaned


def _clean_text_list(
    value: Any,
    field: str,
    errors: list[str],
    *,
    minimum: int,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        errors.append(f"{field} must be an array")
        return ()
    cleaned: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _clean_text(item, f"{field}[{index}]", errors)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            errors.append(f"{field} contains a duplicate value: {text}")
            continue
        seen.add(key)
        cleaned.append(text)
    if len(cleaned) < minimum:
        errors.append(f"{field} requires at least {minimum} distinct value(s)")
    return tuple(cleaned)


def _looks_like_named_human(value: str) -> bool:
    folded = value.casefold()
    if folded in _GENERIC_HUMAN_LABELS:
        return False
    words = re.findall(r"[^\W\d_]+", folded, flags=re.UNICODE)
    if len(words) < 2:
        return False
    return not _NONHUMAN_NAME_PATTERN.search(value)


def validate_original_study_intake(
    payload: Mapping[str, Any],
) -> OriginalStudyIntake:
    """Validate and normalize a proposed observational or interventional study.

    Registration applicability, design choice, and ethical jurisdiction are
    supplied by accountable people; this function deliberately does not infer
    them from the title or intervention.
    """

    if not isinstance(payload, Mapping):
        raise OriginalStudyIntakeError(("intake must be an object",))

    errors: list[str] = []
    unknown = sorted(set(payload) - _INTAKE_FIELDS)
    if unknown:
        errors.append("unknown fields: " + ", ".join(unknown))

    family = _clean_text(payload.get("study_family"), "study_family", errors)
    if family and family not in SUPPORTED_STUDY_FAMILIES:
        errors.append(
            "study_family must be one of: " + ", ".join(SUPPORTED_STUDY_FAMILIES)
        )
    registration = _clean_text(
        payload.get("registration_applicability"),
        "registration_applicability",
        errors,
    )
    if registration and registration not in REGISTRATION_OPTIONS:
        errors.append(
            "registration_applicability must be one of: "
            + ", ".join(REGISTRATION_OPTIONS)
        )

    texts = {
        field: _clean_text(payload.get(field), field, errors)
        for field in _REQUIRED_TEXT_FIELDS
    }
    secondary_objectives = _clean_text_list(
        payload.get("secondary_objectives", []),
        "secondary_objectives",
        errors,
        minimum=0,
    )
    inclusion = _clean_text_list(
        payload.get("inclusion_criteria"), "inclusion_criteria", errors, minimum=1
    )
    exclusion = _clean_text_list(
        payload.get("exclusion_criteria"), "exclusion_criteria", errors, minimum=1
    )
    secondary_outcomes = _clean_text_list(
        payload.get("secondary_outcomes", []),
        "secondary_outcomes",
        errors,
        minimum=0,
    )
    humans = _clean_text_list(
        payload.get("accountable_humans"),
        "accountable_humans",
        errors,
        minimum=2,
    )

    for human in humans:
        if not _looks_like_named_human(human):
            errors.append(
                "accountable_humans must contain named people, not roles or AI systems: "
                + human
            )

    if texts["working_title"] and not 12 <= len(texts["working_title"]) <= 300:
        errors.append("working_title must contain 12 to 300 characters")
    for field in (
        "research_question",
        "rationale",
        "primary_objective",
        "design_rationale",
        "sample_size_basis",
        "feasibility_summary",
        "analysis_overview",
        "registration_basis",
    ):
        if texts[field] and len(texts[field]) < 20:
            errors.append(f"{field} must contain at least 20 characters")

    overlap = {value.casefold() for value in inclusion} & {
        value.casefold() for value in exclusion
    }
    if overlap:
        errors.append("the same criterion cannot be both included and excluded")
    if texts["primary_outcome"].casefold() in {
        value.casefold() for value in secondary_outcomes
    }:
        errors.append("primary_outcome must not be repeated in secondary_outcomes")

    if errors:
        raise OriginalStudyIntakeError(errors)

    return OriginalStudyIntake(
        study_family=family,
        working_title=texts["working_title"],
        research_question=texts["research_question"],
        rationale=texts["rationale"],
        primary_objective=texts["primary_objective"],
        secondary_objectives=secondary_objectives,
        study_design=texts["study_design"],
        design_rationale=texts["design_rationale"],
        population=texts["population"],
        setting=texts["setting"],
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        intervention_or_exposure=texts["intervention_or_exposure"],
        comparison_strategy=texts["comparison_strategy"],
        primary_outcome=texts["primary_outcome"],
        secondary_outcomes=secondary_outcomes,
        data_source_and_recruitment=texts["data_source_and_recruitment"],
        sample_size_basis=texts["sample_size_basis"],
        feasibility_summary=texts["feasibility_summary"],
        analysis_overview=texts["analysis_overview"],
        reporting_framework=texts["reporting_framework"],
        ethics_jurisdiction=texts["ethics_jurisdiction"],
        registration_applicability=registration,
        registration_basis=texts["registration_basis"],
        sponsor_or_institution=texts["sponsor_or_institution"],
        accountable_humans=humans,
    )


_COMMON_START = (
    "topic_intake",
    "feasibility",
    "protocol",
    "ethics_and_governance",
    "registration_assessment",
)

_COMMON_END = (
    "data_dictionary",
    "statistical_analysis_plan",
    "study_conduct_and_data_capture",
    "data_lock",
    "analysis",
    "reporting",
    "quality_assurance",
    "release",
    "completed",
)

_STAGE_GATES: dict[str, tuple[str, ...]] = {
    "topic_intake": ("validated_intake", "accountable_humans_confirmed"),
    "feasibility": (
        "data_access_or_recruitment_assessment",
        "resources_and_timeline_assessment",
        "sample_size_basis_review",
        "human_feasibility_signoff",
    ),
    "protocol": (
        "frozen_protocol",
        "design_rationale_record",
        "eligibility_and_outcomes_record",
        "human_methods_signoff",
    ),
    "ethics_and_governance": (
        "ethics_or_exemption_determination",
        "governance_authorization",
        "conditions_and_restrictions_record",
        "human_governance_signoff",
    ),
    "registration_assessment": (
        "registration_applicability_assessment",
        "registration_basis_record",
        "human_registration_signoff",
    ),
    "registration": (
        "registry_identifier_record",
        "registration_timestamp_record",
        "prospective_status_record",
        "human_registration_signoff",
    ),
    "observational_bias_control_plan": (
        "selection_and_measurement_bias_plan",
        "confounding_strategy",
        "missing_data_plan",
        "human_methods_signoff",
    ),
    "intervention_and_safety_plan": (
        "intervention_specification",
        "allocation_or_assignment_record",
        "safety_monitoring_applicability_record",
        "human_clinical_signoff",
    ),
    "data_dictionary": (
        "versioned_variable_dictionary",
        "coding_and_units_record",
        "source_provenance_plan",
        "human_data_signoff",
    ),
    "statistical_analysis_plan": (
        "frozen_statistical_analysis_plan",
        "primary_analysis_specification",
        "missingness_and_multiplicity_plan",
        "human_statistical_signoff",
    ),
    "study_conduct_and_data_capture": (
        "source_data_inventory",
        "recruitment_or_case_ascertainment_record",
        "monitoring_and_query_log",
        "deviation_log",
        "human_conduct_signoff",
    ),
    "data_lock": (
        "lock_authorization",
        "locked_dataset_checksum",
        "unresolved_query_record",
        "human_data_lock_signoff",
    ),
    "analysis": (
        "executable_analysis_reference",
        "software_environment_record",
        "results_output",
        "sap_deviation_record",
        "independent_analysis_verification",
    ),
    "reporting": (
        "manuscript_source",
        "reporting_checklist",
        "participant_flow_traceability",
        "claims_to_results_traceability",
        "human_reporting_signoff",
    ),
    "quality_assurance": (
        "methods_review",
        "statistical_review",
        "clinical_review",
        "data_and_citation_audit",
        "human_qa_signoff",
    ),
    "release": (
        "release_authorization",
        "authorship_funding_conflicts_record",
        "final_package_checksum",
        "independent_human_release_signoff",
    ),
}


def _pipeline_for(intake: OriginalStudyIntake) -> tuple[str, ...]:
    middle: tuple[str, ...] = ()
    if intake.registration_applicability == "required":
        middle += ("registration",)
    middle += (
        "observational_bias_control_plan"
        if intake.study_family == "observational"
        else "intervention_and_safety_plan",
    )
    return _COMMON_START + middle + _COMMON_END


def required_original_evidence_for_stage(stage: str) -> tuple[str, ...]:
    """Return evidence keys needed to complete a nonterminal workflow stage."""

    if stage not in _STAGE_GATES:
        raise ValueError(f"stage has no completion gate: {stage}")
    return _STAGE_GATES[stage]


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be JSON-serializable") from exc


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return (slug or "original-clinical-study")[:64].rstrip("-")


def _manifest_files(intake: OriginalStudyIntake) -> list[dict[str, Any]]:
    files: list[tuple[str, str, bool]] = [
        ("manifest.json", "Frozen scaffold and intake fingerprint", False),
        ("project-state.json", "Serializable workflow state", True),
        ("audit/gate-transitions.jsonl", "Derived evidence-gate transition log", True),
        ("protocol/topic_intake.json", "Validated original-study intake", False),
        ("feasibility/assessment.md", "Human-reviewed feasibility assessment", True),
        ("protocol/protocol.md", "Dated, versioned study protocol", True),
        ("protocol/amendments.jsonl", "Prospective amendments and deviations", True),
        (
            "governance/ethics_and_governance.json",
            "Recorded ethics and governance determinations and references",
            True,
        ),
        (
            "governance/source_documents_inventory.csv",
            "Inventory of authorization source records, not invented approvals",
            True,
        ),
        (
            "registration/assessment.json",
            "Human registration-applicability assessment",
            True,
        ),
        ("data/data_dictionary.csv", "Versioned variables, coding, units, and roles", True),
        ("data/provenance.jsonl", "Source and transformation provenance", True),
        ("data/query_log.jsonl", "Data clarification and resolution audit trail", True),
        (
            "analysis/statistical_analysis_plan.md",
            "Prespecified, versioned statistical analysis plan",
            True,
        ),
        (
            "conduct/recruitment_or_case_ascertainment.csv",
            "Participant recruitment or case-ascertainment ledger",
            True,
        ),
        ("conduct/deviations.jsonl", "Protocol and conduct deviations", True),
        ("data_lock/lock_record.json", "Authorized lock and dataset checksum", True),
        ("analysis/environment.json", "Reproducible software environment", True),
        ("analysis/results.json", "Verified analysis outputs", True),
        ("reporting/manuscript.md", "Results-traceable manuscript source", True),
        ("reporting/checklist.csv", "Design-appropriate reporting framework", True),
        ("qa/release_gate.json", "Independent QA and human release decisions", True),
    ]
    if intake.registration_applicability == "required":
        files.append(
            (
                "registration/registry_record.json",
                "Registry identifier, dates, and recorded prospective status",
                True,
            )
        )
    if intake.study_family == "observational":
        files.append(
            (
                "methods/observational_bias_control_plan.md",
                "Design-specific bias and confounding control plan",
                True,
            )
        )
    else:
        files.append(
            (
                "methods/intervention_and_safety_plan.md",
                "Intervention, assignment, fidelity, and safety applicability plan",
                True,
            )
        )
    return [
        {"path": path, "purpose": purpose, "mutable": mutable}
        for path, purpose, mutable in sorted(files, key=lambda item: item[0])
    ]


def build_original_study_manifest(
    intake: OriginalStudyIntake | Mapping[str, Any],
) -> dict[str, Any]:
    """Build the same content-addressed scaffold for the same normalized intake."""

    normalized = validate_original_study_intake(
        intake.to_dict() if isinstance(intake, OriginalStudyIntake) else intake
    )
    intake_dict = normalized.to_dict()
    fingerprint = sha256(_canonical_json(intake_dict).encode("utf-8")).hexdigest()
    files = _manifest_files(normalized)
    directories = sorted(
        {
            item["path"].rsplit("/", 1)[0]
            for item in files
            if "/" in item["path"]
        }
    )
    return {
        "schema_version": "1.0",
        "project_id": f"OS-{fingerprint[:12].upper()}",
        "topic_fingerprint_sha256": fingerprint,
        "slug": _slugify(normalized.working_title),
        "study_family": normalized.study_family,
        "registration_applicability": normalized.registration_applicability,
        "pipeline": list(_pipeline_for(normalized)),
        "directories": directories,
        "files": files,
        "integrity_rules": [
            "regulatory statuses are transcribed from referenced human records, never inferred",
            "protocol and statistical analysis plan precede data lock and analysis",
            "data lock requires an authorized record and a content checksum",
            "all conclusions remain traceable to verified data and accountable humans",
            "identifiable participant data and confidential approvals do not enter a public repository",
        ],
        "truth_boundary": (
            "The scaffold validates references and sequencing only; it does not authenticate "
            "approvals, registries, source data, analyses, or clinical claims."
        ),
    }


def _validated_iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc
    if parsed > date.today():
        raise ValueError(f"{field} cannot be in the future")
    return parsed.isoformat()


_EVIDENCE_FIELDS = {"artifact", "sha256", "verified_by", "verified_on", "note"}

_DUAL_VERIFIER_GATES = {
    "accountable_humans_confirmed",
    "human_feasibility_signoff",
    "human_methods_signoff",
    "human_governance_signoff",
    "human_registration_signoff",
    "human_data_signoff",
    "human_statistical_signoff",
    "human_conduct_signoff",
    "human_data_lock_signoff",
    "independent_analysis_verification",
    "human_reporting_signoff",
    "human_qa_signoff",
    "independent_human_release_signoff",
}


def _normalize_original_evidence(
    evidence: Mapping[str, Any],
    *,
    required: Sequence[str],
    accountable_humans: Sequence[str],
    decision_date: str,
) -> dict[str, dict[str, Any]]:
    if set(evidence) != set(required):
        missing = sorted(set(required) - set(evidence))
        unexpected = sorted(set(evidence) - set(required))
        details: list[str] = []
        if missing:
            details.append("missing evidence references: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected evidence keys: " + ", ".join(unexpected))
        raise ValueError("; ".join(details))
    human_lookup = {value.casefold(): value for value in accountable_humans}
    normalized: dict[str, dict[str, Any]] = {}
    for gate in required:
        value = evidence[gate]
        if not isinstance(value, Mapping):
            raise ValueError(
                f"{gate} evidence must contain artifact, sha256, verified_by, and verified_on"
            )
        unknown = sorted(set(value) - _EVIDENCE_FIELDS)
        if unknown:
            raise ValueError(f"{gate} evidence has unknown fields: " + ", ".join(unknown))
        artifact = value.get("artifact")
        if not isinstance(artifact, str) or not artifact.strip():
            raise ValueError(f"{gate}.artifact must be a non-empty string")
        artifact = " ".join(artifact.split())
        path = PurePosixPath(artifact)
        if path.is_absolute() or ".." in path.parts or artifact == ".":
            raise ValueError(f"{gate}.artifact must be a safe project-relative path")
        checksum = value.get("sha256")
        if not isinstance(checksum, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", checksum
        ):
            raise ValueError(f"{gate}.sha256 must be a 64-character SHA-256 digest")
        raw_verifiers = value.get("verified_by")
        if isinstance(raw_verifiers, (str, bytes)) or not isinstance(
            raw_verifiers, Sequence
        ):
            raise ValueError(f"{gate}.verified_by must be an array")
        verifiers = tuple(" ".join(str(item).split()) for item in raw_verifiers)
        if any(not item or item.casefold() not in human_lookup for item in verifiers):
            raise ValueError(f"{gate}.verified_by must contain accountable_humans only")
        if len({item.casefold() for item in verifiers}) != len(verifiers):
            raise ValueError(f"{gate}.verified_by must contain distinct humans")
        minimum = 2 if gate in _DUAL_VERIFIER_GATES else 1
        if len(verifiers) < minimum:
            raise ValueError(f"{gate} requires at least {minimum} accountable verifier(s)")
        verified_on = _validated_iso_date(value.get("verified_on"), f"{gate}.verified_on")
        if verified_on > decision_date:
            raise ValueError(f"{gate}.verified_on cannot be after decision_date")
        note = value.get("note", "")
        if not isinstance(note, str):
            raise ValueError(f"{gate}.note must be a string")
        normalized[gate] = {
            "artifact": artifact,
            "sha256": checksum.lower(),
            "verified_by": [human_lookup[item.casefold()] for item in verifiers],
            "verified_on": verified_on,
            "note": " ".join(note.split()),
        }
    return normalized


class OriginalStudyWorkflow:
    """Forward-only workflow whose transitions require accountable human review."""

    def __init__(self, intake: OriginalStudyIntake | Mapping[str, Any]):
        self.intake = validate_original_study_intake(
            intake.to_dict() if isinstance(intake, OriginalStudyIntake) else intake
        )
        self._pipeline = _pipeline_for(self.intake)
        self._position = 0
        self._transitions: list[dict[str, Any]] = []
        self._fingerprint = sha256(
            _canonical_json(self.intake.to_dict()).encode("utf-8")
        ).hexdigest()

    @property
    def current_stage(self) -> str:
        return self._pipeline[self._position]

    @property
    def next_stage(self) -> str | None:
        if self._position + 1 == len(self._pipeline):
            return None
        return self._pipeline[self._position + 1]

    @property
    def completed(self) -> bool:
        return self.current_stage == "completed"

    def _accountable_name(self, reviewer: Any) -> str:
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("reviewer must be a named accountable human")
        cleaned = " ".join(reviewer.split())
        matches = {
            value.casefold(): value for value in self.intake.accountable_humans
        }
        if cleaned.casefold() not in matches:
            raise ValueError("reviewer must be one of the named accountable_humans")
        return matches[cleaned.casefold()]

    def advance(
        self,
        evidence: Mapping[str, Any],
        *,
        reviewer: str,
        decision_date: str,
        to_stage: str | None = None,
    ) -> dict[str, Any]:
        """Complete exactly one stage using structured, caller-supplied references."""

        if self.completed:
            raise RuntimeError("completed workflow cannot be advanced")
        expected = self.next_stage
        if to_stage is not None and to_stage != expected:
            raise ValueError(f"invalid transition: expected {expected}, received {to_stage}")
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence must be an object")
        if any(not isinstance(key, str) or not key for key in evidence):
            raise ValueError("evidence keys must be non-empty strings")
        accountable_reviewer = self._accountable_name(reviewer)
        normalized_date = _validated_iso_date(decision_date, "decision_date")
        if self._transitions and normalized_date < self._transitions[-1]["decision_date"]:
            raise ValueError("decision_date cannot precede the previous transition")

        required = required_original_evidence_for_stage(self.current_stage)
        try:
            normalized_evidence = _normalize_original_evidence(
                evidence,
                required=required,
                accountable_humans=self.intake.accountable_humans,
                decision_date=normalized_date,
            )
        except ValueError as exc:
            raise ValueError(f"cannot complete {self.current_stage}; {exc}") from exc
        evidence_json = _canonical_json(normalized_evidence)
        transition = {
            "from_stage": self.current_stage,
            "to_stage": expected,
            "reviewer": accountable_reviewer,
            "decision_date": normalized_date,
            "evidence_keys": sorted(evidence),
            "evidence_fingerprint_sha256": sha256(
                evidence_json.encode("utf-8")
            ).hexdigest(),
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

    def snapshot(self) -> dict[str, Any]:
        """Return JSON-serializable state that can be stored and resumed."""

        return {
            "schema_version": "1.0",
            "topic_fingerprint_sha256": self._fingerprint,
            "study_family": self.intake.study_family,
            "registration_applicability": self.intake.registration_applicability,
            "pipeline": list(self._pipeline),
            "current_stage": self.current_stage,
            "next_stage": self.next_stage,
            "completed": self.completed,
            "completed_stages": list(self._pipeline[: self._position]),
            "transitions": deepcopy(self._transitions),
        }

    @classmethod
    def from_snapshot(
        cls,
        intake: OriginalStudyIntake | Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> "OriginalStudyWorkflow":
        """Restore structurally valid state for the same intake fingerprint."""

        workflow = cls(intake)
        if not isinstance(snapshot, Mapping):
            raise ValueError("snapshot must be an object")
        if snapshot.get("schema_version") != "1.0":
            raise ValueError("unsupported snapshot schema_version")
        if snapshot.get("topic_fingerprint_sha256") != workflow._fingerprint:
            raise ValueError("snapshot does not belong to this intake")
        if snapshot.get("study_family") != workflow.intake.study_family:
            raise ValueError("snapshot study_family does not match this intake")
        if snapshot.get("registration_applicability") != (
            workflow.intake.registration_applicability
        ):
            raise ValueError("snapshot registration route does not match this intake")
        if snapshot.get("pipeline") != list(workflow._pipeline):
            raise ValueError("snapshot pipeline does not match this intake")
        transitions = snapshot.get("transitions")
        if not isinstance(transitions, list) or len(transitions) >= len(workflow._pipeline):
            raise ValueError("snapshot transitions are invalid")
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
        for index, transition in enumerate(transitions):
            if not isinstance(transition, Mapping):
                raise ValueError("snapshot transition must be an object")
            if set(transition) != transition_fields:
                raise ValueError("snapshot transition fields are invalid")
            expected_from = workflow._pipeline[index]
            expected_to = workflow._pipeline[index + 1]
            if transition.get("from_stage") != expected_from or transition.get(
                "to_stage"
            ) != expected_to:
                raise ValueError("snapshot contains a nonsequential transition")
            reviewer = workflow._accountable_name(transition.get("reviewer"))
            decision_date = _validated_iso_date(
                transition.get("decision_date"), "decision_date"
            )
            if previous_date and decision_date < previous_date:
                raise ValueError("snapshot transition dates are not monotonic")
            required = required_original_evidence_for_stage(expected_from)
            raw_evidence = transition.get("evidence")
            if not isinstance(raw_evidence, Mapping):
                raise ValueError("snapshot transition evidence must be an object")
            evidence = _normalize_original_evidence(
                raw_evidence,
                required=required,
                accountable_humans=workflow.intake.accountable_humans,
                decision_date=decision_date,
            )
            evidence_keys = sorted(evidence)
            if transition.get("evidence_keys") != evidence_keys:
                raise ValueError("snapshot transition evidence keys do not reconcile")
            evidence_fingerprint = sha256(
                _canonical_json(evidence).encode("utf-8")
            ).hexdigest()
            if transition.get("evidence_fingerprint_sha256") != evidence_fingerprint:
                raise ValueError("snapshot evidence fingerprint is invalid")
            if transition.get("previous_transition_sha256") != previous_hash:
                raise ValueError("snapshot transition hash chain is invalid")
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
            if transition.get("transition_sha256") != transition_hash:
                raise ValueError("snapshot transition hash is invalid")
            normalized_transition["transition_sha256"] = transition_hash
            workflow._transitions.append(normalized_transition)
            previous_hash = transition_hash
            previous_date = decision_date
        workflow._position = len(workflow._transitions)
        if snapshot.get("current_stage") != workflow.current_stage:
            raise ValueError("snapshot current_stage is inconsistent")
        if snapshot.get("next_stage") != workflow.next_stage:
            raise ValueError("snapshot next_stage is inconsistent")
        if snapshot.get("completed") is not workflow.completed:
            raise ValueError("snapshot completed flag is inconsistent")
        if snapshot.get("completed_stages") != list(
            workflow._pipeline[: workflow._position]
        ):
            raise ValueError("snapshot completed_stages are inconsistent")
        return workflow


__all__ = [
    "OriginalStudyIntake",
    "OriginalStudyIntakeError",
    "OriginalStudyWorkflow",
    "REGISTRATION_OPTIONS",
    "SUPPORTED_STUDY_FAMILIES",
    "build_original_study_manifest",
    "required_original_evidence_for_stage",
    "validate_original_study_intake",
]

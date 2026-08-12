#!/usr/bin/env python3
"""Validate structural, provenance, semantic, and readiness guardrails of a research pack."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
WORDS = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?")
MAX_JOURNAL_VERIFICATION_AGE_DAYS = 180

ALLOWED_STAGES = {"planning", "protocol_frozen", "analysis", "manuscript"}
ALLOWED_INFERENCE = {"associational", "causal", "descriptive", "predictive"}
ALLOWED_REQUIREMENT_STATUS = {"verified", "stale", "conflicting", "pending_verification"}
ALLOWED_FIT_STATUS = {"eligible", "not_eligible", "pending_verification"}
ALLOWED_SOURCE_KINDS = {
    "administrative_template",
    "authorized_full_text",
    "bibliographic_metadata",
    "official_guidance",
    "official_journal_requirements",
    "open_access_full_text",
    "user_provided",
}
ALLOWED_RIGHTS = {
    "cc0",
    "cc_by",
    "cc_by_nc",
    "metadata_only",
    "official_webpage",
    "public_domain",
    "unknown",
    "user_owned",
    "user_provided",
}
ALLOWED_USES = {
    "administrative_formatting",
    "discovery",
    "internal_planning",
    "journal_requirement",
    "metadata_only",
    "protocol_support",
    "quotation",
    "style_analysis",
}
STYLE_RIGHTS = {"cc0", "cc_by", "cc_by_nc", "public_domain", "user_owned", "user_provided"}

DESIGN_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "randomized_trial": {
        "guidelines": ("spirit 2025",),
        "title_labels": ("randomized trial", "randomised trial", "randomized controlled trial", "randomised controlled trial"),
        "protocol": ("randomization", "allocation_concealment", "blinding", "registration_plan", "intercurrent_events"),
    },
    "retrospective_cohort": {
        "guidelines": ("strobe",),
        "title_labels": ("retrospective cohort",),
        "protocol": ("exposure_definition", "comparator_definition", "selection_process", "follow_up", "bias_control", "confounders"),
    },
    "prospective_cohort": {
        "guidelines": ("strobe",),
        "title_labels": ("prospective cohort",),
        "protocol": ("exposure_definition", "comparator_definition", "selection_process", "follow_up", "bias_control", "confounders"),
    },
    "cross_sectional": {
        "guidelines": ("strobe",),
        "title_labels": ("cross-sectional", "cross sectional"),
        "protocol": ("sampling_frame", "measurement_plan", "bias_control", "confounders"),
    },
    "case_control": {
        "guidelines": ("strobe",),
        "title_labels": ("case-control", "case control"),
        "protocol": ("case_definition", "control_selection", "exposure_ascertainment", "matching", "bias_control", "confounders"),
    },
    "diagnostic_accuracy": {
        "guidelines": ("stard 2015",),
        "title_labels": ("diagnostic accuracy",),
        "protocol": ("index_test", "reference_standard", "thresholds", "participant_flow", "blinding"),
    },
    "prediction_model": {
        "guidelines": ("tripod+ai",),
        "title_labels": ("prediction model", "prediction models"),
        "protocol": ("candidate_predictors", "validation_plan", "calibration", "discrimination", "overfitting_control"),
    },
    "systematic_review": {
        "guidelines": ("prisma-p",),
        "title_labels": ("systematic review",),
        "protocol": ("search_strategy", "screening", "data_extraction", "risk_of_bias", "synthesis_plan", "registration_plan"),
    },
    "meta_analysis": {
        "guidelines": ("prisma-p",),
        "title_labels": ("systematic review", "meta-analysis", "meta analysis"),
        "protocol": ("search_strategy", "screening", "data_extraction", "risk_of_bias", "synthesis_plan", "registration_plan"),
    },
    "animal_study": {
        "guidelines": ("arrive 2.0",),
        "title_labels": ("animal study", "in vivo"),
        "protocol": ("species", "experimental_unit", "randomization", "blinding", "sample_size"),
    },
    "case_report": {
        "guidelines": ("care",),
        "title_labels": ("case report",),
        "protocol": ("consent", "timeline", "diagnostic_assessment", "intervention_description"),
    },
    "surgical_case_series": {
        "guidelines": ("process",),
        "title_labels": ("case series",),
        "protocol": ("consecutive_or_nonconsecutive", "follow_up", "intervention_description", "complications"),
    },
}

COMMON_PROTOCOL_FIELDS = (
    "version",
    "version_date",
    "primary_objective",
    "primary_outcome",
    "time_zero",
    "eligibility",
    "sample_size_justification",
    "ethics",
    "data_provenance",
)
COMMON_STATISTICS_FIELDS = (
    "analysis_population",
    "primary_estimand",
    "effect_measure",
    "primary_model",
    "missing_data",
    "multiplicity",
    "sensitivity_analyses",
    "clustering_and_repeated_measures",
    "model_diagnostics",
    "data_derivations",
    "dataset_lock",
    "protocol_deviations",
    "software",
    "objective_analysis_map",
)
SENSITIVE_KEYS = {
    "address",
    "dateofbirth",
    "dob",
    "email",
    "medicalrecordnumber",
    "mrn",
    "nationalid",
    "participantidentifier",
    "participantname",
    "patientidentifier",
    "patientname",
    "patientrecord",
    "patientrecords",
    "phone",
}
HYPE = {"breakthrough", "game-changing", "groundbreaking", "innovative", "novel", "promising", "revolutionary"}
CAUSAL = {"causes", "effect", "effects", "efficacy", "improves", "prevents", "reduces", "superior", "superiority"}
RESULT_WORDS = {"associated", "better", "improved", "improves", "increased", "reduced", "superior", "worse"}
STOPWORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "the", "to", "with"}


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def _parse_date(value: Any, path: str, errors: list[str]) -> date | None:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        errors.append(f"{path}: expected YYYY-MM-DD")
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{path}: invalid calendar date")
        return None
    if parsed > date.today():
        errors.append(f"{path}: future verification/retrieval dates are not allowed")
    return parsed


def _is_nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple)):
        return bool(value)
    return value is not None and value is not False


def _require_mapping(parent: dict[str, Any], key: str, path: str, errors: list[str]) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{path}.{key}: required object")
        return {}
    return value


def _validate_https_url(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: required HTTPS URL")
        return
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host:
        errors.append(f"{path}: required HTTPS URL")
    if host in {"example.com", "example.org", "localhost"} or host.endswith(".example.org"):
        errors.append(f"{path}: placeholder/non-official host is not allowed for verified evidence")


def _walk_guardrails(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(key)
            acceptance_proxy = "accept" in normalized and any(
                token in normalized for token in ("chance", "likelihood", "probability", "rate", "score")
            )
            prestige_proxy = any(token in normalized for token in ("country", "institution", "prestige", "university")) and any(
                token in normalized for token in ("bonus", "modifier", "penalty", "score", "weight")
            )
            if acceptance_proxy or prestige_proxy:
                errors.append(f"{path}.{key}: forbidden editorial-outcome or prestige proxy")
            if normalized in SENSITIVE_KEYS or normalized.startswith("patientrecord"):
                errors.append(f"{path}.{key}: individual-level identifying/clinical records do not belong in a research pack")
            errors.extend(_walk_guardrails(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_walk_guardrails(child, f"{path}[{index}]"))
    return errors


def _words(text: str) -> set[str]:
    return {word for word in WORDS.findall(text.casefold()) if word not in STOPWORDS}


def _validate_sources(pack: dict[str, Any], errors: list[str]) -> None:
    sources = pack.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("$.sources: at least one provenance record is required")
        return
    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f"$.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{path}: required object")
            continue
        for key in (
            "source_id",
            "kind",
            "title",
            "url_or_path",
            "retrieved_at",
            "checksum",
            "rights_basis",
            "allowed_use",
        ):
            if not _is_nonempty(source.get(key)):
                errors.append(f"{path}.{key}: required")
        source_id = str(source.get("source_id", ""))
        if source_id in seen_ids:
            errors.append(f"{path}.source_id: duplicate source identifier")
        seen_ids.add(source_id)
        kind = str(source.get("kind", "")).casefold()
        rights = str(source.get("rights_basis", "")).casefold()
        allowed_use = str(source.get("allowed_use", "")).casefold()
        if kind not in ALLOWED_SOURCE_KINDS:
            errors.append(f"{path}.kind: unsupported source kind")
        if rights not in ALLOWED_RIGHTS:
            errors.append(f"{path}.rights_basis: unsupported rights basis")
        if allowed_use not in ALLOWED_USES:
            errors.append(f"{path}.allowed_use: unsupported use")
        _parse_date(source.get("retrieved_at"), f"{path}.retrieved_at", errors)
        if not SHA256.fullmatch(str(source.get("checksum", "")).casefold()):
            errors.append(f"{path}.checksum: expected SHA-256 of the local file or frozen response")
        if kind in {"official_guidance", "official_journal_requirements", "authorized_full_text", "open_access_full_text"}:
            if not _is_nonempty(source.get("evidence_location")):
                errors.append(f"{path}.evidence_location: required for normative or full-text evidence")
        if rights == "unknown" and allowed_use not in {"discovery", "metadata_only"}:
            errors.append(f"{path}: unknown rights allow discovery/metadata only")
        if allowed_use == "style_analysis" and rights not in STYLE_RIGHTS:
            errors.append(f"{path}: style analysis requires user-owned or explicitly licensed full text")
        if "benha" in f"{source.get('title', '')} {source.get('url_or_path', '')}".casefold():
            if allowed_use != "administrative_formatting":
                errors.append(f"{path}: Benha material may be used only as an administrative formatting overlay")


def _validate_journals(pack: dict[str, Any], errors: list[str]) -> None:
    journals = pack.get("journal_targets")
    if not isinstance(journals, list) or not journals:
        errors.append("$.journal_targets: at least one target or explicitly pending target is required")
        return
    for index, journal in enumerate(journals):
        path = f"$.journal_targets[{index}]"
        if not isinstance(journal, dict):
            errors.append(f"{path}: required object")
            continue
        for key in ("journal_id", "name", "requirements_status", "fit_status"):
            if not _is_nonempty(journal.get(key)):
                errors.append(f"{path}.{key}: required")
        status = journal.get("requirements_status")
        fit_status = journal.get("fit_status")
        if status not in ALLOWED_REQUIREMENT_STATUS:
            errors.append(f"{path}.requirements_status: invalid status")
        if fit_status not in ALLOWED_FIT_STATUS:
            errors.append(f"{path}.fit_status: invalid status")
        if status != "verified" and fit_status == "eligible":
            errors.append(f"{path}.fit_status: unverified requirements cannot produce an eligible label")
        if status != "verified":
            continue
        _validate_https_url(journal.get("official_url"), f"{path}.official_url", errors)
        verified_at = _parse_date(journal.get("verified_at"), f"{path}.verified_at", errors)
        if verified_at and (date.today() - verified_at).days > MAX_JOURNAL_VERIFICATION_AGE_DAYS:
            errors.append(f"{path}: verification is older than {MAX_JOURNAL_VERIFICATION_AGE_DAYS} days; mark stale and recheck")
        requirements = journal.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            errors.append(f"{path}.requirements: verified target requires atomic evidence rows")
            continue
        fields: set[str] = set()
        for requirement_index, requirement in enumerate(requirements):
            req_path = f"{path}.requirements[{requirement_index}]"
            if not isinstance(requirement, dict):
                errors.append(f"{req_path}: required object")
                continue
            for key in ("field", "value", "official_url", "final_url", "evidence_location", "verified_at", "checksum"):
                if not _is_nonempty(requirement.get(key)):
                    errors.append(f"{req_path}.{key}: required")
            fields.add(str(requirement.get("field", "")).casefold())
            _validate_https_url(requirement.get("official_url"), f"{req_path}.official_url", errors)
            _validate_https_url(requirement.get("final_url"), f"{req_path}.final_url", errors)
            _parse_date(requirement.get("verified_at"), f"{req_path}.verified_at", errors)
            if not SHA256.fullmatch(str(requirement.get("checksum", "")).casefold()):
                errors.append(f"{req_path}.checksum: expected SHA-256 of frozen official response")
        for required_field in ("scope", "article_type"):
            if required_field not in fields:
                errors.append(f"{path}.requirements: verified fit requires an atomic {required_field!r} claim")


def _validate_titles(pack: dict[str, Any], project: dict[str, Any], errors: list[str]) -> None:
    titles = pack.get("title_candidates")
    if not isinstance(titles, list) or not 6 <= len(titles) <= 10:
        errors.append("$.title_candidates: provide 6-10 candidates")
        return
    design = project.get("study_design")
    labels = DESIGN_REQUIREMENTS.get(str(design), {}).get("title_labels", ())
    planned = project.get("stage") in {"planning", "protocol_frozen"}
    inference = project.get("intended_inference")
    topic_terms = project.get("topic_terms", [])
    topic_words = {word for term in topic_terms if isinstance(term, str) for word in _words(term)}
    seen: set[str] = set()
    for index, candidate in enumerate(titles):
        path = f"$.title_candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{path}: required object")
            continue
        text = candidate.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{path}.text: required non-empty title")
            continue
        normalized = " ".join(WORDS.findall(text.casefold()))
        if normalized in seen:
            errors.append(f"{path}.text: duplicate title candidate")
        seen.add(normalized)
        title_words = _words(text)
        if labels and not any(label in text.casefold() for label in labels):
            errors.append(f"{path}.text: missing accurate design label")
        hype = sorted(title_words & HYPE)
        if hype:
            errors.append(f"{path}.text: promotional wording is not allowed: {', '.join(hype)}")
        if planned:
            result_language = sorted(title_words & RESULT_WORDS)
            if result_language:
                errors.append(f"{path}.text: pre-data title asserts results: {', '.join(result_language)}")
        if design in {"retrospective_cohort", "prospective_cohort", "cross_sectional", "case_control"} and inference != "causal":
            causal = sorted(title_words & CAUSAL)
            if causal:
                errors.append(f"{path}.text: causal language conflicts with the declared {inference!r} aim: {', '.join(causal)}")
        if topic_words and not topic_words.intersection(title_words):
            errors.append(f"{path}.text: title has no supplied topic term")
        title_quality = _require_mapping(candidate, "title_quality", path, errors)
        journal_fit = _require_mapping(candidate, "journal_fit", path, errors)
        if title_quality.get("status") not in {"clear", "revise", "not_usable"}:
            errors.append(f"{path}.title_quality.status: invalid status")
        if not isinstance(title_quality.get("reasons"), list) or not title_quality["reasons"]:
            errors.append(f"{path}.title_quality.reasons: transparent reasons are required")
        if journal_fit.get("status") not in ALLOWED_FIT_STATUS:
            errors.append(f"{path}.journal_fit.status: invalid status")
        if not isinstance(journal_fit.get("reasons"), list) or not journal_fit["reasons"]:
            errors.append(f"{path}.journal_fit.reasons: transparent reasons are required")
        if not _is_nonempty(candidate.get("evidence_alignment")):
            errors.append(f"{path}.evidence_alignment: required")
        if not isinstance(candidate.get("flags"), list):
            errors.append(f"{path}.flags: required list")
        for key, value in candidate.items():
            if "score" in _normalized_key(key) and isinstance(value, (int, float)):
                errors.append(f"{path}.{key}: numeric title/journal scores are not allowed")


def _validate_protocol_and_statistics(
    project: dict[str, Any], protocol: dict[str, Any], statistics: dict[str, Any], errors: list[str]
) -> None:
    design = project.get("study_design")
    rule = DESIGN_REQUIREMENTS.get(str(design))
    if rule is None:
        errors.append(f"$.project.study_design: unsupported exact design {design!r}")
        return
    guidelines = protocol.get("reporting_guidelines")
    if not isinstance(guidelines, list) or not all(isinstance(item, str) for item in guidelines):
        errors.append("$.protocol.reporting_guidelines: required list")
        guidelines_text = ""
    else:
        guidelines_text = " ".join(guidelines).casefold()
    for guideline in rule["guidelines"]:
        if guideline not in guidelines_text:
            errors.append(f"$.protocol.reporting_guidelines: {design} requires {guideline}")
    if project.get("uses_routinely_collected_data") is True and "record" not in guidelines_text:
        errors.append("$.protocol.reporting_guidelines: routinely collected data require RECORD in addition to the core design guideline")

    for field in COMMON_PROTOCOL_FIELDS + tuple(rule["protocol"]):
        if not _is_nonempty(protocol.get(field)):
            errors.append(f"$.protocol.{field}: required for {design}")
    _parse_date(protocol.get("version_date"), "$.protocol.version_date", errors)
    outcome = _require_mapping(protocol, "primary_outcome", "$.protocol", errors)
    for field in ("name", "instrument", "metric", "timepoint"):
        if not _is_nonempty(outcome.get(field)):
            errors.append(f"$.protocol.primary_outcome.{field}: required")
    outcome_text = " ".join(str(outcome.get(field, "")) for field in ("name", "instrument", "metric")).casefold()
    if "koos total" in outcome_text or "total koos" in outcome_text:
        errors.append("$.protocol.primary_outcome: KOOS has subscales; do not invent a generic total score")
    if "koos" in f"{project.get('question', '')} {outcome_text}".casefold():
        subscales = ("pain", "symptom", "activities of daily living", "adl", "sport", "recreation", "quality of life", "qol")
        if not any(subscale in outcome_text for subscale in subscales):
            errors.append("$.protocol.primary_outcome: prespecify one KOOS subscale/metric instead of generic KOOS")

    sample_size = _require_mapping(protocol, "sample_size_justification", "$.protocol", errors)
    for field in ("method", "assumptions", "sensitivity_analysis", "provenance_source_ids"):
        if not _is_nonempty(sample_size.get(field)):
            errors.append(f"$.protocol.sample_size_justification.{field}: required")
    ethics = _require_mapping(protocol, "ethics", "$.protocol", errors)
    for field in ("status", "consent_or_waiver", "privacy_plan"):
        if not _is_nonempty(ethics.get(field)):
            errors.append(f"$.protocol.ethics.{field}: required")
    if project.get("intended_inference") == "causal" and design in {
        "retrospective_cohort",
        "prospective_cohort",
        "cross_sectional",
        "case_control",
    } and not _is_nonempty(protocol.get("causal_assumptions")):
        errors.append("$.protocol.causal_assumptions: required for a causal observational aim")

    for field in COMMON_STATISTICS_FIELDS:
        if not _is_nonempty(statistics.get(field)):
            errors.append(f"$.statistics.{field}: required")
    if design in {"retrospective_cohort", "prospective_cohort", "cross_sectional", "case_control"}:
        if not _is_nonempty(statistics.get("covariates")):
            errors.append("$.statistics.covariates: prespecified covariates are required for observational analysis")
    effect_measure = str(statistics.get("effect_measure", "")).casefold().strip()
    if effect_measure in {"p", "p-value", "p value", "statistical significance"}:
        errors.append("$.statistics.effect_measure: a p-value is not an effect measure")
    missing = _require_mapping(statistics, "missing_data", "$.statistics", errors)
    for field in ("primary_assumption", "primary_method", "sensitivity_analysis"):
        if not _is_nonempty(missing.get(field)):
            errors.append(f"$.statistics.missing_data.{field}: required")
    if str(missing.get("primary_method", "")).casefold().strip() in {"ignore", "ignored", "none"}:
        errors.append("$.statistics.missing_data.primary_method: missing data cannot be silently ignored")
    software = _require_mapping(statistics, "software", "$.statistics", errors)
    for field in ("name", "version"):
        if not _is_nonempty(software.get(field)):
            errors.append(f"$.statistics.software.{field}: required")
    analysis_map = statistics.get("objective_analysis_map")
    if isinstance(analysis_map, list):
        for index, row in enumerate(analysis_map):
            path = f"$.statistics.objective_analysis_map[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{path}: required object")
                continue
            for field in ("objective_id", "outcome", "estimand", "effect_measure", "model", "missing_data_assumption"):
                if not _is_nonempty(row.get(field)):
                    errors.append(f"{path}.{field}: required")


def _validate_style_and_readiness(pack: dict[str, Any], project: dict[str, Any], errors: list[str]) -> None:
    style = _require_mapping(pack, "style_profile", "$", errors)
    status = style.get("status")
    if status not in {"profiled", "insufficient_evidence"}:
        errors.append("$.style_profile.status: expected profiled or insufficient_evidence")
    if status == "insufficient_evidence" and not _is_nonempty(style.get("reason")):
        errors.append("$.style_profile.reason: explain the degraded evidence mode")
    if status == "profiled":
        samples = style.get("samples")
        if not isinstance(samples, list) or len(samples) < 5:
            errors.append("$.style_profile.samples: at least five authorized papers are required")
        else:
            for index, sample in enumerate(samples):
                path = f"$.style_profile.samples[{index}]"
                if not isinstance(sample, dict):
                    errors.append(f"{path}: required object")
                    continue
                for field in ("doi", "article_type", "rights_basis", "full_text_source", "evidence_location"):
                    if not _is_nonempty(sample.get(field)):
                        errors.append(f"{path}.{field}: required")
                if str(sample.get("rights_basis", "")).casefold() not in STYLE_RIGHTS:
                    errors.append(f"{path}.rights_basis: style profile requires authorized full text")

    audit = _require_mapping(pack, "no_fabrication_audit", "$", errors)
    if audit.get("completed") is not True:
        errors.append("$.no_fabrication_audit.completed: must be true")
    if audit.get("fabricated_claims_found") is not False:
        errors.append("$.no_fabrication_audit.fabricated_claims_found: must be false after remediation")
    if not isinstance(audit.get("checks"), list) or not audit["checks"]:
        errors.append("$.no_fabrication_audit.checks: required non-empty list")

    minimum_gate = _require_mapping(project, "minimum_input_gate", "$.project", errors)
    gate_fields = (
        "question_finalized",
        "design_confirmed",
        "primary_outcome_confirmed",
        "data_source_confirmed",
        "results_visibility_recorded",
        "causal_aim_confirmed",
    )
    for field in gate_fields:
        if not isinstance(minimum_gate.get(field), bool):
            errors.append(f"$.project.minimum_input_gate.{field}: required boolean")

    reviews = _require_mapping(pack, "human_reviews", "$", errors)
    for field in ("investigator", "statistician", "ethics_data_governance", "journal_requirements"):
        if reviews.get(field) not in {"approved", "not_required", "pending"}:
            errors.append(f"$.human_reviews.{field}: invalid or missing review state")
    readiness = _require_mapping(pack, "readiness", "$", errors)
    if readiness.get("status") not in {"draft", "under_review", "submission_ready"}:
        errors.append("$.readiness.status: invalid or missing status")
    if not isinstance(readiness.get("limitations"), list):
        errors.append("$.readiness.limitations: required list")

    unresolved = pack.get("unresolved")
    if not isinstance(unresolved, list):
        errors.append("$.unresolved: required list of explicit questions")
        unresolved = []
    else:
        for index, item in enumerate(unresolved):
            if not isinstance(item, dict) or not _is_nonempty(item.get("item")) or not isinstance(item.get("blocking"), bool):
                errors.append(f"$.unresolved[{index}]: require item and boolean blocking fields")

    if readiness.get("status") == "submission_ready":
        if not all(minimum_gate.get(field) is True for field in gate_fields):
            errors.append("$.readiness: submission_ready requires every minimum-input gate")
        if not all(reviews.get(field) in {"approved", "not_required"} for field in reviews):
            errors.append("$.readiness: submission_ready requires completed human reviews")
        if any(isinstance(item, dict) and item.get("blocking") is True for item in unresolved):
            errors.append("$.readiness: submission_ready cannot have blocking unresolved questions")
        journals = pack.get("journal_targets", [])
        if any(not isinstance(journal, dict) or journal.get("requirements_status") != "verified" for journal in journals):
            errors.append("$.readiness: submission_ready requires current verified target-journal requirements")


def validate_pack(pack: Any) -> list[str]:
    if not isinstance(pack, dict):
        return ["$: research pack must be a JSON object"]
    errors = _walk_guardrails(pack)
    project = _require_mapping(pack, "project", "$", errors)
    protocol = _require_mapping(pack, "protocol", "$", errors)
    statistics = _require_mapping(pack, "statistics", "$", errors)

    for key in ("id", "question", "study_design", "stage", "intended_inference"):
        if not isinstance(project.get(key), str) or not project[key].strip():
            errors.append(f"$.project.{key}: required non-empty string")
    if project.get("stage") not in ALLOWED_STAGES:
        errors.append("$.project.stage: unsupported stage")
    if project.get("intended_inference") not in ALLOWED_INFERENCE:
        errors.append("$.project.intended_inference: unsupported value")
    if not isinstance(project.get("topic_terms"), list) or not project["topic_terms"]:
        errors.append("$.project.topic_terms: required non-empty list")
    for key in ("uses_routinely_collected_data", "comparative_results_seen", "protocol_frozen_before_comparative_results"):
        if not isinstance(project.get(key), bool):
            errors.append(f"$.project.{key}: required boolean")
    if (
        project.get("comparative_results_seen") is True
        and project.get("protocol_frozen_before_comparative_results") is False
        and not _is_nonempty(project.get("results_visibility_disclosure"))
    ):
        errors.append("$.project.results_visibility_disclosure: disclose post-result protocol/SAP development")

    _validate_sources(pack, errors)
    _validate_protocol_and_statistics(project, protocol, statistics, errors)
    _validate_journals(pack, errors)
    _validate_titles(pack, project, errors)
    _validate_style_and_readiness(pack, project, errors)
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.pack.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}")
        return 2
    errors = validate_pack(payload)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

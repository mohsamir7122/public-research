from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from statistics import NormalDist
from typing import Iterable
import unicodedata


@dataclass(frozen=True, slots=True)
class EffectEstimate:
    """One independent estimate on a prespecified common analysis scale."""

    study_id: str
    effect: float
    standard_error: float


@dataclass(frozen=True, slots=True)
class PoolingApproval:
    """Traceable human approval of one prespecified, clinically compatible synthesis."""

    artifact: str
    sha256: str
    approved_by: tuple[str, ...]
    approved_on: str
    rationale: str


@dataclass(frozen=True, slots=True)
class MetaAnalysisResult:
    effect_measure: str
    analysis_scale: str
    model: str
    tau_method: str | None
    studies: int
    pooled_effect: float
    standard_error: float
    confidence_level: float
    confidence_interval: tuple[float, float]
    prediction_interval: tuple[float, float] | None
    display_pooled_effect: float
    display_confidence_interval: tuple[float, float]
    display_prediction_interval: tuple[float, float] | None
    q: float
    q_degrees_of_freedom: int
    i_squared_percent: float
    tau_squared: float
    warnings: tuple[str, ...]
    pooling_approval_fingerprint_sha256: str
    analysis_status: str
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validated(estimates: Iterable[EffectEstimate]) -> list[EffectEstimate]:
    values = list(estimates)
    if len(values) < 2:
        raise ValueError("meta-analysis requires at least two independent estimates")
    if any(not isinstance(estimate, EffectEstimate) for estimate in values):
        raise ValueError("every estimate must be an EffectEstimate")
    if any(not isinstance(estimate.study_id, str) for estimate in values):
        raise ValueError("every estimate requires a string study_id")
    identifiers = [
        unicodedata.normalize("NFKC", estimate.study_id).strip().casefold()
        for estimate in values
    ]
    if any(not identifier for identifier in identifiers):
        raise ValueError("every estimate requires a non-empty study_id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("study_id values must be unique; resolve multi-report studies before pooling")
    for estimate in values:
        if not math.isfinite(estimate.effect):
            raise ValueError(f"{estimate.study_id}: effect must be finite")
        if not math.isfinite(estimate.standard_error) or estimate.standard_error <= 0:
            raise ValueError(f"{estimate.study_id}: standard_error must be finite and positive")
    return values


_MACHINE_APPROVER_PATTERN = re.compile(
    r"(?:\bai\b|\bbot\b|\bgpt(?:-?\d+)?\b|chatgpt|openai|codex|"
    r"artificial intelligence|large language model|language model|ai assistant|"
    r"claude ai|gemini ai)",
    flags=re.IGNORECASE,
)

_GENERIC_APPROVER_LABELS = {
    "reviewer one",
    "reviewer two",
    "researcher one",
    "researcher two",
    "methodologist",
    "statistician",
}


def _looks_like_named_human(value: str) -> bool:
    if value.casefold() in _GENERIC_APPROVER_LABELS:
        return False
    words = re.findall(r"[^\W\d_]+", value, flags=re.UNICODE)
    return len(words) >= 2 and not _MACHINE_APPROVER_PATTERN.search(value)


def _validate_pooling_approval(approval: PoolingApproval | None) -> tuple[PoolingApproval, str]:
    if not isinstance(approval, PoolingApproval):
        raise ValueError(
            "pooling_approval must be a traceable PoolingApproval; a boolean approval is insufficient"
        )
    artifact = " ".join(approval.artifact.split())
    artifact_path = PurePosixPath(artifact)
    if not artifact or artifact_path.is_absolute() or ".." in artifact_path.parts:
        raise ValueError("pooling_approval.artifact must be a safe project-relative path")
    checksum = approval.sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("pooling_approval.sha256 must be a 64-character SHA-256 digest")
    approvers = tuple(" ".join(value.split()) for value in approval.approved_by)
    if len(approvers) < 2 or any(not value for value in approvers):
        raise ValueError("pooling_approval requires at least two named human approvers")
    approver_keys = [value.casefold() for value in approvers]
    if len(set(approver_keys)) != len(approver_keys):
        raise ValueError("pooling_approval approvers must be distinct")
    if any(not _looks_like_named_human(value) for value in approvers):
        raise ValueError(
            "pooling_approval approvers must be named humans, not roles or AI/tool identities"
        )
    try:
        approved_on = date.fromisoformat(approval.approved_on)
    except (TypeError, ValueError) as exc:
        raise ValueError("pooling_approval.approved_on must be an ISO date") from exc
    if approved_on > date.today():
        raise ValueError("pooling_approval.approved_on cannot be in the future")
    rationale = " ".join(approval.rationale.split())
    if len(rationale) < 20:
        raise ValueError("pooling_approval.rationale must document the compatibility decision")
    normalized = PoolingApproval(
        artifact=artifact,
        sha256=checksum,
        approved_by=approvers,
        approved_on=approved_on.isoformat(),
        rationale=rationale,
    )
    fingerprint = sha256(
        json.dumps(
            asdict(normalized),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return normalized, fingerprint


def _validate_measure_and_scale(effect_measure: str, analysis_scale: str) -> tuple[str, str]:
    measure = " ".join(effect_measure.split())
    if not measure:
        raise ValueError("effect_measure is required")
    scale = analysis_scale.strip().casefold()
    if scale not in {"identity", "log"}:
        raise ValueError("analysis_scale must be 'identity' or 'log'")
    normalized_measure = re.sub(
        r"[\W_]+",
        " ",
        unicodedata.normalize("NFKC", measure).casefold(),
        flags=re.UNICODE,
    ).strip()
    normalized_tokens = normalized_measure.split()
    ratio_abbreviations = {"rr", "or", "hr", "irr", "pr"}
    abbreviation_prefixes = {
        "adjusted",
        "crude",
        "log",
        "pooled",
        "summary",
        "unadjusted",
    }
    starts_with_ratio_abbreviation = bool(normalized_tokens) and (
        normalized_tokens[0] in ratio_abbreviations
        or (
            len(normalized_tokens) >= 2
            and normalized_tokens[0] in abbreviation_prefixes
            and normalized_tokens[1] in ratio_abbreviations
        )
    )
    uppercase_ratio_abbreviation = bool(
        re.search(
            r"(?<![\w])(?:RR|OR|HR|IRR|PR)(?![\w])",
            unicodedata.normalize("NFKC", measure),
        )
    )
    is_ratio_measure = (
        "ratio" in normalized_tokens
        or any(
            normalized_tokens[index : index + 2] == ["relative", "risk"]
            for index in range(len(normalized_tokens) - 1)
        )
        or starts_with_ratio_abbreviation
        or uppercase_ratio_abbreviation
    )
    if is_ratio_measure and scale != "log":
        raise ValueError("ratio effect measures must be supplied and pooled on the log scale")
    return measure, scale


def _weighted_mean(values: list[EffectEstimate], tau_squared: float) -> tuple[float, float]:
    weights = [1.0 / (item.standard_error**2 + tau_squared) for item in values]
    weight_sum = sum(weights)
    mean = sum(weight * item.effect for weight, item in zip(weights, values, strict=True)) / weight_sum
    return mean, weight_sum


def _q_statistic(values: list[EffectEstimate], tau_squared: float = 0.0) -> float:
    mean, _ = _weighted_mean(values, tau_squared)
    return sum(
        ((item.effect - mean) ** 2) / (item.standard_error**2 + tau_squared)
        for item in values
    )


def estimate_tau_squared_paule_mandel(values: Iterable[EffectEstimate]) -> float:
    """Estimate between-study variance by solving Q(tau²) = k - 1.

    The implementation is deterministic and dependency-free. It is a numerical
    check, not permission to pool clinically incompatible studies.
    """

    estimates = _validated(values)
    target = len(estimates) - 1
    if _q_statistic(estimates) <= target:
        return 0.0

    lower = 0.0
    upper = max(item.standard_error**2 for item in estimates)
    while _q_statistic(estimates, upper) > target:
        upper *= 2.0
        if upper > 1e12:
            raise ValueError("could not bracket the Paule-Mandel tau-squared solution")

    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        if _q_statistic(estimates, midpoint) > target:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def combine_effects(
    estimates: Iterable[EffectEstimate],
    *,
    effect_measure: str,
    analysis_scale: str,
    pooling_approval: PoolingApproval,
    model: str = "random",
    confidence_level: float = 0.95,
) -> MetaAnalysisResult:
    """Pool compatible generic inverse-variance estimates.

    Callers must first harmonize direction, scale, time point, unit of analysis,
    and multi-arm dependencies. This function deliberately refuses to infer
    clinical or methodological poolability from numeric inputs alone.
    """

    values = _validated(estimates)
    measure, scale = _validate_measure_and_scale(effect_measure, analysis_scale)
    _, approval_fingerprint = _validate_pooling_approval(pooling_approval)
    if model not in {"fixed", "random"}:
        raise ValueError("model must be 'fixed' or 'random'")
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0.5 and 1.0")

    fixed_q = _q_statistic(values)
    degrees_of_freedom = len(values) - 1
    i_squared = max(0.0, (fixed_q - degrees_of_freedom) / fixed_q * 100.0) if fixed_q else 0.0
    tau_squared = estimate_tau_squared_paule_mandel(values) if model == "random" else 0.0
    pooled, weight_sum = _weighted_mean(values, tau_squared)
    pooled_standard_error = math.sqrt(1.0 / weight_sum)
    alpha = 1.0 - confidence_level
    critical = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    confidence_interval = (
        pooled - critical * pooled_standard_error,
        pooled + critical * pooled_standard_error,
    )

    prediction_interval: tuple[float, float] | None = None
    warnings: list[str] = []
    if model == "random" and len(values) >= 3:
        prediction_standard_error = math.sqrt(tau_squared + pooled_standard_error**2)
        prediction_interval = (
            pooled - critical * prediction_standard_error,
            pooled + critical * prediction_standard_error,
        )
    if len(values) < 5:
        warnings.append("few studies: heterogeneity and interval estimates are unstable")
    if len(values) < 10:
        warnings.append("do not run or interpret funnel-plot asymmetry tests as reliable")
    if model == "random":
        warnings.append(
            "normal-approximation intervals are a calculation check; prespecify and independently reproduce the primary analysis"
        )

    transform = math.exp if scale == "log" else lambda value: value
    display_prediction_interval = (
        tuple(transform(value) for value in prediction_interval)
        if prediction_interval is not None
        else None
    )

    return MetaAnalysisResult(
        effect_measure=measure,
        analysis_scale=scale,
        model=model,
        tau_method="paule_mandel" if model == "random" else None,
        studies=len(values),
        pooled_effect=pooled,
        standard_error=pooled_standard_error,
        confidence_level=confidence_level,
        confidence_interval=confidence_interval,
        prediction_interval=prediction_interval,
        display_pooled_effect=transform(pooled),
        display_confidence_interval=tuple(transform(value) for value in confidence_interval),
        display_prediction_interval=display_prediction_interval,
        q=fixed_q,
        q_degrees_of_freedom=degrees_of_freedom,
        i_squared_percent=i_squared,
        tau_squared=tau_squared,
        warnings=tuple(warnings),
        pooling_approval_fingerprint_sha256=approval_fingerprint,
        analysis_status="calculation_check_not_release_analysis",
        truth_boundary=(
            "Generic inverse-variance calculation only. It does not establish eligibility, independence, common scale, "
            "clinical poolability, absence of bias, certainty of evidence, or suitability for a final manuscript."
        ),
    )

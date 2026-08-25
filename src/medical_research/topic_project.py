"""Minimal provisional topic intake for persistent research collaboration.

A concise topic may open a project before a protocol-ready intake exists.  This
module records that topic and names the missing decisions; it never treats a
provisional brief as a frozen protocol or permission to collect/analyse data.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


SUPPORTED_ROUTE_HINTS = (
    "undetermined",
    "original_study_or_thesis",
    "systematic_review",
    "systematic_review_with_meta_analysis",
    "umbrella_review",
)

_ROUTE_ALIASES = {
    "": "undetermined",
    "undetermined": "undetermined",
    "thesis": "original_study_or_thesis",
    "original_study": "original_study_or_thesis",
    "original_study_or_thesis": "original_study_or_thesis",
    "systematic_review": "systematic_review",
    "systematic_review_with_meta_analysis": "systematic_review_with_meta_analysis",
    "systematic_review_and_meta_analysis": "systematic_review_with_meta_analysis",
    "meta_analysis": "systematic_review_with_meta_analysis",
    "umbrella_review": "umbrella_review",
    "overview_of_reviews": "umbrella_review",
    "meta_meta_analysis": "umbrella_review",
}

_FIELDS = {
    "topic",
    "route_hint",
    "research_question",
    "clinical_area",
    "project_owner",
    "constraints",
}


class ProvisionalTopicError(ValueError):
    """Raised when even a provisional topic brief is not usable."""


def _clean_optional_text(value: Any, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProvisionalTopicError(f"{field} must be a string")
    return " ".join(value.split())


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize_route(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", value.casefold()).strip("_")
    if key not in _ROUTE_ALIASES:
        raise ProvisionalTopicError(
            "route_hint must be one of: " + ", ".join(SUPPORTED_ROUTE_HINTS)
        )
    return _ROUTE_ALIASES[key]


def assess_provisional_topic(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a minimal topic and return an explicit blocker-led project state."""

    if not isinstance(payload, Mapping):
        raise ProvisionalTopicError("topic brief must be an object")
    unknown = sorted(set(payload) - _FIELDS)
    if unknown:
        raise ProvisionalTopicError("unknown fields: " + ", ".join(unknown))

    topic = _clean_optional_text(payload.get("topic"), "topic")
    if not 12 <= len(topic) <= 1000:
        raise ProvisionalTopicError("topic must contain 12 to 1000 characters")
    route = _normalize_route(_clean_optional_text(payload.get("route_hint"), "route_hint"))
    research_question = _clean_optional_text(
        payload.get("research_question"), "research_question"
    )
    if research_question and len(research_question) < 20:
        raise ProvisionalTopicError(
            "research_question must contain at least 20 characters when supplied"
        )
    clinical_area = _clean_optional_text(payload.get("clinical_area"), "clinical_area")
    project_owner = _clean_optional_text(payload.get("project_owner"), "project_owner")

    raw_constraints = payload.get("constraints", [])
    if not isinstance(raw_constraints, list):
        raise ProvisionalTopicError("constraints must be an array")
    constraints: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_constraints):
        value = _clean_optional_text(raw, f"constraints[{index}]")
        if not value:
            raise ProvisionalTopicError(f"constraints[{index}] must not be empty")
        key = value.casefold()
        if key in seen:
            raise ProvisionalTopicError("constraints must be distinct")
        seen.add(key)
        constraints.append(value)

    normalized = {
        "topic": topic,
        "route_hint": route,
        "research_question": research_question,
        "clinical_area": clinical_area,
        "project_owner": project_owner,
        "constraints": constraints,
    }
    fingerprint = sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()
    blockers = []
    if route == "undetermined":
        blockers.append(
            {
                "code": "route_selection_required",
                "message": "Choose an original-study, systematic-review, meta-analysis, or umbrella-review route.",
            }
        )
    if not research_question:
        blockers.append(
            {
                "code": "structured_question_required",
                "message": "Convert the topic into a route-appropriate structured research question.",
            }
        )
    if not project_owner:
        blockers.append(
            {
                "code": "project_owner_required",
                "message": "Name the investigator who owns scientific decisions.",
            }
        )
    blockers.extend(
        (
            {
                "code": "professional_intake_required",
                "message": "Complete and human-confirm the route-specific professional intake before protocol lock.",
            },
            {
                "code": "accountable_humans_required",
                "message": "Name at least two accountable humans before evidence-gated work advances.",
            },
        )
    )
    return {
        "schema_version": "1.0",
        "project_id": f"TOPIC-{fingerprint[:12].upper()}",
        "topic_fingerprint_sha256": fingerprint,
        "status": "awaiting_user_decision",
        "current_stage": "topic_intake",
        "route_hint": route,
        "topic_brief": normalized,
        "blockers": blockers,
        "next_action": blockers[0]["code"],
        "truth_boundary": (
            "This is a provisional collaboration checkpoint, not a frozen protocol, "
            "registration, approval, eligibility decision, analysis, or manuscript result."
        ),
    }


def build_provisional_topic_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    state = assess_provisional_topic(payload)
    return {
        "schema_version": "1.0",
        "project_id": state["project_id"],
        "topic_fingerprint_sha256": state["topic_fingerprint_sha256"],
        "route_hint": state["route_hint"],
        "files": [
            {
                "path": "manifest.json",
                "purpose": "Deterministic provisional scaffold",
                "mutable": False,
            },
            {
                "path": "topic-brief.json",
                "purpose": "Normalized topic supplied by the investigator",
                "mutable": True,
            },
            {
                "path": "project-state.json",
                "purpose": "Blockers and next collaboration checkpoint",
                "mutable": True,
            },
        ],
        "promotion_rule": (
            "Create and validate a route-specific intake, then initialize the original-study "
            "or review workflow; never relabel this provisional state as protocol-ready."
        ),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def initialize_provisional_topic_project(
    payload: Mapping[str, Any], output_directory: str | Path
) -> dict[str, Any]:
    """Create a new non-overwriting project directory atomically."""

    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    state = assess_provisional_topic(payload)
    manifest = build_provisional_topic_manifest(payload)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=str(parent))
    )
    try:
        _write_json(temporary / "manifest.json", manifest)
        _write_json(temporary / "topic-brief.json", state["topic_brief"])
        _write_json(temporary / "project-state.json", state)
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return state


__all__ = [
    "ProvisionalTopicError",
    "SUPPORTED_ROUTE_HINTS",
    "assess_provisional_topic",
    "build_provisional_topic_manifest",
    "initialize_provisional_topic_project",
]

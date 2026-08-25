from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import sys
import tempfile
from typing import Any, Iterator, Mapping, Sequence

from .meta_analysis import EffectEstimate, PoolingApproval, combine_effects
from .original_study_workflow import (
    OriginalStudyWorkflow,
    build_original_study_manifest,
    required_original_evidence_for_stage,
    validate_original_study_intake,
)
from .pilot import run_pilot
from .review_workflow import (
    ReviewWorkflow,
    build_project_manifest,
    corrected_covered_area,
    derive_prior_counts,
    derive_prisma_counts,
    required_evidence_for_stage,
    validate_topic_intake,
)
from .search_strategy import build_queries
from .topic_project import initialize_provisional_topic_project


STATE_SCHEMA_VERSION = "1.0"


class CliUsageError(ValueError):
    """Raised instead of exiting so usage failures remain machine-readable."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _loads_json(text: str, *, source: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{source}: invalid JSON: {exc}") from exc


def _read_json(path: Path, *, label: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    return _loads_json(text, source=f"{label} {path}")


def _read_json_records(path: Path) -> list[Any]:
    """Read a JSON array or newline-delimited JSON records without guessing rows."""

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read screening records {path}: {exc}") from exc

    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        records: list[Any] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            records.append(
                _loads_json(
                    line,
                    source=f"screening records {path}, line {line_number}",
                )
            )
        if not records:
            raise ValueError("screening JSONL must contain at least one non-empty record")
        return records

    value = _loads_json(text, source=f"screening records {path}")
    if not isinstance(value, list):
        raise ValueError("screening JSON must contain an array of record objects")
    return value


def _json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not finite JSON data: {exc}") from exc


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not finite JSON data: {exc}") from exc


def _state_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _state_document(
    manifest: Mapping[str, Any],
    workflow: ReviewWorkflow | OriginalStudyWorkflow,
) -> dict[str, Any]:
    snapshot = workflow.snapshot()
    if snapshot["completed"]:
        status = "verified"
        required_evidence: list[str] = []
        blockers: list[dict[str, Any]] = []
        next_action = "human_submission_readiness_review"
    else:
        status = (
            "awaiting_user_decision"
            if snapshot["current_stage"] == "topic_intake"
            else "working"
        )
        if isinstance(workflow, ReviewWorkflow):
            required_evidence = list(
                required_evidence_for_stage(snapshot["current_stage"])
            )
        else:
            required_evidence = list(
                required_original_evidence_for_stage(snapshot["current_stage"])
            )
        blockers = [
            {
                "code": f"{snapshot['current_stage']}_gate_open",
                "required_evidence": required_evidence,
            }
        ]
        next_action = f"complete_{snapshot['current_stage']}_gate"
    payload: dict[str, Any] = {
        "schema_version": STATE_SCHEMA_VERSION,
        "project_id": manifest["project_id"],
        "topic_fingerprint_sha256": manifest["topic_fingerprint_sha256"],
        "status": status,
        "current_stage": snapshot["current_stage"],
        "next_stage": snapshot["next_stage"],
        "required_evidence": required_evidence,
        "blockers": blockers,
        "next_action": next_action,
        "workflow": snapshot,
    }
    payload["state_fingerprint_sha256"] = _state_fingerprint(payload)
    return payload


def _write_json_exclusive(path: Path, value: Any) -> None:
    """Create a JSON file without ever replacing an existing path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite existing output: {path}") from exc


def _write_json_atomic(path: Path, value: Any) -> None:
    """Durably replace one known state file using a same-directory temporary."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_jsonl_atomic(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            for value in values:
                stream.write((_canonical_json(value) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _verified_artifact_path(project_dir: Path, relative_path: str) -> Path:
    project_root = project_dir.resolve(strict=True)
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact must be a safe project-relative path")
    unresolved = project_root / Path(*relative.parts)
    if unresolved.is_symlink():
        raise ValueError("artifact references cannot be symbolic links")
    try:
        candidate = unresolved.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"artifact does not exist: {relative_path}") from exc
    if not candidate.is_relative_to(project_root) or not candidate.is_file():
        raise ValueError("artifact must resolve to a regular file inside the project")
    return candidate


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"cannot hash artifact {path}: {exc}") from exc
    return digest.hexdigest()


def _verify_gate_evidence_artifacts(
    project_dir: Path, evidence: Mapping[str, Any]
) -> None:
    for gate, reference in evidence.items():
        if not isinstance(reference, Mapping):
            continue
        artifact = reference.get("artifact")
        checksum = reference.get("sha256")
        if not isinstance(artifact, str) or not isinstance(checksum, str):
            continue
        candidate = _verified_artifact_path(project_dir, artifact)
        if _file_sha256(candidate) != checksum.casefold():
            raise ValueError(f"{gate} artifact SHA-256 does not match the file")


def _verify_historical_evidence_artifacts(
    project_dir: Path,
    workflow: ReviewWorkflow | OriginalStudyWorkflow,
) -> None:
    """Rehash every artifact referenced by a completed gate before resuming.

    The serialized workflow is the authoritative transition ledger.  Its hashes
    establish internal consistency only, so the referenced files must also be
    checked again on every resume rather than trusting a checksum validated by a
    prior process.
    """

    transitions = workflow.snapshot().get("transitions")
    if not isinstance(transitions, list):
        raise ValueError("workflow transition history must be an array")
    for index, transition in enumerate(transitions):
        if not isinstance(transition, Mapping):
            raise ValueError(f"historical transition {index} must be an object")
        evidence = transition.get("evidence")
        if not isinstance(evidence, Mapping):
            raise ValueError(
                f"historical transition {index} is missing structured evidence"
            )
        try:
            _verify_gate_evidence_artifacts(project_dir, evidence)
        except ValueError as exc:
            from_stage = transition.get("from_stage", "unknown_stage")
            raise ValueError(
                f"historical evidence failed verification at transition {index} "
                f"({from_stage}): {exc}"
            ) from exc


@contextmanager
def _project_lock(project_dir: Path) -> Iterator[None]:
    lock_path = project_dir / ".project-state.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            f"project state is locked by another operation: {lock_path}"
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _verified_project(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not project_dir.is_dir():
        raise ValueError(f"project directory does not exist: {project_dir}")
    manifest = _read_json(project_dir / "manifest.json", label="project manifest")
    intake_payload = _read_json(
        project_dir / "protocol" / "topic_intake.json", label="topic intake"
    )
    if not isinstance(manifest, dict):
        raise ValueError("project manifest must be a JSON object")
    if not isinstance(intake_payload, dict):
        raise ValueError("topic intake must be a JSON object")

    rebuilt = build_project_manifest(validate_topic_intake(intake_payload))
    for field in (
        "schema_version",
        "project_id",
        "topic_fingerprint_sha256",
        "review_type",
        "pipeline",
    ):
        if manifest.get(field) != rebuilt.get(field):
            raise ValueError(
                f"frozen project manifest does not match the validated topic: {field}"
            )
    return manifest, intake_payload


def _restore_state(
    state: Any,
    manifest: Mapping[str, Any],
    accountable_reviewers: Sequence[str],
) -> ReviewWorkflow:
    if not isinstance(state, dict):
        raise ValueError("project state must be a JSON object")
    allowed = {
        "schema_version",
        "project_id",
        "topic_fingerprint_sha256",
        "status",
        "current_stage",
        "next_stage",
        "required_evidence",
        "blockers",
        "next_action",
        "workflow",
        "state_fingerprint_sha256",
    }
    unknown = sorted(set(state) - allowed)
    if unknown:
        raise ValueError("project state has unknown fields: " + ", ".join(unknown))
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported project-state schema; an explicit state migration is required"
        )
    if state.get("project_id") != manifest.get("project_id"):
        raise ValueError("project state does not belong to this manifest")
    if state.get("topic_fingerprint_sha256") != manifest.get(
        "topic_fingerprint_sha256"
    ):
        raise ValueError("project state topic fingerprint does not match the manifest")

    stored_fingerprint = state.get("state_fingerprint_sha256")
    if not isinstance(stored_fingerprint, str):
        raise ValueError("project state is missing state_fingerprint_sha256")
    unsigned = {key: value for key, value in state.items() if key != "state_fingerprint_sha256"}
    if stored_fingerprint != _state_fingerprint(unsigned):
        raise ValueError("project state integrity check failed")

    snapshot = state.get("workflow")
    if not isinstance(snapshot, dict):
        raise ValueError("project state workflow must be an object")
    if snapshot.get("review_type") != manifest.get("review_type"):
        raise ValueError("workflow review_type does not match the manifest")
    if snapshot.get("pipeline") != manifest.get("pipeline"):
        raise ValueError("workflow pipeline does not match the frozen manifest")
    if snapshot.get("accountable_reviewers") != list(accountable_reviewers):
        raise ValueError(
            "workflow accountable reviewers do not match the frozen topic intake"
        )
    workflow = ReviewWorkflow.from_snapshot(snapshot)
    if workflow.snapshot() != snapshot:
        raise ValueError("workflow snapshot changed during integrity validation")
    rebuilt = _state_document(manifest, workflow)
    for key in (
        "status",
        "current_stage",
        "next_stage",
        "required_evidence",
        "blockers",
        "next_action",
    ):
        if state.get(key) != rebuilt.get(key):
            raise ValueError(f"project state {key} does not reconcile with workflow")
    return workflow


def create_review_project(topic_path: Path, project_dir: Path) -> dict[str, Any]:
    """Validate a topic and create the minimal persistent scaffold, once."""

    payload = _read_json(topic_path, label="topic intake")
    if not isinstance(payload, dict):
        raise ValueError("topic intake must be a JSON object")
    intake = validate_topic_intake(payload)
    manifest = build_project_manifest(intake)
    workflow = ReviewWorkflow(intake.review_type, intake.accountable_reviewers)
    state = _state_document(manifest, workflow)

    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ValueError(
            f"refusing to initialize over an existing path: {project_dir}"
        ) from exc

    try:
        for directory in manifest["directories"]:
            (project_dir / directory).mkdir(parents=True, exist_ok=True)
        (project_dir / "workflow").mkdir(parents=True, exist_ok=True)
        _write_json_exclusive(project_dir / "manifest.json", manifest)
        _write_json_exclusive(
            project_dir / "protocol" / "topic_intake.json", intake.to_dict()
        )
        _write_json_exclusive(project_dir / "project-state.json", state)
    except Exception:
        # The directory did not exist before this call, so this only removes our
        # own incomplete initialization and can never erase a pre-existing project.
        shutil.rmtree(project_dir)
        raise
    return state


def _verified_original_project(
    project_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not project_dir.is_dir():
        raise ValueError(f"project directory does not exist: {project_dir}")
    manifest = _read_json(project_dir / "manifest.json", label="project manifest")
    intake_payload = _read_json(
        project_dir / "protocol" / "topic_intake.json", label="original-study intake"
    )
    if not isinstance(manifest, dict) or not isinstance(intake_payload, dict):
        raise ValueError("original-study manifest and intake must be JSON objects")
    rebuilt = build_original_study_manifest(
        validate_original_study_intake(intake_payload)
    )
    for field in (
        "schema_version",
        "project_id",
        "topic_fingerprint_sha256",
        "study_family",
        "registration_applicability",
        "pipeline",
    ):
        if manifest.get(field) != rebuilt.get(field):
            raise ValueError(
                f"frozen original-study manifest does not match the intake: {field}"
            )
    return manifest, intake_payload


def _restore_original_state(
    state: Any,
    manifest: Mapping[str, Any],
    intake_payload: Mapping[str, Any],
) -> OriginalStudyWorkflow:
    if not isinstance(state, dict):
        raise ValueError("project state must be a JSON object")
    allowed = {
        "schema_version",
        "project_id",
        "topic_fingerprint_sha256",
        "status",
        "current_stage",
        "next_stage",
        "required_evidence",
        "blockers",
        "next_action",
        "workflow",
        "state_fingerprint_sha256",
    }
    if set(state) - allowed:
        raise ValueError("project state has unknown fields")
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("unsupported project-state schema")
    if state.get("project_id") != manifest.get("project_id"):
        raise ValueError("project state does not belong to this manifest")
    if state.get("topic_fingerprint_sha256") != manifest.get(
        "topic_fingerprint_sha256"
    ):
        raise ValueError("project state topic fingerprint does not match the manifest")
    stored = state.get("state_fingerprint_sha256")
    unsigned = {key: value for key, value in state.items() if key != "state_fingerprint_sha256"}
    if not isinstance(stored, str) or stored != _state_fingerprint(unsigned):
        raise ValueError("project state integrity check failed")
    snapshot = state.get("workflow")
    if not isinstance(snapshot, dict) or snapshot.get("pipeline") != manifest.get("pipeline"):
        raise ValueError("workflow pipeline does not match the frozen manifest")
    workflow = OriginalStudyWorkflow.from_snapshot(intake_payload, snapshot)
    if workflow.snapshot() != snapshot:
        raise ValueError("workflow snapshot changed during integrity validation")
    rebuilt = _state_document(manifest, workflow)
    for key in (
        "status",
        "current_stage",
        "next_stage",
        "required_evidence",
        "blockers",
        "next_action",
    ):
        if state.get(key) != rebuilt.get(key):
            raise ValueError(f"project state {key} does not reconcile with workflow")
    return workflow


def create_original_study_project(
    topic_path: Path, project_dir: Path
) -> dict[str, Any]:
    payload = _read_json(topic_path, label="original-study intake")
    if not isinstance(payload, dict):
        raise ValueError("original-study intake must be a JSON object")
    intake = validate_original_study_intake(payload)
    manifest = build_original_study_manifest(intake)
    workflow = OriginalStudyWorkflow(intake)
    state = _state_document(manifest, workflow)
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ValueError(
            f"refusing to initialize over an existing path: {project_dir}"
        ) from exc
    try:
        for directory in manifest["directories"]:
            (project_dir / directory).mkdir(parents=True, exist_ok=True)
        _write_json_exclusive(project_dir / "manifest.json", manifest)
        _write_json_exclusive(
            project_dir / "protocol" / "topic_intake.json", intake.to_dict()
        )
        _write_json_exclusive(project_dir / "project-state.json", state)
    except Exception:
        shutil.rmtree(project_dir)
        raise
    return state


def advance_original_study_project(
    project_dir: Path,
    evidence_path: Path,
    *,
    reviewer: str,
    decision_date: str,
    to_stage: str | None = None,
) -> dict[str, Any]:
    evidence = _read_json(evidence_path, label="gate evidence")
    if not isinstance(evidence, dict):
        raise ValueError("gate evidence must be a JSON object")
    state_path = project_dir / "project-state.json"
    with _project_lock(project_dir):
        manifest, intake_payload = _verified_original_project(project_dir)
        state = _read_json(state_path, label="project state")
        workflow = _restore_original_state(state, manifest, intake_payload)
        _verify_historical_evidence_artifacts(project_dir, workflow)
        _verify_gate_evidence_artifacts(project_dir, evidence)
        workflow.advance(
            evidence,
            reviewer=reviewer,
            decision_date=decision_date,
            to_stage=to_stage,
        )
        new_state = _state_document(manifest, workflow)
        _write_json_atomic(state_path, new_state)
        _write_jsonl_atomic(
            project_dir / "audit" / "gate-transitions.jsonl",
            workflow.snapshot()["transitions"],
        )
    return new_state


def advance_review_project(
    project_dir: Path,
    evidence_path: Path,
    *,
    reviewer: str,
    decision_date: str,
    to_stage: str | None = None,
) -> dict[str, Any]:
    """Advance exactly one evidence gate and atomically persist the new state."""

    evidence = _read_json(evidence_path, label="gate evidence")
    if not isinstance(evidence, dict):
        raise ValueError("gate evidence must be a JSON object")

    state_path = project_dir / "project-state.json"
    with _project_lock(project_dir):
        manifest, intake_payload = _verified_project(project_dir)
        state = _read_json(state_path, label="project state")
        workflow = _restore_state(
            state, manifest, intake_payload["accountable_reviewers"]
        )
        _verify_historical_evidence_artifacts(project_dir, workflow)
        _verify_gate_evidence_artifacts(project_dir, evidence)
        workflow.advance(
            evidence,
            reviewer=reviewer,
            decision_date=decision_date,
            to_stage=to_stage,
        )
        new_state = _state_document(manifest, workflow)
        _write_json_atomic(state_path, new_state)
        _write_jsonl_atomic(
            project_dir / "audit" / "gate-transitions.jsonl",
            workflow.snapshot()["transitions"],
        )
    return new_state


def _parse_estimates(value: Any) -> list[EffectEstimate]:
    if isinstance(value, dict):
        if set(value) != {"estimates"}:
            raise ValueError("estimate object must contain only the 'estimates' field")
        value = value["estimates"]
    if not isinstance(value, list):
        raise ValueError("estimates JSON must be an array or an object containing estimates")
    estimates: list[EffectEstimate] = []
    expected = {"study_id", "effect", "standard_error"}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"estimate {index} must be an object")
        if set(item) != expected:
            missing = sorted(expected - set(item))
            unknown = sorted(set(item) - expected)
            details: list[str] = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unknown:
                details.append("unknown " + ", ".join(unknown))
            raise ValueError(f"estimate {index} has invalid fields: " + "; ".join(details))
        if not isinstance(item["study_id"], str):
            raise ValueError(f"estimate {index} study_id must be a string")
        for field in ("effect", "standard_error"):
            if isinstance(item[field], bool) or not isinstance(item[field], (int, float)):
                raise ValueError(f"estimate {index} {field} must be a JSON number")
        estimates.append(
            EffectEstimate(
                study_id=item["study_id"],
                effect=float(item["effect"]),
                standard_error=float(item["standard_error"]),
            )
        )
    return estimates


def _parse_pooling_approval(value: Any) -> PoolingApproval:
    if not isinstance(value, dict):
        raise ValueError("pooling approval must be a JSON object")
    expected = {"artifact", "sha256", "approved_by", "approved_on", "rationale"}
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise ValueError("pooling approval has invalid fields: " + "; ".join(details))
    if not all(isinstance(value[field], str) for field in expected - {"approved_by"}):
        raise ValueError("pooling approval text fields must be strings")
    approved_by = value["approved_by"]
    if not isinstance(approved_by, list) or any(
        not isinstance(item, str) for item in approved_by
    ):
        raise ValueError("pooling approval approved_by must be an array of strings")
    return PoolingApproval(
        artifact=value["artifact"],
        sha256=value["sha256"],
        approved_by=tuple(approved_by),
        approved_on=value["approved_on"],
        rationale=value["rationale"],
    )


def _verify_pooling_approval_artifact(
    project_dir: Path,
    approval: PoolingApproval,
    accountable_reviewers: Sequence[str],
) -> None:
    reviewer_keys = {value.casefold() for value in accountable_reviewers}
    unknown = [
        value for value in approval.approved_by if value.strip().casefold() not in reviewer_keys
    ]
    if unknown:
        raise ValueError(
            "pooling approval contains reviewers outside the frozen project intake: "
            + ", ".join(unknown)
        )

    project_root = project_dir.resolve(strict=True)
    relative = PurePosixPath(approval.artifact)
    candidate = (project_root / Path(*relative.parts)).resolve(strict=True)
    if not candidate.is_relative_to(project_root) or not candidate.is_file():
        raise ValueError(
            "pooling approval artifact must resolve to a regular file inside the project"
        )
    digest = sha256()
    try:
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"cannot verify pooling approval artifact: {exc}") from exc
    if digest.hexdigest() != approval.sha256.strip().casefold():
        raise ValueError("pooling approval artifact SHA-256 does not match the file")


def _success(command: str, **values: Any) -> None:
    print(_canonical_json({"command": command, "ok": True, **values}))


def _failure(command: str, exc: Exception) -> None:
    print(
        _canonical_json(
            {
                "command": command,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "ok": False,
            }
        ),
        file=sys.stderr,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="medical-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-search", help="Build database-specific search queries")
    build.add_argument("--config", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)

    pilot = subparsers.add_parser(
        "run-pilot", help="Build queries and deduplicate a frozen metadata pilot"
    )
    pilot.add_argument("--config", required=True, type=Path)
    pilot.add_argument("--records", required=True, type=Path)
    pilot.add_argument("--output", required=True, type=Path)

    initialize = subparsers.add_parser(
        "init-review", help="Validate a topic and create a non-overwriting review project"
    )
    initialize.add_argument("--topic", required=True, type=Path)
    initialize.add_argument("--output", required=True, type=Path)

    provisional = subparsers.add_parser(
        "init-topic",
        help="Open a provisional collaboration checkpoint from a concise topic",
    )
    provisional.add_argument("--topic", required=True, type=Path)
    provisional.add_argument("--output", required=True, type=Path)

    original = subparsers.add_parser(
        "init-original-study",
        help="Validate and initialize an original clinical study or thesis project",
    )
    original.add_argument("--topic", required=True, type=Path)
    original.add_argument("--output", required=True, type=Path)

    advance = subparsers.add_parser(
        "advance-review", help="Complete one evidence gate in a persistent review project"
    )
    advance.add_argument("--project", required=True, type=Path)
    advance.add_argument("--evidence", required=True, type=Path)
    advance.add_argument("--reviewer", required=True)
    advance.add_argument("--decision-date", required=True)
    advance.add_argument("--to-stage")

    advance_original = subparsers.add_parser(
        "advance-original-study",
        help="Complete one evidence gate in an original-study or thesis project",
    )
    advance_original.add_argument("--project", required=True, type=Path)
    advance_original.add_argument("--evidence", required=True, type=Path)
    advance_original.add_argument("--reviewer", required=True)
    advance_original.add_argument("--decision-date", required=True)
    advance_original.add_argument("--to-stage")

    prisma = subparsers.add_parser(
        "derive-prisma", help="Derive PRISMA counts from JSON or JSONL screening events"
    )
    prisma.add_argument("--records", required=True, type=Path)
    prisma.add_argument("--output", required=True, type=Path)
    prisma.add_argument(
        "--project",
        type=Path,
        help="Review project supplying the frozen accountable human reviewer list",
    )
    prisma.add_argument(
        "--accountable-reviewer",
        action="append",
        default=[],
        help="Named human reviewer; repeat at least twice when --project is omitted",
    )
    prisma.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Permit a clearly marked interim flow with incomplete downstream coverage",
    )

    prior = subparsers.add_parser(
        "derive-prior",
        help="Derive PRIOR review-selection flow for an umbrella-review project",
    )
    prior.add_argument("--records", required=True, type=Path)
    prior.add_argument("--output", required=True, type=Path)
    prior.add_argument("--project", required=True, type=Path)
    prior.add_argument("--allow-incomplete", action="store_true")

    overlap = subparsers.add_parser(
        "assess-overlap", help="Calculate corrected covered area from a review-study map"
    )
    overlap.add_argument("--matrix", required=True, type=Path)
    overlap.add_argument("--output", required=True, type=Path)
    overlap.add_argument("--comparison", required=True)
    overlap.add_argument("--outcome", required=True)
    overlap.add_argument("--time-point", required=True)

    meta = subparsers.add_parser(
        "run-meta", help="Pool verified generic inverse-variance estimates"
    )
    meta.add_argument("--estimates", required=True, type=Path)
    meta.add_argument("--output", required=True, type=Path)
    meta.add_argument(
        "--project",
        required=True,
        type=Path,
        help="Frozen systematic-review-with-meta-analysis project",
    )
    meta.add_argument("--model", choices=("fixed", "random"), default="random")
    meta.add_argument("--confidence-level", type=float, default=0.95)
    meta.add_argument("--effect-measure", required=True)
    meta.add_argument("--analysis-scale", choices=("identity", "log"), required=True)
    meta.add_argument(
        "--pooling-approval",
        required=True,
        type=Path,
        help="Traceable JSON approval signed by at least two named human reviewers",
    )
    return parser


def _run(args: argparse.Namespace) -> None:
    if args.command == "build-search":
        config = _read_json(args.config, label="search config")
        if not isinstance(config, dict):
            raise ValueError("search config must be a JSON object")
        payload = {"project_id": config.get("project_id", ""), "queries": build_queries(config)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(args.output, payload)
        _success(args.command, output=str(args.output))
        return

    if args.command == "run-pilot":
        config = _read_json(args.config, label="pilot config")
        records = _read_json(args.records, label="pilot records")
        if not isinstance(config, dict):
            raise ValueError("pilot config must be a JSON object")
        payload = run_pilot(config, records)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(args.output, payload)
        _success(args.command, output=str(args.output))
        return

    if args.command == "init-review":
        state = create_review_project(args.topic, args.output)
        workflow = state["workflow"]
        _success(
            args.command,
            output=str(args.output),
            project_id=state["project_id"],
            current_stage=workflow["current_stage"],
            next_stage=workflow["next_stage"],
            required_evidence=list(required_evidence_for_stage(workflow["current_stage"])),
        )
        return

    if args.command == "init-topic":
        payload = _read_json(args.topic, label="provisional topic")
        if not isinstance(payload, dict):
            raise ValueError("provisional topic must be a JSON object")
        state = initialize_provisional_topic_project(payload, args.output)
        _success(
            args.command,
            output=str(args.output),
            project_id=state["project_id"],
            current_stage=state["current_stage"],
            route_hint=state["route_hint"],
            blockers=state["blockers"],
            next_action=state["next_action"],
        )
        return

    if args.command == "init-original-study":
        state = create_original_study_project(args.topic, args.output)
        workflow = state["workflow"]
        _success(
            args.command,
            output=str(args.output),
            project_id=state["project_id"],
            current_stage=workflow["current_stage"],
            next_stage=workflow["next_stage"],
            required_evidence=list(
                required_original_evidence_for_stage(workflow["current_stage"])
            ),
        )
        return

    if args.command == "advance-review":
        state = advance_review_project(
            args.project,
            args.evidence,
            reviewer=args.reviewer,
            decision_date=args.decision_date,
            to_stage=args.to_stage,
        )
        workflow = state["workflow"]
        required = (
            []
            if workflow["completed"]
            else list(required_evidence_for_stage(workflow["current_stage"]))
        )
        _success(
            args.command,
            output=str(args.project / "project-state.json"),
            project_id=state["project_id"],
            current_stage=workflow["current_stage"],
            next_stage=workflow["next_stage"],
            completed=workflow["completed"],
            required_evidence=required,
        )
        return

    if args.command == "advance-original-study":
        state = advance_original_study_project(
            args.project,
            args.evidence,
            reviewer=args.reviewer,
            decision_date=args.decision_date,
            to_stage=args.to_stage,
        )
        workflow = state["workflow"]
        required = (
            []
            if workflow["completed"]
            else list(required_original_evidence_for_stage(workflow["current_stage"]))
        )
        _success(
            args.command,
            output=str(args.project / "project-state.json"),
            project_id=state["project_id"],
            current_stage=workflow["current_stage"],
            next_stage=workflow["next_stage"],
            completed=workflow["completed"],
            required_evidence=required,
        )
        return

    if args.command == "derive-prisma":
        records = _read_json_records(args.records)
        if args.project is not None and args.accountable_reviewer:
            raise ValueError(
                "use either --project or --accountable-reviewer, not both"
            )
        if args.project is not None:
            _, intake_payload = _verified_project(args.project)
            if intake_payload["review_type"] == "umbrella_review":
                raise ValueError(
                    "umbrella reviews require PRIOR review-level flow, "
                    "not PRISMA primary-study flow"
                )
            accountable_reviewers = intake_payload["accountable_reviewers"]
        else:
            accountable_reviewers = args.accountable_reviewer
        if len(accountable_reviewers) < 2:
            raise ValueError(
                "derive-prisma requires --project or at least two --accountable-reviewer values"
            )
        result = derive_prisma_counts(
            records,
            accountable_reviewers=accountable_reviewers,
            require_complete=not args.allow_incomplete,
        )
        _write_json_exclusive(args.output, result)
        _success(args.command, output=str(args.output), complete=result["complete"])
        return

    if args.command == "derive-prior":
        records = _read_json_records(args.records)
        _, intake_payload = _verified_project(args.project)
        if intake_payload["review_type"] != "umbrella_review":
            raise ValueError("derive-prior requires an umbrella_review project")
        result = derive_prior_counts(
            records,
            accountable_reviewers=intake_payload["accountable_reviewers"],
            require_complete=not args.allow_incomplete,
        )
        _write_json_exclusive(args.output, result)
        _success(args.command, output=str(args.output), complete=result["complete"])
        return

    if args.command == "assess-overlap":
        matrix = _read_json(args.matrix, label="review-study matrix")
        result = corrected_covered_area(
            matrix,
            comparison=args.comparison,
            outcome=args.outcome,
            time_point=args.time_point,
        )
        _write_json_exclusive(args.output, result)
        _success(
            args.command,
            output=str(args.output),
            corrected_covered_area=result["corrected_covered_area"],
        )
        return

    if args.command == "run-meta":
        _, intake_payload = _verified_project(args.project)
        if intake_payload["review_type"] != "systematic_review_with_meta_analysis":
            raise ValueError(
                "run-meta requires a systematic_review_with_meta_analysis project"
            )
        if " ".join(args.effect_measure.split()).casefold() != intake_payload[
            "effect_measure"
        ].casefold():
            raise ValueError(
                "--effect-measure must match the effect measure frozen in topic_intake.json; "
                "record a protocol amendment before changing it"
            )
        raw_estimates = _read_json(args.estimates, label="effect estimates")
        estimates = _parse_estimates(raw_estimates)
        raw_approval = _read_json(args.pooling_approval, label="pooling approval")
        approval = _parse_pooling_approval(raw_approval)
        _verify_pooling_approval_artifact(
            args.project, approval, intake_payload["accountable_reviewers"]
        )
        result = combine_effects(
            estimates,
            effect_measure=args.effect_measure,
            analysis_scale=args.analysis_scale,
            pooling_approval=approval,
            model=args.model,
            confidence_level=args.confidence_level,
        ).to_dict()
        _write_json_exclusive(args.output, result)
        _success(args.command, output=str(args.output), studies=result["studies"])
        return

    raise RuntimeError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    command_hint = arguments[0] if arguments and not arguments[0].startswith("-") else ""
    try:
        args = parser.parse_args(arguments)
        _run(args)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        _failure(command_hint, exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

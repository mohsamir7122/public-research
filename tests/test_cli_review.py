from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
from datetime import date
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import medical_research


CLI_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "medical_research"
    / "__main__.py"
)
SPEC = importlib.util.spec_from_file_location(
    "medical_research._candidate_cli", CLI_PATH
)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


BASE_INTAKE = {
    "review_type": "systematic_review",
    "working_title": "Graft choice and return to sport after primary ACL reconstruction",
    "research_question": (
        "In adults undergoing primary ACL reconstruction, how does graft choice affect "
        "return to sport?"
    ),
    "rationale": (
        "Published comparisons remain clinically heterogeneous and require a transparent "
        "evidence synthesis."
    ),
    "objective": (
        "To compare return-to-sport outcomes after common autograft choices in adults."
    ),
    "population": "Adults undergoing primary anterior cruciate ligament reconstruction",
    "intervention_or_exposure": "Bone-patellar tendon-bone or hamstring autograft",
    "comparator": "Alternative autograft choice",
    "primary_outcome": "Return to preinjury level of sport at 12 months or later",
    "secondary_outcomes": ["Graft failure", "Patient-reported knee function"],
    "eligible_evidence_types": ["Randomized controlled trials", "Prospective cohorts"],
    "inclusion_criteria": ["Primary ACL reconstruction", "Minimum 12-month follow-up"],
    "exclusion_criteria": ["Revision ACL reconstruction", "Skeletally immature cohort"],
    "databases": ["MEDLINE", "Embase", "Scopus"],
    "accountable_reviewers": ["Amina Hassan", "Omar Saleh"],
    "effect_measure": "",
}

TODAY = date.today().isoformat()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def evidence_reference(
    project: Path,
    artifact: str,
    *,
    verified_by=("Amina Hassan",),
    verified_on=TODAY,
):
    artifact_path = project / artifact
    return {
        "artifact": artifact,
        "sha256": sha256(artifact_path.read_bytes()).hexdigest(),
        "verified_by": list(verified_by),
        "verified_on": verified_on,
        "note": "Source artifact reviewed against the prespecified gate.",
    }


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, *arguments: str):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli.main(list(arguments))
        output = json.loads(stdout.getvalue()) if stdout.getvalue() else None
        error = json.loads(stderr.getvalue()) if stderr.getvalue() else None
        return status, output, error

    def initialize(self) -> Path:
        topic = self.root / "topic.json"
        project = self.root / "review-project"
        write_json(topic, BASE_INTAKE)
        status, output, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )
        self.assertEqual(status, 0, error)
        self.assertTrue(output["ok"])
        return project


class InitializationTests(CliTestCase):
    def test_init_creates_valid_minimal_scaffold_and_never_overwrites(self):
        topic = self.root / "topic.json"
        project = self.root / "review-project"
        payload = copy.deepcopy(BASE_INTAKE)
        payload["working_title"] = "  " + payload["working_title"] + "  "
        write_json(topic, payload)

        status, output, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )

        self.assertEqual(status, 0, error)
        self.assertTrue(output["ok"])
        self.assertEqual(output["current_stage"], "topic_intake")
        self.assertEqual(output["required_evidence"], ["intake_validated"])
        manifest = json.loads((project / "manifest.json").read_text(encoding="utf-8"))
        intake = json.loads(
            (project / "protocol" / "topic_intake.json").read_text(encoding="utf-8")
        )
        state_path = project / "project-state.json"
        before = state_path.read_bytes()
        state = json.loads(before)
        self.assertEqual(intake["working_title"], BASE_INTAKE["working_title"])
        self.assertEqual(state["project_id"], manifest["project_id"])
        self.assertEqual(state["workflow"]["transitions"], [])
        self.assertEqual(len(state["state_fingerprint_sha256"]), 64)

        status, output, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )
        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("refusing to initialize", error["error"])
        self.assertEqual(state_path.read_bytes(), before)

    def test_invalid_intake_leaves_no_project_directory(self):
        topic = self.root / "topic.json"
        project = self.root / "review-project"
        payload = copy.deepcopy(BASE_INTAKE)
        payload["accountable_reviewers"] = ["Amina Hassan"]
        write_json(topic, payload)

        status, output, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("accountable_reviewers requires at least 2", error["error"])
        self.assertFalse(project.exists())

    def test_sparse_topic_opens_as_provisional_checkpoint(self):
        topic = self.root / "brief.json"
        project = self.root / "topic-project"
        write_json(
            topic,
            {
                "topic": "Return to sport after revision ACL reconstruction",
                "route_hint": "meta-meta analysis",
            },
        )
        status, output, error = self.invoke(
            "init-topic", "--topic", str(topic), "--output", str(project)
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output["route_hint"], "umbrella_review")
        self.assertEqual(output["current_stage"], "topic_intake")
        self.assertTrue(output["blockers"])
        state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
        self.assertIn("not a frozen protocol", state["truth_boundary"])


class AdvanceTests(CliTestCase):
    def test_advance_replays_evidence_ledger_and_persists_one_gate(self):
        project = self.initialize()
        evidence = self.root / "gate.json"
        write_json(
            evidence,
            {
                "intake_validated": evidence_reference(
                    project,
                    "protocol/topic_intake.json"
                )
            },
        )

        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(evidence),
            "--reviewer",
            "Amina Hassan",
            "--decision-date",
            TODAY,
            "--to-stage",
            "protocol",
        )

        self.assertEqual(status, 0, error)
        self.assertEqual(output["current_stage"], "protocol")
        self.assertEqual(
            output["required_evidence"],
            [
                "protocol_frozen",
                "eligibility_criteria_frozen",
                "outcome_definitions_frozen",
            ],
        )
        state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["workflow"]["transitions"]), 1)
        self.assertEqual(
            state["workflow"]["transitions"][0]["evidence"]["intake_validated"][
                "artifact"
            ],
            "protocol/topic_intake.json",
        )
        self.assertEqual(
            len(state["workflow"]["transitions"][0]["transition_sha256"]), 64
        )

        second_evidence = self.root / "protocol-gate.json"
        (project / "protocol" / "protocol.md").write_text(
            "# Synthetic protocol artifact\n", encoding="utf-8"
        )
        write_json(
            second_evidence,
            {
                "protocol_frozen": evidence_reference(
                    project,
                    "protocol/protocol.md",
                    verified_by=("Amina Hassan", "Omar Saleh"),
                    verified_on=TODAY,
                ),
                "eligibility_criteria_frozen": evidence_reference(
                    project,
                    "protocol/protocol.md",
                    verified_by=("Amina Hassan", "Omar Saleh"),
                    verified_on=TODAY,
                ),
                "outcome_definitions_frozen": evidence_reference(
                    project,
                    "protocol/protocol.md",
                    verified_by=("Amina Hassan", "Omar Saleh"),
                    verified_on=TODAY,
                ),
            },
        )
        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(second_evidence),
            "--reviewer",
            "Omar Saleh",
            "--decision-date",
            TODAY,
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output["current_stage"], "registration")

    def test_missing_gate_evidence_does_not_mutate_state(self):
        project = self.initialize()
        state_path = project / "project-state.json"
        before = state_path.read_bytes()
        evidence = self.root / "gate.json"
        write_json(evidence, {})

        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(evidence),
            "--reviewer",
            "Amina Hassan",
            "--decision-date",
            TODAY,
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("missing evidence", error["error"])
        self.assertEqual(state_path.read_bytes(), before)
        self.assertFalse((project / ".project-state.lock").exists())

    def test_tampered_state_fails_closed(self):
        project = self.initialize()
        state_path = project / "project-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["workflow"]["current_stage"] = "completed"
        write_json(state_path, state)
        evidence = self.root / "gate.json"
        write_json(
            evidence,
            {
                "intake_validated": evidence_reference(
                    project, "protocol/topic_intake.json"
                )
            },
        )

        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(evidence),
            "--reviewer",
            "Amina Hassan",
            "--decision-date",
            TODAY,
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("integrity check failed", error["error"])

    def test_gate_artifact_checksum_is_verified_before_state_mutation(self):
        project = self.initialize()
        state_path = project / "project-state.json"
        before = state_path.read_bytes()
        evidence = self.root / "gate.json"
        reference = evidence_reference(project, "protocol/topic_intake.json")
        reference["sha256"] = "f" * 64
        write_json(evidence, {"intake_validated": reference})

        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(evidence),
            "--reviewer",
            "Amina Hassan",
            "--decision-date",
            TODAY,
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("SHA-256 does not match", error["error"])
        self.assertEqual(state_path.read_bytes(), before)

    def test_changed_historical_artifact_blocks_the_next_gate(self):
        project = self.initialize()
        reviewed_intake = project / "protocol" / "intake-review.md"
        reviewed_intake.write_text(
            "# Human review of the frozen intake\n", encoding="utf-8"
        )
        first_evidence = self.root / "first-gate.json"
        write_json(
            first_evidence,
            {
                "intake_validated": evidence_reference(
                    project, "protocol/intake-review.md"
                )
            },
        )
        status, _, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(first_evidence),
            "--reviewer",
            "Amina Hassan",
            "--decision-date",
            TODAY,
        )
        self.assertEqual(status, 0, error)

        state_path = project / "project-state.json"
        before = state_path.read_bytes()
        reviewed_intake.write_text(
            "# Changed after the gate\n", encoding="utf-8"
        )
        protocol = project / "protocol" / "protocol.md"
        protocol.write_text("# Synthetic protocol\n", encoding="utf-8")
        second_evidence = self.root / "second-gate.json"
        reference = evidence_reference(
            project,
            "protocol/protocol.md",
            verified_by=("Amina Hassan", "Omar Saleh"),
        )
        write_json(
            second_evidence,
            {
                "protocol_frozen": reference,
                "eligibility_criteria_frozen": reference,
                "outcome_definitions_frozen": reference,
            },
        )

        status, output, error = self.invoke(
            "advance-review",
            "--project",
            str(project),
            "--evidence",
            str(second_evidence),
            "--reviewer",
            "Omar Saleh",
            "--decision-date",
            TODAY,
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("historical evidence failed verification", error["error"])
        self.assertEqual(state_path.read_bytes(), before)


class DerivationTests(CliTestCase):
    def test_derive_prisma_accepts_jsonl_and_refuses_output_overwrite(self):
        project = self.initialize()
        records = self.root / "screening.jsonl"
        events = [
            {
                "record_id": "r1",
                "stage": "identification",
                "decision": "identified",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": True,
                "source_type": "database",
                "source_name": "MEDLINE",
            },
            {
                "record_id": "r1",
                "stage": "deduplication",
                "decision": "retained",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": True,
            },
            {
                "record_id": "r1",
                "stage": "title_abstract",
                "decision": "include",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": False,
            },
            {
                "record_id": "r1",
                "stage": "title_abstract",
                "decision": "include",
                "reviewer": "Omar Saleh",
                "decision_date": TODAY,
                "is_final": False,
            },
            {
                "record_id": "r1",
                "stage": "title_abstract",
                "decision": "include",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": True,
            },
            {
                "record_id": "r1",
                "stage": "retrieval",
                "decision": "retrieved",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": True,
            },
            {
                "record_id": "r1",
                "stage": "full_text",
                "decision": "include",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": False,
                "study_id": "Study-1",
            },
            {
                "record_id": "r1",
                "stage": "full_text",
                "decision": "include",
                "reviewer": "Omar Saleh",
                "decision_date": TODAY,
                "is_final": False,
                "study_id": "Study-1",
            },
            {
                "record_id": "r1",
                "stage": "full_text",
                "decision": "include",
                "reviewer": "Amina Hassan",
                "decision_date": TODAY,
                "is_final": True,
                "study_id": "Study-1",
            },
        ]
        records.write_text(
            "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
            encoding="utf-8",
        )
        output_path = self.root / "prisma.json"

        status, output, error = self.invoke(
            "derive-prisma",
            "--records",
            str(records),
            "--output",
            str(output_path),
            "--project",
            str(project),
        )
        self.assertEqual(status, 0, error)
        self.assertTrue(output["complete"])
        counts = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(counts["studies_included_in_review"], 1)
        before = output_path.read_bytes()

        status, output, error = self.invoke(
            "derive-prisma",
            "--records",
            str(records),
            "--output",
            str(output_path),
            "--project",
            str(project),
        )
        self.assertEqual(status, 2)
        self.assertIn("refusing to overwrite", error["error"])
        self.assertEqual(output_path.read_bytes(), before)

    def test_assess_overlap_writes_deterministic_result(self):
        matrix = self.root / "matrix.json"
        output_path = self.root / "overlap.json"
        write_json(
            matrix,
            {"Review-B": ["Study-A", "Study-B"], "Review-A": ["Study-A"]},
        )

        status, output, error = self.invoke(
            "assess-overlap",
            "--matrix",
            str(matrix),
            "--output",
            str(output_path),
            "--comparison",
            "Autograft A versus autograft B",
            "--outcome",
            "Return to sport",
            "--time-point",
            "12 months or later",
        )

        self.assertEqual(status, 0, error)
        self.assertAlmostEqual(output["corrected_covered_area"], 0.5)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(result["review_ids"], ["Review-A", "Review-B"])

    def test_derive_prior_uses_review_level_identifiers(self):
        topic = self.root / "umbrella-topic.json"
        project = self.root / "umbrella-project"
        payload = copy.deepcopy(BASE_INTAKE)
        payload["review_type"] = "umbrella_review"
        payload["eligible_evidence_types"] = ["Systematic reviews with meta-analysis"]
        write_json(topic, payload)
        status, _, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )
        self.assertEqual(status, 0, error)

        records = self.root / "review-screening.json"
        base = {
            "record_id": "review-report-1",
            "reviewer": "Amina Hassan",
            "decision_date": TODAY,
            "is_final": True,
        }
        events = [
            {**base, "stage": "identification", "decision": "identified", "source_type": "database", "source_name": "MEDLINE"},
            {**base, "stage": "deduplication", "decision": "retained"},
            {**base, "stage": "title_abstract", "decision": "include", "is_final": False},
            {**base, "stage": "title_abstract", "decision": "include", "reviewer": "Omar Saleh", "is_final": False},
            {**base, "stage": "title_abstract", "decision": "include"},
            {**base, "stage": "retrieval", "decision": "retrieved"},
            {**base, "stage": "full_text", "decision": "include", "review_id": "Review-1", "is_final": False},
            {**base, "stage": "full_text", "decision": "include", "review_id": "Review-1", "reviewer": "Omar Saleh", "is_final": False},
            {**base, "stage": "full_text", "decision": "include", "review_id": "Review-1"},
        ]
        write_json(records, events)
        output_path = self.root / "prior.json"
        status, output, error = self.invoke(
            "derive-prior",
            "--records",
            str(records),
            "--output",
            str(output_path),
            "--project",
            str(project),
        )
        self.assertEqual(status, 0, error)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(result["reporting_framework"], "PRIOR")
        self.assertEqual(result["systematic_reviews_included_in_overview"], 1)


class MetaAnalysisCliTests(CliTestCase):
    def test_run_meta_requires_traceable_clinical_pooling_approval(self):
        topic = self.root / "meta-topic.json"
        project = self.root / "meta-project"
        topic_payload = copy.deepcopy(BASE_INTAKE)
        topic_payload["review_type"] = "systematic_review_with_meta_analysis"
        topic_payload["effect_measure"] = "Mean difference"
        write_json(topic, topic_payload)
        status, _, error = self.invoke(
            "init-review", "--topic", str(topic), "--output", str(project)
        )
        self.assertEqual(status, 0, error)

        estimates = self.root / "estimates.json"
        approval = self.root / "approval.json"
        output_path = self.root / "meta.json"
        decision_artifact = project / "analysis" / "pooling_decision.json"
        write_json(
            decision_artifact,
            {
                "decision": "pool",
                "scope": "Prespecified primary outcome at the prespecified time point",
            },
        )
        decision_sha256 = sha256(decision_artifact.read_bytes()).hexdigest()
        write_json(
            estimates,
            [
                {"study_id": "Study-A", "effect": -0.2, "standard_error": 0.1},
                {"study_id": "Study-B", "effect": 0.1, "standard_error": 0.15},
                {"study_id": "Study-C", "effect": 0.0, "standard_error": 0.12},
            ],
        )
        write_json(
            approval,
            {
                "artifact": "analysis/pooling_decision.json",
                "sha256": decision_sha256,
                "approved_by": ["Amina Hassan"],
                "approved_on": TODAY,
                "rationale": (
                    "The studies were reviewed for compatible populations, outcomes, "
                    "time points, scales, and units of analysis."
                ),
            },
        )

        status, output, error = self.invoke(
            "run-meta",
            "--estimates",
            str(estimates),
            "--output",
            str(output_path),
            "--project",
            str(project),
            "--effect-measure",
            "Mean difference",
            "--analysis-scale",
            "identity",
            "--pooling-approval",
            str(approval),
        )
        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("at least two named human approvers", error["error"])
        self.assertFalse(output_path.exists())

        valid_approval = json.loads(approval.read_text(encoding="utf-8"))
        valid_approval["approved_by"] = ["Amina Hassan", "Omar Saleh"]
        write_json(approval, valid_approval)

        status, output, error = self.invoke(
            "run-meta",
            "--estimates",
            str(estimates),
            "--output",
            str(output_path),
            "--project",
            str(project),
            "--effect-measure",
            "Mean difference",
            "--analysis-scale",
            "identity",
            "--pooling-approval",
            str(approval),
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output["studies"], 3)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(result["studies"], 3)
        self.assertIn("does not establish eligibility", result["truth_boundary"])


class StrictJsonTests(CliTestCase):
    def test_duplicate_json_keys_are_rejected(self):
        matrix = self.root / "matrix.json"
        matrix.write_text(
            '{"Review-A":["Study-A"],"Review-A":["Study-B"]}\n',
            encoding="utf-8",
        )
        output_path = self.root / "overlap.json"

        status, output, error = self.invoke(
            "assess-overlap",
            "--matrix",
            str(matrix),
            "--output",
            str(output_path),
            "--comparison",
            "Autograft A versus autograft B",
            "--outcome",
            "Return to sport",
            "--time-point",
            "12 months or later",
        )

        self.assertEqual(status, 2)
        self.assertIsNone(output)
        self.assertIn("duplicate JSON object key", error["error"])
        self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()

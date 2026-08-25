import copy
from datetime import date
from hashlib import sha256
import unittest

from medical_research.original_study_workflow import (
    OriginalStudyIntakeError,
    OriginalStudyWorkflow,
    build_original_study_manifest,
    required_original_evidence_for_stage,
    validate_original_study_intake,
)


BASE_INTAKE = {
    "study_family": "observational",
    "working_title": "Recovery trajectories after operative treatment of ankle fractures",
    "research_question": (
        "Among adults treated operatively for an ankle fracture, which baseline factors "
        "are associated with function twelve months after surgery?"
    ),
    "rationale": (
        "Postoperative recovery varies substantially, while locally applicable prognostic "
        "information remains limited."
    ),
    "primary_objective": (
        "To estimate associations between prespecified baseline factors and twelve-month "
        "patient-reported function."
    ),
    "secondary_objectives": [
        "To describe complications during the first postoperative year."
    ],
    "study_design": "Prospective observational cohort study",
    "design_rationale": (
        "A prospective cohort supports consistent baseline measurement and longitudinal "
        "outcome ascertainment without assigning treatment."
    ),
    "population": "Adults undergoing operative treatment of an acute ankle fracture",
    "setting": "Orthopaedic trauma service at the participating teaching hospital",
    "inclusion_criteria": [
        "Age eighteen years or older",
        "Operatively managed acute ankle fracture",
    ],
    "exclusion_criteria": [
        "Pathological fracture",
        "Unable to complete the prespecified outcome instrument",
    ],
    "intervention_or_exposure": (
        "Prespecified demographic, injury, and perioperative baseline factors"
    ),
    "comparison_strategy": (
        "Adjusted comparisons across prespecified factor levels; no treatment is assigned"
    ),
    "primary_outcome": "Twelve-month patient-reported ankle function score",
    "secondary_outcomes": ["Reoperation within twelve months"],
    "data_source_and_recruitment": (
        "Consecutive eligible patients approached prospectively with outcomes collected "
        "at prespecified visits"
    ),
    "sample_size_basis": (
        "Precision and model-complexity calculations will use the anticipated eligible "
        "caseload and prespecified primary analysis"
    ),
    "feasibility_summary": (
        "The service maintains a screening log, trained outcome assessors, and a twelve-"
        "month follow-up pathway; access remains subject to institutional authorization"
    ),
    "analysis_overview": (
        "The primary adjusted association model, functional form checks, missing-data "
        "handling, and sensitivity analyses will be frozen in the statistical plan"
    ),
    "reporting_framework": "STROBE framework selected by the accountable methods team",
    "ethics_jurisdiction": "Participating hospital and university research governance",
    "registration_applicability": "not_required",
    "registration_basis": (
        "The accountable investigators recorded a jurisdiction-specific assessment that "
        "this noninterventional cohort does not require trial registration"
    ),
    "sponsor_or_institution": "Participating university and teaching hospital",
    "accountable_humans": ["Dr Nora Hassan", "Prof Omar Khalil"],
}

TODAY = date.today().isoformat()


def reference(name):
    artifact = f"artifacts/{name}.json"
    return {
        "artifact": artifact,
        "sha256": sha256(artifact.encode("utf-8")).hexdigest(),
        "verified_by": ["Dr Nora Hassan", "Prof Omar Khalil"],
        "verified_on": TODAY,
        "note": "Synthetic test evidence reference",
    }


def gate_evidence(stage):
    return {
        key: reference(f"{stage}/{key}")
        for key in required_original_evidence_for_stage(stage)
    }


class IntakeTests(unittest.TestCase):
    def test_valid_intake_is_normalized_and_immutable(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload["working_title"] = "  " + payload["working_title"] + "  "

        intake = validate_original_study_intake(payload)

        self.assertEqual(intake.working_title, BASE_INTAKE["working_title"])
        self.assertIsInstance(intake.inclusion_criteria, tuple)
        self.assertEqual(intake.accountable_humans, ("Dr Nora Hassan", "Prof Omar Khalil"))

    def test_malformed_intake_reports_multiple_errors(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload.update(
            {
                "study_family": "universal_design",
                "working_title": "TBD",
                "inclusion_criteria": [],
                "accountable_humans": ["ChatGPT", "Reviewer One"],
                "invented_approval": "approved",
            }
        )

        with self.assertRaises(OriginalStudyIntakeError) as raised:
            validate_original_study_intake(payload)

        message = str(raised.exception)
        self.assertIn("unknown fields", message)
        self.assertIn("study_family must be one of", message)
        self.assertIn("working_title contains a placeholder", message)
        self.assertIn("inclusion_criteria requires at least 1", message)
        self.assertIn("named people, not roles or AI systems", message)

    def test_two_distinct_named_accountable_humans_are_mandatory(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload["accountable_humans"] = ["Dr Nora Hassan"]
        with self.assertRaisesRegex(OriginalStudyIntakeError, "at least 2"):
            validate_original_study_intake(payload)

        payload["accountable_humans"] = ["Dr Nora Hassan", "Codex Assistant"]
        with self.assertRaisesRegex(OriginalStudyIntakeError, "not roles or AI systems"):
            validate_original_study_intake(payload)

    def test_design_and_registration_are_human_supplied_not_inferred(self):
        observational = validate_original_study_intake(BASE_INTAKE)
        self.assertEqual(observational.study_design, "Prospective observational cohort study")
        self.assertEqual(observational.registration_applicability, "not_required")

        interventional = copy.deepcopy(BASE_INTAKE)
        interventional.update(
            {
                "study_family": "interventional",
                "study_design": "Single-arm feasibility intervention study",
                "design_rationale": (
                    "A single-arm feasibility design addresses delivery and retention before "
                    "a comparative effectiveness study is considered"
                ),
                "intervention_or_exposure": "A prespecified postoperative rehabilitation pathway",
                "comparison_strategy": (
                    "No concurrent comparator is planned because the objective is feasibility; "
                    "progression criteria are prespecified"
                ),
                "registration_applicability": "required",
                "registration_basis": (
                    "The accountable investigators recorded that prospective registration is "
                    "required under the applicable institutional and journal policies"
                ),
                "reporting_framework": (
                    "A design-appropriate intervention reporting framework selected by the team"
                ),
            }
        )
        validated = validate_original_study_intake(interventional)
        self.assertEqual(validated.study_family, "interventional")
        self.assertIn("No concurrent comparator", validated.comparison_strategy)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_content_addressed(self):
        first = build_original_study_manifest(copy.deepcopy(BASE_INTAKE))
        second = build_original_study_manifest(copy.deepcopy(BASE_INTAKE))

        self.assertEqual(first, second)
        self.assertRegex(first["project_id"], r"^OS-[0-9A-F]{12}$")
        self.assertEqual(len(first["topic_fingerprint_sha256"]), 64)
        self.assertEqual(first["pipeline"][-1], "completed")

        changed = copy.deepcopy(BASE_INTAKE)
        changed["primary_outcome"] = "Twelve-month physical function subscale"
        self.assertNotEqual(
            first["project_id"], build_original_study_manifest(changed)["project_id"]
        )

    def test_manifest_routes_design_and_registration_without_universal_assumptions(self):
        observational = build_original_study_manifest(BASE_INTAKE)
        observational_paths = {item["path"] for item in observational["files"]}
        self.assertIn("observational_bias_control_plan", observational["pipeline"])
        self.assertNotIn("registration", observational["pipeline"])
        self.assertIn("methods/observational_bias_control_plan.md", observational_paths)
        self.assertNotIn("registration/registry_record.json", observational_paths)

        intervention = copy.deepcopy(BASE_INTAKE)
        intervention.update(
            {
                "study_family": "interventional",
                "study_design": "Pragmatic controlled intervention study",
                "design_rationale": (
                    "The pragmatic design evaluates delivery in routine care while preserving "
                    "a prespecified assignment and analysis strategy"
                ),
                "intervention_or_exposure": "Structured postoperative review pathway",
                "registration_applicability": "required",
                "registration_basis": (
                    "The accountable investigators recorded prospective registration as required "
                    "under the applicable policy"
                ),
            }
        )
        routed = build_original_study_manifest(intervention)
        routed_paths = {item["path"] for item in routed["files"]}
        self.assertIn("intervention_and_safety_plan", routed["pipeline"])
        self.assertIn("registration", routed["pipeline"])
        self.assertIn("registration/registry_record.json", routed_paths)

    def test_manifest_states_truth_boundary_and_public_data_rule(self):
        manifest = build_original_study_manifest(BASE_INTAKE)
        self.assertIn("does not authenticate approvals", manifest["truth_boundary"])
        self.assertTrue(
            any("identifiable participant data" in rule for rule in manifest["integrity_rules"])
        )


class WorkflowTests(unittest.TestCase):
    def test_gates_cannot_be_skipped_and_reviewer_must_be_named(self):
        workflow = OriginalStudyWorkflow(BASE_INTAKE)
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
                to_stage="protocol",
            )
        with self.assertRaisesRegex(ValueError, "named accountable_humans"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="Methods Bot",
                decision_date=TODAY,
            )
        self.assertEqual(workflow.current_stage, "topic_intake")

    def test_approval_labels_or_booleans_are_not_evidence(self):
        workflow = OriginalStudyWorkflow(BASE_INTAKE)
        for stage in ("topic_intake", "feasibility", "protocol"):
            workflow.advance(
                gate_evidence(stage),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )
        self.assertEqual(workflow.current_stage, "ethics_and_governance")

        claimed = {
            "ethics_or_exemption_determination": True,
            "governance_authorization": "approved",
            "conditions_and_restrictions_record": True,
            "human_governance_signoff": "Prof Omar Khalil",
        }
        with self.assertRaisesRegex(ValueError, "evidence must contain|missing evidence"):
            workflow.advance(
                claimed,
                reviewer="Prof Omar Khalil",
                decision_date=TODAY,
            )

        claimed_as_reference = {
            key: {"reference": "approved"}
            for key in required_original_evidence_for_stage("ethics_and_governance")
        }
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            workflow.advance(
                claimed_as_reference,
                reviewer="Prof Omar Khalil",
                decision_date=TODAY,
            )

        transition = workflow.advance(
            gate_evidence("ethics_and_governance"),
            reviewer="Prof Omar Khalil",
            decision_date=TODAY,
        )
        self.assertNotIn("approved", transition)
        self.assertNotIn("approval_status", transition)
        self.assertEqual(
            set(transition["evidence_keys"]),
            set(required_original_evidence_for_stage("ethics_and_governance")),
        )

    def test_required_registration_is_non_skippable(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload.update(
            {
                "registration_applicability": "required",
                "registration_basis": (
                    "The accountable investigators recorded prospective registration as required "
                    "under the applicable policy"
                ),
            }
        )
        workflow = OriginalStudyWorkflow(payload)
        while workflow.current_stage != "registration":
            stage = workflow.current_stage
            workflow.advance(
                gate_evidence(stage),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            workflow.advance(
                gate_evidence("registration"),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
                to_stage="data_dictionary",
            )
        self.assertEqual(workflow.current_stage, "registration")

    def test_full_workflow_completes_only_in_order(self):
        workflow = OriginalStudyWorkflow(BASE_INTAKE)
        visited = []
        while not workflow.completed:
            stage = workflow.current_stage
            visited.append(stage)
            workflow.advance(
                gate_evidence(stage),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )

        self.assertLess(visited.index("statistical_analysis_plan"), visited.index("data_lock"))
        self.assertLess(visited.index("data_lock"), visited.index("analysis"))
        self.assertLess(visited.index("quality_assurance"), visited.index("release"))
        self.assertEqual(workflow.current_stage, "completed")
        with self.assertRaisesRegex(RuntimeError, "cannot be advanced"):
            workflow.advance({}, reviewer="Dr Nora Hassan", decision_date=TODAY)

    def test_snapshot_can_resume_only_with_same_intake(self):
        workflow = OriginalStudyWorkflow(BASE_INTAKE)
        workflow.advance(
            gate_evidence("topic_intake"),
            reviewer="Dr Nora Hassan",
            decision_date=TODAY,
        )
        snapshot = workflow.snapshot()

        resumed = OriginalStudyWorkflow.from_snapshot(BASE_INTAKE, snapshot)
        self.assertEqual(resumed.snapshot(), snapshot)
        resumed.advance(
            gate_evidence("feasibility"),
            reviewer="Prof Omar Khalil",
            decision_date=TODAY,
        )
        self.assertEqual(resumed.current_stage, "protocol")

        changed = copy.deepcopy(BASE_INTAKE)
        changed["primary_outcome"] = "Alternative validated functional outcome"
        with self.assertRaisesRegex(ValueError, "does not belong"):
            OriginalStudyWorkflow.from_snapshot(changed, snapshot)

        tampered = copy.deepcopy(snapshot)
        tampered["transitions"][0]["evidence"]["validated_intake"]["artifact"] = "fake.json"
        with self.assertRaisesRegex(ValueError, "fingerprint|hash"):
            OriginalStudyWorkflow.from_snapshot(BASE_INTAKE, tampered)

    def test_future_dates_and_machine_only_evidence_cannot_advance(self):
        workflow = OriginalStudyWorkflow(BASE_INTAKE)
        with self.assertRaisesRegex(ValueError, "future"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="Dr Nora Hassan",
                decision_date="2999-01-01",
            )
        evidence = gate_evidence("topic_intake")
        evidence["validated_intake"]["verified_by"] = ["ChatGPT AI bot"]
        with self.assertRaisesRegex(ValueError, "accountable_humans"):
            workflow.advance(
                evidence,
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )


if __name__ == "__main__":
    unittest.main()

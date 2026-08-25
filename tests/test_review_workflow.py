import copy
from datetime import date
from hashlib import sha256
import unittest

from medical_research.review_workflow import (
    IntakeValidationError,
    ReviewWorkflow,
    build_project_manifest,
    corrected_covered_area,
    derive_prisma_counts,
    derive_prior_counts,
    required_evidence_for_stage,
    validate_topic_intake,
)


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
    "accountable_reviewers": ["Dr Nora Hassan", "Prof Omar Khalil"],
    "effect_measure": "",
}

TODAY = date.today().isoformat()


def gate_evidence(stage, reviewers=("Dr Nora Hassan", "Prof Omar Khalil")):
    values = {}
    for gate in required_evidence_for_stage(stage):
        verified_by = list(reviewers)
        if gate == "methods_review_signed":
            verified_by = [reviewers[0]]
        elif gate == "clinical_review_signed":
            verified_by = [reviewers[1]]
        artifact = f"audit/{stage}-{gate}.json"
        values[gate] = {
            "artifact": artifact,
            "sha256": sha256(artifact.encode("utf-8")).hexdigest(),
            "verified_by": verified_by,
            "verified_on": TODAY,
            "note": "Synthetic test evidence reference",
        }
    return values


def prisma_counts(records, **kwargs):
    return derive_prisma_counts(
        records,
        accountable_reviewers=BASE_INTAKE["accountable_reviewers"],
        **kwargs,
    )


def screening_event(record_id, stage, decision, **kwargs):
    value = {
        "record_id": record_id,
        "stage": stage,
        "decision": decision,
        "reviewer": "Dr Nora Hassan",
        "decision_date": TODAY,
        "is_final": True,
    }
    value.update(kwargs)
    return value


def complete_screening_fixture():
    sources = {
        "r1": ("database", "PubMed"),
        "r2": ("database", "Embase"),
        "r3": ("register", "ClinicalTrials.gov"),
        "r4": ("database", "Scopus"),
        "r5": ("other_method", "Citation searching"),
        "r6": ("database", "Web of Science"),
        "r7": ("database", "PubMed"),
        "r8": ("database", "Embase"),
    }
    events = [
        screening_event(
            record_id,
            "identification",
            "identified",
            source_type=source_type,
            source_name=source_name,
        )
        for record_id, (source_type, source_name) in sources.items()
    ]
    events.extend(
        [
            screening_event("r1", "deduplication", "retained"),
            screening_event("r2", "deduplication", "duplicate", duplicate_of="r1"),
            screening_event("r3", "deduplication", "retained"),
            screening_event("r4", "deduplication", "retained"),
            screening_event("r5", "deduplication", "retained"),
            screening_event("r6", "deduplication", "retained"),
            screening_event("r7", "deduplication", "removed_by_automation"),
            screening_event(
                "r8", "deduplication", "removed_other", reason="Retracted record"
            ),
            screening_event("r1", "title_abstract", "exclude"),
            screening_event("r3", "title_abstract", "include"),
            screening_event("r4", "title_abstract", "include"),
            screening_event("r5", "title_abstract", "include"),
            screening_event("r6", "title_abstract", "include"),
            screening_event(
                "r3", "retrieval", "not_retrieved", reason="No report could be located"
            ),
            screening_event("r4", "retrieval", "retrieved"),
            screening_event("r5", "retrieval", "retrieved"),
            screening_event("r6", "retrieval", "retrieved"),
            screening_event(
                "r4", "full_text", "exclude", reason="Ineligible population"
            ),
            screening_event("r5", "full_text", "include", study_id="Study-01"),
            screening_event("r6", "full_text", "include", study_id="study-01"),
        ]
    )
    independent_events = []
    for value in events:
        if value["stage"] not in {"title_abstract", "full_text"} or not value["is_final"]:
            continue
        independent_events.extend(
            (
                {**value, "reviewer": "Dr Nora Hassan", "is_final": False},
                {**value, "reviewer": "Prof Omar Khalil", "is_final": False},
            )
        )
    return events + independent_events


class TopicIntakeTests(unittest.TestCase):
    def test_valid_intake_is_normalized_and_immutable(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload["working_title"] = "  Graft choice and return to sport after primary ACL reconstruction  "
        intake = validate_topic_intake(payload)

        self.assertEqual(
            intake.working_title,
            "Graft choice and return to sport after primary ACL reconstruction",
        )
        self.assertIsInstance(intake.databases, tuple)
        self.assertEqual(len(intake.accountable_reviewers), 2)

    def test_intake_reports_multiple_professional_deficiencies(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload.update(
            {
                "review_type": "meta_meta_analysis",
                "working_title": "TBD",
                "databases": ["MEDLINE"],
                "accountable_reviewers": ["Dr Nora Hassan"],
                "invented_field": "value",
            }
        )
        with self.assertRaises(IntakeValidationError) as raised:
            validate_topic_intake(payload)

        message = str(raised.exception)
        self.assertIn("unknown fields", message)
        self.assertIn("review-level evidence", message)
        self.assertIn("working_title contains a placeholder", message)
        self.assertIn("databases requires at least 2", message)
        self.assertIn("accountable_reviewers requires at least 2", message)

    def test_meta_analysis_requires_a_prespecified_effect_measure(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload["review_type"] = "systematic_review_with_meta_analysis"
        with self.assertRaisesRegex(IntakeValidationError, "effect_measure is required"):
            validate_topic_intake(payload)

        payload["effect_measure"] = "Risk ratio for graft failure"
        self.assertEqual(
            validate_topic_intake(payload).review_type,
            "systematic_review_with_meta_analysis",
        )

    def test_umbrella_review_requires_review_level_evidence(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload["review_type"] = "umbrella_review"
        with self.assertRaisesRegex(IntakeValidationError, "review-level evidence"):
            validate_topic_intake(payload)

        payload["eligible_evidence_types"] = [
            "Systematic reviews",
            "Systematic reviews with meta-analysis",
        ]
        self.assertEqual(validate_topic_intake(payload).review_type, "umbrella_review")

    def test_meta_meta_alias_is_normalized_and_machine_reviewers_are_rejected(self):
        payload = copy.deepcopy(BASE_INTAKE)
        payload.update(
            {
                "review_type": "meta-meta analysis",
                "eligible_evidence_types": ["Systematic reviews with meta-analysis"],
            }
        )
        self.assertEqual(validate_topic_intake(payload).review_type, "umbrella_review")
        payload["accountable_reviewers"] = ["Dr Nora Hassan", "ChatGPT AI bot"]
        with self.assertRaisesRegex(IntakeValidationError, "roles or AI/tool"):
            validate_topic_intake(payload)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_content_addressed(self):
        first = build_project_manifest(copy.deepcopy(BASE_INTAKE))
        second = build_project_manifest(copy.deepcopy(BASE_INTAKE))
        self.assertEqual(first, second)
        self.assertRegex(first["project_id"], r"^SR-[0-9A-F]{12}$")
        self.assertEqual(len(first["topic_fingerprint_sha256"]), 64)
        self.assertEqual(first["pipeline"][-1], "completed")

        changed = copy.deepcopy(BASE_INTAKE)
        changed["primary_outcome"] = "Return to any sport at 12 months or later"
        self.assertNotEqual(
            first["project_id"], build_project_manifest(changed)["project_id"]
        )

    def test_manifest_contains_review_type_specific_artifacts(self):
        meta = copy.deepcopy(BASE_INTAKE)
        meta.update(
            {
                "review_type": "systematic_review_with_meta_analysis",
                "effect_measure": "Risk ratio",
            }
        )
        meta_paths = {item["path"] for item in build_project_manifest(meta)["files"]}
        self.assertIn("project-state.json", meta_paths)
        self.assertIn("audit/gate-transitions.jsonl", meta_paths)
        self.assertIn("analysis/effect_sizes.csv", meta_paths)
        self.assertIn("meta_analysis", build_project_manifest(meta)["pipeline"])

        umbrella = copy.deepcopy(BASE_INTAKE)
        umbrella.update(
            {
                "review_type": "umbrella_review",
                "eligible_evidence_types": ["Systematic reviews with meta-analysis"],
            }
        )
        umbrella_manifest = build_project_manifest(umbrella)
        umbrella_paths = {item["path"] for item in umbrella_manifest["files"]}
        self.assertIn("overlap/citation_matrix.csv", umbrella_paths)
        self.assertIn("overlap/corrected_covered_area.json", umbrella_paths)
        self.assertIn("overlap_assessment", umbrella_manifest["pipeline"])


class WorkflowTests(unittest.TestCase):
    def test_state_machine_rejects_skips_and_missing_gate_evidence(self):
        workflow = ReviewWorkflow("systematic_review", BASE_INTAKE["accountable_reviewers"])
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
                to_stage="search_strategy",
            )
        with self.assertRaisesRegex(ValueError, "missing evidence"):
            workflow.advance(
                {}, reviewer="Dr Nora Hassan", decision_date=TODAY
            )
        self.assertEqual(workflow.current_stage, "topic_intake")

    def test_meta_analysis_workflow_can_complete_only_in_order(self):
        workflow = ReviewWorkflow(
            "systematic_review_with_meta_analysis",
            BASE_INTAKE["accountable_reviewers"],
        )
        visited = []
        while not workflow.completed:
            stage = workflow.current_stage
            visited.append(stage)
            evidence = gate_evidence(stage)
            workflow.advance(
                evidence,
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )

        self.assertIn("effect_size_harmonization", visited)
        self.assertIn("meta_analysis", visited)
        self.assertNotIn("narrative_synthesis", visited)
        self.assertEqual(workflow.current_stage, "completed")
        self.assertTrue(workflow.snapshot()["completed"])
        self.assertEqual(
            len(workflow.snapshot()["transitions"]),
            len(workflow.snapshot()["pipeline"]) - 1,
        )
        with self.assertRaisesRegex(RuntimeError, "cannot be advanced"):
            workflow.advance(
                {}, reviewer="Methods reviewer", decision_date=TODAY
            )

    def test_transition_log_is_deterministic_for_the_same_evidence(self):
        first = ReviewWorkflow("umbrella_review", BASE_INTAKE["accountable_reviewers"])
        second = ReviewWorkflow("umbrella_review", BASE_INTAKE["accountable_reviewers"])
        first_evidence = gate_evidence("topic_intake")
        second_evidence = dict(reversed(list(first_evidence.items())))
        first_transition = first.advance(
            first_evidence,
            reviewer="Dr Nora Hassan",
            decision_date=TODAY,
        )
        second_transition = second.advance(
            second_evidence,
            reviewer="Dr Nora Hassan",
            decision_date=TODAY,
        )
        self.assertEqual(first_transition, second_transition)

    def test_snapshot_restores_and_tampering_is_detected(self):
        workflow = ReviewWorkflow("systematic_review", BASE_INTAKE["accountable_reviewers"])
        workflow.advance(
            gate_evidence("topic_intake"),
            reviewer="Dr Nora Hassan",
            decision_date=TODAY,
        )
        snapshot = workflow.snapshot()
        restored = ReviewWorkflow.from_snapshot(snapshot)
        self.assertEqual(restored.snapshot(), snapshot)
        detached = workflow.snapshot()
        detached["transitions"][0]["evidence"]["intake_validated"]["artifact"] = "mutated.json"
        self.assertEqual(
            workflow.snapshot()["transitions"][0]["evidence"]["intake_validated"]["artifact"],
            "audit/topic_intake-intake_validated.json",
        )
        tampered = copy.deepcopy(snapshot)
        tampered["transitions"][0]["evidence"]["intake_validated"]["artifact"] = "fake.json"
        with self.assertRaisesRegex(ValueError, "fingerprint|hash"):
            ReviewWorkflow.from_snapshot(tampered)

    def test_truthy_fake_evidence_unbound_actor_and_future_date_fail(self):
        workflow = ReviewWorkflow("systematic_review", BASE_INTAKE["accountable_reviewers"])
        with self.assertRaisesRegex(ValueError, "evidence must be an object"):
            workflow.advance(
                {"intake_validated": True},
                reviewer="Dr Nora Hassan",
                decision_date=TODAY,
            )
        with self.assertRaisesRegex(ValueError, "accountable human"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="ChatGPT AI bot",
                decision_date=TODAY,
            )
        with self.assertRaisesRegex(ValueError, "future"):
            workflow.advance(
                gate_evidence("topic_intake"),
                reviewer="Dr Nora Hassan",
                decision_date="2999-01-01",
            )


class PrismaTests(unittest.TestCase):
    def test_prisma_counts_are_derived_from_final_record_decisions(self):
        counts = prisma_counts(complete_screening_fixture())

        self.assertEqual(counts["records_identified_from_databases"], 6)
        self.assertEqual(counts["records_identified_from_registers"], 1)
        self.assertEqual(counts["records_identified_via_other_methods"], 1)
        self.assertEqual(counts["total_records_identified"], 8)
        self.assertEqual(counts["records_removed_before_screening_as_duplicates"], 1)
        self.assertEqual(
            counts["records_removed_before_screening_by_automation_tools"], 1
        )
        self.assertEqual(
            counts["records_removed_before_screening_for_other_reasons"], 1
        )
        self.assertEqual(counts["records_screened"], 5)
        self.assertEqual(counts["records_excluded"], 1)
        self.assertEqual(counts["reports_sought_for_retrieval"], 4)
        self.assertEqual(counts["reports_not_retrieved"], 1)
        self.assertEqual(counts["reports_assessed_for_eligibility"], 3)
        self.assertEqual(counts["reports_excluded"], 1)
        self.assertEqual(
            counts["reports_excluded_by_reason"], {"Ineligible population": 1}
        )
        self.assertEqual(counts["reports_of_included_studies"], 2)
        self.assertEqual(counts["studies_included_in_review"], 1)
        self.assertEqual(counts["nonfinal_decisions_ignored"], 16)
        self.assertTrue(counts["independent_human_screening_validated"])

    def test_multiple_final_decisions_are_rejected_instead_of_guessed(self):
        records = complete_screening_fixture()
        records.append(screening_event("r1", "title_abstract", "include"))
        with self.assertRaisesRegex(ValueError, "multiple final decisions"):
            prisma_counts(records)

    def test_release_counts_require_two_bound_human_screeners(self):
        records = [
            value
            for value in complete_screening_fixture()
            if not (
                value["record_id"] == "r1"
                and value["stage"] == "title_abstract"
                and not value["is_final"]
                and value["reviewer"] == "Prof Omar Khalil"
            )
        ]
        with self.assertRaisesRegex(ValueError, "two independent human decisions"):
            prisma_counts(records)

    def test_incomplete_flow_fails_final_prisma_gate(self):
        records = [
            value
            for value in complete_screening_fixture()
            if not (value["record_id"] == "r6" and value["stage"] == "full_text")
        ]
        with self.assertRaisesRegex(ValueError, "incomplete full_text coverage"):
            prisma_counts(records)

        interim = prisma_counts(records, require_complete=False)
        self.assertEqual(interim["reports_of_included_studies"], 1)
        self.assertFalse(interim["complete"])

    def test_impossible_downstream_flow_is_rejected(self):
        records = complete_screening_fixture()
        impossible = screening_event(
            "r3", "full_text", "include", study_id="Study-not-retrieved"
        )
        records.extend(
            (
                impossible,
                {**impossible, "reviewer": "Dr Nora Hassan", "is_final": False},
                {**impossible, "reviewer": "Prof Omar Khalil", "is_final": False},
            )
        )
        with self.assertRaisesRegex(ValueError, "only retrieved reports"):
            prisma_counts(records)

    def test_required_reasons_and_study_ids_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "full_text exclusion requires reason"):
            prisma_counts(
                [screening_event("r1", "full_text", "exclude")],
                require_complete=False,
            )
        with self.assertRaisesRegex(ValueError, "full_text inclusion requires study_id"):
            prisma_counts(
                [screening_event("r1", "full_text", "include")],
                require_complete=False,
            )


class PriorTests(unittest.TestCase):
    def test_umbrella_flow_uses_review_ids_and_prior_labels(self):
        records = []
        for value in complete_screening_fixture():
            converted = dict(value)
            if converted.get("stage") == "full_text" and converted.get("decision") == "include":
                converted["review_id"] = converted.pop("study_id")
            records.append(converted)
        result = derive_prior_counts(
            records,
            accountable_reviewers=BASE_INTAKE["accountable_reviewers"],
        )
        self.assertEqual(result["reporting_framework"], "PRIOR")
        self.assertEqual(result["reports_of_included_reviews"], 2)
        self.assertEqual(result["systematic_reviews_included_in_overview"], 1)
        self.assertNotIn("studies_included_in_review", result)

    def test_prior_rejects_study_id_or_missing_review_id(self):
        with self.assertRaisesRegex(ValueError, "review_id, not study_id"):
            derive_prior_counts(
                complete_screening_fixture(),
                accountable_reviewers=BASE_INTAKE["accountable_reviewers"],
            )


class CorrectedCoveredAreaTests(unittest.TestCase):
    def test_corrected_covered_area_and_matrix_follow_the_standard_formula(self):
        result = corrected_covered_area(
            {
                "Review-B": ["Study-A", "Study-B", "Study-E"],
                "Review-A": ["Study-A", "Study-B", "Study-C", "Study-D"],
                "Review-C": ["Study-A", "Study-F"],
            },
            comparison="Autograft A versus autograft B",
            outcome="Graft failure",
            time_point="Minimum 24 months",
        )

        self.assertEqual(result["review_count"], 3)
        self.assertEqual(result["scope"]["outcome"], "Graft failure")
        self.assertEqual(result["unique_primary_studies"], 6)
        self.assertEqual(result["total_study_occurrences"], 9)
        self.assertEqual(result["overlap_excess"], 3)
        self.assertEqual(result["maximum_overlap_excess"], 12)
        self.assertAlmostEqual(result["corrected_covered_area"], 0.25)
        self.assertAlmostEqual(result["corrected_covered_area_percent"], 25.0)
        self.assertEqual(result["interpretation"], "very_high")
        self.assertEqual(result["review_ids"], ["Review-A", "Review-B", "Review-C"])
        self.assertEqual(result["primary_study_ids"][0], "Study-A")
        self.assertEqual(result["citation_matrix"][0], [1, 1, 1])

    def test_no_overlap_is_classified_as_slight(self):
        result = corrected_covered_area(
            {"Review-A": ["Study-A"], "Review-B": ["Study-B"]},
            comparison="Autograft A versus autograft B",
            outcome="Graft failure",
            time_point="Minimum 24 months",
        )
        self.assertEqual(result["corrected_covered_area"], 0.0)
        self.assertEqual(result["interpretation"], "slight")

    def test_duplicate_study_inside_review_is_rejected_case_insensitively(self):
        with self.assertRaisesRegex(ValueError, "duplicate primary study"):
            corrected_covered_area(
                {"Review-A": ["Study-A", "study-a"], "Review-B": ["Study-B"]},
                comparison="Autograft A versus autograft B",
                outcome="Graft failure",
                time_point="Minimum 24 months",
            )

    def test_at_least_two_reviews_are_required(self):
        with self.assertRaisesRegex(ValueError, "at least two reviews"):
            corrected_covered_area(
                {"Review-A": ["Study-A"]},
                comparison="Autograft A versus autograft B",
                outcome="Graft failure",
                time_point="Minimum 24 months",
            )


if __name__ == "__main__":
    unittest.main()

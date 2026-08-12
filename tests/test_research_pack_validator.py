import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "orthopaedic-publication-workbench" / "scripts" / "validate_research_pack.py"
SPEC = importlib.util.spec_from_file_location("validate_research_pack", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def title(text):
    return {
        "text": text,
        "title_quality": {"status": "clear", "reasons": ["accurate, non-causal, and design-labelled"]},
        "journal_fit": {"status": "pending_verification", "reasons": ["official limits remain pending"]},
        "evidence_alignment": "Matches the declared design and question",
        "flags": [],
    }


def valid_pack():
    titles = [
        "ACL remnant preservation and KOOS Pain at 12 months: a retrospective cohort study",
        "KOOS Pain after remnant-preserving versus standard ACL reconstruction: a retrospective cohort study",
        "Twelve-month KOOS Pain in ACL remnant preservation: a retrospective cohort study",
        "ACL reconstruction technique and 12-month KOOS Pain: a retrospective cohort study",
        "Remnant-preserving ACL reconstruction and KOOS Pain: a retrospective cohort study",
        "Patient-reported KOOS Pain after ACL reconstruction: a retrospective cohort study",
    ]
    return {
        "project": {
            "id": "ORTHO-001",
            "question": "What is the association between ACL remnant preservation and KOOS Pain at 12 months?",
            "study_design": "retrospective_cohort",
            "stage": "planning",
            "intended_inference": "associational",
            "topic_terms": ["ACL", "KOOS Pain", "remnant preservation"],
            "uses_routinely_collected_data": False,
            "comparative_results_seen": False,
            "protocol_frozen_before_comparative_results": True,
            "minimum_input_gate": {
                "question_finalized": True,
                "design_confirmed": True,
                "primary_outcome_confirmed": True,
                "data_source_confirmed": True,
                "results_visibility_recorded": True,
                "causal_aim_confirmed": True,
            },
        },
        "sources": [
            {
                "source_id": "strobe-official",
                "kind": "official_guidance",
                "title": "STROBE",
                "url_or_path": "https://www.equator-network.org/reporting-guidelines/strobe/",
                "retrieved_at": "2026-08-12",
                "checksum": "0" * 64,
                "rights_basis": "official_webpage",
                "allowed_use": "protocol_support",
                "evidence_location": "STROBE checklists",
            }
        ],
        "protocol": {
            "version": "1.0",
            "version_date": "2026-08-12",
            "reporting_guidelines": ["STROBE cohort"],
            "primary_objective": "Estimate the adjusted association with KOOS Pain at 12 months",
            "primary_outcome": {"name": "KOOS Pain subscale", "instrument": "KOOS", "metric": "0-100 Pain score", "timepoint": "12 months"},
            "time_zero": "Index ACL reconstruction",
            "eligibility": "Prespecified primary ACL reconstruction cohort",
            "sample_size_justification": {
                "method": "Precision for the adjusted mean difference",
                "assumptions": ["group sizes", "KOOS Pain standard deviation", "attrition"],
                "sensitivity_analysis": "Range of plausible standard deviations and missingness",
                "provenance_source_ids": ["strobe-official"],
            },
            "ethics": {"status": "planned waiver review", "consent_or_waiver": "seek waiver", "privacy_plan": "de-identify analysis data"},
            "data_provenance": "Frozen clinical cohort extract with data dictionary",
            "exposure_definition": "Remnant-preserving technique defined before analysis",
            "comparator_definition": "Standard reconstruction defined before analysis",
            "selection_process": "All consecutive eligible records",
            "follow_up": "Prespecified 12-month visit window",
            "bias_control": "Address selection, confounding by indication, and measurement bias",
            "confounders": ["baseline KOOS Pain", "age", "graft type", "surgeon"],
        },
        "statistics": {
            "analysis_population": "All eligible index reconstructions",
            "primary_estimand": "Adjusted mean difference in KOOS Pain at 12 months",
            "effect_measure": "Adjusted mean difference with 95% confidence interval",
            "primary_model": "Linear regression adjusted for baseline KOOS Pain and prespecified confounders",
            "missing_data": {
                "primary_assumption": "Missing at random conditional on observed variables",
                "primary_method": "Multiple imputation",
                "sensitivity_analysis": "Pattern-mixture sensitivity analysis",
            },
            "multiplicity": "One primary KOOS subscale; others exploratory",
            "sensitivity_analyses": ["Alternative exposure definition", "Missing-not-at-random scenario"],
            "covariates": ["baseline KOOS Pain", "age", "graft type", "surgeon"],
            "clustering_and_repeated_measures": "Assess surgeon clustering and use robust variance if needed",
            "model_diagnostics": "Residual, influence, and functional-form diagnostics",
            "data_derivations": "Versioned derivation specification",
            "dataset_lock": "Hash and lock before primary analysis",
            "protocol_deviations": "Log and disclose deviations without silently changing the primary analysis",
            "software": {"name": "R", "version": "4.x locked at analysis", "packages": "recorded in renv lockfile"},
            "objective_analysis_map": [
                {
                    "objective_id": "primary-1",
                    "outcome": "KOOS Pain at 12 months",
                    "estimand": "Adjusted mean difference",
                    "effect_measure": "Mean difference with 95% CI",
                    "model": "Adjusted linear regression",
                    "missing_data_assumption": "MAR with MNAR sensitivity",
                }
            ],
        },
        "journal_targets": [
            {
                "journal_id": "pending-1",
                "name": "Candidate Journal",
                "requirements_status": "pending_verification",
                "fit_status": "pending_verification",
            }
        ],
        "title_candidates": [title(text_value) for text_value in titles],
        "style_profile": {"status": "insufficient_evidence", "reason": "No authorized journal-specific full-text sample supplied", "samples": []},
        "no_fabrication_audit": {"completed": True, "fabricated_claims_found": False, "checks": ["sources", "journal rules", "statistics"]},
        "human_reviews": {
            "investigator": "pending",
            "statistician": "pending",
            "ethics_data_governance": "pending",
            "journal_requirements": "pending",
        },
        "readiness": {"status": "draft", "limitations": ["Journal requirements pending"]},
        "unresolved": [{"item": "Verify journal requirements", "blocking": True, "owner": "investigator"}],
    }


class ResearchPackValidatorTests(unittest.TestCase):
    def test_accepts_traceable_exact_design_pack(self):
        self.assertEqual(MODULE.validate_pack(valid_pack()), [])

    def test_routinely_collected_cohort_requires_strobe_plus_record(self):
        pack = valid_pack()
        pack["project"]["uses_routinely_collected_data"] = True
        errors = MODULE.validate_pack(pack)
        self.assertTrue(any("require RECORD" in error for error in errors))
        pack["protocol"]["reporting_guidelines"].append("RECORD")
        self.assertEqual(MODULE.validate_pack(pack), [])

    def test_rejects_semantic_title_and_editorial_proxy_failures(self):
        pack = valid_pack()
        pack["likelihood_of_acceptance"] = 99
        pack["project"]["country_bonus"] = 5
        pack["title_candidates"] = [
            title("Novel ACL technique proves superior outcomes: a retrospective cohort study")
        ]
        errors = MODULE.validate_pack(pack)
        self.assertTrue(any("likelihood_of_acceptance" in error for error in errors))
        self.assertTrue(any("country_bonus" in error for error in errors))
        self.assertTrue(any("6-10" in error for error in errors))

    def test_unknown_rights_is_case_insensitive_and_future_dates_fail(self):
        pack = valid_pack()
        pack["sources"][0].update(
            {"rights_basis": "Unknown", "allowed_use": "style_analysis", "retrieved_at": "2099-01-01"}
        )
        errors = MODULE.validate_pack(pack)
        self.assertTrue(any("unknown rights" in error for error in errors))
        self.assertTrue(any("future" in error for error in errors))

    def test_patient_records_are_rejected(self):
        pack = valid_pack()
        pack["patient_records"] = [{"mrn": "123", "name": "Example"}]
        errors = MODULE.validate_pack(pack)
        self.assertTrue(any("patient_records" in error for error in errors))

    def test_koos_total_is_rejected(self):
        pack = valid_pack()
        pack["protocol"]["primary_outcome"].update({"name": "KOOS total", "metric": "total KOOS"})
        self.assertTrue(any("generic total" in error for error in MODULE.validate_pack(pack)))

    def test_submission_ready_requires_human_and_journal_gates(self):
        pack = valid_pack()
        pack["readiness"]["status"] = "submission_ready"
        errors = MODULE.validate_pack(pack)
        self.assertTrue(any("human reviews" in error for error in errors))
        self.assertTrue(any("verified target-journal" in error for error in errors))
        self.assertTrue(any("blocking unresolved" in error for error in errors))

    def test_adversarial_pack_cannot_pass_as_structurally_valid(self):
        pack = copy.deepcopy(valid_pack())
        pack["project"].update(
            {
                "stage": "submission-ready",
                "comparative_results_seen": True,
                "protocol_frozen_before_comparative_results": False,
            }
        )
        pack["statistics"].update(
            {"effect_measure": "p value", "missing_data": {"primary_assumption": "none", "primary_method": "ignore", "sensitivity_analysis": "none"}}
        )
        pack["journal_targets"] = []
        pack["title_candidates"] = [title("ACL technique proves superiority")]
        pack["style_profile"] = {"status": "profiled", "samples": []}
        pack["no_fabrication_audit"] = {"completed": False, "fabricated_claims_found": True, "checks": []}
        pack["patient_records"] = [{"medical_record_number": "secret"}]
        errors = MODULE.validate_pack(pack)
        self.assertGreaterEqual(len(errors), 10)
        for expected in (
            "unsupported stage",
            "p-value is not an effect measure",
            "silently ignored",
            "at least one target",
            "6-10 candidates",
            "at least five authorized papers",
            "individual-level identifying",
        ):
            self.assertTrue(any(expected in error for error in errors), expected)


if __name__ == "__main__":
    unittest.main()

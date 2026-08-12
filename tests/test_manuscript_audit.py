import tempfile
import unittest
from pathlib import Path

from medical_research.manuscript_audit import aggregate_by_journal, profile_text, profile_title
from scripts.audit_manuscript_corpus import _profile_record


class ManuscriptAuditTests(unittest.TestCase):
    def test_title_profile_uses_word_boundaries_and_design_labels(self):
        profile = profile_title("ACL reconstruction outcomes: a retrospective cohort study")
        self.assertTrue(profile.has_colon)
        self.assertFalse(profile.has_question_mark)
        self.assertIn("cohort", profile.design_labels)
        self.assertEqual(profile.word_count, 7)

    def test_text_profile_reports_markers_not_quality(self):
        text = """BACKGROUND: Context\nMETHODS: We used multiple imputation and adjusted regression.\nRESULTS: adjusted mean difference 2.1 (95% CI 1.0 to 3.2), p = 0.01.\nDISCUSSION\nLimitations.\nCONCLUSION: Summary.\nAnalysis used R version 4.3 and followed STROBE.\n"""
        profile = profile_text(text)
        self.assertTrue(profile.structured_abstract_marker)
        self.assertTrue(profile.statistical_markers["confidence_interval"])
        self.assertTrue(profile.statistical_markers["effect_estimate"])
        self.assertTrue(profile.statistical_markers["multiple_imputation"])
        self.assertIn("R", profile.software_mentions)
        self.assertIn("STROBE", profile.reporting_guideline_mentions)

    def test_late_references_are_excluded_from_method_markers(self):
        body = "METHODS\nNo named software.\n" + ("Study body.\n" * 600)
        profile = profile_text(
            body + "\nREFERENCES\nA cited paper used SPSS and reported p = 0.01.\n"
        )
        self.assertTrue(profile.late_references_boundary_detected)
        self.assertNotIn("SPSS", profile.software_mentions)
        self.assertFalse(profile.statistical_markers["exact_or_threshold_p_value"])

    def test_ordinary_words_do_not_count_as_reporting_guidelines(self):
        profile = profile_text(
            "The care process used an electronic health record. Participants arrive at noon."
        )
        self.assertEqual(profile.reporting_guideline_mentions, ())

        contextual = profile_text("Reporting followed the CARE guideline and checklist.")
        self.assertIn("CARE", contextual.reporting_guideline_mentions)

    def test_license_compatible_record_cannot_escape_pdf_root(self):
        with tempfile.TemporaryDirectory() as root:
            profile = _profile_record(
                {
                    "title": "Example",
                    "license": "cc-by",
                    "relative_path": "../outside.pdf",
                    "sha256": "0" * 64,
                },
                Path(root),
                True,
                1,
            )
        self.assertEqual(profile["full_text_status"], "invalid_source_path")

    def test_aggregation_keeps_title_and_full_text_denominators_separate(self):
        rows = [
            {
                "journal": "Journal A",
                "source_sha256": "1" * 64,
                "title_profile": {"word_count": 10, "has_colon": True, "has_question_mark": False, "design_labels": ["cohort"]},
                "full_text_status": "analyzed",
                "text_profile": {
                    "statistical_markers": {"confidence_interval": True},
                    "sections": {"methods": True},
                    "abstract_headings": {"methods": True},
                    "software_mentions": ["R"],
                    "reporting_guideline_mentions": ["STROBE"],
                },
            },
            {
                "journal": "Journal A",
                "title_profile": {"word_count": 20, "has_colon": False, "has_question_mark": False, "design_labels": []},
                "full_text_status": "not_analyzed_rights_gate",
                "text_profile": None,
            },
        ]
        result = aggregate_by_journal(rows)[0]
        self.assertEqual(result["title_records"], 2)
        self.assertEqual(result["full_text_license_compatible_and_analyzed"], 1)
        self.assertEqual(result["distinct_full_text_sources"], 1)
        self.assertEqual(result["style_evidence_status"], "insufficient_sample_below_five")
        self.assertEqual(result["full_text_coverage_fraction"], 0.5)
        self.assertEqual(result["statistical_marker_counts"]["confidence_interval"], 1)


if __name__ == "__main__":
    unittest.main()

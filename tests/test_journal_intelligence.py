import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from medical_research.journal_intelligence import (
    JournalProfile,
    StudyProfile,
    assess_journal_fit,
    assess_title,
    rank_title_quality,
)


REGISTRY_SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_journal_registry.py"
SPEC = importlib.util.spec_from_file_location("validate_journal_registry", REGISTRY_SCRIPT)
REGISTRY_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(REGISTRY_MODULE)


STUDY = StudyProfile(
    study_design="retrospective_cohort",
    stage="planning",
    topic_terms=("anterior cruciate ligament", "ACL reconstruction"),
)


def verified_journal(**changes):
    values = {
        "journal_id": "sports-knee",
        "name": "Synthetic Sports Knee Journal",
        "requirements_status": "verified",
        "verified_at": "2026-08-12",
        "official_url": "https://example.org/official-guidance",
        "scope_terms": ("knee", "ACL", "sports injury"),
        "article_types": ("original_research",),
        "title_word_limit": 20,
        "title_requires_design_label": True,
        "evidence_locations": ("Scope", "Original research"),
    }
    values.update(changes)
    return JournalProfile(**values)


class TitleAssessmentTests(unittest.TestCase):
    def test_clear_observational_title_is_not_an_acceptance_score(self):
        result = assess_title(
            "Remnant-preserving versus standard ACL reconstruction: a retrospective cohort study",
            STUDY,
            verified_journal(),
        )
        self.assertEqual(result.quality_status, "clear")
        self.assertNotIn("score", result.to_dict())

    def test_causal_and_predata_result_claims_are_hard_failures(self):
        result = assess_title(
            "Remnant preservation improves KOOS after ACL reconstruction in a retrospective cohort",
            STUDY,
        )
        self.assertTrue(any("causal language" in item for item in result.hard_failures))
        self.assertTrue(any("cannot assert results" in item for item in result.hard_failures))

    def test_token_matching_does_not_confuse_short_substrings(self):
        study = StudyProfile("cross_sectional", "planning", ("hip",))
        result = assess_title("Ship motion in athletes: a cross-sectional study", study)
        self.assertTrue(any("does not contain" in item for item in result.hard_failures))

    def test_quality_ranking_prefers_accurate_title(self):
        ranked = rank_title_quality(
            [
                "Novel ACL breakthrough",
                "Remnant-preserving versus standard ACL reconstruction: a retrospective cohort study",
            ],
            STUDY,
            verified_journal(),
        )
        self.assertTrue(ranked[0].title.startswith("Remnant-preserving"))


class JournalFitTests(unittest.TestCase):
    def test_unverified_rules_never_produce_eligible(self):
        journal = verified_journal(requirements_status="pending_live_verification")
        self.assertEqual(assess_journal_fit(STUDY, journal).fit_status, "pending_verification")

    def test_scope_mismatch_is_noncompensatory_no_go(self):
        journal = verified_journal(scope_terms=("hip arthroplasty",), article_types=("original_research",))
        result = assess_journal_fit(STUDY, journal)
        self.assertEqual(result.fit_status, "not_eligible")
        self.assertTrue(any("scope" in item for item in result.hard_gates))

    def test_missing_evidence_location_downgrades_verified_label(self):
        journal = verified_journal(evidence_locations=())
        self.assertEqual(assess_journal_fit(STUDY, journal).fit_status, "pending_verification")


class RegistryTests(unittest.TestCase):
    def test_committed_registry_has_all_319_records(self):
        path = Path(__file__).parents[1] / "data" / "journals" / "orthopaedics_sports_2023_snapshot.jsonl"
        self.assertEqual(REGISTRY_MODULE.validate(path, expected_count=319), [])

    def test_verified_registry_record_requires_provenance(self):
        record = {
            "rank_2023": 1,
            "scopus_source_id": "x",
            "title": "Journal",
            "metric_role": "historical_discovery_only",
            "current_journal_status": "active",
            "author_requirements_status": "verified",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            errors = REGISTRY_MODULE.validate(path, expected_count=1)
        self.assertTrue(any("official_url" in item for item in errors))
        self.assertTrue(any("verified_at" in item for item in errors))


if __name__ == "__main__":
    unittest.main()

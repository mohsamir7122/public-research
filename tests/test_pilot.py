import unittest

from medical_research.pilot import run_pilot


CONFIG = {
    "project_id": "ACL-PILOT-001",
    "population": {"terms": ["anterior cruciate ligament"]},
    "intervention": {"terms": ["remnant preservation"]},
    "comparator": {"terms": ["standard reconstruction"]},
    "include_comparator_in_primary_search": False,
}


class PilotTests(unittest.TestCase):
    def test_realistic_metadata_pilot_builds_queries_and_deduplicates(self):
        records = [
            {"title": "Remnant preservation review", "doi": "10.1000/ACL.1", "year": 2025, "source": "PubMed"},
            {"title": "Remnant preservation review", "doi": "https://doi.org/10.1000/acl.1", "year": 2025, "source": "PMC", "abstract": "Richer record"},
            {"title": "Prospective ACL study", "doi": "10.1000/acl.2", "year": 2024, "source": "PubMed"},
        ]
        result = run_pilot(CONFIG, records)
        self.assertEqual(result["counts"], {"input_records": 3, "deduplicated_records": 2, "duplicates_removed": 1})
        self.assertEqual(result["deduplication_decisions"][0]["reason"], "doi")
        self.assertTrue(all("standard reconstruction" not in query for query in result["queries"].values()))
        self.assertIn("novelty and overlap with recent reviews", result["human_review_required"])

    def test_rejects_unknown_metadata_fields(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            run_pilot(CONFIG, [{"title": "Study", "invented_result": "positive"}])


if __name__ == "__main__":
    unittest.main()

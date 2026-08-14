import unittest

from medical_research.search_strategy import build_queries


CONFIG = {
    "population": {"terms": ["anterior cruciate ligament injury"], "mesh": ["Anterior Cruciate Ligament Injuries"]},
    "intervention": {"terms": ["remnant preservation reconstruction"]},
    "comparator": {"terms": ["standard ACL reconstruction"]},
    "outcomes": {"terms": ["proprioception"]},
    "include_outcomes_in_primary_search": False,
    "include_comparator_in_primary_search": False,
}


class SearchStrategyTests(unittest.TestCase):
    def test_database_specific_syntax(self):
        queries = build_queries(CONFIG)
        self.assertIn("[Title/Abstract]", queries["pubmed"])
        self.assertIn("[MeSH Terms]", queries["pubmed"])
        self.assertIn("TITLE-ABS-KEY", queries["scopus"])
        self.assertIn("TS=", queries["web_of_science"])
        self.assertIn(":ti,ab,kw", queries["embase"])

    def test_outcome_excluded_by_default(self):
        queries = build_queries(CONFIG)
        self.assertTrue(all("proprioception" not in query for query in queries.values()))

    def test_comparator_excluded_by_default_for_sensitivity(self):
        queries = build_queries(CONFIG)
        self.assertTrue(all("standard ACL reconstruction" not in query for query in queries.values()))

    def test_comparator_can_be_included_explicitly(self):
        config = dict(CONFIG)
        config["include_comparator_in_primary_search"] = True
        queries = build_queries(config)
        self.assertTrue(all("standard ACL reconstruction" in query for query in queries.values()))

    def test_requires_two_concepts(self):
        with self.assertRaises(ValueError):
            build_queries({"population": {"terms": ["ACL"]}})


if __name__ == "__main__":
    unittest.main()

import unittest

from medical_research.dedupe import deduplicate, normalize_doi
from medical_research.models import StudyRecord


class DedupeTests(unittest.TestCase):
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1000/ABC.1"), "10.1000/abc.1")

    def test_matching_doi_merges(self):
        kept, decisions = deduplicate([
            StudyRecord(title="First", doi="10.1000/X"),
            StudyRecord(title="Richer", doi="https://doi.org/10.1000/x", abstract="abstract"),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "Richer")
        self.assertEqual(decisions[0].reason, "doi")

    def test_different_nonempty_dois_never_merge(self):
        kept, decisions = deduplicate([
            StudyRecord(title="ACL reconstruction outcome", doi="10.1000/a", year=2025),
            StudyRecord(title="ACL reconstruction outcomes", doi="10.1000/b", year=2025),
        ])
        self.assertEqual(len(kept), 2)
        self.assertEqual(decisions, [])

    def test_title_year_fallback_requires_missing_dois(self):
        kept, decisions = deduplicate([
            StudyRecord(title="Outcomes after ACL reconstruction", year=2025),
            StudyRecord(title="Outcomes after ACL reconstruction", year=2025),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(decisions[0].reason, "normalized_title_year")

    def test_blank_titles_never_merge(self):
        kept, decisions = deduplicate([
            StudyRecord(title="", year=2025),
            StudyRecord(title="", year=2025),
        ])
        self.assertEqual(len(kept), 2)
        self.assertEqual(decisions, [])

    def test_non_latin_titles_do_not_normalize_to_empty(self):
        kept, decisions = deduplicate([
            StudyRecord(title="إعادة بناء الرباط الصليبي الأمامي", year=2025),
            StudyRecord(title="إعادة بناء الرباط الصليبي الأمامي", year=2025),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(decisions[0].reason, "normalized_title_year")

    def test_doi_merge_preserves_complementary_provenance(self):
        kept, decisions = deduplicate([
            StudyRecord(title="ACL review", doi="10.1000/acl", source="PubMed", source_id="PMID:1", provenance={"accessed": "first"}),
            StudyRecord(title="ACL review", doi="10.1000/ACL", source="PMC", source_id="PMCID:1", abstract="Full metadata", provenance={"accessed": "second"}),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].abstract, "Full metadata")
        snapshots = kept[0].provenance["merged_records"]
        self.assertEqual({item["source_id"] for item in snapshots}, {"PMID:1", "PMCID:1"})
        self.assertEqual(decisions[0].kept_index, 0)


if __name__ == "__main__":
    unittest.main()

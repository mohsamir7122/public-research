import csv
import hashlib
import json
import unittest
from pathlib import Path

from medical_research.pilot import run_pilot
from medical_research.search_strategy import build_queries


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "pilots" / "acl-remnant-proprioception"


class AclPilotTests(unittest.TestCase):
    def test_committed_search_strategy_matches_generator(self):
        config = json.loads((PILOT / "question.json").read_text(encoding="utf-8"))
        committed = json.loads((PILOT / "search_strategy.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, {"project_id": config["project_id"], "queries": build_queries(config)})

    def test_frozen_pilot_is_reproducible_and_conservative(self):
        config = json.loads((PILOT / "question.json").read_text(encoding="utf-8"))
        records = json.loads((PILOT / "records.json").read_text(encoding="utf-8"))
        result = run_pilot(config, records)
        expected = json.loads((PILOT / "output.expected.json").read_text(encoding="utf-8"))
        self.assertEqual(result, expected)
        self.assertEqual(result["counts"], {"input_records": 7, "deduplicated_records": 6, "duplicates_removed": 1})
        self.assertEqual(result["deduplication_decisions"][0]["reason"], "doi")
        self.assertTrue(all("proprioception" not in query.casefold() for query in result["queries"].values()))
        self.assertTrue(all("standard ACL reconstruction" not in query for query in result["queries"].values()))

    def test_human_novelty_gate_cites_present_source_ids(self):
        records = json.loads((PILOT / "records.json").read_text(encoding="utf-8"))
        decision = json.loads((PILOT / "decision.json").read_text(encoding="utf-8"))
        source_ids = {record.get("source_id") for record in records}
        self.assertEqual(decision["decision_type"], "accountable_human_novelty_gate")
        self.assertEqual(decision["decision"], "no_go_for_duplicate_broad_systematic_review")
        self.assertTrue(set(decision["decisive_source_ids"]).issubset(source_ids))

    def test_search_log_never_invents_execution_or_hit_counts(self):
        with (PILOT / "search_log.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["database"] for row in rows}, {"pubmed", "scopus", "web_of_science", "embase"})
        self.assertTrue(all(row["status"] == "not_executed" for row in rows))
        self.assertTrue(all(not row["hit_count"] and not row["export_file"] and not row["export_sha256"] for row in rows))

    def test_provenance_checksums_match_bytes(self):
        provenance = json.loads((PILOT / "provenance.json").read_text(encoding="utf-8"))
        for artifact in provenance["artifacts"]:
            digest = hashlib.sha256((PILOT / artifact["path"]).read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"], artifact["path"])


if __name__ == "__main__":
    unittest.main()

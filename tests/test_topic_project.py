import json
import tempfile
import unittest
from pathlib import Path

from medical_research.topic_project import (
    ProvisionalTopicError,
    assess_provisional_topic,
    build_provisional_topic_manifest,
    initialize_provisional_topic_project,
)


TOPIC = {
    "topic": "Return to sport after revision anterior cruciate ligament reconstruction",
    "route_hint": "meta-meta analysis",
    "research_question": (
        "What review-level evidence describes return to sport after revision ACL reconstruction?"
    ),
    "clinical_area": "Orthopaedic sports medicine",
    "project_owner": "Dr Nora Hassan",
    "constraints": ["English and Arabic collaboration", "No patient-level data in public Git"],
}


class ProvisionalTopicTests(unittest.TestCase):
    def test_informal_meta_meta_route_is_normalized_without_claiming_a_protocol(self):
        state = assess_provisional_topic(TOPIC)
        self.assertEqual(state["route_hint"], "umbrella_review")
        self.assertEqual(state["current_stage"], "topic_intake")
        self.assertEqual(state["status"], "awaiting_user_decision")
        self.assertIn("not a frozen protocol", state["truth_boundary"])
        self.assertTrue(
            any(item["code"] == "professional_intake_required" for item in state["blockers"])
        )

    def test_sparse_topic_opens_with_named_blockers(self):
        state = assess_provisional_topic({"topic": TOPIC["topic"]})
        codes = {item["code"] for item in state["blockers"]}
        self.assertIn("route_selection_required", codes)
        self.assertIn("structured_question_required", codes)
        self.assertIn("project_owner_required", codes)

    def test_invalid_or_unknown_fields_fail(self):
        with self.assertRaisesRegex(ProvisionalTopicError, "12 to 1000"):
            assess_provisional_topic({"topic": "ACL"})
        with self.assertRaisesRegex(ProvisionalTopicError, "unknown fields"):
            assess_provisional_topic({**TOPIC, "ethics_approved": True})

    def test_manifest_is_deterministic_and_content_addressed(self):
        first = build_provisional_topic_manifest(TOPIC)
        second = build_provisional_topic_manifest(TOPIC)
        self.assertEqual(first, second)
        self.assertRegex(first["project_id"], r"^TOPIC-[0-9A-F]{12}$")
        self.assertEqual(len(first["topic_fingerprint_sha256"]), 64)

    def test_initializer_is_atomic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            state = initialize_provisional_topic_project(TOPIC, root)
            self.assertEqual(
                json.loads((root / "project-state.json").read_text(encoding="utf-8")),
                state,
            )
            self.assertTrue((root / "manifest.json").is_file())
            self.assertTrue((root / "topic-brief.json").is_file())
            with self.assertRaises(FileExistsError):
                initialize_provisional_topic_project(TOPIC, root)


if __name__ == "__main__":
    unittest.main()

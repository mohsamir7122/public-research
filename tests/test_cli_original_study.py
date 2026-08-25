from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest

from medical_research.__main__ import main
from tests.test_original_study_workflow import BASE_INTAKE


TODAY = date.today().isoformat()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class OriginalStudyCliTests(unittest.TestCase):
    def invoke(self, *arguments: str):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(list(arguments))
        output = json.loads(stdout.getvalue()) if stdout.getvalue() else None
        error = json.loads(stderr.getvalue()) if stderr.getvalue() else None
        return status, output, error

    def test_original_thesis_project_initializes_and_resumes_one_verified_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            topic = root / "original-topic.json"
            project = root / "original-project"
            write_json(topic, BASE_INTAKE)
            status, output, error = self.invoke(
                "init-original-study",
                "--topic",
                str(topic),
                "--output",
                str(project),
            )
            self.assertEqual(status, 0, error)
            self.assertEqual(output["current_stage"], "topic_intake")
            self.assertEqual(
                output["required_evidence"],
                ["validated_intake", "accountable_humans_confirmed"],
            )

            artifact = project / "protocol" / "topic_intake.json"
            digest = sha256(artifact.read_bytes()).hexdigest()
            reference = {
                "artifact": "protocol/topic_intake.json",
                "sha256": digest,
                "verified_by": ["Dr Nora Hassan", "Prof Omar Khalil"],
                "verified_on": TODAY,
                "note": "The normalized intake and accountable people were checked.",
            }
            evidence = root / "gate.json"
            write_json(
                evidence,
                {
                    "validated_intake": reference,
                    "accountable_humans_confirmed": reference,
                },
            )
            status, output, error = self.invoke(
                "advance-original-study",
                "--project",
                str(project),
                "--evidence",
                str(evidence),
                "--reviewer",
                "Dr Nora Hassan",
                "--decision-date",
                TODAY,
                "--to-stage",
                "feasibility",
            )
            self.assertEqual(status, 0, error)
            self.assertEqual(output["current_stage"], "feasibility")
            state = json.loads(
                (project / "project-state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(state["workflow"]["transitions"]), 1)
            audit_lines = (
                project / "audit" / "gate-transitions.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(audit_lines), 1)

    def test_changed_historical_artifact_blocks_original_study_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            topic = root / "original-topic.json"
            project = root / "original-project"
            write_json(topic, BASE_INTAKE)
            status, _, error = self.invoke(
                "init-original-study",
                "--topic",
                str(topic),
                "--output",
                str(project),
            )
            self.assertEqual(status, 0, error)

            artifact = project / "protocol" / "intake-review.md"
            artifact.write_text(
                "# Human review of the frozen intake\n", encoding="utf-8"
            )
            reference = {
                "artifact": "protocol/intake-review.md",
                "sha256": sha256(artifact.read_bytes()).hexdigest(),
                "verified_by": ["Dr Nora Hassan", "Prof Omar Khalil"],
                "verified_on": TODAY,
                "note": "The normalized intake and accountable people were checked.",
            }
            first_evidence = root / "first-gate.json"
            write_json(
                first_evidence,
                {
                    "validated_intake": reference,
                    "accountable_humans_confirmed": reference,
                },
            )
            status, _, error = self.invoke(
                "advance-original-study",
                "--project",
                str(project),
                "--evidence",
                str(first_evidence),
                "--reviewer",
                "Dr Nora Hassan",
                "--decision-date",
                TODAY,
            )
            self.assertEqual(status, 0, error)

            state_path = project / "project-state.json"
            before = state_path.read_bytes()
            artifact.write_text("{}\n", encoding="utf-8")
            second_evidence = root / "second-gate.json"
            write_json(second_evidence, {})
            status, output, error = self.invoke(
                "advance-original-study",
                "--project",
                str(project),
                "--evidence",
                str(second_evidence),
                "--reviewer",
                "Prof Omar Khalil",
                "--decision-date",
                TODAY,
            )

            self.assertEqual(status, 2)
            self.assertIsNone(output)
            self.assertIn("historical evidence failed verification", error["error"])
            self.assertEqual(state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

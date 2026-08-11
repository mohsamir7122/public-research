import tempfile
import unittest
from pathlib import Path

from scripts.audit_repository import audit


class RepositoryAuditTests(unittest.TestCase):
    def test_clean_fixture_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "metadata.csv").write_text("title,doi\nACL study,10.1/x\n", encoding="utf-8")
            self.assertEqual(audit(root), [])

    def test_secret_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            synthetic_secret = "12345" + "67890secret"
            key_name = "api_" + "key"
            assignment = f'{key_name} = "{synthetic_secret}"\n'
            (root / "config.py").write_text(assignment, encoding="utf-8")
            self.assertTrue(any("possible secret" in item for item in audit(root)))

    def test_dicom_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "patient.dcm").write_bytes(b"DICOM")
            self.assertTrue(any("blocked file" in item for item in audit(root)))

    def test_publication_and_image_assets_are_blocked_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.PDF").write_bytes(b"%PDF synthetic")
            (root / "questions.epub").write_bytes(b"synthetic epub")
            (root / "figure.png").write_bytes(b"synthetic png")
            findings = audit(root)
            self.assertEqual(sum("requires explicit provenance allowlist" in item for item in findings), 3)

    def test_env_variants_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env.local").write_text("SAFE_PLACEHOLDER=true", encoding="utf-8")
            self.assertTrue(any("blocked file type/name" in item for item in audit(root)))


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

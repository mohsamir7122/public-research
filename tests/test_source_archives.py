import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from medical_research.source_archives import ArchiveLimits, UnsafeArchiveError, audit_zip, extract_zip_safely


class SourceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def make_zip(self, name, members, compression=zipfile.ZIP_STORED):
        path = self.root / name
        with zipfile.ZipFile(path, "w", compression=compression) as archive:
            for member_name, value in members:
                if isinstance(value, zipfile.ZipInfo):
                    archive.writestr(value, b"link-target")
                else:
                    archive.writestr(member_name, value)
        return path

    def test_safe_archive_audits_and_extracts_atomically(self):
        archive = self.make_zip("safe.zip", [("papers/a.pdf", b"%PDF-1.7\n%%EOF")])
        audit = audit_zip(archive)
        self.assertTrue(audit.safe_to_extract)
        destination = self.root / "extracted"
        extract_zip_safely(archive, destination)
        self.assertEqual((destination / "papers" / "a.pdf").read_bytes(), b"%PDF-1.7\n%%EOF")
        self.assertTrue(archive.exists())

    def test_traversal_and_absolute_paths_are_rejected(self):
        for index, member in enumerate(("../escape.pdf", "/absolute.pdf", "C:\\drive.pdf")):
            archive = self.make_zip(f"unsafe-{index}.zip", [(member, b"x")])
            audit = audit_zip(archive, verify_crc=False)
            self.assertFalse(audit.safe_to_extract)
            self.assertTrue(audit.members[0].issues)

    def test_case_colliding_paths_are_rejected(self):
        archive = self.make_zip("collision.zip", [("Papers/A.pdf", b"1"), ("papers/a.pdf", b"2")])
        audit = audit_zip(archive, verify_crc=False)
        self.assertFalse(audit.safe_to_extract)
        self.assertTrue(any("colliding" in issue for issue in audit.members[1].issues))

    def test_symlink_is_rejected(self):
        link = zipfile.ZipInfo("papers/link.pdf")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.make_zip("link.zip", [("papers/link.pdf", link)])
        audit = audit_zip(archive, verify_crc=False)
        self.assertFalse(audit.safe_to_extract)
        self.assertTrue(any("symbolic" in issue for issue in audit.members[0].issues))

    def test_compression_ratio_limit_blocks_bomb_pattern(self):
        archive = self.make_zip("ratio.zip", [("large.txt", b"0" * 100_000)], zipfile.ZIP_DEFLATED)
        audit = audit_zip(archive, ArchiveLimits(max_compression_ratio=2.0), verify_crc=False)
        self.assertFalse(audit.safe_to_extract)
        self.assertTrue(any("compression ratio" in issue for issue in audit.members[0].issues))

    def test_existing_destination_is_never_overwritten(self):
        archive = self.make_zip("safe.zip", [("a.txt", b"new")])
        destination = self.root / "existing"
        destination.mkdir()
        (destination / "a.txt").write_bytes(b"old")
        with self.assertRaises(FileExistsError):
            extract_zip_safely(archive, destination)
        self.assertEqual((destination / "a.txt").read_bytes(), b"old")

    def test_unsafe_archive_is_not_partially_extracted(self):
        archive = self.make_zip("unsafe.zip", [("ok.txt", b"ok"), ("../escape.txt", b"bad")])
        destination = self.root / "not-created"
        with self.assertRaises(UnsafeArchiveError):
            extract_zip_safely(archive, destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()

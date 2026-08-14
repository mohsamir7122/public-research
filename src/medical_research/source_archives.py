from __future__ import annotations

import hashlib
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath


DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_members: int = 10_000
    max_single_uncompressed: int = 250 * 1024 * 1024
    max_total_uncompressed: int = 10 * 1024 * 1024 * 1024
    max_compression_ratio: float = 200.0
    copy_chunk_bytes: int = 1024 * 1024


@dataclass(slots=True)
class ArchiveMemberAudit:
    original_name: str
    normalized_name: str
    file_size: int
    compressed_size: int
    compression_ratio: float | None
    crc32: str
    is_directory: bool
    issues: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArchiveAudit:
    path: str
    size_bytes: int
    sha256: str
    member_count: int
    total_uncompressed_bytes: int
    issues: list[str]
    members: list[ArchiveMemberAudit]
    crc_ok: bool | None = None

    @property
    def safe_to_extract(self) -> bool:
        return not self.issues and all(not member.issues for member in self.members) and self.crc_ok is not False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["safe_to_extract"] = self.safe_to_extract
        return payload


class UnsafeArchiveError(ValueError):
    pass


def sha256_file(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_member_name(name: str) -> tuple[str, list[str]]:
    issues: list[str] = []
    if "\x00" in name:
        issues.append("member name contains a NUL byte")
    portable = name.replace("\\", "/")
    if portable.startswith("/") or DRIVE_PREFIX.match(portable):
        issues.append("member path is absolute or drive-qualified")
    parts = PurePosixPath(portable).parts
    if ".." in parts:
        issues.append("member path traverses outside the extraction root")
    normalized_parts = [part for part in parts if part not in {"", ".", "/"}]
    if not normalized_parts:
        issues.append("member path is empty")
        return "", issues
    return "/".join(normalized_parts), issues


def _type_issues(info: zipfile.ZipInfo) -> list[str]:
    mode = (info.external_attr >> 16) & 0xFFFF
    if not mode or stat.S_IFMT(mode) == 0:
        return []
    if stat.S_ISLNK(mode):
        return ["symbolic links are not allowed"]
    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        return ["special files are not allowed"]
    return []


def audit_zip(path: Path, limits: ArchiveLimits | None = None, *, verify_crc: bool = True) -> ArchiveAudit:
    limits = limits or ArchiveLimits()
    path = path.resolve()
    archive_issues: list[str] = []
    members: list[ArchiveMemberAudit] = []
    total_uncompressed = 0
    seen_names: set[str] = set()
    crc_ok: bool | None = None

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_members:
                archive_issues.append(f"member count {len(infos)} exceeds limit {limits.max_members}")
            for info in infos:
                normalized, issues = _normalized_member_name(info.filename)
                issues.extend(_type_issues(info))
                if info.flag_bits & 0x1:
                    issues.append("encrypted members are not allowed")
                collision_key = normalized.casefold()
                if collision_key in seen_names:
                    issues.append("duplicate or case-colliding member path")
                seen_names.add(collision_key)
                if info.file_size > limits.max_single_uncompressed:
                    issues.append(
                        f"uncompressed size {info.file_size} exceeds per-member limit {limits.max_single_uncompressed}"
                    )
                if info.compress_size == 0:
                    ratio = None if info.file_size == 0 else float("inf")
                else:
                    ratio = info.file_size / info.compress_size
                if ratio is not None and ratio > limits.max_compression_ratio:
                    issues.append(
                        f"compression ratio {ratio:.2f} exceeds limit {limits.max_compression_ratio:.2f}"
                    )
                total_uncompressed += info.file_size
                members.append(
                    ArchiveMemberAudit(
                        original_name=info.filename,
                        normalized_name=normalized,
                        file_size=info.file_size,
                        compressed_size=info.compress_size,
                        compression_ratio=ratio,
                        crc32=f"{info.CRC:08x}",
                        is_directory=info.is_dir(),
                        issues=issues,
                    )
                )
            if total_uncompressed > limits.max_total_uncompressed:
                archive_issues.append(
                    f"total uncompressed size {total_uncompressed} exceeds limit {limits.max_total_uncompressed}"
                )
            if verify_crc:
                bad_member = archive.testzip()
                crc_ok = bad_member is None
                if bad_member is not None:
                    archive_issues.append(f"CRC check failed for {bad_member}")
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        archive_issues.append(f"archive could not be read: {exc}")
        infos = []

    return ArchiveAudit(
        path=str(path),
        size_bytes=path.stat().st_size if path.exists() else 0,
        sha256=sha256_file(path) if path.is_file() else "",
        member_count=len(members),
        total_uncompressed_bytes=total_uncompressed,
        issues=archive_issues,
        members=members,
        crc_ok=crc_ok,
    )


def extract_zip_safely(path: Path, destination: Path, limits: ArchiveLimits | None = None) -> ArchiveAudit:
    """Audit and atomically extract a ZIP without following archive paths or preserving special modes."""

    limits = limits or ArchiveLimits()
    path = path.resolve()
    destination = destination.resolve()
    audit = audit_zip(path, limits, verify_crc=True)
    if not audit.safe_to_extract:
        issue_text = audit.issues + [issue for member in audit.members for issue in member.issues]
        raise UnsafeArchiveError("; ".join(issue_text))
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.extract-", dir=destination.parent))
    try:
        member_by_name = {member.original_name: member for member in audit.members}
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                member = member_by_name[info.filename]
                output = staging.joinpath(*PurePosixPath(member.normalized_name).parts)
                if info.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                copied = 0
                with archive.open(info, "r") as source, output.open("xb") as target:
                    while chunk := source.read(limits.copy_chunk_bytes):
                        copied += len(chunk)
                        if copied > info.file_size or copied > limits.max_single_uncompressed:
                            raise UnsafeArchiveError(f"member expanded beyond audited size: {info.filename}")
                        target.write(chunk)
                if copied != info.file_size:
                    raise UnsafeArchiveError(f"member size changed during extraction: {info.filename}")
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return audit

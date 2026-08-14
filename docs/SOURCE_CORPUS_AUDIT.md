# Source-corpus audit and extraction policy

## Result for the supplied corpus

The upload manifest describes 23 independent ZIP archives with 1,237 PDFs. Eleven archives were supplied; 12 were absent. All 11 supplied archives matched the expected byte sizes and passed ZIP integrity, CRC, traversal, absolute-path, link/special-file, encryption, duplicate-path, size, and compression-ratio checks before extraction.

Safe extraction produced 680 files: 675 PDFs plus five harvest-metadata files. The PDFs contain 8,167 pages across 61 journals. All 675 matched their manifest records, and no PDF-level SHA-256 or DOI duplicate was found. There are 562 expected PDFs in the missing archive parts.

No thesis or dissertation PDF is present. The corpus contains papers, seven protocol articles, reviews/guidelines/consensus documents, and front matter. The only thesis-specific source is the Benha administrative protocol template, which is explicitly excluded from methodological development.

One PDF contains a multipart wrapper before its `%PDF` payload, and one readable PDF is encrypted. Both parsed during the audit, but downstream strict consumers must normalize or quarantine them rather than silently treating them as conformant.

## Metadata caveats

The global harvest metadata contains 14,972 rows and 14,482 unique DOI values. It has 455 duplicate-DOI groups (476 extra rows), 14 rows without a DOI, and two pairs of byte-identical exports. These metadata duplicates are distinct from the available PDF corpus, which has no DOI or content-hash duplicate.

## Public-repository boundary

The raw archives and extracted full text are not committed. Their redistribution rights and the unpublished status of any future source have not been established. This repository stores only derived, non-identifying counts, filenames of archive parts, and checksums. Full-text style analysis must separately document an open licence, user ownership, or other authorization for each paper.

## Safe ingestion

The `source_archives` module audits before extraction, rejects ZIP traversal and path collisions across operating systems, rejects links/special/encrypted members, limits counts/sizes/compression ratios, verifies CRC, streams to a staging directory, and renames the directory only after successful extraction. Existing destination directories are never overwritten.

Example:

```bash
PYTHONPATH=src python scripts/audit_source_archives.py \
  /path/to/ortho_oa_part_001.zip \
  --output output/archive_audit.json \
  --extract-root /path/to/new/extraction-root
```

The original archive is preserved. Review the JSON report and rights basis before any scientific use or repository publication.

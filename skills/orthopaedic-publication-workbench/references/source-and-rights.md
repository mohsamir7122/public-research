# Source, provenance, and rights gate

## Source ledger

Create one record per source with these fields:

| Field | Meaning |
|---|---|
| `source_id` | Stable local identifier |
| `kind` | Official guidance, bibliographic metadata, user-owned full text, open-access full text, or administrative template |
| `title` | Human-readable title |
| `url_or_path` | Exact retrieval location |
| `retrieved_at` | ISO date in UTC |
| `checksum` | SHA-256 for a local file or frozen response |
| `rights_basis` | User-owned, licence name, public domain, metadata-only, or unknown |
| `allowed_use` | Discovery, quotation, analysis, style profile, or internal review |
| `evidence_location` | Page, section, table, paragraph, or structured field supporting the claim |

Unknown rights permit metadata-only discovery, not redistribution or full-text model training. Never commit raw thesis archives, unpublished manuscripts, subscription PDFs, or extracted copyrighted text to a public repository.

For a web source, preserve the exact fetched HTML/PDF or a standards-compliant web archive in the private evidence cache before hashing it. Record the requested URL, final redirect URL, retrieval date, checksum, and evidence location. Do not hash only the URL string and do not commit a copyrighted frozen response to a public repository. If the response cannot be frozen, mark the claim pending rather than inventing a checksum.

## Evidence classes

1. **Official normative source**: journal/publisher instructions, registry, ethics body, or reporting-guideline owner. Use for requirements.
2. **Authorized full text**: use for manuscript-style observations and scientific review.
3. **Abstract or metadata**: use for discovery and screening only; do not infer methods that are not reported.
4. **Administrative template**: use only for layout or local submission fields; it is not methodological evidence.

## Minimum public-repository representation

Prefer checksums, counts, stable IDs, licence status, and derived non-identifying summaries. Keep the source corpus outside the public repository. A path or checksum proves which file was examined; it does not prove permission to redistribute it.

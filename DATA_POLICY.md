# Public Data Policy

## Allowed

- Bibliographic metadata: title, authors, journal, year, DOI, abstract when redistribution is permitted, and public landing-page URL.
- Public reporting guidelines, registry identifiers, and official Author Guidelines links.
- Synthetic or fully de-identified test fixtures that cannot be reversed to a person.
- Code, schemas, queries, templates, logs, checksums, and derived aggregate statistics.
- Open-access full text only when its license explicitly permits redistribution and the license is recorded.

## Prohibited

- Names, civil IDs, medical record numbers, dates of birth, faces, voice, contact details, or other Protected Health Information.
- DICOM files or clinical images unless a documented public license and irreversible de-identification are both verified.
- Hospital exports, consent forms, internal correspondence, ethics documents containing identifiers, or private research datasets.
- Subscription PDFs, copyrighted textbooks, question banks, or scraped full text without redistribution rights.
- API keys, cookies, access tokens, passwords, private URLs, or credentials in code, logs, screenshots, fixtures, or Git history.
- Unpublished manuscripts, abstracts, protocols, or commercially sensitive ideas unless the owner explicitly chooses public disclosure.

## Required provenance

Every imported dataset must record source, retrieval time, exact query or request, filters, license or access basis, file checksum, and transformation step. Unknown rights means metadata-only until resolved.

## Incident response

If prohibited material is committed, stop processing, revoke exposed credentials when relevant, remove access, document the affected paths and commits, and perform history cleanup through an approved Git procedure. Do not conceal the incident with a later deletion commit alone.

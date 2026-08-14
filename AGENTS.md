# Repository Instructions

## Scope

Use this repository only for reproducible medical research workflows. Keep stock-market, financial-analysis, medical-book production, and patient-care record systems outside this repository.

## Before changing research logic

Read `DATA_POLICY.md` and `docs/WORKFLOW.md`. Describe only capabilities present in the current tree and covered by tests. Label unimplemented capabilities as roadmap items.

## Evidence and provenance

Preserve raw inputs unchanged and record the source file, retrieval date, query, filters, and checksum for derived datasets. Never claim that a paper, guideline, author instruction, DOI, license, or full text was checked unless it was opened and verified.

Do not infer eligibility, outcome values, or Risk of Bias judgments from a title or search snippet. Keep extracted text and reviewer judgments separate.

## Public-repository safety

Never commit Protected Health Information, patient images, hospital exports, credentials, API keys, subscription full text, copyrighted textbooks, or confidential/unpublished datasets. Use synthetic fixtures in tests. Run `python scripts/audit_repository.py .` before proposing a release.

## Research rules

- Build database-specific search syntax; do not paste PubMed syntax into every database.
- Deduplicate by normalized DOI first. Only use title and year when DOI evidence is absent, and never auto-merge two different non-empty DOIs.
- Keep Screening decisions auditable with reviewer, stage, decision, reason, and date.
- Select reporting and Risk of Bias frameworks by study design; do not treat one checklist as universal.
- Keep Research Readiness, methodological quality, journal fit, and acceptance probability separate.

## Validation

Run:

```bash
python -m unittest discover -s tests -v
python scripts/audit_repository.py .
```

Do not merge when either command fails.

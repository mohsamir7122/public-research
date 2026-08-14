# Manuscript Style and Statistical-Marker Audit

Snapshot date: 2026-08-12

## Scope

This audit creates reproducible, derived observations from the supplied orthopaedic and sports-medicine corpus. It does not copy PDF text into the repository and does not use the Benha University protocol template.

The audit separates three questions that must not be conflated:

1. title and article metadata patterns observed across all supplied records;
2. full-text style and statistical-marker observations where the supplied inventory carries a compatible license label; and
3. current official journal requirements, which must be verified independently from the journal or publisher before submission.

Observed patterns do not explain why an article was accepted and cannot estimate acceptance probability.

## Input and rights gate

- Supplied PDF records: 675 across 61 journals.
- Metadata/title profiles: 675.
- Full texts analyzed: 341.
- Full texts stopped at the rights gate: 334.
- License labels admitted for internal full-text analysis: `cc-by`, `cc-by-nc`, and `public-domain`.
- The license labels were inherited from the supplied inventory and were not independently reverified against every publisher landing page.
- Raw extracted text persisted: no.

The wider upload manifest describes 1,237 PDFs, but only 675 were present in the 11 supplied archive parts. Consequently, this is a partial-corpus audit, not a complete profile of every listed journal.

## Reproducible method

For every record, the runner:

1. profiles the bibliographic title without opening the PDF;
2. applies the license-label gate;
3. resolves the PDF path and rejects traversal or symlink escape from the declared root;
4. verifies the PDF SHA-256 against the inventory;
5. extracts text in memory with `pdftotext -layout`;
6. stops the statistical/software/guideline scan at a reliable late References or Bibliography heading when one is reconstructed;
7. records booleans and counts for structural, reporting-guideline, software, and statistical markers; and
8. discards the extracted text.

Run from the repository root:

```bash
PYTHONPATH=src python scripts/audit_manuscript_corpus.py \
  --inventory /path/to/pdf_inventory.jsonl \
  --pdf-root /path/to/extracted \
  --output-dir /path/to/derived-output \
  --workers 8 \
  --snapshot-date 2026-08-12
```

The frozen run used `pdftotext` 24.02.0. Its source inventory SHA-256 is recorded in the summary.

## Corpus-level observations

These counts describe detectable text patterns only. Denominators are explicit because the title and full-text samples differ.

| Observation | Count | Denominator | Fraction |
|---|---:|---:|---:|
| Title contains a colon | 346 | 675 | 51.3% |
| Title contains a question mark | 34 | 675 | 5.0% |
| Title contains a recognized study/design descriptor | 146 | 675 | 21.6% |
| Structured-abstract marker | 162 | 341 | 47.5% |
| Exact/threshold p-value marker | 209 | 341 | 61.3% |
| Sample-size or power marker | 149 | 341 | 43.7% |
| Confidence-interval marker | 137 | 341 | 40.2% |
| Effect-estimate marker | 128 | 341 | 37.5% |
| Model-diagnostic marker | 71 | 341 | 20.8% |
| Multivariable-regression marker | 63 | 341 | 18.5% |
| Multiplicity marker | 56 | 341 | 16.4% |
| Missing-data marker | 52 | 341 | 15.2% |
| Multiple-imputation marker | 19 | 341 | 5.6% |
| Sensitivity-analysis marker | 25 | 341 | 7.3% |

Mean title length was 15.71 tokenized words. The corpus mixes research articles, reviews, protocols, corrections, and front matter, so these aggregate values are not journal rules or recommended targets.

The most frequently detected software name was SPSS (101 documents), followed by R (23), SAS (13), Stata (12), and GraphPad Prism (10). Context-filtered reporting-guideline markers included STROBE (28), PRISMA (20), and CONSORT (16). A mention is not evidence that the article complied with the software or guideline, and a non-mention is not evidence that it did not.

A late References/Bibliography boundary was reliably reconstructed in 158 of 341 analyzed full texts (46.3%); those marker scans stopped at the boundary. The remaining PDFs were scanned in full because the stricter parser did not identify a reliable late heading. Study/design descriptors are derived from titles only: a design term appearing in an introduction is never promoted to an article-type classification.

## Journal-level evidence status

- 22 of 61 journals had at least five distinct license-compatible full-text samples.
- 26 had one to four samples and are explicitly marked insufficient for a stable style profile.
- 13 had no license-compatible full-text sample and remain metadata-only.

Even the 22 larger samples are descriptive snapshots of the supplied papers. Article type, year, editorial policy, and publisher production can all affect apparent style. The journal profile therefore retains separate denominators, article-kind counts, and source counts.

## How to use the output

- Use title patterns to generate candidates, then screen for scientific accuracy, design labeling, non-causal wording, and official title rules.
- Route statistical planning from the study design, estimand, outcome structure, missingness, clustering, multiplicity, and sensitivity analyses. Do not copy a method merely because it appears frequently.
- Treat every official requirement as pending until a dated journal/publisher source is captured and verified.
- Keep journal fit, manuscript readiness, and editorial outcome as separate concepts.

## Files

- `data/manuscript_audit/document_profiles_2026-08-12.jsonl`: per-record title and rights-gated marker profiles; no PDF text.
- `data/manuscript_audit/journal_profiles_2026-08-12.json`: journal aggregates with evidence status and explicit denominators.
- `data/manuscript_audit/summary_2026-08-12.json`: provenance, rights-gate counts, extractor version, and interpretation boundary.

## Limitations and required review

Regex markers can produce false positives from introductions, discussions, or reference lists. The code context-checks ambiguous reporting-guideline acronyms such as CARE and PROCESS, but the output still requires human review before scientific use. PDF extraction can also miss content in images or unusual layouts.

The audit does not assess risk of bias, statistical correctness, reporting completeness, novelty, scope eligibility, or editorial quality. Those decisions require an investigator, statistician, and current official journal evidence. No generated profile is submission-ready by itself.

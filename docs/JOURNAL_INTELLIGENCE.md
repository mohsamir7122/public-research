# Journal-intelligence design and source audit

## Input audit

- The historical category snapshot contains 319 ranked records. Its spreadsheet representation is not a normal table: most content is stored in drawing-layer text boxes.
- The “Publishability Factor v4” workbook contains 152 journal records, not the full 319.
- Only 38/152 records are labelled curated and 22 have deep-dive rows. In the final audit, 130/152 still require live verification and 130 rely on publisher-family heuristics.
- The workbook's pilot contains 80 title observations from four table-of-contents URLs without DOI-level extraction provenance. It can describe a small observed title sample; it cannot explain editorial acceptance.

## Confirmed failure modes in the workbook

1. `06_Journal_Matcher!P3:P40`, labelled `Official_URL`, points to the scope column rather than the source-URL column.
2. The title-fit formula compares a bucket with the design field and compares text against numeric thresholds. This produces default points unrelated to the title.
3. Scope mismatch is compensatory: a Foot & Ankle topic can still receive a 90/100 “Strong target” label for an arthroplasty journal.
4. The nominal core score can exceed 100 before country bonuses are applied, and country/university context influences the capped result.
5. Nine rules are mapped across different journals, including Sports Medicine to AJSM and Arthroplasty to Arthroplasty Today.
6. KSSTA is incorrectly treated as archived based on its former Springer page; the journal moved to Wiley in 2024 and remains active. A publisher transfer must not be interpreted as journal cessation.

## Replacement model

- **Historical discovery:** title, stable source identifier, and dated metric only.
- **Current status:** verified separately from a current official publisher or society source.
- **Requirements:** atomic official claims with URL, date, and evidence location; otherwise pending.
- **Eligibility:** non-compensatory scope and article-type gates.
- **Title quality:** accuracy, clarity, searchability, design label, and claim discipline.
- **Journal fit:** evaluated only after eligibility and verification.
- **Research readiness:** protocol, ethics, registration, data, and analysis readiness.
- **Editorial outcome:** unknown; no acceptance score or probability.

The registry validator prevents historical ranks from being treated as current requirements. The title engine uses token-aware rules, rejects causal/result claims that conflict with the declared design or stage, and never produces an acceptance probability.

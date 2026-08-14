---
name: orthopaedic-publication-workbench
description: "Build or audit an orthopaedic research publication pack: choose defensible manuscript titles, match a study to journals using current official requirements, write a design-specific protocol and statistical analysis plan, and profile manuscript style from licensed full text. Use for thesis protocols, journal targeting, title review, manuscript readiness, reporting-guideline routing, and statistical-method review. Do not use it to predict acceptance or to replace ethics, statistical, or clinical review."
---

# Orthopaedic Publication Workbench

## Purpose

Produce a traceable publication pack whose claims can be reviewed independently. Keep four judgments separate at all times:

1. **Title quality** — clarity, specificity, design accuracy, and absence of hype.
2. **Journal fit** — scope, article type, and verified submission constraints.
3. **Research readiness** — protocol, data, ethics, registration, and analysis readiness.
4. **Editorial outcome** — unknown. Never generate an acceptance probability or an “acceptance score.”

## Non-negotiable rules

- Do not use the Benha University protocol template, or any other institutional template, as a methodological authority. If the user later requests it, apply it only as an administrative formatting overlay after the independent scientific protocol is complete.
- Do not reward or penalize a study because of country, university, author identity, or prestige.
- Do not use universal sample-size, follow-up, p-value, or impact-factor cutoffs as proxies for scientific quality.
- Do not state a journal requirement unless it was found on an official journal or publisher page and recorded with the exact URL and verification date. Mark all other requirements `pending_verification`.
- Do not infer journal rules or causal validity from titles, abstracts, or a small sample of published papers.
- Use only user-owned, openly licensed, public-domain, or otherwise authorized full text for style analysis. Bibliographic metadata may be used for discovery.
- Keep unpublished theses, identifiable participant data, subscription PDFs, credentials, and copyrighted full text out of public repositories.
- Treat reporting checklists as minimum reporting frameworks, not substitutes for study design, ethics review, trial registration, or statistical expertise.

## Workflow

### 1. Establish provenance and rights

Read `references/source-and-rights.md`. Inventory every source, checksum local inputs, record ownership or license basis, and separate discovery metadata from full-text evidence. Stop if protected health information or unclear authority makes the requested use unsafe.

### 2. Classify the study before drafting

Record the research question, exact design (for example, `retrospective_cohort`, not merely “observational”), intended inference, setting, recruitment stage, intervention/exposure, comparator, outcomes, follow-up, unit of allocation, unit of analysis, whether routinely collected data are used, and whether comparative results have already been seen. Distinguish a proposal from a completed study. Never write results into a pre-data title. If results were seen before protocol/SAP freeze, label the work transparently and record which decisions were post hoc.

Do not present a complete pack until the investigator has confirmed the question, exact design, one primary outcome/time point, data source, results visibility, and whether the aim is associational or causal. A draft may continue with missing items only when each is explicit in the blocking unresolved-question list.

Use `references/reporting-guideline-router.md` to select the primary reporting framework and any applicable extension. Recheck the linked official source on the day of use because standards change.

### 3. Build the protocol

Read `references/protocol-core.md` and create a versioned protocol with:

- rationale supported by a current, reproducible literature search;
- one primary objective and a prespecified primary outcome/time point;
- eligibility, recruitment, consent, ethics, and registration plans;
- intervention/exposure and comparator definitions detailed enough to reproduce;
- bias-control measures appropriate to the design;
- outcome definitions, measurement properties, harms, and data-quality procedures;
- sample-size justification based on the primary estimand and design assumptions;
- deviations, amendments, monitoring, dissemination, data-sharing, and authorship plans.

For randomized trials, use SPIRIT 2025 and define the estimand before the analysis. Register qualifying clinical trials at or before first participant consent/enrolment as required by ICMJE.

### 4. Write the statistical analysis plan

Read `references/statistical-analysis-router.md`. Align each objective, outcome, estimand, effect measure, model, and sensitivity analysis. Specify analysis populations, covariates, clustering/repeated measures, missing-data assumptions, multiplicity, model diagnostics, protocol deviations, and software/version before examining outcome results.

Lead results with effect estimates and uncertainty. Do not treat statistical significance as clinical importance, do not select tests from normality tests alone, and do not change the primary analysis after viewing results without an explicit dated amendment.

### 5. Generate and assess titles

Create 6–10 candidates only after the study classification and target article type are known. For each candidate, record:

- exact study design and population;
- intervention/exposure and comparator when central;
- primary construct or outcome when helpful;
- setting only when scientifically important;
- whether a journal requires or discourages a design label;
- unsupported causal language, hype, abbreviations, redundancy, and outcome claims.

Score title quality and journal fit separately using transparent reasons. Never convert either into acceptance likelihood. Prefer concise, searchable nouns and accurate design labels over promotional wording.

### 6. Verify journals and profile style

Read `references/journal-evidence.md`. Build a separate evidence record for each journal. Verify scope, article type, word/abstract/reference/figure limits, reporting checklist, trial registration, data-sharing, ethics, anonymization, fees, open-access route, preprint policy, and required files directly from official pages.

For style profiling, sample recent, relevant, authorized full-text articles and record DOI, article type, date, license, source location, and extraction evidence. Use at least five papers per article type. If authorized full text is unavailable or the user did not request a style profile, set the output to `insufficient_evidence` with the reason; do not block title, protocol, SAP, or preliminary journal-fit work. Separate:

- explicit rules from author instructions;
- observed conventions from papers;
- scientific quality judgments from cosmetic style.

Do not claim that an observed convention is mandatory.

### 7. Validate and hand off

Create `research-pack.json` using the fields documented by the validator, then run:

```bash
python skills/orthopaedic-publication-workbench/scripts/validate_research_pack.py research-pack.json
```

Return these outputs:

1. evidence and rights ledger;
2. design/reporting-guideline decision with source links and dates;
3. protocol and statistical analysis plan;
4. title candidate table with separate quality and journal-fit rationales;
5. journal requirement matrix with `verified`, `stale`, or `pending_verification` status;
6. manuscript-style observations with source locations;
7. unresolved questions, required specialist reviews, and a no-fabrication audit.

## Required review gates

Do not label the pack submission-ready until a human investigator confirms the clinical question and feasibility, a statistician reviews the sample-size and SAP, ethics/data-governance/registration requirements are resolved, all decisive journal rules are currently verified with atomic evidence records, every blocking question is resolved, and every full-text use has a recorded rights basis. A validator pass confirms the encoded guardrails; it is not clinical, statistical, ethical, or editorial approval.

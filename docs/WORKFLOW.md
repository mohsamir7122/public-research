# Medical Research Workflow

## 1. Start or resume

Every project begins in one of two states:

- provisional topic: enough to preserve the idea and list blockers, but never protocol-ready;
- validated route intake: enough to create a deterministic manifest and an evidence-gated workflow.

Load project-state.json before continuing. Verify its state fingerprint, route-specific pipeline, topic fingerprint, transition hashes, and every historical artifact reference and checksum. Never reconstruct a later state from chat history when a valid state file exists.

## 2. Route before drafting

Choose one route:

- original_study_or_thesis;
- systematic_review;
- systematic_review_with_meta_analysis;
- umbrella_review.

Normalize “meta-meta-analysis” to umbrella_review. Do not force network meta-analysis, diagnostic-accuracy meta-analysis, IPD meta-analysis, Bayesian synthesis, or other specialist designs into the generic pairwise route.

## 3. Original study or thesis

The executable route proceeds through:

1. topic intake and accountable-human confirmation;
2. feasibility, data access or recruitment, timeline, and design-specific sample-size basis;
3. frozen protocol;
4. ethics and governance determinations recorded from real source documents;
5. human registration-applicability assessment and registration when required;
6. observational bias/confounding plan or intervention/safety plan;
7. versioned data dictionary and provenance plan;
8. frozen Statistical Analysis Plan;
9. study conduct and auditable data capture;
10. authorized data lock with dataset checksum;
11. reproducible analysis and independent verification;
12. results-traceable reporting, QA, and human release.

The workflow records approval evidence; it does not create or authenticate ethics, governance, registration, consent, recruitment, or source data.

## 4. Systematic review routes

All review routes require:

1. a structured question and feasibility/gap assessment;
2. a frozen protocol and recorded registration status;
3. database-specific, peer-reviewed searches with immutable exports and checksums;
4. conservative deduplication and report-to-study or report-to-review linking;
5. two independent human screening decisions and adjudicated final decisions;
6. source-located extraction and independent verification;
7. design-appropriate Risk of Bias or review appraisal;
8. route-appropriate synthesis;
9. outcome-level certainty assessment;
10. PRISMA 2020 or PRIOR flow derived from the event ledger;
11. claims-to-evidence reconciliation and human QA.

A systematic review always permits a structured synthesis without statistical pooling. A meta-analysis is a conditional component, not a mandatory result.

## 5. Pairwise meta-analysis boundary

Before run-meta:

- freeze the outcome, time point, effect measure, direction, estimand, and analysis scale;
- resolve multiple reports, multi-arm studies, repeated outcomes, clusters, and other dependencies;
- create a pooling-decision artifact with a real SHA-256 and two accountable approvers;
- preserve verified effect estimates and standard errors on the declared common scale.

The built-in calculation kernel performs a generic inverse-variance check with fixed or Paule–Mandel random effects. Ratio measures must enter on the log scale and are back-transformed for display. The result remains calculation_check_not_release_analysis. Complex designs and a production primary analysis require a prespecified specialist extension and independent statistical reproduction.

## 6. Umbrella review boundary

An umbrella review screens systematic reviews as the evidence unit. It must:

- derive a PRIOR-labelled review-selection flow using review_id;
- map primary-study overlap within a defined comparison, outcome, and time point;
- calculate CCA only as a descriptive overlap measure;
- compare review recency, scope, appraisal, certainty, and discordance;
- never pool overlapping review summaries as if they were independent.

## 7. Evidence-gated state

A Gate evidence value must identify:

- a safe path inside the project;
- the file SHA-256;
- one or more accountable human verifiers, with two where independence is required;
- a non-future verification date;
- a concise note describing the check.

The CLI verifies that the file exists inside the project and that its digest matches before changing the state. On resume it rehashes every artifact referenced by earlier transitions and fails closed if one changed or disappeared. It writes state atomically, records the full evidence reference in the transition, links transitions with SHA-256, and maintains an audit JSONL derived from the authoritative state.

Passing these checks proves traceability and sequencing, not truth or methodological sufficiency. The fingerprints and hash chain are consistency checks, not digital signatures, trusted timestamps, or proof of actor identity.

## 8. Manuscript and journal package

Draft only from verified artifacts. Never invent citations, outcome values, registrations, approvals, author instructions, or journal rules. Verify current official Author Guidelines immediately before final formatting. Keep title quality, methodological quality, research readiness, journal fit, and editorial outcome separate; never estimate acceptance probability.

## 9. Public-repository boundary

Public Git may contain code, schemas, templates, synthetic fixtures, checksums, and redistributable derived outputs. It must not contain PHI, patient images, hospital exports, credentials, subscription full text, copyrighted books, or confidential/unpublished data.

## 10. Validation

Before a Pull Request or release, run:

    PYTHONPATH=src python -m unittest discover -s tests -v
    python scripts/audit_repository.py .

Automation may organize, calculate, reconcile, and flag. Eligibility, clinical interpretation, Risk of Bias, certainty, ethics/governance, authorship, and final scientific claims remain accountable human decisions.

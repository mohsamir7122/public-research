# Systematic Review, Meta-analysis, and Umbrella Review Method Standard

**Purpose:** repository-level specification for producing defensible medical evidence syntheses with AI assistance and explicit human accountability.  
**Guidance checked:** 25 August 2026.  
**Scope:** systematic reviews of primary studies, pairwise meta-analysis, and umbrella reviews/overviews of systematic reviews. Network meta-analysis, individual-participant-data meta-analysis, diagnostic-accuracy meta-analysis, and qualitative synthesis require separate specialist modules.

## 1. Non-negotiable design rule

The repository must route the question before it searches or writes:

- A **systematic review** searches for and synthesizes eligible primary studies.
- A **meta-analysis** is an optional statistical component of a systematic review, not a synonym for one and not a mandatory output.
- An **umbrella review/overview of reviews** uses systematic reviews as the principal unit of search, inclusion, and analysis.
- “**Meta-meta-analysis**” is not accepted as a sufficient protocol label. The system must translate it into an umbrella-review question and state whether the intended synthesis will summarize review-level findings, select one review per evidence component, or reanalyse non-duplicated primary-study data. It must never naively pool pooled estimates from overlapping reviews.

A well-phrased topic is sufficient to open a project, but not to lock the methods. The system should collaborate with the investigator until the review question, eligibility criteria, outcomes, time points, and analysis choices are approved.

## 2. Normative stack and correct use

- Use the [Cochrane Handbook, version 6.5](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current) as the core conduct reference for intervention reviews and meta-analysis.
- Use the [JBI Manual, Chapter 9: Umbrella Reviews](https://doi.org/10.46658/JBIMES-24-08) and the [Cochrane chapter on Overviews of Reviews](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-v) for umbrella-review conduct.
- Use [PRISMA-P](https://www.prisma-statement.org/protocols) to report the protocol, [PRISMA 2020](https://www.prisma-statement.org/prisma-2020) to report a completed systematic review, and [PRIOR](https://www.bmj.com/content/378/bmj-2022-070849) to report an overview of healthcare-intervention reviews.
- Use [AMSTAR 2](https://amstar.ca/Amstar-2.php) for methodological appraisal of systematic reviews of healthcare interventions and [ROBIS](https://www.bristol.ac.uk/population-health-sciences/projects/robis/robis-tool/) for risk of bias in a systematic review. They answer related but different questions and are not interchangeable.
- Use [GRADE](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14) to judge certainty in each important outcome, not the prestige, sample size, or statistical significance of the review as a whole.

`PRISMA-complete` must mean “reporting fields are complete.” It must not mean “methods are valid,” “risk of bias is low,” or “evidence is certain.” AMSTAR 2 must not be converted to a percentage or summed quality score; its official overall confidence depends on critical-domain weaknesses.

## 3. End-to-end workflow

### Stage A — question and feasibility

1. Convert the topic into a structured question appropriate to the review type, usually PICOTS for intervention questions.
2. Define the intended decision, audience, population, intervention or exposure, comparator, outcomes, time points, settings, study designs, and date/language limits.
3. Run a documented preliminary search to identify recent reviews, active protocols, likely primary-study volume, and whether the work should be a new systematic review, an update, or an umbrella review.
4. Record why the selected design is preferable. If recent high-quality reviews already cover the precise question, consider an update or overview rather than duplicating them.
5. Obtain clinical and methodological sign-off before the formal search.

### Stage B — protocol lock

The versioned protocol must be approved before formal screening and must contain:

- rationale, objectives, structured question, and operational definitions;
- inclusion and exclusion rules, including eligible report status and study designs;
- primary and secondary outcomes fully defined by domain, measurement instrument, metric, method of aggregation, and time point;
- information sources, draft source-specific searches, citation-chasing and registry plans;
- duplicate-screening, duplicate-extraction, and conflict-resolution procedures;
- rules for linking multiple reports of the same study;
- risk-of-bias tools matched to study design;
- synthesis groupings, effect measures, model assumptions, heterogeneity plan, missing-data rules, subgroup and sensitivity analyses;
- small-study and missing-evidence assessment;
- GRADE plan for critical and important outcomes;
- for umbrella reviews, the review definition, currency rule, primary-study overlap plan, discordance plan, and rule for choosing among overlapping reviews;
- funding, conflicts of interest, team roles, data/code sharing, and update policy.

Register the protocol prospectively when eligible, or create a public, immutable, time-stamped protocol. Every later change must retain the old value, new value, date, reason, stage at which it was made, and approver. Post-hoc analyses must be labelled as such.

### Stage C — reproducible search

1. Translate the concepts independently for each database; do not paste one database's syntax into another.
2. Search all sources justified by the question, including relevant bibliographic databases and registers. Add reference-list and forward-citation searching, grey literature, regulators, conference sources, and author contact when relevant.
3. Do not apply language, publication-status, or date restrictions without a protocol-level justification.
4. Save, verbatim, every search string, platform, database, coverage period, run date/time, result count, export file, and any deduplication performed by the platform.
5. Preserve raw exports as immutable evidence. A rerun creates a new `search_run`; it never overwrites the earlier run.
6. Require an information specialist or designated search reviewer to approve the strategy before the final run.

### Stage D — citation normalization and study-family linking

The repository must distinguish:

- a **record**, which is a database result;
- a **report**, which is a publication, abstract, registry entry, thesis, or regulatory document;
- a **study**, which is the underlying investigation and may have several reports;
- a **review**, which is an included evidence synthesis in an umbrella review.

Deduplicate records using identifiers and conservative fuzzy matching. Link reports into study families using trial registration, sample, sites, dates, arms, and author information. Uncertain merges remain flagged for human adjudication; automation must not silently merge them.

### Stage E — selection

1. Pilot the criteria on a sample and refine only through documented protocol clarification.
2. Conduct title/abstract screening and full-text assessment independently in duplicate.
3. Record one primary, controlled exclusion reason for every excluded full text; retain additional notes separately.
4. Resolve disagreements by consensus or a named third reviewer. Do not let an AI vote count as the second independent human decision.
5. Derive the PRISMA or PRIOR flow from stored events. Hand-entered flow totals that do not reconcile with the decision ledger fail validation.
6. Keep “awaiting classification,” “ongoing,” “duplicate report,” and “not retrieved” separate from ordinary exclusions.

AI may rank citations, highlight likely eligibility evidence, or propose a decision, but a human must verify the source and own the final inclusion decision.

### Stage F — extraction and provenance

Use a piloted, versioned form. Extraction must be independently duplicated or independently verified, with disagreements retained and resolved. Every numerical or textual field must point to its source report and exact locator, such as page, table, figure, supplement, registry field, or author correspondence.

For primary studies, capture at minimum study design, setting, recruitment, sample, arms, baseline characteristics, intervention/exposure and comparator details, outcomes, time points, analysis population, funding/conflicts, and all data needed to reproduce each effect estimate.

For umbrella reviews, additionally capture the review search date, scope, included designs, included primary studies, review-level meta-analysis methods and estimates, review authors' risk-of-bias assessments, certainty assessments, and the review's funding/conflicts. Do not extract only the review authors' conclusions.

Conversions, imputations, digitization, and author-supplied data must retain method, operator, date, assumptions, and original value. Silent imputation is prohibited.

### Stage G — critical appraisal

- Select a validated risk-of-bias tool by design and outcome where required. Examples include RoB 2 for randomized trials and ROBINS-I for non-randomized intervention studies.
- Complete domain-level judgements independently in duplicate, including quotations or locators supporting each answer and a resolution record.
- Risk of bias must influence synthesis, sensitivity analysis, certainty assessment, and interpretation; a decorative traffic-light plot is insufficient.
- In an umbrella review, assess the included reviews with a pre-specified tool. AMSTAR 2 evaluates methodological confidence; ROBIS assesses risk of bias. JBI's systematic-review checklist is a valid JBI-route alternative when declared in the protocol. Do not combine tools into an invented score.
- Preserve the primary-study risk-of-bias assessments reported by each included review. If reviews used incompatible tools, report that incompatibility rather than pretending the ratings are directly equivalent.

### Stage H — synthesis decision

Construct synthesis groups before running models. Studies may be combined only when their clinical question, design, outcome definition, time point, and estimand are sufficiently compatible. A parsable number is not evidence that pooling is appropriate.

If pooling is inappropriate or impossible, use structured tabulation and an explicit synthesis-without-meta-analysis approach. Do not use vote counting based only on “statistically significant” results.

### Stage I — certainty, interpretation, and reporting

1. Apply GRADE separately to each critical or important outcome. Record explicit reasons for risk-of-bias, inconsistency, indirectness, imprecision, and publication-bias judgements, plus any justified upgrading considerations.
2. Ideally, two people independently make and reconcile GRADE judgements.
3. Produce a Summary of Findings or evidence profile with absolute and relative effects where meaningful.
4. Report protocol deviations, unavailable data, unresolved uncertainty, conflicts, and limitations.
5. Generate PRISMA 2020 or PRIOR checklists from the project data, then perform human item-by-item verification.
6. Conclusions must reflect effect magnitude, uncertainty, heterogeneity, risk of bias, and certainty—not only P values.

## 4. Statistical safeguards for meta-analysis

The analysis engine must enforce the following rules rather than merely suggest them:

The repository's dependency-free generic inverse-variance/Paule–Mandel kernel is only a guarded calculation check. It does not implement this full statistical standard and must retain `calculation_check_not_release_analysis` until the protocol-appropriate primary analysis is independently reproduced and reviewed.

- Lock outcome direction, effect measure, time window, unit, and preferred estimate before seeing pooled results.
- Use appropriate measures for the data: relative measures for binary outcomes when justified, mean difference for a common scale, standardized mean difference only for conceptually equivalent constructs measured on different scales, and hazard ratios for compatible time-to-event estimands. Ratio measures are analysed on the log scale.
- Prevent double-counting from multi-arm trials, crossover periods, cluster trials, repeated time points, multiple measures of the same construct, and multiple reports. Use an a priori selection rule, valid arm combination, multivariate/multilevel method, or robust variance method as appropriate.
- Choose fixed-effect or random-effects models from the scientific estimand and assumptions, never from a heterogeneity-test threshold. If random effects are used, prespecify and justify a defensible estimator such as REML or Paule–Mandel and a confidence-interval method; Cochrane notes that HKSJ can better reflect heterogeneity uncertainty but also has edge cases with very few studies or estimated zero heterogeneity.
- Report study estimates and confidence intervals, pooled estimate, model, number of studies and participants, heterogeneity variance, I-squared with uncertainty when available, and a prediction interval when a random-effects model and a reasonable number of studies make it interpretable. I-squared alone must not decide whether to pool.
- Pre-specify sensitivity analyses for plausible analytical decisions, imputations, influential studies, risk of bias, effect measures, and model assumptions. Keep exploratory analyses clearly labelled.
- Use formal interaction tests for subgroup differences. Do not infer subgroup effects because one subgroup is significant and another is not. Meta-regression should generally not be run with fewer than ten studies, and roughly ten studies per modelled characteristic may still be inadequate when covariates are sparse.
- Handle rare events and double-zero studies with a method justified for the data; do not apply an unexamined continuity correction to every analysis.
- Assess missing results using protocols, registries, unpublished sources, and the ROB-ME framework where applicable. Funnel-plot asymmetry tests are generally reserved for at least ten studies, have low power, and are not diagnostic of publication bias.
- Do not treat non-significance as proof of no effect. Distinguish statistical uncertainty from clinical importance.
- Require statistician review for dependent effects, complex designs, meta-regression, selection models, dose-response, network meta-analysis, Bayesian models, diagnostic accuracy, or individual-participant data.
- Make every analysis reproducible from a clean environment using locked software versions, scripted transformations, deterministic seeds where relevant, tests on known datasets, and checksums for inputs and outputs.

## 5. Umbrella-review overlap and discordance

Primary-study overlap is a structural dependency, not a cosmetic limitation. The repository must:

1. Resolve each cited primary report into a study family, including companion papers and registry records.
2. Build a review-by-primary-study citation matrix for each clinically distinct comparison and outcome.
3. Report the number, size, and analytic weight of overlapping studies. Calculate corrected covered area when appropriate, but treat it as a descriptive measure, not a statistical correction.
4. Pre-specify one defensible overlap strategy:
   - include all eligible reviews but extract each primary-study outcome only once for reanalysis;
   - select one review for an evidence component using rules based on relevance, recency, coverage, and methodological confidence—not favourable results;
   - retain overlapping reviews for a structured comparison of discordant findings without quantitatively combining dependent summaries.
5. Never pool review-level summary effects as though they were independent when underlying studies overlap. If dependence cannot be removed or validly modelled, do not pool.
6. Investigate discordance through differences in PICOTS, search dates and sources, eligibility, outcome definitions, risk-of-bias decisions, extracted data, effect measure, and model—not by choosing the most attractive estimate.
7. Avoid indirect “best treatment” claims across separate reviews. An umbrella review should not simulate a network meta-analysis.
8. If substantial new primary-study searching or extraction is necessary, reconsider the design and route the project to a new or updated systematic review, as advised by Cochrane.

## 6. Minimum data model

The repository should use stable identifiers and append-only decision histories for these entities:

- `project`: review type, status, owners, conflicts, funding, intended outputs;
- `question`: structured PICOTS, decision context, outcome priorities;
- `protocol_version` and `protocol_deviation`: timestamp, content hash, registration, reason, approver;
- `search_source` and `search_run`: database/platform, exact strategy, dates, limits, counts, export checksum;
- `record`, `report`, `study`, and `study_report_link`: identifiers, normalized metadata, match evidence, adjudication status;
- `screening_decision`: stage, reviewer, decision, exclusion code, evidence text, timestamp, conflict/adjudication link;
- `full_text`: retrieval status, lawful source, version, checksum;
- `study_arm`, `population`, `intervention_or_exposure`, and `comparator`;
- `outcome_definition`: domain, instrument, metric, aggregation, direction, time point;
- `result`: raw arm data or effect and precision, analysis population, source locator, transformation/imputation lineage;
- `risk_of_bias_judgement`: tool/version, domain, outcome, answer, rationale, source locator, reviewer, resolution;
- `synthesis_set`: comparison, outcome, time point, estimand, eligibility rule, included-result IDs, dependency handling;
- `analysis_run`: code commit, environment lock, parameters, seed, diagnostics, input/output checksums;
- `grade_judgement`: outcome-level domain judgements, certainty, rationale, reviewer and resolution;
- `review` and `review_result` for umbrella reviews: scope, search date, methods, pooled estimates, AMSTAR 2/ROBIS data;
- `review_study_link`: the citation matrix with comparison/outcome tags and study-family certainty;
- `audit_event`: actor, action, old/new value, timestamp, reason, and approval.

Raw source files, curated data, derived analysis datasets, and rendered outputs must be separate. Derived PRISMA/PRIOR counts, tables, plots, and manuscript statements must remain traceable to entity IDs.

## 7. Mandatory human gates

The workflow may advance only after these approvals:

- **G0 — Design:** clinical expert and methodologist approve question and review type.
- **G1 — Protocol:** investigator, methodologist, statistician, and search specialist approve applicable sections before screening.
- **G2 — Search:** search reviewer approves source coverage and exact final strategies.
- **G3 — Selection:** two human screening decisions are complete; all conflicts and full-text exclusion reasons are resolved.
- **G4 — Data and bias:** duplicate extraction/verification and duplicate risk-of-bias judgements are reconciled; unresolved data are explicitly missing.
- **G5 — Analysis:** statistician approves synthesis groups, estimands, dependencies, code diagnostics, and sensitivity analyses.
- **G6 — Certainty and interpretation:** clinical/methodological reviewers approve GRADE, Summary of Findings, and conclusion strength.
- **G7 — Release:** named human authors verify every citation, table, number, checklist, disclosure, and journal-specific requirement.

AI can draft, normalize, retrieve, prioritize, calculate, compare, and flag. It cannot be the accountable approver at any gate.

## 8. Claims automation must never make

The system must not claim:

- that a search is exhaustive merely because all configured queries ran;
- that an AI-only screening process equals two independent human reviewers;
- that an inferred study value or citation is verified without a source locator;
- that meta-analysis is appropriate because two or more numeric estimates exist;
- that pooled review estimates are independent when primary-study overlap is unknown;
- that a non-significant funnel test proves no publication bias;
- that a PRISMA checklist proves methodological quality;
- that AMSTAR 2, ROBIS, or GRADE judgements are objective machine facts;
- that observational associations establish causality;
- that statistically significant results are clinically important, or non-significant results prove equivalence/no effect;
- that evidence is “high quality” without outcome-level, justified certainty assessment;
- that the manuscript is plagiarism-free, publication-ready, guaranteed to be accepted, or compliant with current journal instructions unless independently checked at release;
- that AI is an author or bears responsibility for clinical, methodological, or publication decisions.

## 9. Release acceptance criteria

A review cannot reach `submission_ready` unless automated validation confirms and humans attest that:

- the protocol is complete, time-stamped, and deviations are reconciled;
- every search is reproducible from exact strings and archived exports;
- record, report, and study counts reconcile;
- two human selection decisions exist and no screening conflicts remain;
- the flow diagram is generated from the event ledger and all totals balance;
- every included result has a source locator and second verification;
- risk-of-bias assessments are complete, supported, and used in interpretation;
- every synthesis passes duplicate-participant, direction, unit, time-point, arm-total, and dependency checks;
- the analysis reruns successfully in a clean locked environment and matches validated reference cases;
- umbrella reviews include a study-overlap matrix and an implemented, protocol-consistent overlap strategy;
- GRADE is complete for every critical outcome and reasons are recorded;
- tables, abstract, main text, supplement, PRISMA/PRIOR checklist, and data files agree;
- all DOI/PMID/registry identifiers and quotations resolve to the cited source;
- human approvers, conflicts, funding, AI assistance, and data/code availability are disclosed.

## 10. Primary guidance

- [PRISMA 2020 statement, checklist, and flow diagrams](https://www.prisma-statement.org/prisma-2020)
- [PRISMA-P 2015](https://www.prisma-statement.org/protocols)
- [Cochrane Handbook for Systematic Reviews of Interventions, version 6.5](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current)
- [Cochrane Chapter 10: meta-analysis](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10)
- [Cochrane Chapter 13: missing evidence](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-13)
- [Cochrane Chapter 14: Summary of Findings and GRADE](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14)
- [Cochrane Chapter V: Overviews of Reviews](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-v)
- [JBI Manual for Evidence Synthesis, Chapter 9: Umbrella Reviews](https://doi.org/10.46658/JBIMES-24-08)
- [JBI critical appraisal tools](https://jbi.global/critical-appraisal-tools)
- [AMSTAR 2 official guidance](https://amstar.ca/Amstar-2.php)
- [ROBIS official tool](https://www.bristol.ac.uk/population-health-sciences/projects/robis/robis-tool/)
- [GRADE Working Group](https://www.gradeworkinggroup.org/) and [official GRADE handbook](https://gradepro.org/handbook/)
- [PRIOR statement for overviews of healthcare-intervention reviews](https://www.bmj.com/content/378/bmj-2022-070849)

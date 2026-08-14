# Statistical analysis router

## Universal analysis contract

For every objective create a row with: population, treatment/exposure condition, outcome variable, time point, intercurrent-event strategy, summary/effect measure, model, uncertainty interval, covariates, missing-data assumption, sensitivity analysis, and multiplicity status.

For confirmatory randomized trials, use the estimand framework and plan sensitivity analyses consistently with ICH E9(R1). Official index: https://www.ich.org/page/efficacy-guidelines (accessed 2026-08-12).

## By data structure

| Structure | Planning questions | Common defensible approaches |
|---|---|---|
| Continuous endpoint | Scale, skew, baseline measure, repeated observations, clinically important difference | Adjusted linear model/ANCOVA; mixed model for repeated measures when its assumptions match the estimand; robust or transformed analysis if justified |
| Binary endpoint | Risk window, competing events, repeated events | Risk difference or ratio with confidence interval; logistic model for odds when appropriate; prespecified marginal estimand if interpretation matters |
| Time-to-event | Time origin, event, censoring, competing risks, proportional hazards | Kaplan–Meier description; Cox model only with diagnostics; restricted mean survival time or competing-risk methods when more suitable |
| Count/recurrent events | Exposure time, overdispersion, within-person dependence | Poisson or negative-binomial model with offset; recurrent-event approach when clinically justified |
| Ordinal score | Category meaning, proportional-odds assumption, repeated measures | Ordinal regression with assumption checks; prespecified alternative if assumptions fail |
| Clustered data | Cluster unit, number and size imbalance, intracluster correlation | Mixed or marginal model; small-cluster correction; inflate sample size for design effect |
| Diagnostic accuracy | Threshold, reference standard, spectrum, paired tests | Sensitivity/specificity with confidence intervals; paired comparison; calibration/discrimination when prediction is the aim |
| Prediction model | Sample size for model parameters, missingness, overfitting, internal/external validation | Penalization/shrinkage where justified; bootstrap or cross-validation; calibration and discrimination with uncertainty |
| Meta-analysis | Clinical compatibility, effect measure, sparse data, heterogeneity | Select model from the question and assumptions; report tau-squared and prediction interval when meaningful; investigate heterogeneity cautiously |

Current Cochrane synthesis guidance: https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10 (accessed 2026-08-12).

## Required decisions

- Primary analysis population and handling of non-adherence/crossover.
- Baseline adjustment and prespecified covariates; no automated stepwise selection for confirmatory inference.
- Missing-data prevention, amount/pattern reporting, primary assumption, imputation model if used, and sensitivity to departures from that assumption.
- Multiplicity strategy across outcomes, time points, arms, subgroups, and interim analyses.
- Model diagnostics and a prespecified response to serious violations.
- Subgroups limited to prespecified effect-modification questions with interaction estimates and uncertainty.
- Data derivations, analysis dataset lock, independent programming checks where feasible, software and package versions, and reproducible code.

## Reporting audit

Report denominators and missingness, descriptive summaries appropriate to distributions, effect sizes with confidence intervals, exact p-values when useful, model assumptions, deviations from the SAP, and clinically interpretable units. Never write “no difference” merely because a p-value exceeds a threshold.

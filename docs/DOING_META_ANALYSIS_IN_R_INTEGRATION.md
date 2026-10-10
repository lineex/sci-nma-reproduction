# Doing Meta-Analysis in R Integration

## Purpose

This project now incorporates the analysis workflow represented by
[Mathias Harrer et al., *Doing Meta-Analysis with R*](https://github.com/MathiasHarrer/Doing-Meta-Analysis-in-R)
and keeps it inside the existing Cochrane/PRISMA stage ledger. The integration
does not copy the book's example data or replace the approved figure/table
contract. It converts the book's reusable analysis decisions into a
project-level form, an R execution scaffold, and hash-bound release evidence.

The integration was checked against the repository's chapter structure on
2026-10-11. The comparison snapshot was commit
`4a1131910e792366e41b9214cabba4c4e1e253b3` (repository history timestamp
2026-07-03); rerun the comparison when the upstream guide changes.

| Guide chapter | Integrated project control |
|---|---|
| Effect sizes | `effect_size_calculation`: outcome type, measure, input columns, transformations, CI/SE conversions, small-sample correction, direction of benefit |
| Pooling effect sizes | `pooling`: common/random-effects decision, `tau^2` estimator, interval method, Q-profile CI, prediction interval, fixed-effect and estimator sensitivity |
| Heterogeneity | `heterogeneity`: `Q`, `I^2`, `H^2`, `tau^2`, uncertainty intervals, prediction interval and interpretation |
| Forest plots | Existing fixed figure contract plus `reporting` and result-artifact paths |
| Subgroup analysis | `moderators.subgroups`: prespecified groups, interaction test, minimum information rule |
| Meta-regression | `moderators.meta_regression`: moderators, coding, interaction terms, study-count rule and ecological interpretation |
| Publication bias | `small_study_effects`: funnel plot, Egger/Begg thresholds, selection/trim-and-fill sensitivity-only status |
| Multilevel/meta-analytic models | `dependency`: multi-arm, repeated outcomes, multiple timepoints, covariance or robust-variance rule |
| Network meta-analysis | `network_meta_analysis`: node definitions, connectivity, transitivity, inconsistency, multi-arm covariance, ranking uncertainty |
| Bayesian meta-analysis | Optional Bayesian route with likelihood/link, priors, chains, warmup, iterations, seed, R-hat, ESS, divergences and posterior predictive checks |
| Power analysis | `precision_and_power`: target estimand, smallest important effect, precision target, number-of-studies scenario and limitations |
| Risk-of-bias plots | Existing design-specific RoB stage and `robvis`-compatible evidence |
| Reporting and reproducibility | `renv.lock`, `sessionInfo()`, code commit, input/intermediate/output hashes and deviations |
| Effect-size calculation appendix | `effect_size_calculation.conversion_rules` and source-level conversion provenance |

## Project defaults

For a new review, the default production route is:

```text
R -> meta/metafor -> netmeta when NMA is planned
```

Python remains orchestration and QA only. The production estimator and interval
method are protocol decisions, not automatic consequences of a high `I^2`.
The default template recommends:

- random-effects pooling;
- REML or Paule-Mandel as an explicitly declared `tau^2` estimator;
- Hartung–Knapp adjustment when appropriate for the number and structure of
  studies;
- Q-profile intervals for `tau^2`/`tau`;
- prediction intervals when a random-effects interpretation is clinically
  meaningful;
- a fixed/common-effect model and an alternative `tau^2` estimator as
  sensitivity analyses;
- subgroup and meta-regression only when prespecified, clinically motivated,
  and supported by enough studies;
- influence, leave-one-out, Baujat, and GOSH diagnostics as diagnostics rather
  than automatic exclusion rules;
- Egger/Begg, trim-and-fill, or selection models only as conditional
  small-study-effect sensitivity analyses, never as proof of publication bias.

## Required execution package

`sci-nma-agent init PROJECT` creates:

```text
analysis/r_meta_analysis_plan.json
code/meta_analysis.R
verification/analysis_manifest.json
```

The plan is the human-readable decision form. The analysis manifest is the
machine-readable release record. The R scaffold is intentionally conservative:
it validates the plan, records the R session, reads the locked input snapshot,
and leaves explicit sections for effect-size calculation, pooling, diagnostics,
moderators, and NMA. It does not silently invent an effect measure or include a
study that fails the approved study/report map.

Before synthesis release, the executor must:

1. replace all placeholders in `analysis/r_meta_analysis_plan.json`;
2. declare the exact primary and sensitivity estimators;
3. record every effect-size conversion and its source coordinate;
4. specify the multi-arm/repeated-outcome dependency rule;
5. run the R script under the project `renv.lock`;
6. save `sessionInfo()` and diagnostics;
7. hash the locked input snapshot, R code, intermediate diagnostics and final
   results;
8. submit those files through the synthesis stage ledger for its configured
   independent reviews.

## What remains separate

The guide is an R methods and implementation resource. It does not replace:

- Cochrane eligibility, search, screening, risk-of-bias, certainty or
  reporting requirements;
- the project's Zotero full-text provenance and fact-status rules;
- the strict serial browser-search queue;
- the fixed figure/table contract;
- the stage ledger's independent review policy.

Conversely, the project adds governance that is outside the guide, including
hash-bound artifacts, resumable retrieval, database-native search evidence,
Zotero reconciliation, and release gates.


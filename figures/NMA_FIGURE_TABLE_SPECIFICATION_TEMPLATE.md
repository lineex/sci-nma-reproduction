# NMA figure and table specification template

Version: 2026-09-21  
Scope: RCT systematic reviews, frequentist network meta-analysis (NMA), and hierarchical Bayesian NMA  
Status: reusable fill-in specification; the values in the examples are not transferable study data

## 1. Reference format audit

The attached articles are format references only. Their numbers, populations, interventions, and conclusions must never be copied into a new review.

| Reference | Model family | Figure structure observed | Table/supplement structure observed | Reusable rule |
|---|---|---|---|---|
| `s13054-026-06185-5_reference.pdf` (Critical Care, doi:10.1186/s13054-026-06185-5) | Frequentist random-effects NMA | Fig 1 PRISMA; Fig 2 RoB 2; Fig 3 network geometry plus aligned relative-effect forest; Fig 4 relative-effect and CINeMA-certainty heatmap | Table 1 trial characteristics; eTables for dose conversion, endpoint extraction, RoB 2, CINeMA, effect modifiers, sensitivity, meta-regression, Baujat, TSA, and reporting bias | Keep network topology and forest rows linked; state when a star network has no closed loops and inconsistency is not estimable |
| `bmj-2026-100561.full (1).pdf` (BMJ 2026;394:e100561, doi:10.1136/bmj-2026-100561) | Hierarchical Bayesian NMA plus multivariable dose-response NMA | Fig 1 multi-source PRISMA; Fig 2 outcome-specific network plots; Fig 3 predicted-effects forest plots; Fig 4 dose-BMD association; Fig 5 modality-specific dose-response curves; Fig 6 fracture forest plots | Tables 1-4 outcome-specific trial characteristics and minimal/optimal doses; 19 supplementary appendix files for protocol, extraction, model specification, diagnostics, and sensitivity | Show the hierarchy, prior specification, dose transformation, posterior diagnostics, and certainty assessment as separate auditable objects |

## 2. Mandatory production rules

1. **Figure 1 is always the project-standard two-column PRISMA 2020 flow.** The left header is `Identification of studies via databases and registers`; the right header is `Identification of studies via other methods`. Use vertical tabs `Identification`, `Screening`, and `Included`.
2. Use actual counts from a structured flow JSON. Never type counts directly into a drawing script and never reuse counts from an example article.
3. Every figure must have a source-data file, a generation script, a caption, and a validation record.
4. Statistical plots must distinguish direct evidence, indirect evidence, and model-derived estimates. Do not draw an edge that is not supported by at least one randomized comparison.
5. Disconnected networks are separate components. They may be shown side by side but must not be ranked against each other or pooled without a prespecified bridge.
6. Bayesian stratification is conditional. It is fitted only when the independent-trial, common-bridge, exchangeable-endpoint, and event-information gates are met. Otherwise the template must show `omitted - identifiability gates not met`.
7. Required master assets: 600-dpi PNG, editable SVG with live text and no embedded raster image, and Type 42 PDF. The same master is used in the manuscript, DOCX, and submission archive.

## 3. Fill-in data contract

Replace every token in `{{DOUBLE_BRACES}}`. A blank or `NR` must mean not reported in the source, not an invented value.

### 3.1 Review-level fields

| Field | Placeholder | Validation |
|---|---|---|
| Review title | `{{TITLE}}` | Same string in manuscript, figure manifest, and archive |
| Search date | `{{SEARCH_DATE}}` | ISO date; database export timestamps retained |
| Databases | `{{DATABASES}}` | Each database has an exact query and export count |
| Registration | `{{REGISTRATION_ID_OR_NONE}}` | Do not claim registration when no verified identifier exists |
| Population | `{{POPULATION}}` | Eligibility text and Table 1 use the same definition |
| Intervention nodes | `{{NODE_SET}}` | Node definitions are fixed before model fitting |
| Primary outcome | `{{PRIMARY_OUTCOME}}` | Outcome definition and time horizon are explicit |
| Effect measure | `{{RR_OR_OR_OR_MD}}` | One scale per outcome; direction is declared |
| Model family | `{{FREQUENTIST_NMA_OR_BAYESIAN_HIERARCHICAL_NMA}}` | Matches the analysis script and Methods |

### 3.2 PRISMA flow fields

| Field | Placeholder | Required equation |
|---|---|---|
| Database records | `{{DB_TOTAL}}` | Sum of source counts equals total |
| Duplicate records | `{{DUPLICATES}}` | `DB_TOTAL - DUPLICATES = {{AFTER_DEDUP}}` |
| Records screened | `{{SCREENED}}` | Equals `AFTER_DEDUP` unless a documented pre-screen filter exists |
| Records excluded | `{{TITLE_ABSTRACT_EXCLUDED}}` | `SCREENED - TITLE_ABSTRACT_EXCLUDED = REPORTS_SOUGHT` |
| Reports sought | `{{REPORTS_SOUGHT}}` | Includes only title/abstract candidates |
| Reports not retrieved | `{{NOT_RETRIEVED}}` | `REPORTS_SOUGHT - NOT_RETRIEVED = REPORTS_ASSESSED` |
| Reports assessed | `{{REPORTS_ASSESSED}}` | Full-text or archived report review denominator |
| Full-text exclusions | `{{FULL_TEXT_EXCLUSION_REASON_COUNTS}}` | Sum of reasons equals `FULL_TEXT_EXCLUDED` |
| Study-level included reports | `{{REPORTS_INCLUDED}}` | `REPORTS_ASSESSED - FULL_TEXT_EXCLUDED = REPORTS_INCLUDED` |
| Other-methods branch | `{{OTHER_METHODS_COUNTS}}` | Kept separate; does not inflate the database denominator |

## 4. Figure specification: frequentist NMA track

| Figure | Fixed layout | Required data fields | Caption skeleton | Gate |
|---|---|---|---|---|
| Figure 1 | Mandatory two-column PRISMA flow | All fields in section 3.2; exclusion reasons | `PRISMA 2020 flow of study selection. {{DB_TOTAL}} records were identified...` | All flow equations pass; right branch is separate |
| Figure 2 | RoB 2 traffic-light matrix plus domain summary | Study ID, five RoB 2 domains, overall judgement | `Risk of bias was assessed with RoB 2 across {{N_STUDIES}} reports...` | Two reviewers or explicitly labelled preliminary audit |
| Figure 3 | Left: network geometry. Right: aligned forest/relative effects. Use one panel per prespecified stratum if needed | Node, arm-level randomized N, direct comparison, number of trials, estimate, CI | `Network geometry and relative effects for {{OUTCOME}}...` | No unsupported edges; star network limitation stated |
| Figure 4 | Heatmap or league-style summary with certainty overlay | Comparison, effect, interval, CINeMA domains, overall certainty | `Summary of relative effects and certainty across {{OUTCOMES}}...` | Certainty is not inferred from P-score or posterior rank |
| Figure 5 (optional) | Comparison-adjusted funnel plot or small-study audit | Direct-comparison study effects, SE, eligibility threshold | `Reporting-bias assessment was restricted to comparisons with at least {{MIN_STUDIES}} informative studies...` | Do not run formal asymmetry tests below the prespecified threshold |

### Figure 3 panel template

```text
Panel A: {{STRATUM_OR_OVERALL}} network geometry
  Nodes: {{NODE_LABELS}}
  Node size: randomized participants, not arm count unless explicitly stated
  Edge width: number of direct trials
  Edge label: k direct trials
  Disconnected component note: {{COMPONENT_NOTE}}

Panel B: {{STRATUM_OR_OVERALL}} relative effects
  Reference: {{REFERENCE_NODE}}
  Scale: {{RR_OR_OR_OR_MD}}
  Interval: 95% CI
  Rows: {{COMPARISON_ROWS_IN_SAME_ORDER_AS_NODE_DATA}}
  Ranking: {{OMITTED_OR_P_SCORE_WITH_LIMITATIONS}}
```

## 5. Figure specification: hierarchical Bayesian NMA track

| Figure | Fixed layout | Required data fields | Caption skeleton | Gate |
|---|---|---|---|---|
| Figure 1 | Same mandatory two-column PRISMA flow | Section 3.2 | Same PRISMA skeleton | Flow conservation |
| Figure 2 | Outcome-specific network plots, one panel per anatomical/outcome site | Node, participant N, direct k, outcome-specific eligibility | `Network plots for {{OUTCOME_SET}}. Circle size... line thickness...` | Outcome-specific network; no cross-outcome edge |
| Figure 3 | Posterior forest plot of relative effects | Posterior median/mean, 95% CrI, contrast, reference, population stratum | `Posterior relative effects from the hierarchical NMA...` | CrI and estimand match model output |
| Figure 4 | Dose-response association or covariate effect plot | Dose metric, transformation, posterior curve, 95% CrI, MCID | `Association between {{DOSE_METRIC}} and {{OUTCOME}}...` | Dose harmonization and MCID are prespecified |
| Figure 5 | Modality/class-specific posterior dose-response curves | Class, dose grid, posterior mean/median, 95% CrI, knots/form | `Predicted dose-response curves across {{N_CLASSES}} modalities...` | R-hat, ESS, trace, posterior predictive checks pass |
| Figure 6 | Secondary binary-outcome posterior forest | Outcome, contrast, posterior estimate, CrI, certainty | `Posterior effects for {{SECONDARY_OUTCOME}}...` | Sparse outcomes and zero-cell handling disclosed |
| Supplementary diagnostic figures | Trace/density, rank probabilities, posterior predictive checks, leave-one-out or sensitivity | Chain, parameter, R-hat, ESS, divergence count, PPC statistic | `Bayesian diagnostics and sensitivity analyses...` | No unresolved divergent transitions or poor mixing |

### Bayesian model card (fill-in)

```text
Likelihood: {{BINOMIAL_LOGIT_OR_NORMAL_OR_OTHER}}
Effect scale: {{LOG_RR_OR_LOG_OR_OR_MD}}
Study baseline: {{STUDY_SPECIFIC_RANDOM_EFFECT_OR_OTHER}}
Treatment hierarchy: {{CLASS_AND_WITHIN_CLASS_STRUCTURE}}
Between-study heterogeneity: {{TAU_PRIOR_AND_PARAMETERIZATION}}
Priors: {{ALL_PRIORS_WITH_SCALE_AND_RATIONALE}}
Chains / iterations / warmup: {{MCMC_SETTINGS}}
R-hat threshold: {{RHAT_THRESHOLD}}
Minimum bulk/tail ESS: {{ESS_THRESHOLD}}
Divergences: {{N_DIVERGENCES}}
Posterior predictive checks: {{PPC_SUMMARY}}
Dose metric: {{DOSE_METRIC_AND_CONVERSION_RULE}}
MCID: {{MCID_DEFINITION_AND_SOURCE}}
Ranking output: {{P_POSTERIOR_OR_RANKING_OMITTED}}
Stratification decision: {{FITTED_OR_OMITTED_AND_REASON}}
```

## 6. Table specification

| Table | Required columns | Rules |
|---|---|---|
| Table 1. Study characteristics | Study ID; citation; country; design; population; severity; intervention; comparator; sample size; age/sex; follow-up; funding | One row per independent randomized study; nested reports linked with `parent_study_id` |
| Table 2. Node and outcome definitions | Node code; intervention definition; dose/intensity; comparator; outcome; horizon; eligibility status; source anchor | Node coding is protocol-defined; actual received treatment is not substituted for randomized assignment |
| Table 3. Relative effects and certainty | Contrast; k; effect; 95% CI or 95% CrI; prediction interval if available; CINeMA domains; overall certainty | Direct, indirect, and network estimates are labelled; disconnected components are not ranked together |
| Table 4. Analysis diagnostics | Model; outcome; k; tau/tau2; heterogeneity; inconsistency status; R-hat; ESS; divergences; sensitivity conclusion | `Not estimable` is a valid result and must not be converted to `No concern` |
| Supplementary S1 | Exact database strategies and dates | Preserve field tags, limits, and export counts |
| Supplementary S2 | Full-text exclusion ledger | One reason per report; duplicate/secondary reports linked to parent study |
| Supplementary S3 | Arm-level extraction | Events, denominators, means/SDs, time horizon, source/page/table anchor |
| Supplementary S4 | RoB 2 | Five domains plus overall judgement and reviewer agreement |
| Supplementary S5 | Model specification | Code version, package versions, priors, data transformations, seed |
| Supplementary S6 | Sensitivity and subgroup analyses | Prespecified/post hoc label, estimand, sample, result, interpretation |
| Supplementary S7 | Certainty assessment | CINeMA domain judgments and downgrade rationale |

## 7. Figure and table manifest (copy for a new project)

```yaml
project_id: "{{PROJECT_ID}}"
title: "{{TITLE}}"
model_track: "{{FREQUENTIST_NMA_OR_BAYESIAN_HIERARCHICAL_NMA}}"
search_date: "{{SEARCH_DATE}}"
primary_outcome: "{{PRIMARY_OUTCOME}}"
effect_measure: "{{EFFECT_MEASURE}}"
figures:
  - id: F1
    type: PRISMA_2020_two_column
    source_json: "{{PRISMA_JSON}}"
    output_stem: Figure1_PRISMA_flow
    required: true
  - id: F2
    type: "{{ROB2_OR_NETWORK_GEOMETRY}}"
    source_data: "{{F2_DATA}}"
    required: true
  - id: F3
    type: "{{NETWORK_PLUS_FOREST_OR_POSTERIOR_FOREST}}"
    source_data: "{{F3_DATA}}"
    required: true
  - id: F4
    type: "{{CINEMA_HEATMAP_OR_DOSE_RESPONSE}}"
    source_data: "{{F4_DATA}}"
    required: true
tables:
  - id: T1
    type: study_characteristics
    source_data: "{{T1_DATA}}"
  - id: T2
    type: node_and_outcome_definitions
    source_data: "{{T2_DATA}}"
  - id: T3
    type: relative_effects_and_certainty
    source_data: "{{T3_DATA}}"
  - id: S1
    type: exact_search_strategies
    source_data: "{{SEARCH_EXPORTS}}"
validation:
  flow_conservation: true
  svg_live_text: true
  svg_embedded_images: false
  pdf_type42: true
  png_dpi: 600
  word_table_header_repeat: true
  word_rows_cant_split: true
  disconnected_components_not_ranked: true
  bayesian_gates_required: true
```

## 8. Automated acceptance checks

| Check | Pass condition |
|---|---|
| Search conservation | Sum of database counts equals `DB_TOTAL` |
| Deduplication | `DB_TOTAL - DUPLICATES = AFTER_DEDUP` |
| Screening | `SCREENED - TITLE_ABSTRACT_EXCLUDED = REPORTS_SOUGHT` |
| Retrieval | `REPORTS_SOUGHT - NOT_RETRIEVED = REPORTS_ASSESSED` |
| Full-text closure | `REPORTS_ASSESSED - sum(exclusion reasons) = REPORTS_INCLUDED` |
| Other-method separation | Other-method counts do not enter the database denominator unless a new bibliographic record is added |
| Network topology | Every edge maps to a direct randomized comparison; no invented triangle |
| Estimand consistency | Outcome, horizon, population, and effect scale are identical within each pooled model |
| Bayesian diagnostics | R-hat, ESS, divergences, and posterior predictive checks meet the model card thresholds |
| SVG editability | SVG contains live `<text>` and no `<image>` element |
| PDF | Type 42 font embedding is verified |
| PNG | Pixel dimensions correspond to 600 dpi at the declared physical size |
| Manuscript synchronization | Caption, figure file, DOCX embedded image, and archive checksum refer to the same master |

## 9. Current project mapping example

The current trauma project fills Figure 1 with `data/figure1_prisma_template_2026-09-21.json`: database total 6,989, duplicates 1,824, after deduplication 5,165, screened 5,165, title/abstract exclusions 4,535, reports sought 630, not retrieved 5, assessed 625, full-text/second-pass exclusions 608, and 17 reports retained for endpoint/network adjudication. The other-methods branch is zero and audit-only. These values are an example of the fill-in process, not a reusable default.

To reuse the fixed Figure 1 layout for another review, copy the PRISMA JSON, replace the values, validate the flow equations, and run:

```powershell
python -X utf8 .\redraw_latest_figures.py --figure1-data .\data\figure1_prisma_<DATE>.json
```

The drawing coordinates, typography, headers, stage tabs, arrows, and output formats remain unchanged.

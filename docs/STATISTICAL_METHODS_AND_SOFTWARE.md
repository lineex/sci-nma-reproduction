# Statistical Methods and Software Contract

This contract applies to a new systematic review, pairwise meta-analysis, or
network meta-analysis. It is a project implementation contract informed by
the current Cochrane Handbook; it is not a claim that Cochrane mandates a
particular package. The approved figure and table format remains unchanged.

## 0. New-project software default

For a **new** evidence-synthesis project, the project default primary
production engine is **R**. At protocol freeze, replace the default with the
exact installed R version, package versions, runtime lock (normally
`renv.lock`), and analysis script paths. The default is a project choice that
keeps the pairwise, frequentist NMA, Bayesian NMA, and diagnostic tooling in a
single reproducible ecosystem; it is not a Cochrane requirement.

An investigator may select Stata or another validated production engine when
the review methods or local validation require it. That selection must be
explicit in the protocol and analysis manifest, include the exact versions and
runtime lock, and record the rationale as a protocol decision. Python remains
the orchestration/QA layer and is not a primary production synthesis engine.

This default applies only to new reviews. A reproduction or calibration task
must preserve the published study's software and settings when fidelity to the
source analysis is the objective; R is then a verification or reimplementation
choice only when declared in that task's protocol.

## 1. Analysis decisions before synthesis

The protocol must define the estimand before any model is run. Record the
population, intervention/comparator contrast, outcome definition, timepoint,
analysis population, effect scale, direction of benefit, and handling of
multiple reports. Do not pool estimates merely because their column names are
similar.

| Data type | Prespecified effect options | Required decisions |
|---|---|---|
| Binary outcomes | RR, OR, or RD | Choose one scale per outcome/timepoint; state whether the analysis is on the log scale; define zero-event and double-zero rules. |
| Continuous outcomes | MD or SMD | Define the direction of scales, change versus final values, SD conversions, and the common SD convention for SMD. |
| Time-to-event outcomes | log HR | State the preferred source (reported HR, reconstructed HR, or other) and the censoring/estimand assumptions. |
| Proportions or rates | A justified transformation or a generalized model | Define the denominator, boundary handling, exact/approximate model, and back-transformation. |
| Diagnostic/prognostic outcomes | Design-specific bivariate/HSROC or other prespecified model | Do not use a generic binary-outcome model without checking the design and threshold structure. |
| Clustered, multi-arm, repeated, or multiple-outcome data | Covariance-aware, multivariate, robust-variance, or a single-estimate rule | Record the intracluster/correlation assumption, arm splitting/combining rule, and sensitivity analysis. |

The protocol must identify conversions from confidence intervals or standard
errors, assumptions for missing dispersion, and whether an estimate is
adjusted or unadjusted. A report that does not provide a requested quantity
is not silently converted into a zero or a study exclusion.

## 2. Pairwise meta-analysis

1. Apply the clinical and methodological compatibility gate before pooling.
2. Name the primary model and estimator in advance. A typical production
   choice is a random-effects model with REML or Paule-Mandel and a stated
   small-sample interval method (for example Hartung-Knapp where appropriate).
   DerSimonian-Laird may be a sensitivity estimator, not an unlabelled default.
3. Report the pooled estimate, 95% interval, number of studies, `tau^2`,
   `I^2`, Cochran's `Q` with its limitations, and a prediction interval when
   a random-effects interpretation is clinically meaningful.
4. Prespecify fixed-effect or alternative-estimator sensitivity analyses,
   zero-event handling, high-risk-of-bias exclusions, leave-one-out or
   influence checks, and the minimum number of studies for small-study tests.
5. Treat subgroup and meta-regression coefficients as comparisons of
   prespecified interactions. State the residual heterogeneity, the number of
   studies per moderator, and the ecological interpretation limitation.

## 3. Network meta-analysis

An NMA is released only when the network is connected for the planned
comparison. Disconnected components are reported separately and are never
ranked together. The protocol must state:

- treatment-node definitions and permissible combination rules;
- plausible effect modifiers and the transitivity assessment;
- a global contrast-based model, common or design-specific heterogeneity, and
  multi-arm covariance handling;
- global and local inconsistency checks (for example design-by-treatment and
  node-splitting approaches) and the action when assumptions fail;
- ranking probabilities or P-scores/SUCRA with uncertainty, not a ranking from
  point estimates alone;
- the certainty framework and how direct, indirect, and network estimates are
  reconciled.

For Bayesian NMA also record the likelihood/link, reference treatment, prior
distributions, chains, warmup, iterations, seed, convergence diagnostics
(`R-hat`, effective sample sizes, divergences), posterior predictive checks,
and rank/credible-interval summaries.

## 4. Small-study effects and missing information

Funnel plots, Egger or Begg tests, and selection/trim-and-fill analyses are
secondary diagnostics, not proof of publication bias. Use them only when the
outcome and study count provide enough information; otherwise record “not
assessed” with the reason. Separate unavailable full text, unreported facts,
and statistically missing values in the data and fact-status manifests.

## 5. Software roles

| Role | Project default / approved software | Contract |
|---|---|---|
| Pairwise synthesis | **R 4.x with `meta` and/or `metafor` (default for new projects)** | Primary production engine; record estimator, interval method, transformations, and package versions. |
| Frequentist NMA | **R `netmeta` (default for new projects)** | Use a connected contrast-based model with explicit inconsistency and multi-arm checks. |
| Bayesian NMA | R `gemtc`/`BUGSnet` with JAGS, or Stan via `rstan`/`brms` | Record model code, priors, sampler settings, seed, and convergence diagnostics. |
| Dependent effects/meta-regression | R `clubSandwich`, `metafor`, or a prespecified multivariate model | State the covariance or robust-variance assumptions. |
| Risk of bias | RoB 2/ROBINS-I workflows; `robvis` for visualization | Preserve domain-level judgements and evidence; do not substitute a quality total score. |
| Certainty | GRADEpro GDT for pairwise Summary of Findings; CINeMA for NMA certainty | Export the profile and reconcile every rating with the validated synthesis. |
| Independent cross-check | Stata 18 `meta`, `network`, `mvmeta`, `metareg`, or `metabias`; RevMan Web for standard pairwise review | Optional verification route, not a substitute for protocol decisions or NMA diagnostics. |
| Orchestration and QA | Python `numpy`, `scipy`, `pandas`, project validators, and plotting code | Input validation, provenance, hashes, reproducibility checks, and figure/table generation. The bundled simplified engines are QA/teaching aids and are not the authority for production NMA or GRADE conclusions. |

Software choice does not replace a methods decision. The report must state the
actual software and package versions used, including failed or exploratory
runs that influenced a decision.

The protocol preflight rejects Python as the primary production synthesis
engine. New projects start with R unless an explicit protocol decision selects
Stata or another validated engine. Python remains available for orchestration,
input validation, QA, and figure/table generation; a formal release must name
a locked production engine with explicit package versions and a project-local
runtime lock.

## 6. `analysis_manifest.json`

The synthesis gate requires a machine-readable analysis manifest bound to the
approved protocol and locked input snapshot. Start from the repository template
`data/templates/analysis_manifest_template.json` (the packaged runtime copy is
`sci_nma_agent/templates/analysis_manifest_template.json`) and record:

- estimand/effect measure by outcome and timepoint;
- primary and sensitivity estimators, interval method, transformations,
  zero-event policy, multi-arm/dependency rule, and missing-data rule;
- NMA connectivity, transitivity, inconsistency, heterogeneity, and ranking
  decisions when applicable;
- primary/verification/certainty software, package versions, runtime locks,
  random seeds, and code commit;
- protocol, input, intermediate, diagnostic, and output SHA-256 hashes. Store
  file-backed intermediate or diagnostic records in `intermediate_outputs` so
  the stage ledger can re-check their bytes;
- model warnings, convergence results, deviations, and independent reviewer
  sign-off.

For a formal release, `software.runtime_lock_paths` must contain at least one
project-relative lock file (for example `renv.lock`) and that file must be
present in the submitted synthesis artifacts. Package entries are recorded
with explicit versions (for example `meta 8.1-0`, not only `meta`). When NMA
is planned, the manifest values for node definitions, connectivity,
transitivity, prespecified effect modifiers, inconsistency, model
specification, multi-arm handling, ranking uncertainty, certainty, and the
assumption-failure plan must match the approved protocol values exactly; a
merely non-empty description is insufficient.

### External production result hand-off

The bundled Python calculators remain exploratory QA. To render formal figures
or office documents, provide a project-local JSON file from the locked R/Stata
or otherwise validated production engine:

```json
{
  "pairwise": {
    "planned": true,
    "engine_role": "r_production",
    "production_use": "release",
    "pooled_estimate": 0.82,
    "ci_lower": 0.70,
    "ci_upper": 0.96,
    "i2_percent": 42.1,
    "tau2": 0.03,
    "p_value": 0.01,
    "studies": [
      {"study_id": "STUDY_ID", "effect_size": 0.82, "ci_lower": 0.60,
       "ci_upper": 1.10, "weight_percent": 10.0}
    ]
  },
  "network": {
    "planned": true,
    "engine_role": "r_production",
    "production_use": "release",
    "treatments": [
      {"id": "TREATMENT", "sample_size": 120, "color": "#2563EB"},
      {"id": "COMPARATOR", "sample_size": 130, "color": "#059669"}
    ],
    "rankings": [{"treatment": "TREATMENT", "rank": 1,
                  "sucra_percent": 80.0, "relative_or_vs_ref": 0.82,
                  "ci_lower": 0.60, "ci_upper": 1.10}],
    "comparisons": [{"t1": "TREATMENT", "t2": "COMPARATOR", "trial_count": 3,
                      "estimate": 0.82, "ci_lower": 0.60, "ci_upper": 1.10}]
  }
}
```

For a pairwise-only protocol, the `network` object may be omitted. A planned
NMA must include non-empty ranking, treatment-node, and comparison records;
release metadata alone is not a synthesis result. Each treatment ID must be
unique and have a positive finite `sample_size` plus a non-empty display
`color`. Each ranking must cover exactly one declared treatment. Each
comparison must use two distinct declared treatment IDs, have a positive
integer `trial_count`, and appear only once as an undirected edge. The
comparison graph must be connected so that disconnected treatments are never
rendered or ranked together.

Stage 4 uses the declared `treatments` and `comparisons` for every production
Figure 3 render; it never substitutes the bundled QA geometry fixture. If NMA
is explicitly not planned, Figure 3 keeps its fixed file contract with an
explicit `Not estimable` rendering and no synthetic nodes or edges. Missing or
invalid geometry metadata stops the production release before any formal
figure is emitted.

When pairwise synthesis is explicitly not planned (for example, an NMA-only
protocol), the fixed forest-figure file contract is retained with an explicit
`Not estimable` rendering. The renderer must not create synthetic pairwise
study rows, pooled effects, confidence intervals, or summary diamonds.

The file must be listed in `outputs` or `intermediate_outputs` in the
analysis manifest, and its SHA-256 is rechecked by the stage ledger. Use it
with `--production --production-results results/locked_production_results.json`
on `run-step --stage 4`, `run-step --stage 5`, or `run-all`. QA- or Python-marked
results are rejected for formal release.

The analysis manifest is an audit artifact. The stage ledger's two independent
review records are the authoritative reviewer sign-off; the optional
`review_signoff` object in the manifest is a convenience summary. The manifest
does not turn an inaccessible report into evidence and does not authorize a
downstream stage until the stage ledger and two independent reviews approve the
synthesis.

## 7. Synthesis release checklist

- [ ] Effect scale and estimand match the protocol for every pooled outcome.
- [ ] Transformations, zero-event handling, multi-arm/dependency rules, and
      missing-data decisions are explicit.
- [ ] Model, estimator, interval method, `tau^2`, `I^2`, `Q`, prediction
      interval, and sensitivity analyses are recorded where applicable.
- [ ] NMA connectivity, transitivity, inconsistency, multi-arm covariance,
      and ranking uncertainty are documented, or NMA is explicitly not planned.
- [ ] Software, package/runtime versions, seed, code commit, input hash, and
      output hashes are present in `analysis_manifest.json`.
- [ ] Results, figures, tables, certainty ratings, and the analysis manifest
      have passed two independent reviews before the next stage is released.

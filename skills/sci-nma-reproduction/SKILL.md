---
name: sci-nma-reproduction
description: Routes new clinical systematic reviews and meta-analyses through a protocol-first Cochrane-based workflow with Zotero full-text provenance. Loads the separate publication-reproduction and calibration module only when the user explicitly asks to reproduce or calibrate an already-published study.
---

# Evidence Synthesis Workflow Router

First classify the requested work, then load only its workflow module:

- **New review question, systematic review, pairwise meta-analysis, or network
  meta-analysis:** use [the new-review module](modules/new-systematic-review.md).
- **Reproduce, replicate, or calibrate a named published study or its analysis:**
  use [the publication-reproduction module](modules/publication-reproduction.md).
- A new review is not a reproduction task. Do not load reproduction-only
  instructions, calibration fixtures, or example-study assumptions for it.

For new reviews, follow the project's approved protocol and the stage ledger;
use stage-specific review counts. The search stage has one executor and one
independent reviewer. Other release stages retain two independent approvals by
default. Screening, extraction, and risk-of-bias decisions must retain their
own paired independent decisions. An agent's recommendation is not a stage
approval; the orchestrator records the decision after reviewing the configured
reports.

Search uses an executor and one independent reviewer; it does not use two
independent reviewers. After each database is complete, report its results and
wait for the user's confirmation before starting the next database.

Within a database, use the persisted `line_checkpoints` as the authoritative
to-do list: execute only the first unchecked native query line, record its
result count and history/query locator with `search-queue record-line`, then
verify the saved checkpoint before executing the next line. On interruption,
run `search-queue checklist` and continue at the first unchecked line; never
rely on conversation memory or silently rerun completed lines. Component lines
record counts only; the final combination line supplies the detailed export.

Treat the review as a resumable, hierarchical work plan—not a single-turn
conversation. `sci-nma-agent init` creates the project work-plan scaffold and
append-only work log defined in
[`CONTINUOUS_WORKPLAN_AND_RESUME.md`](../../docs/CONTINUOUS_WORKPLAN_AND_RESUME.md).
After protocol approval, bind its hash and add stable child tasks from the
approved stage sequence and database queue; never reset an existing plan/log.
Represent each approved stage as a parent task and each database, report
batch, analysis decision, and reporting artifact as a stable child task with
dependencies, acceptance criteria, declared inputs/outputs, owner, and
checkpoint. Record starts, pauses, resumes, completed operations, reviews,
blockers, and reruns as durable events tied to artifact paths and SHA-256
hashes. The stage ledger remains the release authority; the work plan records
continuity.

At every activation, identify the active project and reload its approved
protocol, the exact figure/table contract named by that protocol, the work
plan, stage ledger, and search checklist before continuing. Verify the
contract and referenced artifact hashes; if the approved contract hash differs,
stop output work and use the protocol amendment/review gate. Recover stale
in-progress work as interrupted, load the latest checkpoint, then continue the
first ready leaf at its next idempotent boundary. Never rely on chat history as
the only record, repeat a completed leaf, or create a second queue to bypass an
unresolved task. Human actions pause and later resume the same task.

Before generating a figure or table, reload the approved protocol and the
single project contract at `data/nma_figure_table_spec_template.json`. Follow
[`OUTPUT_CONTRACT_AND_STEPWISE_SEARCH.md`](../../docs/OUTPUT_CONTRACT_AND_STEPWISE_SEARCH.md):
complete its project-specific fields, freeze its SHA-256 in the protocol, and
keep every declared item and layout unchanged.

For every browser-facing database skill (search, session checks, paging,
parsing, details, citation export, or full-text handoff), apply the project
[`BROWSER_ROUTE_POLICY.md`](../../docs/BROWSER_ROUTE_POLICY.md): use the Codex
built-in CDP browser first. Chrome DevTools is only a documented fallback for
a specific unavailable capability, and the reason must be recorded. This
project policy overrides older route preferences in helper skills.

Use the current Cochrane Handbook chapters mapped in
[`docs/COCHRANE_AGENT_REQUIREMENTS.md`](../../docs/COCHRANE_AGENT_REQUIREMENTS.md).
That document distinguishes Handbook methods from project choices such as
Zotero, AI role cards, and the two-reviewer ledger. Preserve the approved
project figure/table contract; change it only when the project owner asks.

Before synthesis, apply [`docs/STATISTICAL_METHODS_AND_SOFTWARE.md`](../../docs/STATISTICAL_METHODS_AND_SOFTWARE.md)
and [`docs/DOING_META_ANALYSIS_IN_R_INTEGRATION.md`](../../docs/DOING_META_ANALYSIS_IN_R_INTEGRATION.md).
Complete `analysis/r_meta_analysis_plan.json`, run the generated
`code/meta_analysis.R`, and create the required `analysis_manifest.json`. The document defines the
effect-measure, estimator, NMA, software-version, and hash requirements; it
does not load reproduction-only calibration instructions. The bundled Python
calculators are QA/teaching aids only; formal pairwise or NMA results must be
generated by the protocol-declared locked R/Stata/validated engine and released
through the stage ledger.

For a new review, use **R as the default primary production engine** and
freeze its exact version, package versions, `renv.lock`, and scripts in the
protocol before synthesis. Stata or another validated engine requires an
explicit protocol rationale and the same runtime/hash controls. This is a
project default, not a software requirement imposed by Cochrane. Reproduction
or calibration work follows the published analysis software for fidelity and
does not inherit the new-review default automatically.

Use the required runtime defaults in
[`docs/ENVIRONMENT_AND_APPLICATION_DEFAULTS.md`](../../docs/ENVIRONMENT_AND_APPLICATION_DEFAULTS.md):
search through the built-in CDP browser first and Chrome DevTools second;
retrieve full text through Zotero MCP first and the read-only local Zotero
bridge second. Record the selected route and fallback reason in the stage
artifacts.

For the Chrome DevTools fallback, use only a loopback CDP endpoint
(`127.0.0.1`, `localhost`, or `::1`) and a dedicated non-default Chrome
`--user-data-dir`. Never attach the debugging port to the user's everyday
profile or a network/public address. The session preflight must validate
`/json/version` and the advertised loopback WebSocket before any search
automation; classify an unsafe or incomplete endpoint as a failed fallback,
not as an empty search. The fallback adds
`--disable-blink-features=AutomationControlled` in both headed and headless
launch modes. It does not inject JavaScript property overrides. A site
verification page remains a user-action checkpoint in the same authenticated
profile, followed by recovery and a small probe search before the full rerun.

After title/abstract screening, run the post-screen full-text acquisition route:
resolve missing DOI values with optional Metapub (PMID, then exact title/year),
call the configured ScanSci PDF connector for a DOI, deduplicate by DOI then
PDF SHA-256, and pause for a user-completed institutional CARSI/WebVPN login
when a paywall is encountered. Explicitly authorize Zotero MCP identifier/PDF
writes only when the live schema advertises them; then read the exact Zotero
item back and compare DOI, PMID, title, and year. Write every mismatch to the
verification discrepancy table and keep downstream review blocked until it is
resolved. See [`docs/FULLTEXT_ACQUISITION.md`](../../docs/FULLTEXT_ACQUISITION.md).

For search formulation, use a sensitivity-first PICOS strategy: require P
and I for the default intervention question, omit C and O by default, and
enable either optional block only with a protocol rationale. This is not an
absolute rule for diagnostic, prognostic, or other non-intervention questions;
the protocol may define a different concept structure. Language, date, human,
publication-status, document-type, and study-design restrictions are also
opt-in and require database-specific rationales. Generate a separate native
line-by-line strategy for each database. The rendered supplement shows those
native lines and interface set references; the collapsed generated execution
query stays in a separate hash-bound artifact. Before release, replace or
annotate planned generated lines with the exact-as-run history/export record,
including set numbers, totals, date/timezone, and peer review.

When Embase.com is in the approved database queue, also load
[`EMBASE_SEARCH_AND_EXPORT.md`](../../docs/EMBASE_SEARCH_AND_EXPORT.md) for
database-specific history and export checkpoints.

Use a **form-first, journal-shaped package** for every new review:

- Complete the line-by-line search supplement at
  `reporting/supplementary/search_strategy_supplement.csv`. Each database line
  records the exact statement, field tags, controlled vocabulary, free-text
  terms, limits, date/timezone, hit count, export hash, history/query locator,
  peer review, and rerun instructions.
- Complete the paired screening, Zotero retrieval, extraction, risk-of-bias,
  synthesis, and certainty supplements from the initialized templates. Do not
  reconstruct these details from narrative prose after the fact.
- Complete `analysis/r_meta_analysis_plan.json` before production R code. It
  captures effect-size conversions, pooling, heterogeneity, diagnostics,
  moderators, dependency handling, small-study effects, and NMA decisions.
- Generate the manuscript, cover letter, reproducibility README, figures,
  tables, and supplementary archive from approved, hash-bound artifacts.
  `reporting/supplementary_materials_manifest.json` and
  `reporting/submission_package_checklist.csv` are the release inventory.
- The reporting stage requires every required artifact, project-relative path,
  source locator, SHA-256 hash, and two independent reporting approvals before
  a submission package is released.
- The search stage requires only one independent review after execution; this
  does not reduce the paired decisions required for screening, extraction, or
  risk-of-bias assessment.

Do not load all role cards up front. For each new-review stage, assemble only
the generic executor or reviewer card, the relevant stage-method row, the
approved protocol, and that stage's declared inputs.

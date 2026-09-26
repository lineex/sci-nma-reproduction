# Cochrane and Tutorial Requirements Mapped to the Agent Workflow

## Evidence Base

| Source | Relevant location | Requirements carried into this project |
|---|---|---|
| Cochrane Handbook current online edition | Ch 1 §§1.4-1.6; Ch 2 §§2.1-2.5; Ch 3 §3.2 | Prespecified scope, explicit question/criteria, protocol and quality assurance |
| Cochrane Handbook | Ch 4 §§4.3-4.6, especially §§4.6.3-4.6.4 | Reproducible searching, documented selection, full-text retrieval, independent full-text eligibility assessment and transparent reasons |
| Cochrane Handbook | Ch 5 §§5.2-5.7 | Structured extraction of study/outcome data, multi-report linkage, source and decision provenance |
| Cochrane Handbook | Ch 7-8; Ch 25 when non-randomized intervention studies are eligible | Consider bias/conflicts across studies and assess risk of bias with design-appropriate methods; do not use a generic quality score |
| Cochrane Handbook | Ch 9 | Summarize study characteristics and prepare for synthesis; this is not the risk-of-bias chapter |
| Cochrane Handbook | Ch 10 and Ch 11 | Compatibility before synthesis, analysis choices and NMA assumptions |
| Cochrane Handbook | Ch 14 | Outcome-level evidence certainty and Summary of Findings |
| Zhang et al. (2022), user-attached JSLHR tutorial | pp. 3-7 | Prespecified question, protocol/registration, eligibility, multiple databases and independent screening |
| Zhang et al. (2022) | pp. 7-9 | Pilotable coding checklist, two independent coders, effect-size data, dependent effects/multi-arm issues and missing-data handling |
| Zhang et al. (2022) | pp. 9-15 | Heterogeneity, influence/outlier checks, publication-bias caution, sensitivity analysis, theoretically selected moderators, transparent reporting |
| Zhang et al. (2022) | Appendix A, pp. 20-21 | PRISMA reporting items and checklist |

## Source Boundary

The attached tutorial is a practical methods article, not an instruction to copy
its example topic, R package, effect thresholds, or conclusions into a medical
review. Its specific dataset and example decisions are illustrative. The
project protocol must choose outcome measures, models, thresholds, and tools
for the new clinical question and justify them.

The Cochrane Handbook does not require Zotero or AI agents. Zotero is the
project's user-selected retrieval interface; agent roles and two-agent gate
reviews are governance mechanisms chosen to implement independent work and
quality assurance.

The Handbook informs the synthesis methods but does not prescribe this
project's statistical software. For new reviews, this project's default
primary production engine is R; selecting Stata or another validated engine
is a project-level protocol decision that must be justified and version-locked.
For publication reproduction, follow the source study's software and settings
when fidelity to its analysis is the objective.

The Handbook primarily addresses systematic reviews of intervention effects.
For diagnostic, prognostic, prevalence, or other review questions, the protocol
must identify the applicable method guidance rather than treating this mapping
as sufficient. The current online Handbook is updated by chapter; record the
chapter version/update date and access date in each project's methods-source
log. Declare the selected `chapter-NN` IDs and scope rationale in
`review_protocol.json`; start from `data/templates/methods_source_log_template.json`
with one matching Handbook chapter per record and the attached tutorial as a
separate source. The Protocol gate requires exact chapter-set and URL matching.
This mapping was checked on 2026-09-25.

The skill entrypoint is a compact task router. It loads this new-review workflow
only for a new evidence-synthesis question; publication reproduction and its
calibration fixtures live in a separate optional module and are not used for a
new review.

## Stage Release Matrix

| Stage | Execution agent(s) | Required independent assessment |
|---|---|---|
| Protocol | Clinical methodologist | Content expert + methods reviewer |
| Search | Information specialist | Search peer reviewer + methodologist |
| Deduplication | Evidence data steward | Provenance and study-linkage auditor |
| Title/abstract screening | Two independent screeners (project policy; Cochrane describes duplicate initial screening as ideal, not a minimum) | Adjudicator + screening auditor |
| Full-text retrieval | Zotero retrieval operator | Retrieval auditor + unresolved-item audit |
| Full-text screening | Two independent reviewers | Adjudicator + eligibility auditor |
| Data extraction | Two independent extractors or one plus independent verification | Data/provenance auditor |
| Risk of bias | Design-specific reviewers | Independent domain-judgement auditor |
| Synthesis | Statistician | Independent statistician + clinical compatibility reviewer |
| Certainty | GRADE/CINeMA assessors | Independent assessor + SoF consistency auditor |
| Reporting | Review writer | PRISMA and reproducibility reviewers |

## Protocol Preflight

The project protocol template is not itself an approved protocol. Stage 0
requires a completed project-specific `review_protocol.json` and a
`methods_source_log.json`, both independently reviewed. The protocol declares
the exact Handbook chapter set used. The local validator checks chapter-level
edition/update/access fields, set completeness, and URL-to-chapter alignment and checks
the question, eligibility, operational outcome and
timepoint-selection rules, search sources and limits, paired reviewer plans,
Zotero collection and unavailable-report policy, pilot/data-verification plan,
design-specific risk-of-bias tools, synthesis estimands and assumptions,
certainty framework, registration status, and project accountability. These
are project gate criteria used to operationalize the cited Handbook chapters.

The retrieval stage must submit `full_text_retrieval_manifest.json` bound to
the approved title/abstract decisions; deduplication must submit a machine-
readable `study_report_map.json`; full-text screening accounts for each
retrieval row; extraction must submit `fact_status_manifest.json` bound by
SHA-256 to the approved map, retrieval, and full-text eligibility results. Report-level
`not_reported_in_reviewed_report` requires reviewed section/page coverage.
Study-level `not_reported_after_all_linked_sources_review` or
`cannot_tell_after_full_text_review` requires every report ID in the approved map
to have a confirmed retrieval, completed review/adjudication, and explicit
coverage evidence. These status controls are local implementation rules based
on the Handbook's distinction between unavailable/incomplete information and
data that are not reported; they do not establish that an outcome was not
measured or that its value was zero.

When network meta-analysis is planned, the protocol must additionally specify
intervention node definitions, clinically plausible effect modifiers and the
transitivity assessment, network connectivity/geometry, incoherence checks,
model and multi-arm handling, ranking interpretation, certainty framework,
and what to do if assumptions fail. If NMA is not planned, record the rationale.
These are methodological decisions informed by Cochrane Ch 11; the software
validator and agent-release rules are local implementation.

# EBM Systematic Review and Meta-analysis Workflow

This workflow is for conducting a new evidence synthesis. It complements the
repository's paper-reproduction workflow; it does not replace it. The project
owner may keep existing figure and table contracts fixed.

The skill entrypoint routes to this workflow only for a new review question.
Published-study reproduction and calibration remain an independent optional
module and are loaded only when explicitly requested for a reproduction task.

## Method Sources

- Cochrane Handbook for Systematic Reviews of Interventions, current online
  edition: [Handbook landing page](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current).
- Core chapters used here: [Ch 1: Introduction](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-01),
  [Ch 2: Determining the scope](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-02),
  [Ch 3: Defining the criteria](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-03),
  [Ch 4: Searching for and selecting studies](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04),
  [Ch 5: Collecting data](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05),
  [Ch 6: Effect measures](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-06),
  [Ch 7: Considering bias](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-07),
  [Ch 8: Risk of bias in randomized trials](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-08),
  [Ch 9: Summarizing study characteristics and preparing for synthesis](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-09),
  [Ch 10: Analysing data and undertaking meta-analyses](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10),
  [Ch 11: Network meta-analysis](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-11),
  [Ch 25: Risk of bias in non-randomized studies of interventions](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-25),
  [Ch 14: Summary of findings and GRADE](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14).
- Zhang X, Cheng B, Zhang Y. *A Hands-On Tutorial for Systematic Review and
  Meta-Analysis With Example Data Set and Codes*. JSLHR. 2022; doi:
  [10.1044/2022_JSLHR-21-00607](https://doi.org/10.1044/2022_JSLHR-21-00607).
  The user's 22-page PDF is the tutorial copy used for the complementary
  practical sequence and reproducibility/reporting checklist.

The Handbook and tutorial guide evidence-synthesis methods. Zotero collections,
agent roles, local manifests, and the approval ledger are implementation
choices; they are not prescribed by Cochrane.

## Gated Sequence

| Gate | Work product | Method checkpoints | Release rule |
|---|---|---|---|
| 0. Protocol | Question, scope, eligibility, outcomes, methods, registration/amendment log, declared Handbook chapter set, and chapter-level methods source log | Cochrane Ch 1-3; tutorial pp. 3-5 | Operational definitions and decisions are prespecified; source-log chapter IDs exactly match the declared set and URLs; chapter update/access dates and tutorial provenance are recorded; two independent agent reviews approve |
| 1. Search | Database-specific strategies, dates, result counts, citation searching, search peer review | Cochrane Ch 4; tutorial pp. 5-7 | Search can be rerun; restrictions are justified; all batches are accounted for |
| 2. Corpus | Imported reports, identifiers, duplicate links, study-report map | Cochrane Ch 4; PRISMA flow | Source records remain intact; duplicate reports are linked at study level |
| 3. Title/abstract | Two independent reviewer decisions and disagreement log | Cochrane Ch 4; tutorial pp. 6-7 | Paired screening is the project's stricter policy (Cochrane describes duplicate initial screening as ideal, not a minimum); decisions follow protocol; unresolved conflicts go to adjudication |
| 4. Full-text retrieval | Zotero collection, attachments, retrieval state, hash manifest, manual-acquisition queue | Cochrane Ch 4.6.3 steps 3-6; Ch 4.6.4 for eligibility assessment | Sought/retrieved/not-retrieved totals reconcile; inaccessible reports stay `not_assessed_pending_full_text` and are never coded as fact absence |
| 5. Full-text eligibility | Two independent decisions, report-level exclusion reasons, study links | Cochrane Ch 4.6.4 | At least two independent full-text eligibility assessments; every exclusion has a protocol-aligned reason; disagreements are adjudicated |
| 6. Extraction | Pilot-tested data form, independent extraction/verification, source coordinates | Cochrane Ch 5; tutorial pp. 7-9 | Each analysis value traces to a report/page/table/figure; discrepancies are resolved and logged |
| 7. Risk of bias | Design-specific, result-level judgements and supporting evidence | Cochrane Ch 7-8; Ch 25 for eligible non-randomized intervention studies | Tool matches design; domain judgements are independently checked; no quality-total-score substitution. Ch 9 supports study-characteristic summaries and synthesis preparation |
| 8. Synthesis | Compatibility decision, analysis dataset/code, outputs, heterogeneity and sensitivity checks | Cochrane Ch 6, 10-11; tutorial pp. 9-15 | Pool only clinically/methodologically coherent data; deviations and model decisions are documented |
| 9. Certainty | Critical outcomes, GRADE/CINeMA rationale, Summary of Findings | Cochrane Ch 14 and Ch 11 for NMA | Rating rationale and reported absolute/relative effects agree with validated synthesis |
| 10. Reporting | PRISMA flow/checklist, search appendix, limitations, final reproducibility audit | Cochrane Ch 1, 4, 10, 14; tutorial Appendix A pp. 20-21 | Two independent reviewers approve; all prior stage gates remain valid |

## Full-text Retrieval Through Zotero

1. Create a Zotero collection for reports that reached full-text retrieval.
2. Prefer the configured `cookjohn/zotero-mcp` server. Resolve the collection
   through `get_collections`/`search_collections`, page through
   `get_collection_items`, and use `get_item_details` to resolve candidate
   identities and attachments.
3. When citations need importing, add them to the project collection in the
   Zotero desktop application and let Zotero's own plugin retrieve available
   attachments. The project CLI is read-only and does not call
   `add_by_identifier` or trigger attachment downloads. For existing collection
   items, use advertised MCP read tools such as `get_content` and
   `fulltext_database`; record the exact item/attachment and returned content
   locator. See [Zotero MCP integration](ZOTERO_MCP_INTEGRATION.md).
4. If MCP is not present, use the read-only local adapter:
   `sci-nma-agent zotero-fulltext --project PROJECT --source ZOTERO_DATA_DIR
   --collection COLLECTION_NAME`. A Zotero JSON export is also supported.
5. Reconcile DOI/PMID/title identity and attachment cardinality. Never select
   the first of multiple plausible reports silently. Keep the original
   attachment, content/hash manifest, extraction status, and returned page
   locators; where the connector supplies no page locator, do not invent one.
6. For unresolved reports, create a route-tracked manual-acquisition queue,
   notify the user, and pause dependent work. The retrieval submit gate stores
   the queue beside the versioned manifest. To display or refresh it, use
   `sci-nma-agent manual-fulltext queue`; after Zotero has attached a candidate,
   use `sci-nma-agent manual-fulltext confirm` with the exact study/report,
   item key, attachment key, local attachment path, actor, and session.
   Confirmation re-reads and identity-checks the selected attachment, creates
   immutable hashed artifacts, and resumes or hands off the retrieval stage.
   The executor submits the new manifest and queue for two fresh independent
   reviews before dependent stages proceed.

The deduplication stage submits `study_report_map.json`; title/abstract
screening submits `title_abstract_screening_manifest.json`; retrieval submits
`full_text_retrieval_manifest.json`; full-text eligibility submits
`full_text_screening_manifest.json`; and extraction submits
`fact_status_manifest.json`. Each downstream manifest is hash-bound to all
approved upstream inputs it depends on. Retrieval must contain exactly the
reports marked `include_for_full_text` in the approved screening manifest; it
must not include title/abstract exclusions or omit a sought report. Extraction
facts must match the approved retrieval state and an included full-text
eligibility result. Full-text exclusions require a reason and report locator.
Record `retrieval_status`, `full_text_review_status`, and per-field `fact_status`
separately. Before retrieval and confirmation, facts are
`not_assessed_pending_full_text`; after retrieval but before independent review
and adjudication, they are `pending_full_text_review`.
`not_reported_in_reviewed_report` is report-level and requires reviewed
section/page coverage. It does not mean the outcome was not measured, that
there were zero events, or that a numeric value is zero. The study-level status
`not_reported_after_all_linked_sources_review` is permitted only after every
report in the approved linkage map has a confirmed retrieval and completed,
adjudicated review with explicit coverage evidence. Use
`cannot_tell_after_full_text_review` with a reason when review is complete but
the reporting status remains indeterminate. Retrieval failure, an inaccessible
attachment, OCR failure, or ambiguity is not evidence of factual absence.

## Independent Agent Review Gate

Each stage has one or more execution agents and at least two independent review
agents. The executor submits durable artifacts and a concise summary. Reviewers
record a distinct session identity, `approve` or `revise`, a report artifact,
and findings. Only two distinct approvals release the next stage. One revision
vote blocks progression. Rerunning an approved stage invalidates its downstream
approvals so stale outputs cannot survive a changed input. Session IDs are
orchestrator-supplied audit fields; the local ledger does not attest to model
provider, agent isolation, or human identity.

The ledger is auditable and hash-chained, but hashes do not establish scientific
truth. Method review, evidence coordinates, and human adjudication remain
necessary.

## Preserved Output Contract

Existing PNG/SVG/PDF, DOCX, XLSX, and PPTX dimensions and formatting stay under
the project's current format contract. This workflow changes upstream evidence
and governance, not the established figure/table appearance.

# New Systematic Review Module

Use this module only when the user is starting a new clinical evidence
synthesis. Never import a reproduction example's cohort, treatment list,
effect estimates, model, or figure contents as new-review data.

## Workflow

1. Draft and validate the project-specific `review_protocol.json` and
   `verification/methods_source_log.json`; declare the `chapter-NN` set,
   record matching chapter-level Handbook update/access dates and tutorial provenance, then freeze the question,
   eligibility, outcomes, synthesis decisions, registration status, and
   amendment process before screening.
2. Execute database-specific searches and peer review; preserve exact
   strategies, dates, counts, exports, and provenance.
3. Deduplicate while retaining source records and study/report links.
4. Screen titles/abstracts and full texts with separate reviewer decisions,
   then document adjudication and full-text exclusion reasons.
5. Have the user create the project collection, import report items, and use
   Zotero's own attachment retrieval in the desktop application. Use the
   configured Zotero MCP connection only to read the existing collection and
   extract cached text; the current CLI is read-only and does not import items
   or trigger downloads. Reconcile item identity, attachment choice, retrieval
   state, hashes, page locators, and extraction errors before eligibility or
   analysis. Follow [the Zotero MCP integration contract](../../../docs/ZOTERO_MCP_INTEGRATION.md)
   for the implemented export boundary.
   If retrieval fails, create a route-tracked manual queue, notify the user,
   and pause only dependent work. The retrieval submit gate persists the queue
   beside the attempt manifest. Use `sci-nma-agent manual-fulltext queue` to
   display or refresh it. After the candidate is attached in Zotero, use
   `sci-nma-agent manual-fulltext confirm` with the exact report, item and
   attachment keys, local file, actor, and session. The command re-reads the
   attachment through MCP, compares it with the approved report identity,
   writes versioned hashes, and resumes or hands off the retrieval stage.
   Submit the new manifest and queue for two fresh independent reviews before
   any dependent stage proceeds.
6. Pilot the extraction form; preserve paired extraction/verification,
   report/page/table/figure locators, transformations, and unresolved data.
7. Assess risk of bias using design- and result-appropriate methods; decide
   compatibility before synthesis; apply the [statistical methods and software
   contract](../../../docs/STATISTICAL_METHODS_AND_SOFTWARE.md), create
   `analysis_manifest.json`, and prespecify analysis, diagnostics, and
   sensitivity decisions. Use the bundled Python engines only for QA; formal
   synthesis must come from the locked production engine named in the protocol.
   Assess certainty and report under the applicable framework.

## Stage Control

Read [the workflow](../../../docs/EBM_SYSTEMATIC_REVIEW_WORKFLOW.md),
[the release gates](../../../docs/AGENT_STAGE_GATES.md), and only the assigned row
of [the method map](../../../docs/COCHRANE_AGENT_REQUIREMENTS.md). Dispatch the
generic executor and reviewer cards from `agents/review_roles/`, augmented by
the corresponding stage-method row and stage card. The orchestrator releases a
stage only after both independent reports approve; a revision vote blocks the
next stage. Zotero status is retrieval provenance, never an eligibility
decision. Before a report is retrieved and confirmed, use
`not_assessed_pending_full_text`; after retrieval but before independent review
and adjudication, use `pending_full_text_review`. Report-level
`not_reported_in_reviewed_report` requires reviewed section/page coverage.
Study-level `not_reported_after_all_linked_sources_review` requires confirmed
retrieval and adjudicated coverage evidence for every report in the approved
study/report map. Use `cannot_tell_after_full_text_review` with an uncertainty
reason when review is complete but reporting remains indeterminate. These
statuses do not mean unmeasured or zero. An OCR or extraction failure stays an
access/content-processing issue until resolved.

The agent roster, local ledger, and Zotero interface are project governance and
implementation choices, not requirements imposed by Cochrane. Preserve the
project owner's figure/table contract when producing outputs.

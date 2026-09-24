# Systematic Review Agent Workflow

These cards support new evidence-based systematic reviews and meta-analyses.
Publication reproduction/calibration is a separate optional workflow, invoked
only when a task explicitly requests it. Cochrane specifies review methods; it
does not prescribe AI roles, Zotero, or this project's approval mechanism.

## Files

- [Stage executor](review_roles/stage-executor.md): execute one assigned stage.
- [Independent reviewer](review_roles/independent-reviewer.md): independently
  assess a submitted stage using the stage card's `review_focus`.
- [Screening adjudicator](review_roles/screening-adjudicator.md): resolve
  conflicts between locked dual screening decisions.
- [Stage-method matrix](STAGE_METHOD_MATRIX.md): Handbook basis, acceptance
  checkpoints, and artifacts for every stage.

## Dispatch Rules

1. Supply the current role card, approved protocol (or protocol brief for the
   protocol stage), stage card, relevant upstream approved artifacts, exact
   output paths, and acceptance criteria. Inputs not listed on the stage card
   are out of scope.
2. Set `review_focus` on each stage card as a concise list of stage-specific
   audit questions derived from `STAGE_METHOD_MATRIX.md`. Reviewers use that
   field; do not create a permanent role card per specialty.
3. For title/abstract screening, full-text screening, data extraction, and risk
   of bias, dispatch the executor card twice with distinct agent IDs, separate
   output paths, and no shared draft/decisions before both submissions are
   locked. These paired judgments are methodological work products.
4. Separately dispatch two distinct independent reviewer IDs for every stage.
   Their gate reviews do not replace paired screening, extraction, or RoB
   judgments. Reviewers return `approve` or `revise` recommendations with
   checked hashes, criterion-level results, evidence locations, corrections,
   and unresolved issues.
5. Dispatch the adjudicator only after both screening files are locked. Preserve
   both original votes and record the final disposition and evidence; unresolved
   criteria go to the project lead rather than being forced.

## Shared Boundaries

- No agent edits or advances `verification/agent_stage_ledger.json`. Only the
  workflow orchestrator records two distinct stage approvals and releases the
  next stage.
- An executor cannot review its own work. Any `revise` recommendation blocks
  downstream work until a revised attempt receives two independent reviews.
- Preserve study identity separately from report identity. Record source IDs,
  hashes, dates, decisions, assumptions, and page/table/figure coordinates.
- Keep `retrieval_status`, `full_text_review_status`, and each field's
  `fact_status` separate. Before retrieval/confirmation, use
  `not_assessed_pending_full_text`; after retrieval but before completed
  independent review and adjudication, use `pending_full_text_review`.
  `not_reported_in_reviewed_report` requires reviewed section/page coverage;
  study-level `not_reported_after_all_linked_sources_review` requires completed,
  adjudicated coverage evidence for every report in the approved study/report
  map. `cannot_tell_after_full_text_review` records a reviewed but indeterminate
  fact. Neither missingness status means unmeasured or zero. Unavailable or
  unconfirmed reports stay in the retrieval queue and are never treated as fact
  absence. Zotero retrieval status is not eligibility.
- Keep the user's approved figure/table format unchanged. Validate data and
  methods before rendering.
- Separate Handbook methods from project controls such as role cards, Zotero,
  the two-review gate, artifact paths, and ledger.

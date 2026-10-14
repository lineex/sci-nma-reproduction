# Output Contract and Stepwise Search

## One Format Authority

The source-of-truth figure/table specification is
`data/nma_figure_table_spec_template.json`. The copy under
`sci_nma_agent/templates/` is a distribution mirror for project initialization
and must remain byte-identical to the source. Once initialized, use only the
project copy at `data/nma_figure_table_spec_template.json`.

Before generating any figure or table:

1. Fill the project-specific placeholders in the project contract, including
   title, search date, outcome, effect measure, model track, data sources, and
   output names.
2. Keep the contract's declared figure and table IDs, mandatory set, layouts,
   and output requirements unchanged. Do not add, remove, rename, or redesign
   contract items unless the project owner approves a protocol amendment.
3. Compute the completed contract's SHA-256 and record it in
   `review_protocol.json` at `figure_table_contract.contract_sha256`.
4. Submit `review_protocol.json`, its methods-source log, and the exact
   contract file to the protocol stage. The protocol gate checks the hash;
   the stage ledger retains and rechecks the submitted contract artifact.
5. Do not generate output until the protocol and its contract are approved.

At every new work session, reload the approved protocol and contract before
creating or editing a deliverable. Conversation history is not the format
authority. If the contract hash no longer matches, stop figure/table work and
use the protocol amendment and review process before continuing.

## Figure and Table Completion

Use only the figure, table, and supplementary item IDs already declared in the
approved contract. Populate every project-specific field required by each
item; do not carry example values into a new review. Each output must be
derived from its declared source data and generation code and retain its
caption and validation evidence.

After rendering, a person completes
`reporting/figure_table_format_audit.csv` one row at a time against the
approved contract. The audit records each declared item, output path/hash,
source-data path/hash, generation-script path/hash, caption path/hash,
contract path/hash, validation-report path/hash, result, and reviewer notes.
Mark an item `passed` only after the visual and structural checks required by
that item's contract have been performed. Do not generate a replacement layout
or add audit rows for items absent from the contract.

Include the completed audit CSV and every required figure/table/source artifact
in the reporting-stage submission manifest. The stage ledger records SHA-256
for submitted artifacts and rechecks them during review and release. A format
review is a human comparison against the contract; hashes establish file
identity, not visual or methodological correctness.

## Search as a User-Confirmed To-do List

Search work is organized by database, not by parallel browser calls or an
automatic scheduler. `search/browser_search_queue.json` provides ordering,
status, provenance, and recovery information; the executor still advances one
database only after the user confirms the prior database's completed report.
Within a database, the queue is also a checklist: each native strategy line
must be recorded as a completed count checkpoint before the next line is
executed. The final-combination checkpoint is recorded before the full export
is submitted.

For each database, show and complete this checklist before proceeding:

- [ ] Confirm this is the first unresolved database in the saved queue.
- [ ] Open its approved native strategy and record the exact query lines.
- [ ] Start the database task and execute the next unchecked native line only.
- [ ] Save that line's count and history/query locator with
  `search-queue record-line`; do not proceed until the checkpoint is persisted.
- [ ] Repeat for every component/concept/filter line; record counts only and
  never export detailed records from component lines.
- [ ] Execute the final combined query, save its authoritative total and
  locator as the final line checkpoint, then export detailed records from this
  line only.
- [ ] Reconcile total versus exported-record count; retain exact-as-run
  history/export paths and SHA-256 values.
- [ ] Fill the database's supplement rows and save the checkpoint/evidence.
- [ ] Report the database, line counts, final total, export total, paths/hashes,
  and unresolved issues to the user; pause here for explicit confirmation.

Do not claim or start the next database until the user confirms continuation.
For queues created by the current project version, record the confirmation
before claiming the next task:

```powershell
sci-nma-agent search-queue confirm-next `
  --queue PROJECT/search/browser_search_queue.json `
  --actor user `
  --session USER_CONFIRMATION_SESSION
```

This records the user's decision only; it does not run a search.
If work is interrupted, inspect the same queue and resume the current
incomplete database from its saved line checkpoint; do not repeat completed
lines, completed database tasks, or skip to a later database. Browser execution
remains strictly serial.

The search stage has one executor and **one independent reviewer** after all
database tasks and evidence are complete. This is one reviewer, not two
independent reviewers. Screening, extraction, risk-of-bias, and other stages
retain their separately configured paired decisions and review gates.

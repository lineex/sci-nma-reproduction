# Continuous Workplan and Resume Contract

## Purpose

Long evidence-synthesis projects span multiple sessions. This contract turns
the approved research protocol into a durable task tree so that a later
activation can continue from the last verified boundary instead of guessing,
repeating work, or treating an interrupted task as complete.

The work plan is an operational continuity layer. It does not replace
`verification/agent_stage_ledger.json`, paired evidence decisions, or the
scientific review gate. The stage ledger decides whether a stage may be
released; the work plan records what remains to be done and how to resume it.

## Required artifacts

Create these files inside each project:

```text
verification/
  research_workplan.json
  workplan_events.jsonl
  workplan_checkpoints/
    <task-id>/attempt-<n>.json
  workplan_sessions/
    <session-id>.json
```

`sci-nma-agent init` now creates the `research_workplan.json` scaffold,
`workplan_events.jsonl` with its initialization event, and the checkpoint and
session directories. Because no protocol has been approved at initialization,
`protocol_sha256` is null. After the protocol gate approves
`review_protocol.json`, replace that null with its SHA-256 and populate stable
child tasks from the approved database queue and stage-specific work. Never
reset an existing work plan or event log by rerunning initialization.

Use the template at
[`continuous_workplan_template.json`](continuous_workplan_template.json) as a
starting point. Keep the work plan and event log project-relative, include
their hashes in the relevant stage artifact set, and preserve prior versions
when the protocol or task scope is amended.

## Task-tree model

Use stable hierarchical IDs. The recommended top level is the approved EBM
sequence (`G0` protocol, `G1` search, `G2` corpus, `G3` title/abstract,
`G4` retrieval, `G5` full-text eligibility, `G6` extraction, `G7` risk of bias,
`G8` synthesis, `G9` certainty, `G10` reporting). Add children with dotted IDs,
for example `G1.DB01`, `G1.DB01.L03`, or `G4.R042.ATT01`. IDs are never reused
after a task is completed, cancelled, or superseded.

Each task must contain at least:

- `task_id`, `parent_id`, `ordinal`, `title`, and `kind` (`stage`, `batch`,
  `leaf`, or `review`);
- `status`, `dependencies`, and `children`;
- `objective` and a concrete `acceptance_criteria` list;
- declared `inputs` and `required_outputs` with project-relative paths;
- `executor`, `reviewers`, `attempt`, `checkpoint_id`, and `last_event_id`;
- `created_at`, `updated_at`, and an optional `human_action_required` record.

Use these states consistently:

| State | Meaning |
|---|---|
| `pending` | The task exists but a dependency or parent release is not ready. |
| `ready` | All dependencies are released and the leaf may be claimed. |
| `in_progress` | One session has claimed the task. |
| `paused` | A user action, external service, or recoverable interruption is recorded. |
| `blocked` | Progress requires a decision or input that cannot be inferred. |
| `awaiting_review` | Outputs exist and are submitted for the configured review gate. |
| `approved` | The task's acceptance criteria and review requirements passed. |
| `completed` | The approved task is closed; its parent may be derived as complete when all siblings pass. |
| `failed` | The attempt ended with an error; preserve evidence and create a deliberate retry. |
| `superseded` | A protocol amendment replaced the task; retain the prior record and reason. |

`ready` is derived from dependencies and may be written as a convenience. A
parent cannot become `completed` while any child is unresolved. A stage cannot
be `approved` merely because all work-plan children are complete; it must still
pass the stage-ledger review and artifact validation.

## Event and checkpoint rules

`workplan_events.jsonl` is append-only. One event records one transition or
one material piece of work:

```json
{
  "event_id": "evt-000042",
  "timestamp": "2026-10-13T09:30:00+08:00",
  "session_id": "session-20261013-01",
  "task_id": "G1.DB01.L03",
  "action": "checkpoint",
  "status_before": "in_progress",
  "status_after": "in_progress",
  "summary": "Final combination submitted and export validation passed",
  "inputs": [{"path": "search/PubMed_strategy.txt", "sha256": "..."}],
  "outputs": [{"path": "raw_exports/pubmed/run-0001.ris", "sha256": "..."}],
  "acceptance_checks": ["final_search_total equals database history total"],
  "next_action": "submit for search-stage review",
  "human_action_required": false
}
```

After each idempotent boundary, write a checkpoint at
`verification/workplan_checkpoints/<task-id>/attempt-<n>.json`. It must state
the last completed child operation, remaining operations, input/output hashes,
external locators (history number, Zotero item/attachment key, page/table
locator, or R result ID), and the exact next action. Do not store credentials,
session cookies, access tokens, or full browser dumps in the work plan.

When a task is paused or a process exits, preserve the partial files and write
the checkpoint before changing status. A failed attempt is never silently
rewritten: increment `attempt`, retain the old checkpoint, and record why the
retry is idempotent or what changed.

## Activation and resume protocol

At the start of every session, perform these actions in order:

1. Locate the project and load `research_workplan.json`.
2. Validate its schema, protocol/amendment hash, event sequence, and all
   artifact hashes referenced by the latest events. Validate the stage-ledger
   hash chain before claiming work.
3. Mark an `in_progress` task from a missing/expired session as `paused` with
   an `interrupted` event. Never assume that an unfinished process completed.
4. Select the first ready leaf by parent ordinal and task ordinal. If a higher
   priority task is `blocked`, report the blocker instead of skipping it.
5. Load its latest checkpoint and compare every existing output hash. Reuse
   outputs that match; resume only the remaining operations. If an output
   changed, open a new attempt and record the reason before recomputing it.
6. Create a session record, claim exactly one active task for browser work,
   and append a `started` or `resumed` event with actor and session IDs.
7. After each meaningful operation, append the event and update the checkpoint.
   At a stopping point, write the checkpoint even when no task is complete.
8. On successful work, attach artifact hashes and acceptance checks, move the
   leaf to `awaiting_review`, and invoke the configured independent review.
   Only an approving review may move it to `approved` and then `completed`.
9. Recompute parent status from its children. The next activation begins at
   the first unresolved leaf, not at the beginning of the stage.

The resume report should always state: project ID, last approved task,
currently active or paused task, latest checkpoint, unresolved blockers, next
action, and whether user confirmation is required.

## Stage-specific decomposition

- **Protocol (`G0`)**: question/scope, eligibility, outcomes, methods source
  log, analysis decisions, and amendment procedure.
- **Search (`G1`)**: one ordered database task at a time; native component
  lines are count-only children, while the final combination/export is its own
  child. A verification or login page pauses the same database task.
- **Corpus and screening (`G2-G3`)**: import, deduplicate, and batch paired
  decisions. Each batch records its source export hash and disagreement state.
- **Full text (`G4-G5`)**: one report or explicit batch per child. DOI lookup,
  ScanSci route, Zotero MCP read-back, attachment hash, and manual CARSI or
  Zotero confirmation are separate checkpoints. Retrieval failure is a
  retrieval state, never a factual absence.
- **Extraction and bias (`G6-G7`)**: one outcome/timepoint or study batch per
  child with source coordinates, transformations, paired verification, and
  unresolved fields.
- **Synthesis (`G8-G9`)**: R plan, locked environment, input snapshot, model
  run, diagnostics, sensitivity analyses, certainty, and reviewer checks are
  separate tasks. Use the local R override only on this machine; keep it out of
  project/cloud artifacts.
- **Reporting (`G10`)**: one child per required supplement, manuscript,
  checklist, figure/table, reproducibility file, archive, and final QA review.

## Non-negotiable continuity rules

1. Never overwrite the event log or delete a prior checkpoint.
2. Never mark a task complete without an artifact path/hash and acceptance
   result.
3. Never start a dependent task while its parent or upstream stage is merely
   `in_progress`, `paused`, or `awaiting_review`.
4. Never treat a missing file, login page, API error, OCR failure, or an
   unconfirmed attachment as evidence that a study fact is absent.
5. Never run browser tasks concurrently; the search queue remains strictly
   serial even when the work plan contains multiple ready database children.
6. If the protocol changes, append an amendment event, hash the new protocol,
   and supersede only the affected subtree. Do not silently edit historical
   task results.


# Serial Browser Search Queue

## Purpose

Browser searches are run as an ordered queue rather than as concurrent
automation calls. This keeps one authenticated browser session focused on one
database, makes verification or login checkpoints unambiguous, and preserves a
reviewable record for every database. The queue is an ordered task list and
evidence gate; the existing CDP/browser skills perform each search. It does
not automatically execute or advance searches; the user confirms each
database transition.

The invariant is:

```text
max_active_tasks = 1
parallel_browser_calls = false
```

A later database starts only after the previous database has an exact-as-run
history, an export, hashes for both, and a completed queue record.
After presenting that database's completed checklist and evidence, pause for
explicit user confirmation before claiming the next database. The queue stores
order and provenance; the agent does not automatically advance the search.
For queues created by the current project version, `start` rejects the next
database until `confirm-next` records that explicit decision.

## Queue schema

`search/browser_search_queue.json` uses schema version `2` and contains:

- `execution_policy`: `strict_serial`, one active task, preferred
  `cdp_builtin_browser`, then `chrome_devtools`;
- `tasks`: one ordered task per database (`ordinal`, `task_id`, database,
  strategy/execution-artifact paths and hashes, an ordered per-line checklist,
  browser route, session, status, and evidence);
- `events`: append-only lifecycle records for queue creation, start, pause,
  resume, failure, and completion.

Task states are:

| State | Meaning | Next action |
|---|---|---|
| `pending` | The next task is ready to claim | `start` |
| `running` | One executor owns the browser task | complete, pause, or fail |
| `paused` | Verification, login, or recovery needs user action | resolve the checkpoint, then `resume` |
| `failed` | The attempt ended with a retained error | diagnose, then `resume` |
| `completed` | Exact-as-run evidence passed validation | start the next ordinal |

Each task's `line_checkpoints` persist one completed result count and history
locator per strategy line. Only the first unchecked line may be recorded. This
lets a resumed search continue from its next line instead of repeating earlier
queries. Completion validates the saved line checkpoints against the submitted
count/export evidence.

`pause` and `fail` release the active slot, but they do not advance the
ordinal. A paused or failed task must be explicitly resumed before another
attempt. A later task cannot be completed ahead of an unresolved earlier task.

## CLI

Create a queue after the protocol and native strategies are ready:

```powershell
sci-nma-agent search-queue create `
  --pico PROJECT/config_pico.json `
  --project PROJECT `
  --output PROJECT/search/browser_search_queue.json
```

Inspect the queue:

```powershell
sci-nma-agent search-queue status `
  --queue PROJECT/search/browser_search_queue.json
```

Render it as a resumable to-do checklist:

```powershell
sci-nma-agent search-queue checklist `
  --queue PROJECT/search/browser_search_queue.json
```

Claim exactly one database. The built-in CDP route is the default:

```powershell
sci-nma-agent search-queue start `
  --queue PROJECT/search/browser_search_queue.json `
  --actor search-agent `
  --session SEARCH_SESSION_001 `
  --browser-route cdp_builtin_browser
```

Execute the next unchecked native strategy line, then persist its count and
history/query locator before moving to the following line:

```powershell
sci-nma-agent search-queue record-line `
  --queue PROJECT/search/browser_search_queue.json `
  --task-id TASK_ID `
  --actor search-agent `
  --session SEARCH_SESSION_001 `
  --line-number 1 `
  --result-count 8123 `
  --locator "history:#1"
```

Repeat with the next line number. Component lines save counts only. The final
combination is also checkpointed with its total and locator before exporting
full records from that line.

Use `chrome_devtools` only when the primary route is unavailable and retain
the loopback endpoint, dedicated profile, `/json/version` response, and
advertised WebSocket as session evidence.

Pause at a verification, institutional login, or recoverable browser error:

```powershell
sci-nma-agent search-queue pause `
  --queue PROJECT/search/browser_search_queue.json `
  --task-id TASK_ID `
  --actor search-agent `
  --session SEARCH_SESSION_001 `
  --reason "verification page requires user action" `
  --checkpoint same_authenticated_browser
```

After the user completes the checkpoint in the same authenticated profile:

```powershell
sci-nma-agent search-queue resume `
  --queue PROJECT/search/browser_search_queue.json `
  --task-id TASK_ID `
  --actor user `
  --session USER_SESSION_001
```

Resume returns the task to `pending`; it does not claim the browser. Start it
again with the executor session that will run the probe and full search.

Record an unrecoverable attempt without discarding its evidence:

```powershell
sci-nma-agent search-queue fail `
  --queue PROJECT/search/browser_search_queue.json `
  --task-id TASK_ID `
  --actor search-agent `
  --session SEARCH_SESSION_001 `
  --reason "database export failed after the retained probe"
```

## Evidence required for completion

Each native strategy line is executed for a count only. Component-line
execution must not export citation details or record-level data. The final
combination line is executed separately and is the only step that exports the
full records used for screening. The evidence therefore has two distinct
parts:

1. `component_line_counts`: one count and history/query locator per concept,
   filter, or limit line; no export path, record IDs, or detailed records are
   allowed in these entries.
2. `final_search_total` plus `final_records_exported`, with a complete
   final-combination export and history artifact.

The executor creates an evidence JSON inside the project and then calls
`complete`. A compact example is:

```json
{
  "database": "PubMed",
  "browser_route": "cdp_builtin_browser",
  "strategy_sha256": "STRATEGY_SHA256",
  "execution_query_sha256": "EXECUTION_QUERY_SHA256",
  "component_line_counts": [
    {"line_number": 1, "result_count": 8123, "history_or_query_locator": "history:#1"},
    {"line_number": 2, "result_count": 4567, "history_or_query_locator": "history:#2"}
  ],
  "final_combination_line_number": 3,
  "final_combination_locator": "history:#3",
  "final_search_total": 1234,
  "final_records_exported": 1234,
  "final_export_scope": "final_combination_only",
  "final_record_detail_level": "full",
  "final_export_complete": true,
  "final_export_path": "raw_exports/pubmed/run-0001.ris",
  "final_export_sha256": "EXPORT_SHA256",
  "final_history_path": "search/PubMed_history.json",
  "final_history_sha256": "HISTORY_SHA256",
  "search_date": "2026-10-07",
  "timezone": "Asia/Shanghai"
}
```

The queue validates that the database and browser route match the claimed
task, strategy and execution hashes match the queued artifacts, every component
line has a count-only record, and the final export/history files exist inside
the project with current hashes. `final_search_total` is the database-reported
count for the final combined query; `final_records_exported` describes the
full-detail records actually written to the final export. Component counts are
not corpus records and must never be ingested as screening citations.

Complete the task:

```powershell
sci-nma-agent search-queue complete `
  --queue PROJECT/search/browser_search_queue.json `
  --task-id TASK_ID `
  --actor search-agent `
  --session SEARCH_SESSION_001 `
  --evidence PROJECT/verification/search/PubMed_evidence.json
```

After completion, show the user the counts, export total, history/export paths,
hashes, and unresolved issues. Only after the user confirms continuation,
record that decision:

```powershell
sci-nma-agent search-queue confirm-next `
  --queue PROJECT/search/browser_search_queue.json `
  --actor user `
  --session USER_CONFIRMATION_SESSION
```

This command only records permission to proceed; it does not start the next
database. The confirmation command and subsequent `start` both revalidate the
completed database's native strategy, execution query, history, export, and
saved line checkpoints against their hashes. If a source or evidence artifact
changed, resolve it through a tracked rerun before advancing. Claim the next
task separately with `search-queue start`.

## Browser execution rules

1. Start only the queue's next task.
2. Use one browser tab/session for that task; do not open a second database
   search while it is `running`.
3. Keep native line-by-line strategy artifacts separate from the private
   collapsed execution artifact. Execute each native component line for its
   count only. Execute the final combination line to obtain the final total
   and export full record details. The supplement displays native syntax and
   exact-as-run history/export references, not the collapsed query by default.
4. A verification, SSO, CARSI/WebVPN, or recoverable connector error pauses the
   current task. Preserve the checkpoint and resume the same task after the
   user action.
5. Do not turn a blocked page, failed connector, or missing export into a
   zero-result search.
6. Complete and hash the history/export evidence, present the database report
   to the user, and wait for confirmation before starting the next database.

## Stage submission

When the search stage uses browser automation, submit
`search/browser_search_queue.json` with the other search artifacts. The stage
ledger revalidates the queue, strategy/execution hashes, history/export hashes,
execution policy, and completion of every task. A queue with unresolved
`pending`, `running`, `paused`, or `failed` tasks is not release-ready.
Search-stage release requires one independent reviewer after the executor;
the two-reviewer requirement remains for the downstream evidence-judgement
stages.

Projects created before the queue feature may retain an older search artifact
set. For a new or rerun browser search, create and submit the queue so that the
serial execution contract is explicit.
Queues created before durable per-line checkpoints remain readable for audit,
but the current executor will not start them. Preserve the original queue and
reconcile its already-executed line counts before continuing; do not overwrite
it or assume earlier query lines were completed.

## Recovery and audit

The queue uses an exclusive lock for read-modify-write transitions and keeps
session, actor, timestamp, browser route, attempt count, and checkpoint event
history. If a process exits during a task, inspect `status`, retain the
partial files, and resume or fail the owned task deliberately. Never create a
second queue to bypass an active or unresolved task; use a versioned rerun
through the stage ledger when the protocol or strategy changes.

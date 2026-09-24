# Agent Stage Gates

The new-review workflow uses `verification/agent_stage_ledger.json` as its
release-control record. Its states are `pending`, `in_progress`,
`awaiting_review`, `needs_revision`, and `approved`.

## CLI Sequence

```powershell
# New project: initialize its scaffold and stage ledger together.
sci-nma-agent init PROJECT
# Existing project without a ledger only: use the next command instead of `init`.
# sci-nma-agent review-stage init --project PROJECT
sci-nma-agent review-stage start --project PROJECT --stage protocol --agent protocol-lead --agent-session EXECUTOR_SESSION_1
sci-nma-agent review-stage submit --project PROJECT --stage protocol --agent protocol-lead --agent-session EXECUTOR_SESSION_1 --artifact review_protocol.json --artifact verification/methods_source_log.json --summary "Protocol draft complete"
sci-nma-agent review-stage review --project PROJECT --stage protocol --reviewer clinical-reviewer --reviewer-session REVIEWER_SESSION_A --verdict approve --report verification/reviews/protocol-clinical.md --findings "Eligibility and clinical scope verified against the protocol checklist"
sci-nma-agent review-stage review --project PROJECT --stage protocol --reviewer methods-reviewer --reviewer-session REVIEWER_SESSION_B --verdict approve --report verification/reviews/protocol-methods.md --findings "Search, outcomes, synthesis, and certainty decisions verified"
sci-nma-agent review-stage status --project PROJECT
```

The two initialization commands are alternatives. `sci-nma-agent init PROJECT`
already creates the stage ledger; do not run `review-stage init` afterward unless
you explicitly intend to replace an existing ledger with `--overwrite`.

Every stage stays blocked until all earlier stages are approved. Each
transition rechecks every upstream artifact and review-report hash; status
reports both ledger-chain and evidence integrity, and returns failure if
either check fails. An executor cannot review its own stage. Reviewer IDs and session IDs must be
distinct, and reviewers must submit different report artifacts. Session IDs
are supplied by the orchestrator and recorded for traceability; the local CLI
does not attest to a model provider or prove that different IDs are different
people. Review reports should record the runner/task identity and responsible
human sign-off. Artifacts and reports must exist under the project directory
and are recorded with SHA-256. The ledger hash chain binds each recorded stage
state; the gate rechecks evidence hashes before approval and before the next
stage starts. `--rerun` on an approved stage preserves prior attempt metadata
and resets that stage and all downstream stages to pending.

The protocol stage must submit exactly one `review_protocol.json` and one
`verification/methods_source_log.json`. Protocol fields and the source log's
chapter-level edition/update and access provenance are validated before review,
including a conditional NMA assumptions section. Blank templates are
intentionally not submit-ready.

The `deduplication` stage must submit one validated `study_report_map.json`;
`title_abstract_screening` must submit one complete dual-decision manifest;
`fulltext_retrieval` must submit one manifest whose rows exactly match the
approved reports-sought set; `fulltext_screening` must resolve every retrieval
row; and `data_extraction` must bind each fact to the approved map, retrieval,
and full-text eligibility manifests.
The ledger rejects a submission when its required manifest is absent, invalid,
or detached from the upstream linkage artifact.

## Full-text State Separation

Keep three fields independent on each report/fact: `retrieval_status`,
`full_text_review_status`, and `fact_status`. A failed or pending retrieval
uses `not_assessed_pending_full_text`; a retrieved report awaiting independent
review uses `pending_full_text_review`. `not_reported_in_reviewed_report` is a
report-level status and requires documented section/page coverage after
adjudicated review. A study-level `not_reported_after_all_linked_sources_review`
or `cannot_tell_after_full_text_review` requires the complete approved linkage
map, successful confirmed retrieval of each linked report, completed review and
adjudication, and per-report coverage evidence. Neither status means the outcome
was not measured or that its value is zero. Retrieval failures, OCR failures,
and identity/attachment ambiguity are not evidence that a report omitted a fact.

When manual acquisition is needed, keep the report in the retrieval-stage
queue with the attempted routes and identity checks. After the user confirms
the attached file and Zotero item, resume the unfinished work within the same
retrieval stage, record the confirmation and updated evidence hashes, then run
the ordinary two-reviewer gate. Never jump to full-text screening or mark a
fact as absent merely because an attachment was not found.

## Review Record Requirements

Each review report should state:

- protocol/Handbook criteria applied and version checked;
- inputs and artifact hashes reviewed;
- pass/fail for each acceptance criterion;
- unresolved methodological decisions and their impact;
- exact corrections requested, or reason for approval;
- reviewer ID, role, and review date.

The ledger stores lifecycle and artifact provenance. It is an auditable local
workflow gate, not a cryptographic identity service or a substitute for human
methodological accountability. Study-level screening,
extraction, and risk-of-bias decisions must additionally retain their own
reviewer-specific records; two gate approvals alone do not constitute those
decisions.

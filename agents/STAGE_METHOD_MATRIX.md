# Stage-Method Matrix

Use the row for the assigned `stage_id` with the approved protocol and current
Handbook edition. Checkpoints are minimum method requirements; the stage card
sets project-specific acceptance criteria and output paths.

| Stage | Handbook / tutorial basis | Acceptance checkpoints | Required artifact set |
|---|---|---|---|
| `protocol` | Cochrane Ch 1-3; tutorial pp. 3-5 | Operational question, eligibility, outcomes/timepoints, designs, analysis and amendment rules; declare the selected `chapter-NN` set and log matching chapter-level version/update and access dates | `review_protocol.json`; `methods_source_log.json`; protocol decision/amendment log |
| `search` | Cochrane Ch 4; tutorial pp. 5-7 | Rerunnable source-specific strategies, dates, limits/rationale, counts, saved exports, reconciliation, peer review | Per-source strategies; search log; immutable exports; peer-review report |
| `deduplication` | Cochrane Ch 4; PRISMA flow accounting | Preserve every source record; auditable duplicate rationale; distinguish reports from studies; reconcile counts | Source-preserving corpus; dedup/linkage log; validated `study_report_map.json`; count summary |
| `title_abstract_screening` | Cochrane Ch 4; tutorial pp. 6-7 | Two independent decisions per record (project policy; Cochrane describes duplicate initial screening as ideal, not a minimum); insufficient abstracts retained for full text; conflicts logged | Separate locked A/B files; conflict list; adjudication log; flow counts; `title_abstract_screening_manifest.json` |
| `fulltext_retrieval` | Cochrane Ch 4.6.3 steps 3-6; Ch 4.6.4 for full-text eligibility review | Reconcile sought/retrieved/not-retrieved; bind report IDs to approved study map; surface item/attachment ambiguity; preserve route attempts and page provenance; unavailable items remain unassessed, never coded as fact absence; user confirms manual attachments before the same stage resumes | `full_text_retrieval_manifest.json` bound to `study_report_map.json`; Zotero MCP/local-source manifest; attachment/hash inventory; manual-acquisition and confirmation queue |
| `fulltext_screening` | Cochrane Ch 4.6.4; tutorial pp. 6-7 | At least two independent full-text eligibility assessments; each exclusion has a protocol reason and report locator; retrieval failure is not exclusion; conflicts are adjudicated | Separate locked A/B files; reason-coded exclusions; conflict list; adjudication log |
| `data_extraction` | Cochrane Ch 5 §§5.2-5.7; tutorial pp. 7-9 | Pilot-tested form; two independent extractions; each analysis value traces to source; conversions/conflicts logged; report-level missingness is distinguished from study-level missingness across linked reports | Separate locked A/B files; discrepancy/resolution log; `fact_status_manifest.json` bound to approved study/report, retrieval, and full-text eligibility manifests; audited analysis dataset |
| `risk_of_bias` | Cochrane Ch 7-8; Ch 25 for eligible non-randomized intervention studies | Tool fits design/result; preserve domain rationale/evidence and independent judgements; no generic quality total score; Ch 9 is used for study-characteristic summaries and synthesis preparation | Reviewer-specific domain records; reconciliation log; final domain dataset |
| `synthesis` | Cochrane Ch 6, 10-11; tutorial pp. 9-15 | Assess compatibility before pooling; prespecified effects/models/dependencies/missing data; NMA assumptions when applicable; reproducible results | Locked input snapshot; executable code/environment; results/diagnostics; synthesis report |
| `certainty` | Cochrane Ch 14; Ch 11 §11.5 for NMA context | Protocol-selected certainty method; rationale per critical outcome; SoF agrees with validated synthesis | Certainty profile; Summary of Findings in fixed project format; audit trail |
| `reporting` | Cochrane Ch 1, 4, 10, 14; PRISMA 2020/extensions; tutorial Appendix A pp. 20-21 | Flow and manuscript values reconcile to approved artifacts; methods/deviations/limits/certainty transparent; figure/table format unchanged | Manuscript; PRISMA checklist; flow data; search appendix; final audit manifest |

## Dispatch Note

The orchestrator adds `review_focus` to each stage card as a concise list of
stage-specific audit questions derived from these checkpoints. The independent
reviewer follows that list. The matrix describes review methods; agent roles,
Zotero, two-agent review, and ledger are project controls. Paired screening,
extraction, and risk-of-bias judgments are methodological work products and do
not replace two distinct stage-reviewer reports.

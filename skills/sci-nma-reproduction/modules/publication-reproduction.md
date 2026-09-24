# Published-Study Reproduction Module

Load only when the task is to reproduce, replicate, or calibrate an identified
published study or its analysis. This module does not run for a new review
question.

## Reproduction Sequence

1. Identify the target article, version of record, protocol/registry, data,
   supplement, corrections, and user-requested reproduction scope. Record what
   is available and what remains unavailable.
2. Build an inventory of source files and analysis artifacts with provenance
   and checksums. Preserve originals unchanged.
3. Reconstruct the reported cohort, eligibility, variables, outcomes, models,
   and figure/table definitions from cited source locations. Separate source
   facts from inferred implementation choices.
4. Implement the analysis or output using the source-defined population and
   methods. Calibration settings and test fixtures belong to this task only;
   do not apply them to new evidence syntheses.
5. Compare counts, estimates, uncertainty intervals, diagnostics, and visual
   outputs against the published report. Report exact agreements, differences,
   likely causes, and unresolved checks; do not tune a model merely to force a
   match.
6. Run focused tests and a final provenance/output audit. Retain scripts,
   software versions, inputs, intermediate results, and a discrepancy report.

## Output Contract

Follow the user's requested scope and the target project's approved file and
figure/table formats. Do not require unrelated output formats or expand a
reproduction into a new systematic review unless the user requests both.

The historical long-form specification is retained at
[`publication-reproduction-legacy.md`](publication-reproduction-legacy.md) as
an archive only. Do not load it for routine new reviews or routine reproduction;
consult a specific section only when the user explicitly requests that legacy
repository convention.

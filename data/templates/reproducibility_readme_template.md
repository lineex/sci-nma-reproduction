# Reproducibility and Submission Package README

## Project

- Project ID: `PROJECT_ID`
- Manuscript title: `MANUSCRIPT_TITLE`
- Protocol: `review_protocol.json`
- Package manifest: `reporting/supplementary_materials_manifest.json`
- Submission checklist: `reporting/submission_package_checklist.csv`

## Runtime defaults

- Search: built-in CDP browser first; Chrome DevTools fallback.
- Full text: Zotero MCP (`cookjohn/zotero-mcp`) first; read-only local Zotero bridge fallback.
- Statistics: locked R environment, with exact versions recorded in `verification/analysis_manifest.json` and `renv.lock`.

## Reproduce

1. Review the approved protocol and methods-source log.
2. Confirm the search-strategy supplement contains one row per database search line, exact dates, limits, hit counts, export hashes, and peer-review status. Search-stage release requires one independent review after execution; downstream evidence-judgement stages retain two independent approvals.
3. Confirm Zotero retrieval and full-text screening manifests are hash-bound to the approved study/report map.
4. Restore the locked R environment with `renv.lock`.
5. Run the declared scripts in the order recorded in the analysis manifest.
6. Compare generated output hashes with the manifest and retain any documented deviations.

## Submission inventory

Complete the checklist and package manifest before release. Every required manuscript,
figure, table, supplement, code, dataset, and checklist must have a project-relative
path, source locator, SHA-256 hash, and two independent reporting approvals.

## Known limitations

Record access limitations, unresolved reports, OCR issues, author-contact outcomes,
and any analysis or reporting deviations here with links to the corresponding ledger
events and source artifacts.

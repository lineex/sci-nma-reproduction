# Supplementary Material: Complete Search Strategies (PRISMA-S aligned)

Use this form as the **source of truth** for the search appendix. Populate one CSV row for
**each executable line/set** exactly as displayed by the database interface (including field
tags, controlled vocabulary, punctuation, truncation, proximity operators, limits, and date
stamps). Do not paraphrase or silently repair a query. Export the completed CSV together
with the PRISMA-S checklist and raw search-history files.

## Package-level record

- Review/project ID: `[PROJECT_ID]`
- Review question/PICO: `[PICO_OR_RESEARCH_QUESTION]`
- Protocol version/date: `[VERSION; YYYY-MM-DD]`
- Search methods owner: `[NAME/ROLE]`
- Search peer reviewer: `[NAME/ROLE; DATE; METHOD]`
- Search update policy: `[RERUN_DATE_OR_TRIGGER; ALERTS; CONTACTS]`
- Deduplication software/version and batch: `[SOFTWARE; VERSION; BATCH_ID]`
- Total records across all sources before deduplication: `[N]`
- Total records exported to screening: `[N]`
- Search files and hashes: `[PATH; SHA-256]`
- PRISMA-S checklist: `prisma_s_checklist.csv`
- PRISMA 2020 item 6/7 evidence: `[MANUSCRIPT_LOCATION_OR_ARTIFACT]`

## Source block (repeat for every database, register, website, citation search, or other source)

- Source type: `[database | register | website | citation_search | contact | other]`
- Database/source name: `[DATABASE_OR_SOURCE]`
- Platform/interface: `[PLATFORM_AND_INTERFACE]`
- Host/provider: `[HOST_OR_VENDOR]`
- Coverage: `[INCEPTION_OR_START]` to `[END_DATE]`
- Search date/time/timezone: `[YYYY-MM-DD; HH:MM; TIMEZONE]`
- Search run/history identifier or query URL: `[ID_OR_URL]`
- Search version/run ID: `[RUN_ID; VERSION]`
- Searcher and peer reviewer: `[NAME; NAME; DATE; PRESS/OTHER METHOD]`
- Published filter used: `[NAME/VERSION/CITATION OR NONE]`
- Limits/restrictions: `[EXACT LIMITS OR NONE]`
- Rationale for each restriction: `[RATIONALE]`
- Prior strategy adapted: `[CITATION/DOI OR NONE]`
- Translation/adapter and syntax notes: `[NAME/TOOL; CHANGES; NONE]`
- Final set identifier and total: `[SET_ID; N]`
- Export: `[FORMAT; FILE; SHA-256; RECORD_COUNT]`
- Deduplication batch: `[BATCH_ID; SOFTWARE/VERSION]`
- Search update/rerun instructions: `[WHEN/WHY/HOW]`
- Evidence locator: `[HISTORY_FILE; SCREENSHOT; PAGE/LINE; MANUSCRIPT LOCATION]`

### Exact line-by-line history

| Line number | Line type (`concept`, `combination`, `limit`, `final`) | Exact statement copied verbatim | Concept block/field tags | Controlled vocabulary | Free-text terms | Filter/limit | Records returned | Final-set flag | Evidence locator |
|---:|---|---|---|---|---|---|---:|---|---|
| 1 | `[TYPE]` | `[PASTE EXACT INTERFACE LINE]` | `[BLOCK]` | `[TERMS]` | `[TERMS]` | `[NONE/EXACT]` | `[N]` | `no` | `[HISTORY/SCREENSHOT]` |
| 2 | `[TYPE]` | `[PASTE EXACT INTERFACE LINE]` | `[BLOCK]` | `[TERMS]` | `[TERMS]` | `[NONE/EXACT]` | `[N]` | `no` | `[HISTORY/SCREENSHOT]` |
| … | … | … | … | … | … | … | … | … | … |
| final | `final` | `[PASTE EXACT FINAL COMBINATION]` | `[ALL]` | `[TERMS]` | `[TERMS]` | `[NONE/EXACT]` | `[N]` | `yes` | `[HISTORY/SCREENSHOT]` |

### Source-specific notes

- Non-line-history source method (if applicable): `[COMPLETE URL/CONTACT/CITATION/BROWSING METHOD]`
- Citation chasing: `[BACKWARD/FORWARD; INDEX; DATE; COUNT]`
- Author/expert/manufacturer contacts: `[WHO; DATE; METHOD; RESPONSE/NO RESPONSE]`
- Search peer-review findings and resolution: `[FINDINGS; CHANGES; DATE]`
- Deviations from protocol and reason: `[DEVIATION; APPROVAL; DATE]`

## Release rules

1. The CSV, this rendered appendix, raw history/export files, and PRISMA-S checklist must
   describe the same run IDs, dates, line counts, and final totals.
2. `exact_line_copied_verbatim` is mandatory; an empty field means the search is not ready
   for release. If the interface provides no lines, preserve the complete query/URL and
   explain the method in the source block.
3. Every completed source must have an export or documented no-export reason, SHA-256 when
   a file exists, an evidence locator, and independent peer review/adjudication.
4. Report inaccessible history or failed retrieval as an access state, never as evidence
   that no records or no studies existed. Record the next rerun/manual-recovery action.
5. Before submission, reconcile source totals with the PRISMA flow ledger and lock the
   final CSV hash in `reporting/supplementary_materials_manifest.json`.

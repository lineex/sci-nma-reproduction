# Supplementary Material: Database-Native Search Strategies (PRISMA-S aligned)

Use this form as the **source of truth for the visible search-strategy appendix**.
The appendix is componentized: it shows each database's native syntax line by
line (concept blocks, filters, limits, and interface combination references),
not the collapsed one-line execution query. The complete executable query is
preserved as a separate, hash-bound execution artifact for audit and reruns.

## Search-concept policy

- For an intervention review, the default retrieval blocks are **P
  (population/problem)** and **I (intervention/exposure)**.
- **C (comparator)** and **O (outcome)** are omitted by default to protect
  sensitivity. Include either block only when the protocol records an explicit
  `search.include_comparator` or `search.include_outcome` decision, stable
  indexing/reporting, and a restriction rationale. This is not an absolute
  rule for diagnostic, prognostic, or other non-intervention questions.
- Study-design, language, human, publication-status, document-type, date, and
  other limits are separate lines. They are opt-in by default; each enabled
  restriction must have a protocol rationale and its own database-native
  syntax.
- Do not copy a collapsed private execution query into the rendered appendix.
  Record its relative artifact path and SHA-256 instead.

## Package-level record

- Review/project ID: `[PROJECT_ID]`
- Review question/PICOS: `[PICOS_OR_RESEARCH_QUESTION]`
- Protocol version/date: `[VERSION; YYYY-MM-DD]`
- Search concept policy: `[P+I default; C/O explicit opt-in; rationale]`
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
- Native syntax dialect/version: `[PubMed | Embase | Cochrane | WoS | Scopus; interface/version]`
- Comparator block included: `[yes/no; protocol rationale]`
- Outcome block included: `[yes/no; protocol rationale]`
- Private generated execution artifact: `[PROJECT-RELATIVE PATH; SHA-256]`
- Exact-as-run history/export record: `[PROJECT-RELATIVE PATH; SHA-256; STATUS]`
- Final collapsed query shown in appendix: `no (default)`
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

### Native line-by-line history

| Line | Line type (`concept`, `filter`, `limit`, `combination`) | Concept block | Native field tags | Controlled vocabulary | Free-text terms | Native syntax line | Records returned | Visible in appendix | Evidence locator |
|---:|---|---|---|---|---|---|---:|---|---|
| 1 | `concept` | `P` | `[FIELD TAGS]` | `[TERMS]` | `[TERMS]` | `[PASTE EXACT NATIVE LINE]` | `[N]` | `yes` | `[HISTORY/SCREENSHOT]` |
| 2 | `concept` | `I` | `[FIELD TAGS]` | `[TERMS]` | `[TERMS]` | `[PASTE EXACT NATIVE LINE]` | `[N]` | `yes` | `[HISTORY/SCREENSHOT]` |
| 3 | `filter/limit` | `S/L` | `[FIELD TAGS]` | `[FILTER TERMS]` | `[FILTER TERMS]` | `[PASTE EXACT NATIVE LINE]` | `[N]` | `yes` | `[HISTORY/SCREENSHOT]` |
| … | … | … | … | … | … | … | … | … | … |
| set reference | `combination` | `ALL` | `[INTERFACE SET SYNTAX]` | `[BLOCK REFERENCES]` | `[BLOCK REFERENCES]` | `[e.g., #1 AND #2 AND #3; do not paste collapsed private query]` | `[N]` | `yes` | `[HISTORY/SCREENSHOT]` |

## Release rules

1. The CSV, this rendered appendix, raw history/export files, and PRISMA-S
   checklist must describe the same run IDs, dates, line counts, and totals.
2. `native_syntax_line` is mandatory for every executable concept/filter/limit
   line. The generated plan is marked `planned_generated`; before release,
   replace or annotate it with the exact line copied from the relevant
   database interface/history or documented API response. Do not translate it
   into a generic pseudo-query.
3. The visible appendix must set `final_combination_displayed=no` by default and
   must point to the private execution artifact plus its SHA-256. If a journal
   explicitly requires the collapsed query, record the release exception,
   reviewer approval, and the exact artifact version before publication.
4. Every completed source must have an export or documented no-export reason,
   SHA-256 when a file exists, an evidence locator, and independent
   peer-review/adjudication.
5. Report inaccessible history or failed retrieval as an access state, never as
   evidence that no records or no studies existed. Record the next rerun/manual
   recovery action.
6. Before submission, reconcile source totals with the PRISMA flow ledger and
   lock CSV/appendix/execution-artifact hashes in
   `reporting/supplementary_materials_manifest.json`.

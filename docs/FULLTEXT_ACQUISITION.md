# Post-screen full-text acquisition and Zotero verification

This stage starts **after title/abstract screening** and only processes the
approved reports-sought scope. It preserves the distinction between a missing
bibliographic fact and an unavailable connector:

- `doi_not_present_lookup_unavailable`: the screened record has no DOI and
  Metapub was not installed or could not be reached;
- `doi_not_found_after_metapub_lookup`: Metapub completed its lookup and found
  no DOI;
- `multiple_metapub_doi_candidates`: title/year lookup returned conflicting
  DOI candidates; and
- `resolved_by_metapub` / `resolved_by_metapub_title`: a DOI was found with
  the lookup route recorded.

None of these states is treated as a zero result or as proof that a report is
not published.

## Run the form-first queue

```powershell
sci-nma-agent fulltext-acquire plan `
  --manifest screening/full_text_retrieval_manifest.json `
  --output screening/full_text_acquisition_queue.json
```

The queue contains the expected report identity, DOI-resolution evidence,
ScanSci PDF route, institutional-access checkpoint, Zotero write/readback
state, and a route ledger. Install the optional DOI resolver when needed:

```powershell
python -m pip install -e ".[fulltext]"
```

`metapub` is loaded lazily. If it is not installed, the queue remains valid and
routes the report to the manual identifier queue rather than fabricating a DOI.

## DOI to PDF through ScanSci PDF

For a resolved DOI, run one record at a time so the PDF hash and connector
response are bound to the report:

```powershell
sci-nma-agent fulltext-acquire download `
  --queue screening/full_text_acquisition_queue.json `
  --study-id STUDY_ID --report-id REPORT_ID `
  --output-dir original_materials/scansci_pdf/run-0001
```

The adapter calls the installed `scansci-pdf get DOI` connector, records the
command/stdout/stderr, chooses the produced PDF, hashes it, and marks repeated
content as `duplicate` by SHA-256. The project does not embed publisher
passwords or scrape credentials. Configure ScanSci PDF outside this repository
and retain its own route/session evidence.

When the connector reports a paywall or institutional login, the status is
`carsi_user_action_required`. Complete the university's CARSI, WebVPN, or
library SSO in the user-visible browser, confirm the session, and rerun the
same queued record. The queue remains open until a PDF is produced and hashed;
no failed download is reclassified as a factual absence.

## Zotero import and readback

After reviewing the DOI/PDF target, explicitly authorize the write call:

```powershell
sci-nma-agent fulltext-acquire zotero-push `
  --queue screening/full_text_acquisition_queue.json `
  --study-id STUDY_ID --report-id REPORT_ID `
  --collection "Review full text" `
  --pdf original_materials/scansci_pdf/run-0001/STUDY_REPORT.pdf `
  --refresh-metadata --confirm-write
```

The write facade only calls capabilities advertised by the live Zotero MCP
schema. It can request identifier import, PDF attachment, and metadata refresh
when those write tools are available. It never assumes a tool name or silently
falls back to a mutation. If the server exposes only read tools, finish the
import/attachment in Zotero Desktop and use the existing `manual-fulltext
confirm` checkpoint.

Read the exact item back through MCP and generate a table-ready discrepancy
report:

```powershell
sci-nma-agent fulltext-acquire zotero-verify `
  --queue screening/full_text_acquisition_queue.json `
  --study-id STUDY_ID --report-id REPORT_ID `
  --item-key ZOTERO_ITEM_KEY `
  --output verification/zotero_metadata_discrepancies.csv
```

The verification compares DOI, PMID, title, and year. Any mismatch or missing
field is written to the CSV with severity, status, and the MCP tool locator;
the queue is marked `metadata_mismatch` and downstream full-text review stays
blocked until the discrepancy is corrected and read back again. An empty table
is the successful identity result, not a reason to skip provenance.

## Release requirements

Submit these artifacts with the full-text retrieval stage:

1. `screening/full_text_retrieval_manifest.json`;
2. `screening/full_text_acquisition_queue.json` and its SHA-256;
3. retained PDF and SHA-256 (or the manual queue row when access remains
   unresolved);
4. Zotero item/attachment keys and raw MCP read/write evidence; and
5. `verification/zotero_metadata_discrepancies.csv` with a zero-row or resolved
   status.

Two independent stage reviews are still required. The acquisition queue does
not replace the existing eligibility, extraction, or fact-status ledgers.

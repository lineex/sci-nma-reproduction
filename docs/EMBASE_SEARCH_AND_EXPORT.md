# Embase Search and Export Contract

Use this reference whenever the database queue contains `Embase.com`. It is
the database-specific supplement to the generic search queue and does not
replace the approved protocol, native strategy, or stage ledger.

## 1. Session gate

1. Run `embase-session` before search, paging, or export.
2. Continue only when the host is `embase.com`, a real search/results surface
   is visible, and no sign-in, institutional-access, CAPTCHA, or verification
   wall dominates the page.
3. Do not treat a login page, a DOI/publisher page, or a failed export page as
   a completed search. Pause the queue and preserve the same-tab checkpoint
   when user action is required.

## 2. Search History and identifiers

Embase exposes two different identifiers:

- `searchNo`: the visible Search History line number, used for human audit.
- `searchId`: the REST search identifier, recovered from the authenticated
  network request containing `/rest/execute-search?searchId=` after the line is
  run.

Record both. Never substitute one for the other. Keep the exact native query,
line number, count, date/timezone, database edition, and browser route in the
search supplement.

## 3. Line execution policy

- Execute component, limit, and filter lines for counts only.
- Execute the final primary combination separately and export its detailed
  records only.
- Execute the validated RCT/sensitivity combination separately; never append
  it to the primary corpus.
- If Embase presents separate result types, treat **Articles** and **Clinical
  trials** as separate export streams and sum them only in the evidence
  manifest when the database reports them as mutually exclusive.

## 4. Retrieval order

Prefer the authenticated REST route for complete records. Use the native UI
and Search History to establish the query, then retrieve pages with one of the
following routes:

### Direct result endpoint

```text
/rest/article-search-results?offset=OFFSET&size=200&order=PUBLICATION_DATE&searchId=SEARCH_ID
/rest/ct-search-results?offset=OFFSET&size=200&order=PUBLICATION_DATE&searchId=SEARCH_ID
```

The direct endpoint returns structured records and a database hit total. Keep
`size=200`, advance `offset` by the returned record count, and retain the
response JSON/NDJSON with all fields needed for screening: title, authors,
abstract, source, year, DOI, PMID, Embase identifier/PUI, publication type,
links, and index terms when present.

### Stable page-activation fallback

If the direct endpoint is unavailable or returns a transient error, activate
each page first:

```text
/rest/execute-search?searchId=SEARCH_ID&page=PAGE&pageSize=200&orderby=PUBLICATION_DATE
/rest/searchresults/results?offset=0&size=200
```

In this flow `offset=0` is page-local. Do not send a global offset to the
second endpoint. Do not run page activations in parallel because the result
surface is session-scoped.

### Reliability

- Pace requests at roughly one request cycle per second.
- Retry 429 and transient 5xx responses with bounded exponential backoff and
  preserve the response status in the evidence log.
- If the browser navigates away or the REST request loses the search context,
  return to Embase, rerun the Search History line, and reacquire `searchId`.
- A failed request, blocked page, or incomplete response is an unresolved
  retrieval state, never a zero-result search.

## 5. Native RIS download window

The Embase UI submits `POST /rest/export/records` and commonly opens a new
`https://www.embase.com/search/download` window. The popup may not appear in
the browser tab inventory even though the export job is active.

1. Select the final-combination batch and open **Export**.
2. In the export dialog choose RIS and keep full citation/abstract/index-term
   fields appropriate for screening.
3. Submit the dialog and capture the `Page.windowOpen` event or the generated
   `/search/download` page.
4. If the popup is not bindable, create or bind an authenticated Embase tab at
   `/search/download`. Poll until **Ready for download** and a
   `/rest/download/.../records.ris` link is visible.
5. Start `waitForEvent('download')` before clicking **Download**, then save the
   file into the project export directory.
6. Validate the file by counting RIS `TY  -` and `ER  -` records, compare the
   count with the selected batch, calculate SHA-256, and record the download
   URL, search ID, result type, offset, requested count, actual count, and
   timestamp.

The current Embase export endpoint accepts up to 10,000 records per RIS batch
and rejects offsets greater than 50,000. Treat an HTTP 400 for a larger offset
as an export-cap signal, not as a failed search. Use the direct REST route for
the remaining offsets and save those records as hash-bound NDJSON/JSON. Do not
silently relabel REST records as RIS exports.

## 6. Export completeness and release gate

The Embase checkpoint must include:

- frozen formal count and any later rerun count, kept as separate values;
- Article and Clinical-trial totals for each final combination;
- every RIS batch range and SHA-256;
- every REST page range/file/hash;
- the final database total and the number of detailed records actually
  written;
- missing ranges, if any, and the next recovery action.

The Embase task is not complete until all final primary and validated RCT
records are captured, the range union is contiguous or explicitly reconciled,
and the queue/integrity audit passes. Component counts never enter the
screening corpus.

---
name: wos-search
description: Reliable Web of Science search through the built-in CDP browser, with Chrome DevTools as fallback and the Clarivate Starter API available for protocol-recorded export or independent checking. Use when exact WoS counts, accession IDs, DOI metadata, or full multi-page harvesting is needed.
---

# Web Of Science Search

Use the built-in CDP browser as the primary search transport and Chrome
DevTools as the fallback. The Clarivate Starter API may be used for a
protocol-recorded export or independent check after the browser route; it is
not the default transport for a new review.

## Browser-First Path

Start in the authenticated built-in CDP browser and retain the search/session evidence. If that session is unavailable, use Chrome DevTools. After the browser search is recorded, an optional Clarivate Starter API export or independent check may use `https://api.clarivate.com/apis/wos-starter/v1/documents` with:
- `X-ApiKey`
- `db=WOS`
- `limit=50`
- `page=<n>`
- `sortField=<value>`

Capture at least:
- total count
- WoS accession/UID
- title
- authors
- source
- year
- document type
- DOI
- citation counts

## Query Construction

Use native WoS syntax:
- `TS=` topic
- `TI=` title
- `AU=` author
- `SO=` source
- `DO=` DOI
- `PY=` publication year

For systematic retrieval, prefer English query terms and explicit document-type filters such as:
`DT=(Article OR Review) NOT DT=(Meeting Abstract OR Proceedings Paper)`

## Large Result Sets

If the query is broad, partition by publication year:
- run `(<base query>) AND PY=YYYY`
- page each year separately
- merge normalized records afterward

This is more reliable than trying to harvest one very large result set in a single sequence.

## Reliability Rules

- Assume Starter API page size is capped at 50.
- Keep gentle pacing between requests even if the key allows more.
- Respect `Retry-After` on `429`.
- Back off and retry on transient `5xx` failures.
- Some academic VPN or proxy routes may cause TLS EOF errors. Retry first. Only relax SSL verification if the connection path is otherwise unusable, and record that choice explicitly.

## API Export or Browser Recovery

If the browser session cannot be used or an API export is needed after the browser run:
- require an authenticated `webofscience.com` session
- use the browser search page or Search History
- remember that the page/export path is limited to 50 records per page
- if exporting from Search History, select the history line first

## Practical Notes

- For exact counts and reproducibility, retain the browser query, authenticated session evidence, visible count, and any API export/check together; an API response does not replace the required browser/session record.
- If the user provides Chinese keywords for WoS Core Collection, translate them into English and state the translation.
- When the user wants a top-N browse only, a single API page is sufficient. When the user wants the full set, plan the year partitions and all pages up front.

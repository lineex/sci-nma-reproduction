---
name: wos-search
description: Reliable Web of Science search with the Clarivate Starter API as the primary path and authenticated browser export as fallback. Use when exact WoS counts, accession IDs, DOI metadata, or full multi-page harvesting is needed.
---

# Web Of Science Search

Prefer the Clarivate Web of Science Starter API when an API key is available. Use the browser UI only as a fallback when the API cannot be used.

## Preferred Path: Starter API

Use `https://api.clarivate.com/apis/wos-starter/v1/documents` with:
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

## Browser Fallback

If no API key is available:
- require an authenticated `webofscience.com` session
- use the browser search page or Search History
- remember that the page/export path is limited to 50 records per page
- if exporting from Search History, select the history line first

## Practical Notes

- For exact counts and reproducibility, API results are preferred over visible browser pages.
- If the user provides Chinese keywords for WoS Core Collection, translate them into English and state the translation.
- When the user wants a top-N browse only, a single API page is sufficient. When the user wants the full set, plan the year partitions and all pages up front.

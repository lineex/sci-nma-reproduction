---
name: embase-web-search
description: Reliable authenticated Embase search and bulk retrieval through the embase.com web UI plus REST pagination. Use when exact counts, PMID/DOI extraction, Search History execution, or full multi-page harvesting is needed.
---

# Embase Web Search

Use this skill after `embase-session` confirms that the browser session is ready.

## Query Style

Build native Embase syntax, for example:
- Emtree explosions: `'multiple trauma'/exp`
- fields: `:ti,ab,kw`
- limits: `[english]/lim`, `[humans]/lim`, `[2000-2026]/py`

Keep the exact final query for reporting.

## Preferred Retrieval Path

Do not depend on manual export for full retrieval. Prefer the embase.com web REST sequence behind Search History.

## Workflow

1. Use `embase-session`.
2. Run the query in Embase Advanced Search and confirm the Search History line exists.
3. Treat the visible Search History number as `searchNo` only. It is not the same as the REST `searchId`.
4. Extract the latest `searchId` from recent network resource URLs after running the line. Inspect browser performance entries for a URL containing:

```text
/rest/execute-search?searchId=
```

5. For each page:
   - call `/rest/execute-search?searchId=...&page=N&pageSize=200&orderby=RELEVANCE`
   - then read `/rest/searchresults/results?offset=0&size=200`
6. Change `page` on `execute-search` for subsequent pages.
7. Keep `offset=0` after each page activation. In this flow, `offset` is page-local, not a global record offset.

## Extract

Capture at least:
- title
- authors
- year
- source/journal
- DOI
- PMID when present
- Embase/Luwak identifier
- result URL

## Reliability Rules

- Use `pageSize=200`, which is the stable large-page size observed in the web UI.
- Pace requests at about 1 request cycle per second.
- Retry `429` and transient `5xx` responses with backoff.
- If the browser has gone to a DOI/publisher page and the network history no longer shows Embase REST requests, return to Embase, rerun the history line, and reacquire `searchId`.
- Exact full retrieval does not require file download or RIS export.

## Practical Notes

- Search History line numbers are useful for human tracking but not enough for REST paging.
- If the session is anonymous, exact browsing may still work, but institutional login is preferable for stable systematic-review retrieval.

---
name: pm-advanced-search
description: Reliable advanced PubMed search via NCBI E-utilities with field tags, MeSH terms, date ranges, publication types, and reproducible query translation. Use when exact PubMed syntax, protocol-grade search strings, or bulk harvesting of advanced searches is needed.
---

# PubMed Advanced Search

Use the Codex built-in CDP browser as the primary search transport. Chrome
DevTools is only a documented fallback when the built-in browser is unavailable
or cannot perform a required operation. Build the exact PubMed syntax first;
use E-utilities for protocol-recorded export or independent checking after
the browser route, not as a silent replacement for browser/session evidence.
Follow the project
[`BROWSER_ROUTE_POLICY.md`](../../docs/BROWSER_ROUTE_POLICY.md).
When this search belongs to a `sci-nma-reproduction` project with an active
browser queue, also follow [`SEARCH_QUEUE.md`](../../docs/SEARCH_QUEUE.md):
execute only the first unchecked native line, persist its count and locator
with `search-queue record-line`, and resume from the saved checklist after an
interruption. Do not batch-run the remaining lines from this helper skill.

## Common Field Tags

| Need | Tag |
|---|---|
| Title/Abstract | `[Title/Abstract]` or `[TIAB]` |
| Title only | `[Title]` or `[TI]` |
| Author | `[Author]` or `[AU]` |
| Journal | `[Journal]` or `[TA]` |
| MeSH term | `[MeSH Terms]` |
| Publication type | `[Publication Type]` or `[PT]` |
| Publication date | `[Date - Publication]` or `[DP]` |
| Language | `[Language]` or `[LA]` |

## Workflow

1. Translate the request into exact PubMed syntax with uppercase boolean operators.
2. Add limits explicitly rather than implying them. Examples:
   - date range
   - `english[Language]`
   - `NOT (animals[MeSH Terms] NOT humans[MeSH Terms])`
3. Record the exact-as-run query, visible count, history/query locator, browser
   route, and session evidence. When approved by the protocol, execute the
   corresponding E-utilities request as an export or independent check and
   capture:
   - exact query
   - `querytranslation`
   - total count
4. Batch record metadata with `esummary.fcgi`.
5. Use `efetch.fcgi` when abstract text, XML fields, or article ID confirmation is required.
6. For broad protocol-style searches, partition by year if one pass is too large or unstable.

## Reliability Rules

- Keep the Codex built-in CDP browser as the primary protocol search route.
- Use E-utilities only for protocol-recorded export or independent checking.
- When E-utilities is used, also report the PubMed `querytranslation`.
- Keep conservative rate limiting even when an API key is available.
- Retry on `429` and transient server/network failures with backoff.
- When a broad query hits retrieval ceilings, repair the run with year partitions instead of returning a partial result set.

## Output Expectations

Return at least:
- exact query
- translated query
- total results
- PMID
- DOI
- title
- authors
- journal/source
- year/date
- publication type

## Practical Notes

- For quick visual confirmation, optionally open `https://pubmed.ncbi.nlm.nih.gov/?term={URL_ENCODED_QUERY}` after the query is finalized.
- Keep MeSH terms and free-text terms together when the user wants high recall.
- If the user provides a PMID or DOI directly, use `pm-paper-detail` instead of rerunning a broad search.

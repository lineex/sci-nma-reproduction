---
name: pm-advanced-search
description: Reliable advanced PubMed search via NCBI E-utilities with field tags, MeSH terms, date ranges, publication types, and reproducible query translation. Use when exact PubMed syntax, protocol-grade search strings, or bulk harvesting of advanced searches is needed.
---

# PubMed Advanced Search

Use this skill when the query must be explicit and reproducible. Build the exact PubMed syntax first, then execute through E-utilities instead of relying on page DOM behavior.

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
3. Execute with `esearch.fcgi` and always capture:
   - exact query
   - `querytranslation`
   - total count
4. Batch record metadata with `esummary.fcgi`.
5. Use `efetch.fcgi` when abstract text, XML fields, or article ID confirmation is required.
6. For broad protocol-style searches, partition by year if one pass is too large or unstable.

## Reliability Rules

- Prefer E-utilities over browser-only search for exact counts and exportable identifiers.
- Always show the exact query and PubMed `querytranslation` in the final response.
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

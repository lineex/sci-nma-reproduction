---
name: ch-advanced-search
description: Reliable Cochrane Library advanced search via the real advanced-search form and results portlet flow. Use when exact section counts, review/protocol/CENTRAL separation, or full multi-page harvesting is needed.
---

# Cochrane Advanced Search

Do not treat Cochrane advanced search as a simple query-string page. The stable path is the real advanced-search form plus the results portlet.

## Preferred Entry

Open:

```text
https://www.cochranelibrary.com/advanced-search?q=&t=1
```

Always include:

```text
initScript: "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
```

## Primary Flow

1. Establish session cookies by opening the advanced-search page.
2. Submit the real advanced-search form, not a guessed URL.
3. Use the Cochrane validation endpoint first:

```text
/en/advanced-search?p_p_id=scolarissearchresultsportlet_WAR_scolarissearchresults&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=validate-advanced-search&p_p_cacheability=cacheLevelPage&p_p_col_id=column-1&p_p_col_count=2
```

4. Submit the same serialized form to the results portlet:

```text
/en/c/portal/render_portlet?p_l_id=20761&p_p_id=scolarissearchresultsportlet_WAR_scolarissearchresults&p_p_lifecycle=0&p_t_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_pos=1&p_p_col_count=2&p_p_isolated=1&currentURL=%2Fadvanced-search%3Fq%3D%26t%3D1
```

5. Parse section tabs and counts from `.search-results .tab`.
6. Harvest each section separately through the generated tab URLs using:
   - `selectedType=review`
   - `selectedType=protocol`
   - `selectedType=central`
7. Set `resultPerPage=100` and iterate `cur=1..N`.

## Core Form Fields

Use these fields for reproducible bulk search:
- `searchType=advanced`
- `database=`
- `status=`
- `publicationYear=between`
- `startPublicationYear=2000`
- `endPublicationYear=<end year>`
- `publicationDate=alldates`
- `wordVariation=true`
- `controlOptions=AND`
- `searchOptions=6`
- `searchText=<query>`
- repeated `cochraneReviews=review`, `protocol`, `central`

`searchOptions=6` means All Text.

## Extract

Capture at least:
- section counts for Reviews, Protocols, CENTRAL
- title
- DOI from `.access[data-article-doi]`
- CD number or CENTRAL CN accession
- authors
- visible type/stage/date
- result URL

## Reliability Rules

- For exact counts, trust the tab counts from the advanced-search result surface, not a simplified hand-built GET URL.
- Validate that the tab counts remain stable after switching `selectedType`.
- If the page shows an authentication wall, CAPTCHA, or access block, stop and ask the user to resolve it in Chrome.
- If using external HTTP requests instead of in-browser fetch, transient TLS EOF errors can occur; retry with conservative pacing and record any SSL workarounds explicitly.

## Limitation To Record

The current Cochrane advanced-search form exposes `publicationYear=between` mainly as a CENTRAL original-publication-year control. Do not silently claim that this is an equivalent strict review/protocol date filter; record that limitation when reporting methods.

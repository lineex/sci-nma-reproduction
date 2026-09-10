---
name: scopus-search
description: Search Scopus documents by keyword through Chrome DevTools MCP and extract structured result metadata including EID, title, authors, source, year, DOI, cited-by count, and result links.
argument-hint: [search keywords]
---

# Scopus Basic Document Search

Use this skill when the user wants a keyword search in Scopus.

## Step 1: Ensure Access

If the browser is not already authenticated in Scopus, run `scopus-login`.

Set `BASE_URL` from the active Scopus or proxy origin.

## Step 2: Search

Preferred route:

1. Navigate to:

```text
{BASE_URL}/search/form.uri?display=basic
```

2. Use `evaluate_script` to fill the document search field and submit.

```javascript
async (query) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  for (let i = 0; i < 20; i++) {
    if (document.querySelector('input, textarea')) break;
    await new Promise(r => setTimeout(r, 500));
  }

  const fields = [...document.querySelectorAll('input[type="text"], input[type="search"], textarea')];
  const searchField =
    fields.find(el => /search documents|search within|document/i.test(el.getAttribute('aria-label') || el.placeholder || '')) ||
    fields.find(el => !el.disabled && el.offsetParent !== null) ||
    fields[0];
  if (!searchField) return { error: 'No visible Scopus search input found.' };

  searchField.focus();
  searchField.value = query;
  searchField.dispatchEvent(new Event('input', { bubbles: true }));
  searchField.dispatchEvent(new Event('change', { bubbles: true }));

  const buttons = [...document.querySelectorAll('button, input[type="submit"]')];
  const btn = buttons.find(el => /search/i.test(norm(el.innerText) || el.value || el.getAttribute('aria-label')));
  if (btn) btn.click();
  else searchField.form?.submit();

  return { submitted: true, query, url: location.href };
}
```

Fallback route if form automation fails:

```text
{BASE_URL}/results/results.uri?sort=plf-f&src=s&sot=b&sdt=b&sl={QUERY_LENGTH}&s=TITLE-ABS-KEY({ENCODED_QUERY})&origin=searchbasic
```

## Step 3: Check Access

After submitting, run a compact access check:

- Login/SSO page: ask the user to authenticate in the browser.
- CAPTCHA/browser verification: ask the user to complete it in the browser.
- Scopus preview or entitlement warning: explain that full access is needed for
  export and some detail fields.
- Results page or no-results message: proceed.

## Step 4: Extract Results

Use `evaluate_script`. Do not use `wait_for`.

```javascript
async () => {
  for (let i = 0; i < 30; i++) {
    const hasResults = document.querySelector('a[href*="record/display"], a[href*="/pages/publications/"]');
    const hasNoResults = /no documents found|0 documents|no results/i.test(document.body?.innerText || '');
    if (hasResults || hasNoResults) break;
    await new Promise(r => setTimeout(r, 500));
  }

  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const eidFromHref = href => {
    try {
      const u = new URL(href, location.href);
      return u.searchParams.get('eid') ||
        (u.pathname.match(/\/(?:pages\/publications|record\/display)[\/?]([^/?#]+)/i) || [])[1] ||
        '';
    } catch {
      return '';
    }
  };
  const doiFromText = text => (text.match(/\b10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i) || [''])[0];
  const yearFromText = text => (text.match(/\b(19|20)\d{2}\b/) || [''])[0];
  const citedFromText = text => {
    const m = text.match(/cited by\s*([0-9,]+)/i) || text.match(/([0-9,]+)\s+citations?/i);
    return m ? m[1].replace(/,/g, '') : '';
  };

  const anchors = [...document.querySelectorAll('a[href*="record/display"], a[href*="/pages/publications/"]')];
  const seen = new Set();
  const papers = [];

  for (const a of anchors) {
    const title = clean(a.innerText || a.textContent);
    const href = a.href;
    const eid = eidFromHref(href);
    const key = eid || href;
    if (!title || title.length < 8 || seen.has(key)) continue;
    seen.add(key);

    const row = a.closest('tr, li, article, [role="row"], [data-testid], .result-item, .document-result') || a.parentElement;
    const text = clean(row?.innerText || a.parentElement?.innerText || '');
    const authorLinks = [...(row || document).querySelectorAll('a[href*="author"], a[href*="authid"]')]
      .map(x => clean(x.innerText))
      .filter(Boolean)
      .slice(0, 12);

    papers.push({
      rank: papers.length + 1,
      title,
      eid,
      doi: doiFromText(text),
      year: yearFromText(text),
      citedBy: citedFromText(text),
      authors: [...new Set(authorLinks)],
      snippet: text.slice(0, 600),
      url: href
    });
  }

  const body = clean(document.body?.innerText || '');
  const total =
    (body.match(/([0-9,]+)\s+documents?/i) || body.match(/results?\s*[:\-]?\s*([0-9,]+)/i) || [])[1] || '';

  return {
    url: location.href,
    title: document.title,
    totalResults: total,
    papers: papers.slice(0, 25),
    empty: papers.length === 0 && /no documents found|no results/i.test(body)
  };
}
```

## Step 5: Present Results

Use this format:

```text
Found: {totalResults or unknown}

1. {title}
   Authors: {authors}
   Year: {year} | Cited by: {citedBy}
   DOI: {doi}
   EID: {eid}
   URL: {url}
```

## Notes

- EID is the primary key for follow-up Scopus detail/export workflows.
- DOI is the best key for publisher full text and Zotero metadata.
- Keep extracted output compact. Do not paste raw page text.
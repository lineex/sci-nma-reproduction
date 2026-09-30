# Environment and Application Defaults

This document is the required runtime configuration for a new evidence-
synthesis project. It is a project implementation standard, not a claim that
the Cochrane Handbook mandates a particular browser, connector, or package.
The values are copied into `review_protocol.json` under
`execution_defaults` when a project is initialized and are checked during
protocol preflight.

## Required Defaults

| Function | Primary | Fallback | Required behavior |
|---|---|---|---|
| Literature search | `cdp_builtin_browser` | `chrome_devtools` | Try the built-in CDP browser first, then the Chrome DevTools session. Reuse the authenticated session and retain the browser/session evidence used for each search. |
| Zotero full text | `zotero_mcp` using [`cookjohn/zotero-mcp`](https://github.com/cookjohn/zotero-mcp) | `zotero_local_read_only` | Discover the active MCP schema at runtime, use only advertised read capabilities, and fall back to the local SQLite/JSON bridge when the MCP endpoint is unavailable. |
| Statistical synthesis | `R` | An explicitly documented validated engine | New projects start with R. Pairwise work defaults to `meta`/`metafor`, frequentist NMA to `netmeta`, and the environment is locked with `renv.lock`. Python is orchestration and QA only. |

The fallback order is deterministic:

```text
search:    cdp_builtin_browser -> chrome_devtools
full_text: zotero_mcp -> zotero_local_read_only
statistics: R (no silent Python production fallback)
```

## Operational Rules

1. Search agents must select the built-in CDP browser before opening or
   attaching to a Chrome DevTools session. A search may use database APIs for
   export or independent checking only when the approved protocol records that
   route; an API response does not silently replace the required browser
   session evidence.
2. The Zotero MCP connection is the default full-text application path. Run
   `sci-nma-agent zotero-mcp-check` before collection export. The connected
   server's discovered tool schemas are authoritative. Preserve collection,
   item, attachment, raw-response, extracted-text, and locator hashes. If MCP
   is unavailable, record the connection state and use the read-only local
   adapter; do not claim that an MCP call succeeded.
3. `sci-nma-agent init PROJECT` creates the default protocol and
   `verification/analysis_manifest.json`. Before synthesis, replace the R
   placeholders with the exact R version, package versions, `renv.lock`,
   script paths, seed/deterministic-analysis rationale, and output hashes.
4. `sci-nma-agent init PROJECT` also creates the form-first reporting package
   under `reporting/`: line-by-line search supplement, supplementary-materials
   manifest, submission checklist, manuscript/cover-letter starters,
   reproducibility README, and risk-of-bias/synthesis/certainty tables.
   Reporting release requires required artifacts to be present, hashed,
   source-located, and independently approved.
5. A project may explicitly select Stata or another validated production
   engine when the protocol records the rationale, exact versions, runtime
   lock, and independent verification. This does not change the new-project
   default and does not make the bundled Python calculators production
   estimators.
6. Publication reproduction and calibration are separate routes. They follow
   the source study's browser, Zotero, and statistical software settings when
   fidelity to the published analysis is the objective; they do not inherit
   these new-review defaults automatically.

## Protocol Contract

The initialized protocol contains the following machine-readable defaults:

```json
{
  "execution_defaults": {
    "search": {
      "primary_browser": "cdp_builtin_browser",
      "fallback_browser": "chrome_devtools",
      "fallback_order": ["cdp_builtin_browser", "chrome_devtools"]
    },
    "full_text": {
      "primary_connector": "zotero_mcp",
      "primary_server": "cookjohn/zotero-mcp",
      "fallback_connector": "zotero_local_read_only",
      "fallback_order": ["zotero_mcp", "zotero_local_read_only"]
    },
    "statistics": {
      "primary_engine": "R",
      "pairwise_packages": ["meta", "metafor"],
      "frequentist_nma_package": "netmeta",
      "runtime_lock": "renv.lock",
      "python_role": "orchestration_and_qa_only"
    }
  }
}
```

The protocol's `synthesis.software` section records the actual locked engine
used for the project. The `execution_defaults` block records the required
starting configuration and is not a substitute for actual version, package,
runtime, or result hashes.

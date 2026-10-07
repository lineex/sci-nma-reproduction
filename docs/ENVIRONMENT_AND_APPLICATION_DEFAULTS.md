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
| Literature search | `cdp_builtin_browser` | `chrome_devtools` | Try the built-in CDP browser first, then the Chrome DevTools session. Execute databases through `search/browser_search_queue.json` in strict ordinal order, with one active browser task and no parallel browser calls. Reuse the authenticated session and retain the browser/session evidence used for each search. The optional DevTools endpoint is local-only and must use a dedicated non-default Chrome profile. |
| Post-screen identifiers/full text | `metapub` → `scansci_pdf` → `zotero_mcp` | manual queue → `zotero_local_read_only` | Resolve a missing DOI with Metapub, download through the configured ScanSci PDF connector, pause for user CARSI/WebVPN authentication at a paywall, explicitly authorize Zotero MCP import/attachment writes, then read the exact item back and emit a discrepancy table. |
| Zotero full-text readback | `zotero_mcp` using [`cookjohn/zotero-mcp`](https://github.com/cookjohn/zotero-mcp) | `zotero_local_read_only` | Discover the active MCP schema at runtime, use advertised read capabilities, and fall back to the local SQLite/JSON bridge when the MCP endpoint is unavailable. |
| Statistical synthesis | `R` | An explicitly documented validated engine | New projects start with R. Pairwise work defaults to `meta`/`metafor`, frequentist NMA to `netmeta`, and the environment is locked with `renv.lock`. Python is orchestration and QA only. |

The fallback order is deterministic:

```text
search:    cdp_builtin_browser -> chrome_devtools
full_text: metapub -> scansci_pdf -> zotero_mcp(read/write with confirmation) -> manual queue -> zotero_local_read_only
statistics: R (no silent Python production fallback)
```

## Operational Rules

1. Search agents must select the built-in CDP browser before opening or
   attaching to a Chrome DevTools session. A search may use database APIs for
   export or independent checking only when the approved protocol records that
   route; an API response does not silently replace the required browser
   session evidence.
   - Browser database calls are serialized by the project search queue. Claim
     only the next ordinal, keep `max_active_tasks=1`, and complete its
     history/export evidence before claiming another database. A verification,
     SSO, or recoverable connector error pauses the current task and resumes it
     explicitly; it does not start a second browser task.
   - The built-in browser is the preferred route and does not require exposing a
     user's normal Chrome profile through a debugging port.
   - The optional Chrome DevTools fallback must bind to `127.0.0.1`,
     `localhost`, or `::1` only. Network, VPN, and public IP endpoints are
     rejected before connection.
   - Use a dedicated non-default `--user-data-dir`. Chrome 136 and later
     ignore remote-debugging switches for the default Chrome data directory;
     isolating the profile also prevents the debugging session from exposing
     the user's everyday cookies. See the
     [Chrome security change](https://developer.chrome.com/blog/remote-debugging-port?hl=zh-cn)
     for the upstream rationale.
   - The CDP preflight validates `/json/version`, the browser identity, and the
     advertised loopback WebSocket endpoint. An unsafe, incomplete, or
     unreachable endpoint is recorded as a failed fallback and never treated as
     a zero-result search.
   - **Automation-visibility status (updated 2026-09-30):** the Chrome
     fallback applies `--disable-blink-features=AutomationControlled` in both
     headed and headless launch modes. The project does not inject JavaScript
     property overrides or suppress site verification. A verification page is
     paused as a user-action checkpoint and resumed in the same authenticated
     profile. This addresses the known Blink AutomationControlled branch while
     retaining the loopback/profile/session safeguards.
   - Search formulation follows a sensitivity-first PICOS policy for
     intervention reviews: P and I are required; C and O are optional and
     omitted by default. Enabling C or O requires stable indexing/reporting,
     a protocol rationale, and a search-supplement record. Diagnostic,
     prognostic, and other non-intervention questions may declare a different
     concept structure.
   - Language, date, human, publication-status, document-type, and
     study-design limits are opt-in rather than global defaults. Each enabled
     restriction is recorded with a database-specific rationale and native
     syntax; CENTRAL is not assigned a generic trials/human filter.
   - The visible supplement is componentized by database-native lines. It
     records the exact native concept/filter/limit syntax and interface set
     combination, while the collapsed generated execution query remains a
     separate hash-bound artifact referenced by path and SHA-256. Generated
     lines are marked planned until the exact-as-run history/export, totals,
     date/timezone, and peer review are attached.
2. After screening, build the acquisition queue with
   `sci-nma-agent fulltext-acquire plan`. Resolve missing DOI values with the
   optional Metapub connector, then call the configured ScanSci PDF connector
   by DOI. Treat `carsi_user_action_required` as a user-visible institutional
   login checkpoint, not a failed fact. Deduplicate by DOI and then PDF
   SHA-256. Push identifiers/PDFs to Zotero only after explicit confirmation,
   read the exact Zotero item back through MCP, and write
   `verification/zotero_metadata_discrepancies.csv` for any DOI/PMID/title/year
   mismatch. Downstream full-text review remains blocked while discrepancies
   are open.
3. The Zotero MCP connection is the default full-text readback path. Run
   `sci-nma-agent zotero-mcp-check` before collection export. The connected
   server's discovered tool schemas are authoritative. Preserve collection,
   item, attachment, raw-response, extracted-text, and locator hashes. If MCP
   is unavailable, record the connection state and use the read-only local
   adapter; do not claim that an MCP call succeeded.
4. `sci-nma-agent init PROJECT` creates the default protocol and
   `verification/analysis_manifest.json`. Before synthesis, replace the R
   placeholders with the exact R version, package versions, `renv.lock`,
   script paths, seed/deterministic-analysis rationale, and output hashes.
5. `sci-nma-agent init PROJECT` also creates the form-first reporting package
   under `reporting/`: line-by-line search supplement, supplementary-materials
   manifest, submission checklist, manuscript/cover-letter starters,
   reproducibility README, and risk-of-bias/synthesis/certainty tables.
   Reporting release requires required artifacts to be present, hashed,
   source-located, and independently approved.
6. A project may explicitly select Stata or another validated production
   engine when the protocol records the rationale, exact versions, runtime
   lock, and independent verification. This does not change the new-project
   default and does not make the bundled Python calculators production
   estimators.
7. Publication reproduction and calibration are separate routes. They follow
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
      "fallback_order": ["cdp_builtin_browser", "chrome_devtools"],
      "execution_mode": "strict_serial_queue",
      "max_active_tasks": 1,
      "parallel_browser_calls": false,
      "queue_path": "search/browser_search_queue.json"
    },
    "full_text": {
      "primary_connector": "zotero_mcp",
      "primary_server": "cookjohn/zotero-mcp",
      "fallback_connector": "zotero_local_read_only",
      "fallback_order": ["zotero_mcp", "zotero_local_read_only"],
      "doi_resolver": "metapub_optional",
      "pdf_provider": "scansci_pdf",
      "institutional_access": "carsi_user_action_checkpoint",
      "zotero_write_policy": "explicit_confirmation_then_readback",
      "deduplication_policy": "doi_then_pdf_sha256"
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

# CLAUDE.md — Sci-NMA Reproduction Autonomous Agent

## Project Identity & Mission
`sci-nma-reproduction` is an industrial-grade autonomous agent framework engineered to reproduce and synthesize publication-grade Systematic Reviews, Meta-Analyses (Pairwise & Network), and Narrative Reviews for top-tier clinical medicine journals (*The Lancet*, *JAMA*, *NEJM*, *BMJ*, *Critical Care*, *European Heart Journal*).

The agent enforces a **Zero-Discrepancy Protocol**, **Mandatory 5-Tier Verification Gates**, **Strict PRISMA 2020 Mathematical Flow Conservation ($L \equiv 0$)**, and **6-Format Publication Delivery** (600 DPI PNG, editable live-text SVG `<text>`, Type 42 vector PDF, native XML Word `.docx`, Master Excel `.xlsx`, 16:9 PPTX).

---

## Quick Commands

### Python Environment & CLI
- Install package in editable mode:
  ```bash
  pip install -e .
  ```
- Run full test suite:
  ```bash
  pytest tests/ -v
  ```
- Run 5-Tier Verification Gate audit on any project directory:
  ```bash
  sci-nma-agent audit examples/case_study_corticosteroids_nma
  ```
- Generate 4-database search queries from PICO:
  ```bash
  sci-nma-agent search --pico examples/case_study_corticosteroids_nma/config_pico.json
  ```
- Synthesize meta-analysis data:
  ```bash
  sci-nma-agent synthesize --data examples/case_study_corticosteroids_nma/data/extraction_dataset.json
  ```
- Render all publication figures (PRISMA, Forest Plot, Network Geometry):
  ```bash
  sci-nma-agent render --project examples/case_study_corticosteroids_nma
  ```
- Run AI Reviewer audit:
  ```bash
  sci-nma-agent review --project examples/case_study_corticosteroids_nma
  ```
- Execute individual SOP stage with strict acceptance gate:
  ```bash
  sci-nma-agent run-step --stage 1 --project examples/case_study_corticosteroids_nma
  ```
- Execute full 6-stage SOP pipeline with step-by-step gated acceptance:
  ```bash
  sci-nma-agent run-all --project examples/case_study_corticosteroids_nma
  ```
- Launch MCP Server (Model Context Protocol):
  ```bash
  python -m sci_nma_agent.mcp_server
  ```

---

## 7 Core Ironclad Rules

1. **Anti-Generic-Template Rule**: Never guess standard tables/figures. Reverse-engineer ground truth from published PDFs, JATS XMLs, and electronic supplementary material (MOESM).
2. **Mandatory Complete Redraw Rule**: Zero low-res raster modification. Pure math code rendering for diagrams, anti-collision bounding boxes, and genuine anatomical fidelity.
3. **Exact Numerical & Data Fidelity**: Cohort sample sizes, point estimates (OR, RR, MD, SMD), 95% CIs, and heterogeneity ($I^2, \tau^2, P$) must match with zero rounding drift.
4. **Multi-Format 6-Suite Delivery**: Simultaneous generation of 600 DPI PNG, live-text SVG (`svg.fonttype = 'none'`), Type 42 vector PDF (`pdf.fonttype = 42`), Word `.docx` with XML `<w:tblHeader>` and `<w:cantSplit>`, 16:9 PPTX, and formula-backed Master Excel.
5. **Anti-Mojibake Protocol**: UTF-8 encoding across all I/O streams (`sys.stdout.reconfigure(encoding='utf-8')`), safe math symbols, normalized dashes.
6. **Strict Gated Execution (Anti-Shortcut Rule)**: Every phase must pass its automated verification test before moving to the next phase.
7. **Strict Superset & No Information Loss**: Reproduction outputs must be a strict superset of the original paper and all supplements ($N_{\text{refs}}$ fully conserved).

---

## 5-Tier Verification Gates

- **Gate 1 [Search & PRISMA Math Flow]**:
  $$\sum N_{\text{databases}} + N_{\text{registries}} \equiv N_{\text{total identified}}$$
  $$N_{\text{total}} - N_{\text{duplicates}} \equiv N_{\text{screened}}$$
  $$N_{\text{screened}} - N_{\text{title\_abstract\_excluded}} \equiv N_{\text{sought}}$$
  $$N_{\text{sought}} - N_{\text{not\_retrieved}} \equiv N_{\text{assessed}}$$
  $$N_{\text{assessed}} - \sum N_{\text{fulltext\_reasons}} \equiv N_{\text{included}}$$
  Flow loss must be exactly zero: $L \equiv 0$.

- **Gate 2 [Evidence Authenticity & Provenance]**:
  - Triad cross-lock: DOI, PMID, PMCID verification.
  - Coordinate anchoring: Every claim and parameter anchored to `[Document]:[Table/Paragraph]:[Variable]`.
  - Zero LLM hallucination: unrecorded metrics flagged as "Not Reported".

- **Gate 3 [Statistical Consistency & Logit Transformation]**:
  - Reml / DerSimonian-Laird random effects with Knapp-Hartung adjustment.
  - Bounded metrics (AUROC, prevalence, proportions) MUST use Logit transformation:
    $$\text{logit}(p) = \ln\frac{p}{1-p}, \quad \text{ilogit}(z) = \frac{e^z}{1+e^z}$$
  - Heterogeneity $I^2$ and Cochrane's $Q$ test consistency check.

- **Gate 4 [Zero-Raster Vector Rendering & Anti-Collision]**:
  - Matplotlib parameters: `svg.fonttype = 'none'` (raw XML `<text>`), `pdf.fonttype = 42` (Type 42 TrueType).
  - High resolution: $\ge 600\text{ DPI}$ PNG canvas ($\ge 3800\text{ px}$).
  - Dynamic bounding box calculation: arrows must NEVER cross text labels.

- **Gate 5 [Office Suite Engineering & Audit Report]**:
  - Word docx table XML injection:
    - `<w:tblHeader>` on header row (repeats on every page).
    - `<w:cantSplit>` on all rows (prevents row splitting across pages).
  - Excel `.xlsx`: Live formulas (`SUM`, `AVERAGE`, `COUNTIF`) with frozen panes.
  - Generates `verification_audit_report.json` and `verification_audit_report.md`.

---

## Four Core Medical Databases

| Database | Primary Search Syntax | API / Retrieval Method | Key Filters |
|---|---|---|---|
| **PubMed** | MeSH `[Mesh]`, Title/Abstract `[tiab]`, `AND/OR/NOT` | NCBI E-utilities (`esearch`, `esummary`, `efetch`) | Cochrane Highly Sensitive Search Strategy for RCTs |
| **Embase** | Emtree `'/exp'`, `:ti,ab,kw`, `[humans]/lim` | Embase Web REST Session (`pageSize=200`) | Pharmaceutical adverse effects & clinical trials |
| **Cochrane Library** | Search Manager syntax, `[All Text]`, CENTRAL | Advanced Search Form + Results Portlet | Review / Protocol / CENTRAL separation |
| **Web of Science** | `TS=`, `TI=`, `AU=`, `SO=`, `PY=` | Clarivate Starter API (`/v1/documents`) | Core Collection, Articles/Reviews only |

---

## Directory Organization Standard

```text
<project_root>/
├── figures/                     # 600 DPI PNGs (Figure1_PRISMA.png, Figure2_Forest.png...)
├── editable_files/
│   ├── vector_svg/              # Pure vector SVG (<text> nodes for Illustrator/Inkscape)
│   ├── vector_pdf/              # Vector PDF with embedded Type 42 TrueType
│   └── office_docs/             # Word docx with XML table headers, Master Excel, PPTX
├── verification/                # verification_audit_report.json & .md
└── original_materials/          # Source XMLs, raw extraction CSVs, reference metadata
```

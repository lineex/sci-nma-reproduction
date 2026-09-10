# Top-Tier Medical Review & NMA Autonomous Agent (`sci-nma-reproduction`)

<p align="center">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-success" alt="Status"/>
  <img src="https://img.shields.io/badge/Verification%20Gates-5--Tier%20Enforced-blue" alt="Verification Gates"/>
  <img src="https://img.shields.io/badge/PRISMA-2020%20Compliant-orange" alt="PRISMA 2020"/>
  <img src="https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue" alt="Python Version"/>
  <img src="https://img.shields.io/badge/Core%20Databases-PubMed%20%7C%20Embase%20%7C%20Cochrane%20%7C%20WoS-indigo" alt="Databases"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License"/>
</p>

An industrial-grade autonomous agent framework engineered to reproduce, synthesize, and calibrate publication-grade **Systematic Reviews, Pairwise Meta-Analyses, Network Meta-Analyses (NMA), and Narrative Reviews** for world-leading clinical medicine journals (*The Lancet*, *JAMA*, *NEJM*, *BMJ*, *Critical Care*, *European Heart Journal*).

[English](#english) | [中文说明](#中文说明)

---

## English

### Key Capabilities

1. **Zero-Discrepancy Protocol & Strict Superset Delivery**:
   - Zero hallucination or algorithmic fabrication.
   - Exact numerical fidelity across sample sizes ($n/N$), point estimates (OR, RR, MD, SMD), 95% CIs, and heterogeneity ($I^2, \tau^2, Q, P$).
   - Output artifacts are a strict superset of the original paper plus Electronic Supplementary Material (MOESM).
2. **Mandatory 5-Tier Verification Gates**:
   - **Gate 1**: Boolean search syntax & PRISMA 2020 mathematical flow conservation ($L \equiv 0$).
   - **Gate 2**: Primary evidence provenance, DOI/PMID/PMCID cryptographic cross-lock, and coordinate anchoring.
   - **Gate 3**: Statistical consistency (REML/DL, Knapp-Hartung, Logit bounded transformations).
   - **Gate 4**: Zero-raster code rendering, live-text SVG (`<text>`), Type 42 vector PDF font embedding, anti-collision bounding boxes.
   - **Gate 5**: Word docx XML `<w:tblHeader/>` and `<w:cantSplit/>` table engineering, Master Excel dynamic formulas (`=SUM`, `=AVERAGE`).
3. **Four Core Medical Literature Databases**:
   - **PubMed / MEDLINE**: MeSH indexing, field tags, Cochrane Highly Sensitive Search Strategy for RCTs, NCBI E-utilities.
   - **Embase**: Emtree explosion (`'/exp'`), `:ti,ab,kw`, pharmaceutical adverse event filters, REST session harvesting.
   - **Cochrane Library**: Cochrane Reviews & CENTRAL query builder, portlet pagination.
   - **Web of Science Core Collection**: `TS=`, `TI=`, `AU=`, `SO=`, `PY=` syntax, Clarivate Starter API.
   - *Supplementary*: Scopus (proximity operators `W/n`, `PRE/n`), ClinicalTrials.gov, Google Scholar.
4. **Universal Cross-Platform Reusability**:
   - Works natively with **Claude Code** (`CLAUDE.md`), **Cursor** (`.cursorrules` and `.cursor/rules/`), **Windsurf**, **Cline / Roo Code**, **GitHub Copilot**, **Antigravity** (`skills/`), and **Model Context Protocol (MCP)**.
   - Zero-setup master prompt in `SYSTEM_PROMPT.md` for any LLM (ChatGPT, Claude.ai, DeepSeek, Gemini).
5. **6-Format Industrial Publication Suite**:
   - Ultra-HD Bitmap ($\ge 600\text{ DPI}$ PNG, canvas $\ge 3800\text{ px}$)
   - Editable Vector SVG (live `<text>` nodes for Adobe Illustrator / Inkscape)
   - Print-Ready Vector PDF (Type 42 TrueType font embedding)
   - Submission-Ready Word Manuscript (`.docx` with XML anti-split tables)
   - Formula-Backed Master Research Database (`.xlsx` with live formulas)
   - Academic Presentation Slide Deck (16:9 widescreen `.pptx`)

---

### Architecture Overview

```text
sci-nma-reproduction/
├── .cursor/rules/                     # Cursor IDE rules (.mdc)
├── .github/workflows/ci.yml           # Automated CI verification suite
├── CLAUDE.md                          # Claude Code agent commands & protocols
├── SYSTEM_PROMPT.md                   # Universal Master System Prompt for any LLM
├── skills/                            # Modular Reusable Skills
│   ├── sci-nma-reproduction/          # Core reproduction specification (55KB complete standard)
│   ├── pm-advanced-search/            # PubMed MeSH & E-utilities
│   ├── embase-web-search/             # Embase Emtree & REST harvesting
│   ├── ch-advanced-search/            # Cochrane CENTRAL & portlet flow
│   ├── wos-search/                    # Web of Science Core Collection API
│   ├── scopus-search/                 # Scopus proximity indexing
│   ├── ai-reviewer/                   # Top journal AI Peer Reviewer simulation
│   └── lit-intelligence-mining/       # Forward/backward citation intelligence mining
├── sci_nma_agent/                     # Production Python Engine
│   ├── core/                          # 5-Tier Verification Gate System
│   ├── databases/                     # 4 Core Database Query Builders & Clients
│   ├── meta_engine/                   # Pairwise, NMA, Logit, Meta-Regression, Bias
│   ├── generators/                    # PRISMA SVG, Forest SVG, NMA SVG, Docx, Excel, PPTX
│   ├── workflow/                      # 6-Stage End-to-End SOP Pipeline
│   ├── reviewer/                      # AI Peer Reviewer module
│   ├── cli.py                         # Standalone CLI entrypoint
│   └── mcp_server.py                  # Model Context Protocol (MCP) Server
├── examples/case_study_corticosteroids_nma/ # Complete Verified Case Study (100% PASS)
└── tests/                             # Pytest automated test suite (16 tests, 100% pass)
```

---

### Installation & Quick Start

```bash
# Clone repository
git clone https://github.com/lineex/sci-nma-reproduction.git
cd sci-nma-reproduction

# Install in editable mode with dependencies
pip install -e .

# Run test suite
pytest tests/ -v
```

#### Run 5-Tier Verification Audit on Any Review Project
```bash
sci-nma-agent audit examples/case_study_corticosteroids_nma
```

#### Generate Harmonized 4-Database Search Queries from PICO
```bash
sci-nma-agent search --pico examples/case_study_corticosteroids_nma/config_pico.json
```

#### Execute Full End-to-End SOP Pipeline
```bash
sci-nma-agent run-all --project examples/case_study_corticosteroids_nma
```

---

## 中文说明

### 核心定位与设计目标

`sci-nma-reproduction` 是专为**顶级临床医学期刊（Critical Care, The Lancet, JAMA, BMJ, NEJM）**量身定制的作者级系统评价、Meta分析与叙述性综述自主智能体。

本框架解决了大模型在医学综述写作中的关键痛点：
- **拒绝模版臆造**：穿透真实发表材料（PDF/JATS XML/MOESM附录），建立 1:1 镜面对齐；
- **数学流向绝对守恒**：严格执行 PRISMA 2020 流平衡公式，流向损耗必须恒等于 0（$L \equiv 0$）；
- **有界变量 Logit 转换**：针对 AUROC、患病率、发生率等在 $(0, 1)$ 有界区间的指标，强制在 Logit 正态尺度精算并逆变换，防止 95% CI 越界；
- **全要素从零纯代码渲染**：严禁在低清作者位图上涂抹补字，流程图、森林图与网络拓扑图全由纯代码生成，保留原生 `<text>` 节点；
- **Office 工业级排版工程**：自动化为 Word 表格底层注入 `<w:tblHeader/>`（跨页表头自动重复）与 `<w:cantSplit/>`（行防跨页撕裂），Excel 注入动态公式；
- **五级强制门禁（5-Tier Verification Gates）**：Gate 1 检索与流平衡 -> Gate 2 DOI/PMID真实溯源 -> Gate 3 统计精算 -> Gate 4 纯矢量防碰撞 -> Gate 5 交付审计，验证不通过决不进入下一步。

---

### 四大核心数据库规范

| 数据库 | 检索语法体系 | API / 检索途径 | 关键过滤器 / 规范 |
|---|---|---|---|
| **PubMed** | MeSH `[Mesh]`, Title/Abstract `[tiab]` | NCBI E-utilities (`esearch`, `efetch`) | Cochrane RCT 敏感检索策略过滤器 |
| **Embase** | Emtree `'/exp'`, `:ti,ab,kw` | Embase Web REST Session (`pageSize=200`) | 药物不良反应、临床试验分期过滤器 |
| **Cochrane Library** | Search Manager, CENTRAL | Advanced Search Form + Results Portlet | 系统评价 / 方案 / CENTRAL 试验严格分仓 |
| **Web of Science** | `TS=`, `TI=`, `AU=`, `SO=`, `PY=` | Clarivate Starter API (`/v1/documents`) | 核心合集（SCI-EXPANDED）、论著/综述限定 |

---

### 出版级 6 大交付格式套件

每一个生成的系统评价/Meta分析项目，均在本地自动产出 6 种工业级标准格式：
1. **高清印刷位图 (PNG)**：分辨率 $\ge 600\text{ DPI}$，主画布 $\ge 3800\text{ px}$；
2. **纯矢量可编辑图 (SVG)**：强制配置 `plt.rcParams['svg.fonttype'] = 'none'`，文字全部保留为原生 XML `<text>` 标签，可在 Adobe Illustrator 中双击编辑；
3. **印刷级矢量图 (PDF)**：强制配置 `plt.rcParams['pdf.fonttype'] = 42`，嵌入原生 Type 42 TrueType 字体；
4. **投稿级 Word 手稿 (`.docx`)**：注入 `<w:tblHeader/>` 与 `<w:cantSplit/>`，排版严密；
5. **结构化 Master Database (`.xlsx`)**：包含研究基线、结局指标、RoB 2 偏倚风险、SUCRA 排序等独立 Sheet，内嵌 `=SUM` / `=AVERAGE` 动态验证公式；
6. **16:9 学术演示文稿 (`.pptx`)**：宽屏报告幻灯片，内嵌高分辨率矢量图件与临床决策卡片。

---

### 自动化验证与测试

本项目自带完整的集成测试与案例验证工程，执行以下命令即可全自动检验所有 5 级门禁：

```bash
python -m pytest tests/ -v
```

测试输出：
```text
tests/test_end_to_end_pipeline.py::test_case_study_audit PASSED          [  6%]
tests/test_gate1_prisma_math.py::test_prisma_flow_valid_conservation PASSED [ 12%]
tests/test_gate1_prisma_math.py::test_prisma_flow_violation_detection PASSED [ 18%]
tests/test_gate1_prisma_math.py::test_search_syntax_parentheses PASSED   [ 25%]
tests/test_gate1_prisma_math.py::test_search_syntax_lowercase_boolean PASSED [ 31%]
tests/test_gate2_provenance.py::test_doi_valid PASSED                    [ 37%]
tests/test_gate2_provenance.py::test_doi_mock_rejection PASSED           [ 43%]
tests/test_gate2_provenance.py::test_pmid_validation PASSED              [ 50%]
tests/test_gate2_provenance.py::test_coordinate_anchor PASSED            [ 56%]
tests/test_gate3_statistics.py::test_logit_transformation_roundtrip PASSED [ 62%]
tests/test_gate3_statistics.py::test_odds_ratio_calculation PASSED       [ 68%]
tests/test_gate3_statistics.py::test_pairwise_meta_analysis PASSED       [ 75%]
tests/test_gate4_vector_rendering.py::test_audit_svg_with_live_text PASSED [ 81%]
tests/test_gate4_vector_rendering.py::test_audit_svg_rejects_embedded_raster PASSED [ 87%]
tests/test_gate5_office_xml.py::test_docx_xml_injection_and_audit PASSED [ 93%]
tests/test_gate5_office_xml.py::test_excel_formula_audit PASSED          [100%]
============================= 16 passed in 1.02s ==============================
```

---

### 许可证与免责声明

- 本项目遵循 [MIT License](LICENSE)。
- 本项目生成的统计数据与图表须由具备专业资质的临床医生与统计学家复核后方可用于临床指导。

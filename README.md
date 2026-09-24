# Top-Tier Medical Review & NMA Autonomous Agent (`sci-nma-reproduction`)

<p align="center">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-success" alt="Status"/>
  <img src="https://img.shields.io/badge/Verification%20Gates-5--Tier%20Enforced-blue" alt="Verification Gates"/>
  <img src="https://img.shields.io/badge/Tests-21%20Passed-brightgreen" alt="Tests"/>
  <img src="https://img.shields.io/badge/Literature%20Corpus-Zero%20Relevance%20Truncation-purple" alt="Corpus"/>
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


### Full Corpus Ingestion & Two-Stage Screening Workflow

1. **Zero Relevance Truncation Policy (全量检索不截断)**:
   - Systematic reviews must never truncate retrieval results by arbitrary relevance rank (e.g. top-50 cutoff).
   - Ingests all hit records from **PubMed, Embase, Web of Science, and Cochrane Library** across multiple batch landing files (`raw_exports/{pubmed, embase, wos, cochrane}`).
   - Native parsers for PubMed `.nbib`/`.medline`, Embase/Cochrane `.ris`, Web of Science `.txt`/`.ciw`, and Cochrane `.csv`.

2. **Browser Institutional Session Reuse (机构会话复用)**:
   - Directly attaches to existing running Chrome instances with university/hospital SSO or WebVPN via remote debugging:
     `chrome.exe --remote-debugging-port=9222`
   - Active probe validates institutional access for Embase (Elsevier), Web of Science (Clarivate), and Cochrane (Wiley) before export, preventing export throttles.

3. **Multi-Source Provenance-Retaining Deduplication (带溯源多标签去重)**:
   - Multi-tier matching: DOI exact match -> PMID exact match -> Normalized Title + Year string similarity.
   - When duplicate citations merge, contributing database source tags (`sources: ["PubMed", "Embase", "Web of Science"]`) and native database IDs (`pmid`, `embase_pui`, `wos_uid`, `cochrane_id`) are preserved intact.
   - Mathematical accounting: N_duplicates = N_total_identified - N_unique_screened.

4. **Search Flow Conservation Audit Ledger (检索流量守恒审计表)**:
   - Verifies that records across all landed export batches match reported database hit counts (100% batch completeness).
   - Generates publication-grade `Search_Flow_Audit_Table.xlsx` and `prisma_flow_data.json` for supplementary files.

5. **Two-Stage Unified Screening Ledger (两阶段统一筛选表)**:
   - Automatically scaffolds `screening/master_screening_table.xlsx` with data-validation dropdowns.
   - **Stage 1: Title/Abstract Screening (初筛)**: records exclusions with broad clinical reasons.
   - **Stage 2: Full-Text Eligibility Screening (复筛)**: enforces 5 standard hierarchical exclusion reasons (*Wrong Population*, *Wrong Intervention*, *No Control Group*, *Ineligible Study Design*, *Duplicate Cohort*).
   - `sci-nma-agent screen-check` reconciles decisions and mathematically verifies Gate 1 PRISMA Flow Conservation:
     L = N_total - (N_duplicates + N_tiab_excluded + N_not_retrieved + N_fulltext_excluded + N_included) == 0.

---


### Mandatory NMA Figure & Table Specification (v2026-09-21)

Aligned with top-tier publications (*Critical Care* 2026, doi:10.1186/s13054-026-06185-5; *BMJ* 2026;394:e100561, doi:10.1136/bmj-2026-100561):

1. **Figure 1 Unique Standard (PRISMA 2020 Two-Column Layout)**:
   - **Left column**: `Identification of studies via databases and registers`
   - **Right column**: `Identification of studies via other methods` (strictly preserved with `0 additional bibliographic records` if none found; citation/registry checks never inflate the database denominator).
   - **Vertical stage tabs**: `Identification`, `Screening`, `Included` (rotated 90° on the far left).
   - **Flow Conservation Equation**:
     $$DB\_TOTAL = \sum \text{database\_source\_counts}$$
     $$AFTER\_DEDUP = DB\_TOTAL - DUPLICATES - \text{other\_pre\_screen\_removals}$$
     $$REPORTS\_SOUGHT = SCREENED - TITLE\_ABSTRACT\_EXCLUDED$$
     $$REPORTS\_ASSESSED = REPORTS\_SOUGHT - REPORTS\_NOT\_RETRIEVED$$
     $$REPORTS\_INCLUDED = REPORTS\_ASSESSED - \sum \text{full\_text\_exclusion\_reasons}$$
     $$L \equiv 0$$
   - Three synchronized formats: 600-dpi PNG, live-text SVG (no raster `<image>`), Type 42 vector PDF.

2. **Dual NMA Reference Tracks**:
   - **Frequentist Track** (*Crit Care* 2026): Fig 1 PRISMA $\to$ Fig 2 RoB 2 matrix $\to$ Fig 3 Network geometry + aligned relative-effect forest $\to$ Fig 4 CINeMA certainty heatmap $\to$ Fig 5 Funnel plot audit.
   - **Hierarchical Bayesian Track** (*BMJ* 2026): Fig 1 PRISMA $\to$ Fig 2 Outcome-specific networks $\to$ Fig 3 Posterior forest $\to$ Fig 4-5 Dose-response curves (95% CrI, MCID) $\to$ Fig 6 Secondary outcomes forest $\to$ Appendix MCMC diagnostics (R-hat, bulk/tail ESS, divergences, PPC).

3. **Reusable Data Contract Templates**:
   - [`data/nma_figure_table_spec_template.json`](data/nma_figure_table_spec_template.json)
   - [`figures/NMA_FIGURE_TABLE_SPECIFICATION_TEMPLATE.md`](figures/NMA_FIGURE_TABLE_SPECIFICATION_TEMPLATE.md)

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

#### Execute Individual SOP Stage with Strict Acceptance Gate
```bash
# Execute Stage 1 (Search Strategy & Syntax Verification)
sci-nma-agent run-step --stage 1 --project examples/case_study_corticosteroids_nma

# Execute Stage 2 (PRISMA 2020 Flow Math Conservation Gate 1)
sci-nma-agent run-step --stage 2 --project examples/case_study_corticosteroids_nma

# Execute Stage 3 (Data Extraction, Gate 2 Provenance & Gate 3 Statistics)
sci-nma-agent run-step --stage 3 --project examples/case_study_corticosteroids_nma
```

#### Execute Full End-to-End SOP Pipeline
```bash
sci-nma-agent run-all --project examples/case_study_corticosteroids_nma
```

---

### Step-by-Step SOP Workflow with Gated Acceptance

The framework strictly enforces the **Anti-Shortcut Protocol**: Every single phase is executed sequentially and must pass an explicit Acceptance Checkpoint before the next phase is allowed to run. If any check fails, execution immediately halts with a diagnostic traceback:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 1] PICO & Multi-Database Search Formulation                     │
│ └── Checkpoint 1: Syntax balance, uppercase booleans, MeSH/Emtree tags │
├────────────────────────────────────────────────────────────────────────┤
│ [Stage 2] Ground-Truth Catalog & PRISMA Flow Ledger                    │
│ └── Checkpoint 2 (Gate 1): Mathematical flow conservation (L ≡ 0)      │
├────────────────────────────────────────────────────────────────────────┤
│ [Stage 3] Data Extraction & Statistical Modeling                       │
│ └── Checkpoint 3 (Gate 2 & 3): 100% DOI provenance & logit consistency │
├────────────────────────────────────────────────────────────────────────┤
│ [Stage 4] Multi-Format Vector Figure Rendering                         │
│ └── Checkpoint 4 (Gate 4): 600 DPI, live <text> nodes, PDF Type 42     │
├────────────────────────────────────────────────────────────────────────┤
│ [Stage 5] Office Suites Industrial Engineering                         │
│ └── Checkpoint 5 (Gate 5): Word XML tblHeader/cantSplit, Excel formulas│
├────────────────────────────────────────────────────────────────────────┤
│ [Stage 6] 5-Tier Verification Audit & AI Peer Review                   │
│ └── Checkpoint 6: Full pass certificate & Lancet referee evaluation    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 中文说明

### 新建循证综述与 Meta 分析

新研究问题走独立的协议优先工作流，不加载发表研究复现/校准模块。入口技能为
[`skills/sci-nma-reproduction/SKILL.md`](skills/sci-nma-reproduction/SKILL.md)，方法和阶段规范见
[`docs/EBM_SYSTEMATIC_REVIEW_WORKFLOW.md`](docs/EBM_SYSTEMATIC_REVIEW_WORKFLOW.md)、
[`docs/COCHRANE_AGENT_REQUIREMENTS.md`](docs/COCHRANE_AGENT_REQUIREMENTS.md) 和
[`agents/STAGE_METHOD_MATRIX.md`](agents/STAGE_METHOD_MATRIX.md)。

- 按 Cochrane Handbook 与项目方案依次通过 11 个门：方案、检索、去重关联、题录初筛、全文获取、全文资格、数据提取、偏倚风险、综合、证据确定性、报告。每门由执行 agent 提交可审查工件，两个独立 reviewer 均通过后才能进入下一门；上游文件哈希变化会阻止旧审批继续生效。
- Zotero 优先使用 [`cookjohn/zotero-mcp`](https://github.com/cookjohn/zotero-mcp)：读取指定 collection、核对条目和附件、提取全文。安装 MCP 可选依赖并配置 Zotero MCP endpoint 后，可使用直连适配器；无 MCP endpoint 时可使用只读 Zotero 本地数据库/JSON 导出适配器。
- 全文获取不等于事实缺失。不可获取、附件待确认、全文待审、报告内未报告、所有关联来源均未报告、全文审阅后仍无法判断分别记录；未获取报告进入逐条人工获取队列，用户确认正确的 Zotero 条目/附件后，回到同一阶段续跑。相关状态由阶段账本校验，来源关联图谱通过 SHA-256 固定。
- 新项目沿用既有图表合同；新流程不会自行改变图表外观。已发表研究的复现及校准只在用户明确提出复现任务时加载。

### 强制开源 NMA 图表与 Figure 1 固定范式（v2026-09-21 最新版）

与顶级医学期刊（*Critical Care* 2026, doi:10.1186/s13054-026-06185-5 与 *BMJ* 2026;394:e100561）严格对齐：

1. **Figure 1 的唯一范式（PRISMA 2020 双栏固定标准）**：
   - **左栏**：`Identification of studies via databases and registers`
   - **右栏**：`Identification of studies via other methods`（即使为零也必须明确保留 `0 additional bibliographic records`，审计性检索绝不虚增数据库分母）。
   - **最左侧阶段带**：`Identification`、`Screening`、`Included` 标签垂直旋转 90°。
   - **视觉规范**：顶部橙色/琥珀色实心横幅、白色流程框带深色边框、黑色实线箭头。
   - **流量守恒**：严格满足闭环方程，全局流向损耗 $L \equiv 0$。
   - **三格式强同步**：600-dpi PNG、含原生 `<text>` 节点的纯矢量 SVG、嵌入 Type 42 TrueType 字体的矢量 PDF。

2. **NMA 频率学 vs 贝叶斯双轨参考模式**：
   - **频率学 NMA Track**（*Crit Care* 2026）：Fig 1 PRISMA $\to$ Fig 2 RoB 2 矩阵 $\to$ Fig 3 网络几何与相对效应森林图 $\to$ Fig 4 CINeMA 确定性热图 $\to$ Fig 5 漏斗图。
   - **层次贝叶斯 NMA Track**（*BMJ* 2026）：Fig 1 PRISMA $\to$ Fig 2 结局特异性网络图 $\to$ Fig 3 后验森林图 $\to$ Fig 4-5 剂量-结局与类别剂量反应曲线 $\to$ Fig 6 次要结局森林图 $\to$ 附录 MCMC 诊断。

3. **开箱即用数据契约模版**：
   - 标准填空 JSON 模版：[`data/nma_figure_table_spec_template.json`](data/nma_figure_table_spec_template.json)
   - 规范 Markdown 模版：[`figures/NMA_FIGURE_TABLE_SPECIFICATION_TEMPLATE.md`](figures/NMA_FIGURE_TABLE_SPECIFICATION_TEMPLATE.md)


### 全量文献检索记录库与两阶段筛选工作流

1. **拒绝相关性截断（Zero Relevance Truncation）**：
   - 绝不采取前 20/50 条截断策略，杜绝严重的文献检索选择偏倚（Selection Bias）。
   - 全量支持多批次分卷落盘文件扫描：`raw_exports/{pubmed, embase, wos, cochrane}`。
   - 内置 PubMed `.nbib`、Embase `.ris`（含 EMTREE 词与 PUI 编号）、WoS `.txt`/`.ciw`（含 WOS Accession Number）、Cochrane `.csv` 原生解析器。
2. **浏览器机构用户登录状态复用（Session Reuse）**：
   - 支持直连日常使用的 Chrome（启动参数 `--remote-debugging-port=9222`）或持久化用户 Profile。
   - 自动探针检测 Embase/WoS/Cochrane 校园网 SSO/WebVPN 认证状态，过期自动挂起等待用户浏览器登录后无缝续导。
3. **带溯源多标签去重（Provenance Deduplication）**：
   - 三级锚定去重（DOI 精确匹配 -> PMID 精确匹配 -> 规范化 Title + 出版年份比对）。
   - 去重时严格保留多库复合来源标签与各库原生编号（`sources: ["PubMed", "Embase", "WoS"]`）。
4. **检索流量守恒审计表（Search Flow Audit Table）**：
   - 校验各库落盘文件记录数与检索原生命中数 100% 匹配，导出中英双语可投顶刊的 Excel 审计表。
5. **两阶段统一筛选主表（Master Screening Table）**：
   - 自动生成带下拉数据验证的 `screening/master_screening_table.xlsx`。
   - 严格约束复筛 5 大标准化排除原因（非目标人群、非目标干预、缺乏合规对照、非合规设计、重复队列），一键校验 PRISMA 流量闭环 L == 0。


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

### 全流程分步推进与强制逐级前置验收机制（Anti-Shortcut Protocol）

智能体**严格按照六大标准作业阶段（Stage 1 ~ Stage 6）一步步执行**，并在**每一步结束时触发强制验收检查点（Acceptance Checkpoint）**。只有当前阶段通过自动化质检（Status: PASSED），系统才允许进入下一阶段；若发现任何偏差或不自洽，立即**熔断中断（Raise StepAcceptanceError）**并输出诊断回溯：

1. **第一步（Stage 1 检索式制定）**：
   - **产出**：四大数据库（PubMed、Embase、Cochrane、WoS）+ Scopus 原生布尔检索式。
   - **验收检查点 (Checkpoint 1)**：括号平衡性校验、布尔逻辑大写校验、MeSH/Emtree 字段合法性校验。
2. **第二步（Stage 2 PRISMA 2020 流向对账）**：
   - **产出**：结构化筛选流向数据（检出、去重、初筛、索取、评估、纳入）。
   - **验收检查点 (Checkpoint 2 / Gate 1)**：严格核验 PRISMA 数学闭环，保证流向损耗绝对归零（$L \equiv 0$），初筛与全文排除细项加和 100% 守恒。
3. **第三步（Stage 3 数据抽取与统计精算）**：
   - **产出**：基线数据、2x2 四格表、成对 Meta 分析、网状 Meta 分析（NMA）及 SUCRA 概率矩阵。
   - **验收检查点 (Checkpoint 3 / Gate 2 & 3)**：Gate 2 真实性核验（100% 检验 DOI 结构、PMID 及坐标锚定，零 mock 伪造）；Gate 3 统计自洽性核验（样本量守恒、95% CI 正确包裹、AUROC/患病率强制 Logit 正态尺度转换）。
4. **第四步（Stage 4 纯矢量图件代码渲染）**：
   - **产出**：PRISMA 2020 流程图、亚组高密度森林图、网状拓扑图。
   - **验收检查点 (Checkpoint 4 / Gate 4)**：自动化扫描 SVG 源码，强制核验原生可编辑 `<text>` 节点存在性，核查 PDF Type 42 字体嵌入，严禁任何内嵌 base64 位图，确保图元文字防碰撞。
5. **第五步（Stage 5 工业级 Office 办公套件生成）**：
   - **产出**：投稿级 Word 手稿、Master Excel 数据库（多 Sheet）、16:9 宽屏演示文稿（PPTX）。
   - **验收检查点 (Checkpoint 5 / Gate 5)**：自动化扫描 Word 底层 XML，强制验收 `<w:tblHeader/>`（表头跨页重复）与 `<w:cantSplit/>`（行防截断撕裂）；扫描 Excel 验证动态公式（`=SUM` 等）与窗格冻结。
6. **第六步（Stage 6 全局五级审计与同行评审终审）**：
   - **产出**：机器可读 `verification_audit_report.json`、高管级 `verification_audit_report.md` 以及 AI 模拟 Lancet 审稿人的评审意见书。
   - **验收检查点 (Checkpoint 6)**：全项目五级门禁全绿（100% Verified）方可签署交付！

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

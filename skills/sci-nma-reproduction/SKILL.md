---
name: sci-nma-reproduction
description: Publication-grade reproduction, calibration, and synthesis skill for top-tier medical journals (Critical Care, The Lancet, JAMA, BMJ, NEJM). Covers Quantitative Systematic Reviews/Meta-Analyses (PRISMA 2020, multi-panel trajectory forest plots, NMA geometry) and Qualitative Narrative Reviews/Expert Consensus (mechanistic pathophysiology hubs, unabridged master tables). Enforces mandatory 5-tier verification gates (search syntax & multi-database flow conservation, DOI/PMID/PMCID cryptographic provenance, cell-level statistical audit & flow closure reconciliation, zero-raster code vector rendering, anti-collision bounding box validation, biological anatomical fidelity constraints, and automated verification audit reporting), live text vector SVGs, vector PDFs, Word docx with tblHeader/cantSplit, 16:9 PPTX, and multi-sheet Excel databases.
---

# 顶级医学 SCI 论文（Meta 分析与叙述性/指南共识综述）作者级复现与出版级交付规范

本规范确立了针对顶级临床医学期刊（*Critical Care*, *The Lancet*, *JAMA*, *BMJ*, *NEJM*, *European Heart Journal* 等）两类核心学术文体：
- **Track A：定量系统评价与 Meta 分析 / 临床试验系统评价**（Pairwise MA, Longitudinal Trajectory MA, Network MA, PRISMA 2020 RCT Mapping, Comorbidity Prevalence & Multimorbidity Reporting Evaluations）；
- **Track B：叙述性综述与专家共识指南**（Narrative Review, Expert Clinical Consensus, Mechanistic Pathophysiology Pathways）；

的**作者级全景反演、数据逆向工程与出版级 6 大可编辑格式全套交付标准**。

---

## 1. 核心铁律：零偏差与双轨真实反演原则 (The Zero-Discrepancy Dual Protocol)

在执行文献复现或高标准生成时，必须严格遵守以下七项核心铁律，杜绝任何学术造假、算法臆造与简化偷懒：

### 1.1 拒绝“通用范式臆断”原则 (Anti-Generic-Template Rule)
* **严禁套用默认范式**：绝对禁止在未深入核验原刊结构的情况下，机械套用“Table 1 必为患者人口学基线表、Table 2 必为 GRADE 质量评级表、Figure 2 必为偏倚风险图”等通用模板。
* **穿透式原刊逆向工程**：
  1. 必须首先获取原刊已发表 PDF（包括 Accepted Manuscript 或 Version of Record）、JATS XML 结构化全文、图表原版高清大图、图题（Captions）、脚注说明以及全部补充材料（Supplementary Materials / MOESM）。
  2. 严格核验原刊正文图表与附录图表的分工划分与逻辑递进。
  3. **必须与原刊图表目录（Figures & Tables Catalog）保持 1:1 结构映射**。

### 1.2 针对“概念简化图”与“零表格论文”的完整全景扩充与全要素从零重绘铁律 (Mandatory Complete Redraw & Unabridged Synthesis Rule)
* **原图简化识别与零表格现象**：高水平叙述性综述（如 Schippers et al., *Crit Care* 2026; 30:258, Adolph et al., *Crit Care* 2026）的原刊插图常采用高度简化的概念流向图（Schematic Diagrams），且原刊甚至可能**完全未设置表格（0 Tables）**，而将海量核心参数、截断值、对比数据、病理生理级联与试验方案隐藏于正文长篇大段散文中。
* **双轨反演与表格扩充要求**：
  1. **视觉层面全要素纯净从零重绘（绝对禁止低清作者底图涂抹修补）**：绝对禁止任何偷工减料的伪重构行为（如直接截取原刊低清 PPT 位图、在其上用白块覆盖字迹重新打字等“治标不治本”的劣质修补！）。必须执行**全要素独立医学插画重绘（Complete Redraw from Scratch）**：所有解剖器官（心、肺、脑、肝、肾）、细胞微环境（小管上皮、微绒毛、线粒体、受体、毛细血管、白细胞）、临床场景（ICU 病床、监护仪、呼吸机、CRRT 机）必须逐一独立生成高精度无背景纯净图元，再以**纯数学代码构建背景几何卡片（圆角矩形抗锯齿）、纯矢量流线箭头与原生 Windows TrueType 字体（$\ge 600\text{ DPI}$ 超高清画幅）**进行亚像素组装，确保整幅图无论是图画内容还是文字排版均达到 Nature/Lancet 顶刊印刷级超清质感（绝对零压缩伪影、零毛刺、零发虚！）。
  2. **信息层面无损全景大表补充**：严禁仅停留于简化的概念流向或受限于原刊“零表格”！必须穿透全文全部章节与参考文献，提取所有关键参数、诊断效能、分子机制与试验设计，构建**完整、详尽、无删减的正交综合大表（如 Table 1 诊断效能与物理原理全景对比表，Table 2 分子靶点与病理生理级联表，Table 3 II 期临床试验设计主框架表）**，将散落的定性描述升华为高密度、结构化的学术成果，实现学术信息的 100% 无损提炼。

### 1.3 数据与数值 100% 精确对齐 (Exact Numerical & Data Fidelity)
* **研究列表与样本量一致性**：纳入队列名称（`Author YYYY`）、各组样本量（$n/N$）、权重比例（Weight %）必须完全对应。
* **效应值与置信区间**：点估计值（MD, SMD, RR, OR, HR）、95% 置信区间（CI）、异质性检验指标（$I^2, \tau^2, P$ 值）必须保留原刊精度，杜绝因重新拟合算法差异导致的四舍五入漂移。
* **离群值与敏感性分析保真**：若原刊包含离群值敏感性分析（如 Lei 2025 剔除前后对比），必须完整构建多面板对比图（Panel A 含离群值高异质性模型 vs Panel B 剔除离群值完全收敛模型）。
* **拓扑真实性（网状 Meta 专有）**：严禁虚构直接比较。网络几何结构必须严格维持**星形/树状（Star/V-shaped）**，绝对禁止人为连线闭合不存在临床试验的三角形。

### 1.4 出版级 6 大全格式可编辑套件 (Multi-Format Production Suite)
所有图表与交付产出必须同时提供以下 6 种工业级标准格式，严禁交付无法二次编辑的死图：
1. **高清位图 (PNG)**：分辨率 $\ge 300\text{ DPI}$（推荐 600 DPI），背景纯白，无重影无重叠；
2. **纯矢量可编辑图 (SVG)**：强制配置 `plt.rcParams['svg.fonttype'] = 'none'`，文字必须保留为原生 XML `<text>` 标签节点，方便在 Adobe Illustrator / Inkscape 中直接双击修改文字与数值；
3. **印刷级矢量图 (PDF)**：强制配置 `plt.rcParams['pdf.fonttype'] = 42`，嵌入原生 TrueType (Type 42) 字体；
4. **原生排版文档 (Word `.docx`)**：包含完整手稿正文与三线表，表格底层必须注入 XML `<w:tblHeader/>`（表头跨页自动重复）与 `<w:cantSplit/>`（行防截断撕裂）；
5. **完整演示文稿 (PPTX)**：16:9 宽屏学术报告幻灯片，内嵌全部高分辨率原真图表与临床决策卡片；
6. **结构化底层数据库 (Excel `.xlsx`)**：每个图表、每个临床阶段、关键临床试验矩阵与生物标志物字典独立 Sheet 存储，含冻结窗格、表头底色与自适应列宽。

### 1.5 全平台防乱码与安全字符规范 (Anti-Mojibake Protocol)
在 Windows 环境与跨平台环境下，必须确保 100% 字符编码安全：
* 所有的 Python 文件读写与命令行输出流必须显式强制 UTF-8 编码：`sys.stdout.reconfigure(encoding='utf-8')`。
* 严防破折号与特殊数学符号转码损坏：
  * 将不安全的 unicode 破折号（`–`, `—`, `−`）规范化处理，避免出现 `C` 或 `?`；
  * Matplotlib 绘图标签中涉及数学符号使用标准文本或 LaTeX 转义（如 `$\pm$`, `$\le$`, `$\ge$`）；
  * 字体回退机制：使用跨平台通用西文字体（Arial, Calibri, DejaVu Sans），杜绝方块乱码。

### 1.6 绝不走捷径与全流程强制逐级门禁铁律 (The Strict Gated Step-by-Step Execution Rule - Anti-Shortcut Protocol)
* **严禁偷工减料与省略跳步**：绝对禁止任何形式的走捷径、省略核心工作、使用 mock 占位符（如假 DOI、"Unknown" 占位、简陋草图）假冒真实结果！
* **分步逐项强制推进与前置门禁**：
  1. 每一个流程阶段（文献捕获 -> 原刊结构逆向 -> 底层数据抽取 -> 矢量设计绘图 -> 文档全格式编排 -> 审计验收）必须完整详尽地执行每一项子任务。
  2. **验证不过决不进入下一步**：每一阶段必须配备独立的自动化验证测试脚本。只有该阶段验证完全通过（Status: PASSED / 100% Verified），才允许进入下一阶段工作！
  3. 若验证发现偏差（如 DOI 失效、数值不闭环、图表偏离原版、文字重叠），必须立即熔断并回溯修正，重新验证直至 100% 闭环。

### 1.7 顶级医学设计绘图与全要素从零重绘及超越铁律 (Mandatory From-Scratch Redraw & Visual Superiority Protocol)
* **严禁初版低劣简笔画与自创偏离仪表板**：坚决摒弃“第一次给的图非常糟糕”、“用几个简单彩色方块糊弄用户”的低质量恶习！绝不允许将顶级期刊的专业临床图表篡改成不伦不类的仪表板卡片。
* **绝对禁止在低清作者位图上涂抹补字（Anti-Inpainting-Hack Rule）**：严禁截取原刊低清、模糊、压缩严重的位图并通过矩形覆盖字迹重新打字这种“伪重绘”！必须推倒重来，执行**全要素纯净重绘（Complete Redraw Pipeline）**：
  1. **全要素解剖/场景图元独立重绘**：每个解剖器官（立体心、立体肺、正常/损伤/纤维化肾脏、肝脏胆囊、脑组织矢状面）、细胞群（中性粒细胞、巨噬细胞、细菌）与医疗设备/场景（ICU 床位、监护仪、呼吸机、CRRT 机器）必须单独调用专业医学视觉绘图生成，确保形态学与解剖结构 100% 准确、纯白底色、超清无噪点；
  2. **高精度 Alpha 通道透明抠图**：利用数学算法将图元纯白底色转为透明 Alpha 通道，确保与任何底色背景、几何卡片完美融合，边缘无任何白色锯齿或硬边缘；
  3. **纯代码数学几何卡片与绝对防碰撞排版（Zero-Collision Spatial Layout）**：背景卡片必须使用纯数学抗锯齿圆角矩形渲染；文字与箭头必须严格计算边界（Bounding Box），**绝对禁止箭头穿透文字标签、绝对禁止解剖图元压盖机制卡片边框**；
  4. **原生 Windows TrueType 字体 600 DPI 亚像素渲染**：所有标注、标题、分行机制条目统一使用 Arial / Arial Bold 矢量字库，在 $\ge 3800\text{ px}$ 尺度上渲染，达到顶级学术期刊出片级锐度；
  5. **三格式强同步闭环**：位图 (PNG, 600 DPI 与 300 DPI)、纯矢量图 (SVG)、矢量印刷图 (PDF) 以及 Word/PPTX 内部媒体必须由同一组完全重绘的超高清资产同步编译更新，严禁出现版本割裂！

### 1.8 严格超集与无损交付铁律 (Strict Superset & No Information Loss Protocol)
* **内容只准多不准少原则**：复现已发表顶刊论文（无论是定量 Meta 分析、网状 Meta 分析，还是叙述性/共识综述）时，最终交付内容必须是原论文及其所有附录材料（Supplementary Materials / Electronic Supplementary Material, ESM）的**严格超集（Strict Superset）**，绝对禁止任何删减、简略或偷工减料！
* **全景无损覆盖清单**：
  1. **正文完整性**：Background, Methods, Results, Discussion, Conclusion 必须 100% 毫无保留地还原，保留原刊所有分析维度与定量结论；
  2. **全部主表与附录大表 (Table 1~N + Table S1~Sn)**：原刊所有正文表格与全部补充材料表格（如基线表、营养干预参数表、预设结局提取大表、并发症 Meta 分析表等）必须全部独立构建 Word 版三线表并具备 `<w:tblHeader/>` 与 `<w:cantSplit/>`；
  3. **全部主图与附录图件 (Figure 1~N + Figure S1~Sn)**：原刊所有流程图、森林图、多面板结局图、偏倚风险图（RoB Graph / RoB Summary）及发表偏倚漏斗图（Funnel Plot）必须 1:1 纯代码生成，绝对禁止遗漏附录图表；
  4. **顶刊级高价值增益资产扩充**：在 100% 覆盖原刊全部要素的基础上，必须强制增补：
     - **GRADE 证据分级汇总表（Summary of Findings Table）**：涵盖所有主要结局与次要结局的偏倚风险、不一致性、间接性、不精确性与发表偏倚评估；
     - **顶刊级病理生理与生物能量机制图（Graphical Abstract / Pathophysiological Framework）**：纯矢量从零绘制宏观监测、微观生理代谢与临床干预靶点；
     - **底层全动态公式数据库（Master Research Database .xlsx）**：至少包含 8~10 个独立 Sheet，涵盖所有原始数据与动态验证公式；
     - **出版级 16:9 学术演示文稿（PPTX）**：内嵌全部高分辨率原真图表与临床决策结论；
     - **五级自动化审计闭环报告**（`verification_audit_report.json` 与 `.md`）。

### 1.9 全引文基数绝对守恒铁律 (Exact Reference Cardinality & Provenance Protocol)
* **严禁引文截断与漏提**：绝不允许因抓取不全或第三方页面限制导致引文截断！必须核验原刊已发表 PDF 最后一页的终末引用编号（如本次原刊正式版第 16 页达 181 篇），确保引文总数与原刊尾项编号绝对 1:1 守恒（$N_{\text{refs}} \equiv 181$）。
* **全引文元数据结构化**：所有引文必须完整提取并归档在 `original_materials/references_verified.json`，包含序号、完整作者（多作者保留 et al.）、完整篇名、刊名、出版年份、卷期、起止页码及官方 DOI 链接。

### 1.10 机制插图拓扑与版式 1:1 镜面对齐铁律 (Strict Schematic & Topology Mirroring Protocol)
* **严禁篡改原图构图与视觉语言**：叙述性综述的机制流向图，必须 1:1 深度对齐原刊 PDF 构图拓扑，严禁自创偏离原意的通用工程流程框图！
  - **Figure 1 必须具备**：左侧“肾功能受损 (Reduced kidney function)”人体全身剪影及 5 大全身表现（水负荷、酸中毒、电解质紊乱、毒素蓄积、RAAS/SNS 激活）；上方中央原发 AKI 肾脏图符；右侧“肾内炎症 (Intrarenal inflammation)”微观解剖模块（肾小管上皮、DAMPs/ROS、TLR2/4、微血管内皮、TNF-α/IL-10、白细胞趋化招募）；底部收敛汇集于“远隔器官损伤 (Distant organ injury)”大胶囊卡片。
  - **Figure 2 必须具备**：顶部中央大标题横幅（`AKI-INDUCED DISTANT ORGAN DAMAGE`）；原发病因（Ischemia, sepsis, toxins）指向 AKI 肾脏，并伴随持续性肾内炎症（Persistent intrarenal inflammation）指向 CKD 萎缩肾；中央辐射连接 5 大器官交互模块（肺、心、脑、肝、免疫系统），每个模块必须严格由“解剖器官图符 + 病理生理机制白卡 + 临床表型蓝卡”三元构成；中部必须设置完整的“治疗选择 (THERAPEUTIC OPTIONS)”横幅与双列临床干预矩阵；底部必须设置“患者结局 (OUTCOMES)”横幅与三大预后卡片（↑ KRT 及并发症、↑ 远期发病率、↑ 死亡率）。

### 1.11 表格文本与结构 1:1 绝对保真铁律 (Table 1:1 Textual & Structural Fidelity Protocol)
* **必须完整复刻原刊三张主表**：
  - **Table 1**：必须采用原刊经典的 3 列架构（`Stage`, `Serum creatinine`, `Urine output`），包含 3 级分期与精确界值及脚注。
  - **Table 2**：必须完整重构 4 列架构（`Organ/system`, `Biomarkers`, `Status`, `Purpose`），逐一覆盖原刊 7 大系统（肺 [40]、脑 [41, 42]、心 [43]、肝 [44, 45]、感染 [46]、免疫系统 [46]、肾脏 [47]）的所有具体生物标志物及其临床验证状态（Implemented vs Experimental）。
  - **Table 3**：必须完整重构 3 列架构（`Outcome`, `Interaction with AKI`, `Examples from prior trials`），逐一覆盖 6 大结局域（机械通气/无呼吸机天数、心律失常、血流动力学、谵妄/昏迷、感染、术后出血）以及所有临床试验里程碑文献引用（[78], [155, 161, 162, 174], [175-177], [178], [159, 161], [179], [180, 181]）。

### 1.12 全流程原始文件、步骤代码、过程日志与中间结果强制固化与归档铁律 (Mandatory Full-Provenance, Execution Logs & Step-by-Step Intermediate Artifact Archiving Protocol)
* **每一步骤必须强制落地成实体文件并持久化归档**：
  严禁任何内存中暂存、一次性抛弃式计算或无痕执行！从最初的数据捕获到最终报告生成，每一个环节都必须产生并保留对应的底层源文件、执行脚本、过程日志和中间/最终结果：
  1. **原始文件层 (`original_materials/`)**：
     - 必须完整持久化官方原生材料（如 PMC/NLM JATS XML `PMCXXXXX_raw.xml`、官方 PDF 全文提取稿 `PMCXXXXX_fulltext.md`、补充材料与附录）；
     - 必须将解析与提取脚本（如 `parse_pmc.py`, `extract_references.py`, `clean_references.py`）及清洗校验后的引文数据库（`references_verified.json`，含官方 Crossref DOI）同级归档；
     - 包含从零重绘所使用的所有独立医学细胞/器官/设备图元（如 `.jpg`, `.png`）。
  2. **底层数据矩阵层 (`data/`)**：
     - 必须生成完整的结构化提取数据表（如 `.csv`, `.json`），包含所有研究名称、亚组分类、样本量、事件数、效应值及所有协变量，支持人机直接读取。
  3. **多软件统计引擎与计算过程层 (`meta_analysis_toolkit/`)**：
     - 必须同时提供并保留真实运行的 **R 脚本 (`meta_analysis.R`)**、**Python 独立统计引擎 (`meta_engine.py`)** 与 **Stata 批处理脚本 (`meta_analysis.do`)**；
     - 必须真实调用本地环境（如 Rscript、Python）执行计算，保留统计执行的中间输出物、过程日志及中间图表（如 R 生成的高清森林图、漏斗图、气泡图，Python 计算输出的明细表 `Meta_Analysis_Output_Python.xlsx`）；
     - 确保任何第三方审稿人或研究人员均可脱离 AI 独立重现完全一致的数值。
  4. **全套独立执行脚本层 (`scripts/`)**：
     - 每一个产出物（PRISMA 流程图、森林图、漏斗图、亚组回归图、机制图、Master Excel、Word 正文手稿、独立三线表、PPTX 幻灯片）都必须拥有独立的 Python/R 构建脚本，代码行行注释、逻辑透明；
     - 严禁黑盒拼接，所有参数与坐标均可通过修改代码重新执行调整。
  5. **出版级矢量与高清图像层 (`figures/`, `editable_files/`)**：
     - 600 DPI 超清位图、300 DPI 适配图、可编辑矢量 SVG（保留 `<text>`）、印刷级 Type 42 矢量 PDF 分目录严格归档。
  6. **五级自动化审计闭环报告层 (`verification/`)**：
     - 必须包含自动化审计代码（`run_5tier_audit.py`）以及执行后生成的机器可读报告（`verification_audit_report.json`）与人类可读 Markdown 报告（`verification_audit_report.md`）；
     - 真实记录五个门禁的每一个具体测试项、实测值、理论值与合格状态（PASS/FAIL）。

### 1.13 顶刊图件科学规范与原刊 1:1 镜面对齐铁律 (The Strict 1:1 Journal-Grade Scientific Figure Specification)
任何 Meta 分析与系统评价的图表绘制，必须以已发表原刊或国际顶刊（*Critical Care*, *Lancet*, *JAMA*）的图表逻辑与学术规范为唯一黄金标杆，坚决杜绝任何随意发挥、简陋占位与信息降维：
1. **PRISMA 2020 检索与筛选流向图 (Figure 1) 强制规范**：
   - **左侧阶段纵向指示带**：必须规范标示 `Identification`（识别）、`Screening`（筛选）、`Included`（纳入）三大垂直阶段横幅；
   - **顶端数据库输入框**：必须精确注明检索的数据库名称与具体截止日期（例如：`Records identified from PubMed and Embase (December 1st, 2023): 950`）；
   - **初筛排除框 (Screening Exclusion)**：严禁概括粗提！必须 1:1 镜像原刊给出的所有具体临床/方法学排除细项及精确括号数字（例如：动物研究 20、个案报告 53、综述与Meta 47、转化医学 418、非APL急性髓系 62、儿科研究 57、长期随访无早期结局 55、非英法语言 53），细项求和必须绝对严格等于初筛排除总数（$20+53+47+418+62+57+55+53 = 765$）；
   - **全文索取与排除框 (Full-Text Retrieval & Exclusion)**：精确记录索取数（`Records sought: 185`）、未获取数（`17 records not retrieved`）、评估数（`168 assessed`，且 $185 - 17 = 168$），以及全文排除的具体细项与精确数字（重复报告 12、中期分析 1、综述 1、个案 4、非APL 4、无早期结局 4、语种 2，总和绝对严格等于 28）；
   - **最终纳入框 (Final Included)**：精确对应最终纳入文献数与患者总数（`140 studies, 54,923 patients`），全流程流向损耗绝对守恒 ($L \equiv 0$)。
2. **定量森林图 (Figure 2) 科学规范与双轨呈现**：
   - **正文主图规范（汇总亚组森林图 Summarized Subgroup Forest Plot）**：当纳入队列庞大（如 $\ge 50$ 甚至 122 项研究）时，正文主图必须严格遵循原刊的亚组汇总高密度表达方式：按研究类型（干预性 vs 观察性）分栏呈现各组事件数/总样本量（如 $679/8807$ vs $5740/37152$）、RE 模型汇总率及 95% CI（$8\% [6; 9]$ vs $15\% [13; 17]$）、异质性指标（$Q, p, I^2, \tau^2$）、全亚组总合并效应量（$12\% [11; 14]$），绘制贯穿全局的垂直参考虚线（Vertical reference line at 12%），并标注亚组差异 Wald 检验统计量（$Q_M = 24.23, p < 0.01$）；
   - **附录图规范（单队列展开森林图 Individual Study Forest Plots）**：在补充材料或双轨附录中，必须完整提供展开至每一项单独研究的精细森林图（Figure S2 干预性队列展开，Figure S3 观察性队列展开），满足同行评议对个体数据的穿透式核验。
3. **多元元回归气泡图 (Figure 3) 科学规范**：
   - **气泡物理权重映射**：散点气泡的半径大小必须严格由各研究在元回归模型中的方差倒数（$1/\text{SE}^2$）动态计算映射，真实体现样本量与统计精度的视觉权重；
   - **亚组视觉区分**：用双色体系严格区分亚组（如蓝色代表 Interventional studies，绿色代表 Observational studies）；
   - **回归曲线与置信带**：为每个亚组分别拟合元回归回归线，并绘制伴随的 95% 置信区间半透明灰带（Grey 95% CI ribbon），X 轴为入组年代均值（Mean year of inclusion: 1990, 2000, 2010, 2020），Y 轴为早期死亡率（Early mortality rate: 0.0, 0.1, 0.2, 0.3, 0.4）；
   - **顶部标准图例**：顶部居中设立 `Study type — Interventional — Observational` 双色标准图例横幅。
4. **死因与并发症多面板图 (Figure 4) 科学规范**：
   - 必须融合统计定量与解剖可视化，禁止单调粗陋的单色条形图：
     - Panel A：早期死因占比环形图（Donut Chart），标明各病因百分比与总文献/病例数；
     - Panel B：严重出血解剖定位分布，必须左/右嵌入**人体出血解剖投影剪影**，以高亮色彩准确定位颅内（ICH 61%）、肺泡（14%）与消化道（20%），并与置信区间条形图精准对齐；
     - Panel C：并发症病死率（CFR）对比水平条形图，突出展示灾难性颅内出血（CFR 64%）与极低病死率但高发的分化综合征（CFR 5%）；
     - Panel D：年代演变柱状趋势图，展现各年代特定并发症死亡率的阶梯式下降。
5. **病理生理与 ICU 急救机制图 (Figure 5) 科学规范**：
   - 坚决杜绝“纯文字框加子弹项”的伪插图！必须达到顶刊插画级：具备纯净 3D 白血病原幼细胞图元（Auer小体/柴捆细胞）、$t(15;17)$ 染色体易位模型、微血管内皮破损破裂与大量红细胞喷涌外渗的微观动力学断面、致命性脑大出血（ICH）冠状切面、严重弥漫性肺水肿（ARDS）双肺切面，以及 ICU 四大急救器械图元（ATRA胶囊、冷沉淀/血小板输注袋、地塞米松注射器、急诊CT）。

### 1.14 主题分析、精准检索、真实筛选、统计精算与科学制图全流程五维闭环规范 (The 5-Dimensional Scientific Rigor End-to-End Governance Protocol)
以后执行任何一篇新的或复现的 Meta 分析 / 系统评价时，必须强制做到以下五维绝对科学规范：
1. **维度一：主题与临床问题剖析绝对正确 (Accurate Thematic & Clinical Scope)**：
   - 明确定义研究对象（如 APL 早期死亡率）、暴露/干预措施（如靶向分化治疗、诱导方案）、比较组（如临床试验 vs 真实世界观察性研究）、主要结局（30天死亡率）与次要结局（出血、分化综合征、严重感染）；
2. **维度二：检索式与跨库策略绝对正确 (Precise Multi-Database Search Execution)**：
   - 严格遵循 MeSH/Emtree 主题词与自由词布尔逻辑（AND / OR），跨 PubMed、Embase 等数据库执行无遗漏检索，锁定检索截止日期与去重规则；
3. **维度三：文献两级双盲筛选与守恒绝对正确 (Rigorous Two-Stage Screening & Conservation)**：
   - 标题/摘要初筛与全文复筛双级推进，严格记录每一个排除理由分类与入选数字，保证输入、排除、索取、评估与最终纳入的数学等式绝对闭环守恒；
4. **维度四：多软件底层统计分析与建模精算绝对正确 (Validated Multi-Software Statistical Pipeline)**：
   - 严格采用顶刊公认模型：Restricted Maximum Likelihood (REML) 或 DerSimonian-Laird 随机效应模型；
   - 采用 Knapp-Hartung 调整计算置信区间；
   - 严格执行亚组差异检验（Wald-type test）与多元元回归分析（强制输入法，解释方差 $R^2$ 评估）；
   - 双向使用 R（`meta`/`metafor`）与独立统计引擎交叉验算，确保汇总率、95% CI、$\tau^2$、$I^2$、$Q$ 与 $P$ 值与原刊完全一致；
5. **维度五：图表科学制图与出版级交付绝对规范 (Scientific Figure Standardization & Delivery Suite)**：
   - 严格按照 1.13 与 1.15 条款标准，纯代码数学矢量生成 600 DPI Ultra-HD 超高清母版（$\ge 3800\text{ px}$），并同步输出纯矢量 SVG（含 `<text>` 标签）、印刷级 Type 42 矢量 PDF、带防撕裂 XML 的 Word 三线表、16:9 宽屏 PPTX 与多工作表 Master Excel。

### 1.15 顶刊（Critical Care / Lancet）PRISMA 2020 流程图与定量森林图 1:1 像素级镜面约束与科学校验规范 (Mandatory 1:1 Pixel-Level Mirroring & Constraint Protocol)
基于顶级医学期刊（*Critical Care*, *Lancet*, *JAMA*）的正式发表原刊，强制约束以下排版构图与科学要素，杜绝任何概念漂移与简化：
1. **PRISMA 2020 流程图顶刊经典构图规范 (Figure 1)**：
   - **顶部大横幅**：必须设置金色/琥珀色实心横幅（如 `#F59E0B` 或 `#D97706`），文字加粗：`Identification of studies via databases and citation searching`；
   - **左侧阶段纵向导航条**：必须使用淡蓝或深蓝色卡片竖向排列 `Identification`、`Screening`、`Included`，文字垂直居中旋转 90 度；
   - **跨库检索框明细列示**：数据库检索必须明确标注数据库数量（如 `Databases (n = 4):`），并逐行罗列数据库名称与精确命中篇数（如 `Embase (n = 279)`、`Scopus (n = 210)`、`Web of Science (n = 117)`、`PubMed (n = 88)`），下方紧随 `Citation searching (n = 1)`；
   - **初筛前排除框严格拆分**：右侧初筛前排除必须包含 3 个标准子类：`Duplicate records removed (n = 333)`、`Records marked as ineligible by automation tools (n = 0)`、`Records removed for other reasons (n = 0)`，严禁遗漏自动化工具项；
   - **初筛与索取流向闭环**：初筛数量必须严格等于检出总数减去重复数（$695 - 333 = 362$）；初筛排除数（$n = 316$）；索取评估数（$362 - 316 = 46$）；未获取数（`Reports not retrieved (n = 0)`）；
   - **全文排除原因 1:1 拆分**：绝对禁止将原因笼统合并为“其他”或“不符”！必须严格按原刊拆分为细分项（如：`Conference abstracts (n = 9)`、`Reviews (n = 5)`、`Generic hospital readmission (n = 3)`、`No deep learning model (n = 3)`、`Including paediatric population (n = 2)`），排除细项加总必须严格等于 $22$（$9+5+3+3+2 = 22$）；
   - **纳入框双层架构**：最终纳入必须同时标明文献数与报告数：`Studies included in review (n = 24)` 与 `Reports of included studies (n = 24)`；
   - **数学流向绝对无损**：全图流向损耗绝对守恒 ($L \equiv 0$)。

2. **定量森林图顶刊镜面级排版规范 (Figure 2)**：
   - **表头双横线结构**：最上方设置粗实线（lw = 1.5），栏目标题（`Authors (year)` 与 `AUROC [95% CI]`）下方设置细实线（lw = 1.0）；
   - **亚组命名 1:1 镜面对齐**：亚组标题必须与原刊术语完全一致（例如必须采用 `General ICU populations` 与 `Specific subpopulations`，严禁擅自篡改为非原刊用词）；
   - **个体队列与数值绝对保真**：个体研究的点估计值与 95% CI 必须与原刊完全一致（例如 `Lim et al. (2025)` 必须准确呈现为 `0.83 [0.82, 0.85]`）；
   - **方块面积精准映射**：研究点估计方块（Box）必须严格映射统计权重，误差线（Whiskers）末端必须带有微小垂直截线（Caps）；
   - **汇总菱形与贯穿虚线**：
     - 亚组汇总菱形必须标明异质性指标：`RE Model for Subgroup (I² = 99.94%)` 与 `RE Model for Subgroup (I² = 17.06%)`；
     - 总体合并菱形上方必须设立水平分隔细线，名称加粗：`RE Model for All Studies (I² = 99.96%)`，数值居右对齐：`0.79 [0.73, 0.85]`；
     - 垂直参考虚线必须精准从总体合并效应量中心（$0.79$）纵贯整个图幅；
   - **组间差异检验注记**：必须在总体菱形正下方标明组间差异检验结果：`Test for Subgroup Differences: p = .002`；
   - **坐标轴极简规范**：横轴刻度线仅显示主要分度值（如 `0.6`, `0.7`, `0.8`, `0.9`, `1`），中间靠下居中标注 `AUROC`，无多余装饰框。

3. **有界变量 Meta 分析的 Logit 转换铁律**：
   - 对严格处于 $(0, 1)$ 有界区间的临床指标（如 AUROC、C-index、患病率、敏感度、特异度），在进行随机效应模型计算时，必须优先使用 Logit 变换（$\text{logit}(p) = \ln\frac{p}{1-p}$）进入正态尺度计算，避免直接线性加权导致的置信区间越界（$> 1.0$ 或 $< 0.0$）；
   - 计算完成后必须通过逆 Logit 变换（$\text{ilogit}(z) = \frac{e^z}{1+e^z}$）反演回临床直观的 $(0, 1)$ 尺度，保证统计严密性与顶刊同行评议标准一致。

---



## 2. 核心质控生命线：全流程五级强制验证与证据可溯源铁律 (The Mandatory 5-Tier Verification & Traceability Protocol)

所有复现与学术交付项目**必须将“验证”作为前置门禁（Verification Gates）**贯穿始终。任何未经双向验证的数据、检索流与图表，一律禁止进入下一阶段或交付用户！

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        五级验证门禁系统 (The 5-Tier Verification Gates)                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Gate 1 【检索与方法学闭环验证】: 语法布尔逻辑、跨库检出求和守恒、PRISMA 流数学绝对闭环 │
│  Gate 2 【原始真伪与坐标溯源验证】: DOI/PMID/PMCID 三元互锁、原始资产归档、证据坐标锚定 │
│  Gate 3 【统计学一致性与精算验证】: 队列样本量守恒、分母子集审计、百分比与 95% CI 自洽  │
│  Gate 4 【代码与视觉呈现无损验证】: 零底图代码渲染、解剖真实保真度、文字边界防重叠、SVG│
│  Gate 5 【交付资产可溯源审计验证】: Master Excel 单元格级溯源、Word XML 注入、审计报告  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Gate 1：检索策略与流程图数学闭环验证 (Search & PRISMA Flow Verification Gate)
1. **检索式语法与布尔逻辑核验**：
   - 必须逐行核验 MeSH 主题词（`exp .../`, `*.../`）、自由词字段修饰符（`.tw.`, `.mp.`, `[tiab]`）及邻近检索词（`adj`, `NEAR`）的合法性；
   - 必须校验年代过滤器（如 `1992-Current`）、人群限制（如成人限制、排除纯儿科）、语种限制（如英语）与研究类型过滤器（Cochrane RCT Filter）的布尔逻辑交集（AND / OR / NOT）。
2. **跨库命中量与阶段流向守恒验证**：
   - **检出总数守恒**：$\sum N_{\text{databases}} + N_{\text{registries/tracking}} \equiv N_{\text{total identified}}$，必须逐个数据库核对并累加，零差错；
   - **去重与初筛前过滤守恒**：$N_{\text{total}} - (N_{\text{manual}} + N_{\text{software}} + N_{\text{automated}}) \equiv N_{\text{abstract screened}}$；
   - **初筛排除与全文评估守恒**：$N_{\text{screened}} - N_{\text{abstract excluded}} \equiv N_{\text{fulltext assessed}}$；
3. **全文排除原因流向平衡与对账审计（Flow Discrepancy & Reconciliation Audit）**：
   - 必须将全文排除框内的所有细分原因逐项累加：$\sum N_{\text{reasons}} = N_{\text{total excluded}}$；
   - 验证下游纳入数：$N_{\text{assessed}} - N_{\text{total excluded}} \equiv N_{\text{eligible trials}}$；
   - **作者笔误识别与穿透对账**：若原刊图表标题存在归类口径脱节（例如原图表头标注排除 $238$ 篇，但细项累加为 $278$ 篇，差额为 40 篇伴随报告/重复分析），必须以文献底层实际流平衡为准进行闭环对账，在图表注记与审计报告中明确标示对账依据，杜绝数字悬空断流。

### 2.2 Gate 2：原始真伪与凭据溯源锚定 (Authenticity & Primary Evidence Provenance Gate)
1. **三元互锁验证（Triad Cross-Lock）**：
   - 必须核验原刊正式发表的 **DOI**、**PMID** 与 **PMCID**，确保三者一一对应；
   - 查验 PROSPERO 临床方案预注册号（如 `CRD42024510506`）及更新记录。
2. **三位一体官方原始资料归档（Primary Evidence Archiving）**：
   - 必须在本地 `original_materials/` 目录完整归档：① 已发表官方原版 PDF (Version of Record)；② JATS/NLM 结构化底层 XML 全文；③ 官方 Supplementary Materials（包含全部 MOESM 附件，如检索策略表、数据提取字典、纳入试验大表）。
3. **坐标级证据溯源（Provenance Coordinate Anchoring）**：
   - 任何提取的数据、参数、截断值、分子机制或结论，必须标注原始出处坐标（格式：`[文档标识]:[表格/段落号]:[字段名]`，例如 `MOESM1_ESM.docx:Table 1:Step 39` 或 `fulltext.xml:Par3`）；
4. **零大模型臆测铁律（Zero LLM Hallucination Rule）**：
   - 严禁大模型根据通用医学常识擅自脑补缺失数据；若原文献确实未报告（如 382 篇未报告合并症），必须如实标记为“Not Reported”，不可编造统计学均值。

### 2.3 Gate 3：底层数值与统计学一致性验证 (Numerical & Statistical Consistency Gate)
1. **样本量与队列闭环校验**：
   - 纳入研究总数必须精确等于各亚组之和（例如：总试验 $591 = 382 \text{ 未报告} + 209 \text{ 报告}$）；
   - 患者总数、中位数、四分位距（IQR）必须与全文及附录逐一核对（如 $N = 48,429$，中位数 $91$, IQR $56\text{--}211$）。
2. **分母基准与患病率精算核验**：
   - 必须严格区分“报告率分母”（总纳入试验数 $N=209$）与“患病率分母”（仅报告该特定合并症的试验入组患者数子集）；
   - 验算所有百分比精度（如糖尿病报告率 $180 / 209 = 86.124\% \rightarrow 86.1\%$；糖尿病患病率 $8,638 / 35,492 = 24.338\% \rightarrow 24.3\%$），确保与原刊报告百分比保持最高精度对齐。
3. **统计检验指标自洽性核算**：
   - 必须核算假设检验指标：检验统计量（如 Kruskal-Wallis $\chi^2(2) = 6.25$）、自由度、P 值（$p = 0.040$）、Spearman 相关系数（$\rho = 0.80, p < 0.001$）、OR/RR 及其 95% CI 上下界（$OR = 1.08, 95\% \text{ CI } [1.06, 1.11]$），保证数学自洽无悖论。

### 2.4 Gate 4：渲染代码、真实临床影像与医学插画视觉门禁 (Rendering Code, Clinical Imaging & Biological Artwork Gate)
1. **全要素纯净重绘与零作者低清光栅门禁 (Complete Redraw & Zero-Author-Raster Gate)**：
   - 方法学流程图（PRISMA/CONSORT）、森林图、漏斗图等纯统计/流向图件，**严禁将位图作为底图进行描摹**！必须完全依靠纯 Python / SVG 代码根据几何数学坐标从零渲染生成；
   - 纯统计图件 SVG 中严禁包含任何内嵌 base64 栅格图，所有文字节点必须保留为原生 `<text>` 标签。
2. **BioRender / Figdraw 顶级医学手绘插画铁律 (BioRender / Figdraw Biological Artwork Mandate - Zero-Simplistic-Code-Box Rule)**：
   - **机制图（Graphical Abstract / Mechanistic Hub / Pathophysiological Pathways）必须达到 BioRender / Figdraw 等国际顶刊级医学艺术手绘水准**！
   - **绝对禁止用 Matplotlib 简单几何形状（矩形框、圆角框、简单椭圆、彩色气泡）堆叠假冒生物病理机制图**（写代码简单绘图在机制表达上是远远不够的！）。
   - 必须呈现真实的三维生物医学微观/宏观解剖艺术：精准绘制器官解剖断面（如肥胖躯干、受压横膈、气管插管与食道压球囊）、肺泡微环境（过度膨胀薄壁肺泡与毛细血管受压闭塞 vs 萎陷水肿实变肺泡与大量渗出）、受体极性分子排布及心肺交互动力学，再通过抗锯齿高清排版引擎复合顶刊标题栏、跨肺压物理公式徽标与临床决策卡片。
3. **真实临床影像切片直出铁律 (Authentic Clinical Diagnostic Imaging Protocol)**：
   - 当文献原文包含真实患者诊断影像（如**胸部轴位 CT 扫描、真实临床 EIT 肺阻抗断层切片、超声波形、血管造影**）时，**绝对禁止用任何简陋的几何卡通示意图替代真实影像**！
   - 必须直接提取并保留原刊真实的患者影像切片（保持解剖与病理原真性），将其镶嵌于高分辨率矢量画框内，并配以矢量放射学解剖读片箭头、标尺、梯度对比面板及出版级西文字体（Helvetica/Arial）进行多维复合呈现。
4. **几何边界与绝对防碰撞校验（Zero-Collision & Bounding Box Check）**：
   - 渲染脚本必须包含动态坐标测算或文本分行机制，**绝对禁止连接箭头穿透文字标签内部、绝对禁止解剖图元压盖机制卡片边框与标题**，所有视觉要素留白呼吸感充足。
5. **纯矢量文字节点扫描**：
   - 检查 SVG 产物源码：必须包含可编辑的 `<text` 标签节点，严禁出现将字体轮廓化（Path Outline）的假矢量操作；
6. **字体与超高分辨率质量门禁（600 DPI Ultra-HD Standard）**：
   - PDF 文件必须嵌入 Type 42 TrueType 字体；PNG 出版母版位图长宽分辨率必须达到 **$600\text{ DPI}$（主画布尺寸 $\ge 3800\text{ px}$，主图可达 $8000\sim 9600\text{ px}$）**，具备顶刊展板级超高清质感；
   - 必须多格式强同步：600 DPI PNG、300 DPI PNG、矢量 PDF、纯矢量 SVG、Word/PPTX 内部媒体必须同时更新且 100% 一致。

### 2.5 Gate 5：交付资产可溯源性与自动化审计报告 (Deliverables Traceability & Audit Gate)
1. **Master Excel 单元格级公式与溯源**：
   - 交付的 `Master_Research_Database.xlsx` 中，汇总行必须使用标准 Excel 公式（`SUM`, `AVERAGE`, `COUNTIF`），各 Sheet 必须设立“Data Source”列明确记录该行数据的原始出处。
2. **Word 手稿底层 XML 防截断校验**：
   - 自动化扫描 `Manuscript_Full_Text_Submission_Ready.docx` 及各分立表，确保表格第一行注入 `<w:tblHeader/>`，所有数据行注入 `<w:cantSplit/>`。
3. **自动化生成审计报告（Verification Audit Report）**：
   - 每个项目交付时，**必须自动生成并归档两个审计文件**：
     - `verification_audit_report.json`（机器可读的结构化验证指标与数值对账单）；
     - `verification_audit_report.md`（人类可读的高管级验证声明与五级质检证据链）。

---

## 3. 标准操作程序（6 阶段端到端 SOP 与对应验证门禁）

```
┌──────────────────────────────────────────────────────────────────────────┐
│              SOP 阶段 1：文献与多源附录全息捕获 (Harvesting)              │
│    - 原文 PDF / HTML / JATS XML 抓取与文本解析                             │
│    - Supplementary Materials (MOESM1~MOESM6) 完整解构与提取               │
│    ★ 强制执行 Gate 2: DOI/PMID/PMCID 三元互锁与坐标溯源锚定              │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│           SOP 阶段 2：图表骨架逆向工程映射 (Ground-Truth Catalog)         │
│    - 建立 1:1 图表真实清单（Figure 1~N, Table 1~N, Supplementary Tables） │
│    - 识别图表属性：定量森林图/流程图 VS 定性概念机制图/阶段图             │
│    ★ 强制执行 Gate 1: 检索式语法审计、跨库求和守恒与 PRISMA 流数学闭环     │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│               SOP 阶段 3：底层统计数据与临床参数结构化 (Data Extraction)  │
│    - 提取样本量、效应值、置信区间、靶向剂量、标志物阈值、试验结论         │
│    - 构建多工作表结构化 Master Database (Excel .xlsx)                     │
│    ★ 强制执行 Gate 3: 队列样本量闭环、分母子集审计与统计指标自洽核算     │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│           SOP 阶段 4：出版级图表矢量渲染 (Multi-Format Rendering)         │
│    - 纯代码从零渲染纯矢量 SVG (强制 svg.fonttype='none')                  │
│    - 出版级矢量 PDF (强制 pdf.fonttype=42, Type 42 字体)                  │
│    - 300+ DPI 印刷级 PNG 位图                                             │
│    ★ 强制执行 Gate 4: 零底图依赖代码验证、文字边界防重叠与 SVG 文本扫描   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│            SOP 阶段 5：Office 办公套件工业级排版 (Office Suites)          │
│    - Word 表格注入 <w:tblHeader/> 与 <w:cantSplit/>                      │
│    - 生成 16:9 PPTX 幻灯片与完整投稿手稿 (Manuscript_Submission_Ready)   │
│    ★ 强制执行 Gate 5: Master Excel 单元格溯源与 Word XML 防撕裂核查       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              SOP 阶段 6：零缺陷质校验收与交付 (Audit & Delivery)          │
│    - 运行全自动质检脚本，扫描字符编码与数学自洽性                         │
│    - 自动生成 verification_audit_report.json 与 verification_audit_report.md│
│    - 输出规范的交付文件目录与可点击访问链接                               │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 图表工程化实现规范与关键代码模板

### 4.1 叙述性/机制性解剖病理图绘制铁律 (Biomedical & Pathophysiological Illustration Standard)
1. **解剖机制图“零方块敷衍”铁律 (Zero-Simplistic-Box Protocol)**：
   - 严禁将精密的人体解剖系统（如肾单位、肺泡毛细血管膜、心脏传导系统）粗暴简化为带文字的圆角矩形和直线箭头！
   - 对于从零纯代码渲染的解剖生理图件，必须构建三大核心图层：
     - **宏观解剖与微环境层 (Macro-Anatomy & Gradient Environment)**：
       - 真实的生理走行动力学（例如肾小球毛细血管球与包曼囊包绕、近曲小管弯曲盘绕、降支细段深入高渗髓质、亨利袢发夹形 U 弯、粗升支返折穿行于入球与出球小动脉之间并在致密斑处形成解剖接触、远曲小管与皮质/髓质集合管分支汇集）；
       - 组织微环境渗透压或氧分压渐变梯度背景（如皮质 300 mOsm/kg $\rightarrow$ 外髓质 600 mOsm/kg $\rightarrow$ 内髓质乳头深部 1200 mOsm/kg，带平滑渐变底色与物理标尺）。
     - **微观细胞膜极性与分子转运层 (Micro-Cellular & Transporter Polarization)**：
       - 提供高分辨率细胞膜解剖局部视窗，清晰区分管腔膜（Apical Membrane with Brush Border）与基底外侧膜（Basolateral Membrane facing Peritubular Capillaries）；
       - 绘制具体跨膜转运体与离子通道（如 NHE3, SGLT2, NKCC2, NCC, ENaC, AQP2, 及全段通用的基底侧 $Na^+/K^+$ ATPase 泵），明确标示离子的跨膜转运化学计量与电化学势能。
     - **生理反馈回路与临床干预层 (Physiological Feedback & Clinical Synergy)**：
       - 完整展现代偿与反馈通路：如利尿剂抵抗的远端肥大、代偿性氯重吸收、管球反馈（TGF: 致密斑感受溶质增加致腺苷释放与入球微动脉收缩）、肾静脉淤血对有效滤过压的抑制；
       - 标注精准的药物分子结合靶点、推荐临床剂量及里程碑试验凭据锚定（如 ADVOR, CLOROTIC, EMPULSE, ATHENA-HF 等）。
2. **顶刊医学插画设计美学规范**：
   - 采用国际医学顶刊（*NEJM*, *Lancet*, *Nature Medicine*）经典科研配色：柔和肉粉色、淡浅蓝、高渗紫灰渐变、低饱和度警示红与琥珀色，避免刺眼荧光与低端工程色块；
   - 保持原生纯矢量文本（SVG `<text>`，PDF Type 42），排版留白呼吸感充足，绝对无文本遮挡与坐标重叠。

### 4.2 矢量图渲染强制配置
```python
import matplotlib.pyplot as plt

# 强制文字保留为原生可编辑文本，严禁轮廓化
plt.rcParams['svg.fonttype'] = 'none'
# 强制 PDF 嵌入 Type 42 TrueType 字体
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
```

### 4.3 Word 文档三线表与 XML 跨页防撕裂控制
在生成 Python `python-docx` 表格时，为防止跨页断行以及打印时表头丢失，必须强制执行底层 XML 注入：

```python
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def apply_table_engineering_rules(table):
    # 1. 表头行注入：跨页自动重复 + 行内不分页断裂
    header_tr = table.rows[0]._tr.get_or_add_trPr()
    header_tr.append(OxmlElement('w:tblHeader'))
    header_tr.append(OxmlElement('w:cantSplit'))
    
    # 2. 所有数据行注入：行内不分页断裂
    for row in table.rows[1:]:
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:cantSplit'))
        
    # 3. 单元格内边距微调 (上/下 100 dxa, 左/右 120 dxa)
    for row in table.rows:
        for cell in row.cells:
            tcMar = OxmlElement('w:tcMar')
            for m, val in [('top', 100), ('bottom', 100), ('left', 120), ('right', 120)]:
                node = OxmlElement(f'w:{m}')
                node.set(qn('w:w'), str(val))
                node.set(qn('w:type'), 'dxa')
                tcMar.append(node)
            cell._tc.get_or_add_tcPr().append(tcMar)
```

---

## 5. 交付文件组织与目录规范

所有基于本规范执行的项目，必须生成如下标准层级交付矩阵（含质检与审计报告目录）：

```text
<project_root>/
├── figures/                                    # 高清印刷位图 (>= 300 DPI, 主画布 >= 3000 px)
│   ├── Figure1_PRISMA_2020_Flow_Diagram.png
│   ├── Figure2_Mechanisms_and_Anatomical_Targets_of_SNB.png
│   ├── Figure3_Network_Geometry_Map.png
│   ├── Figure4_Forest_Plots_and_SUCRA_Ranking_Curves.png
│   └── Figure5_Risk_of_Bias_2_Assessment.png
│
├── editable_files/
│   ├── vector_svg/                             # 纯矢量 SVG (live text 原生 <text> 节点，可二次编辑)
│   ├── vector_pdf/                             # 出版级矢量 PDF (嵌入 Type 42 TrueType 字体)
│   └── office_docs/                            # 微软原生 Office 可编辑办公套件
│       ├── Manuscript_Full_Text_Submission_Ready.docx  # 投稿级完整手稿正文（含内嵌图表与全部引用）
│       ├── Table1_Baseline_Characteristics_29_RCTs.docx
│       ├── Table2_Network_League_Table_Efficacy_Safety.docx
│       ├── Table3_SUCRA_Rankings_and_Evidence_Grading.docx
│       ├── Publication_Figures_and_Tables.pptx         # 16:9 高清学术报告演示文稿
│       └── Master_Research_Database.xlsx               # 原始结构化多工作表数据库 (8 Sheets，公式自洽)
│
├── verification/                               # ★ 强制审计与验证凭证归档目录
│   ├── verification_audit_report.json          # 结构化机器可读验证指标（检索守恒、流平衡、统计检验量）
│   └── verification_audit_report.md            # 高管级可读 5 级验证声明与证据坐标对账单
│
└── original_materials/                         # 原始文献与附录归档（溯源存根）
    ├── included_29_rcts_metadata.json          # 29项纳入RCT元数据
    └── references_verified.json                # 79项真实DOI验证凭据
```

---

## 6. 验收质检清单 (Quality Assurance Checklist & Gates)

交付前必须逐项核对并确保 100% 达标：

- [ ] **Gate 1 检索与流平衡验证**：
  - 各数据库检出量求和是否等于总数？
  - 去重与初筛前过滤是否守恒？
  - PRISMA 全文排除细项加和是否与纳入量数学闭环？
- [ ] **Gate 2 真实性与坐标溯源验证**：
  - DOI 是否 100% 经权威 Handle API / Crossref 在线解析验证（0 伪造）？
  - 本地 `original_materials/` 是否具备真实试验元数据与校验单？
- [ ] **Gate 3 底层统计一致性验证**：
  - 纳入试验总数、总患者数、干预组与对照组数据是否完全自洽？
  - 效应量（OR/MD）与其 95% 置信区间/可信区间是否数学一致？
- [ ] **Gate 4 渲染代码与视觉保真度验证 (Mandatory Complete Redraw)**：
  - 流程图与统计图是否 100% 纯代码从零生成（零位图背景依赖）？
  - **解剖机制图是否彻底执行全要素从零纯净重绘（100% 杜绝在作者低清 PPT 位图上涂抹补字）？**
  - 是否包含高精独立解剖器官、微环境细胞、生理管腔形态学与重症医疗场景图元？
  - 几何空间与拓扑是否通过**绝对防碰撞检测（箭头与文字零交叉、图元与卡片边框零压盖）**？
  - SVG 源码是否包含原生可编辑 `<text>` 节点？PDF 是否嵌入 Type 42 TrueType 字体？
  - PNG 出版母版分辨率是否 **$\ge 600\text{ DPI}$（主画布尺寸 $\ge 3800\text{ px}$）**？
  - 600 DPI PNG、300 DPI PNG、PDF、SVG 与 Word/PPTX 内部媒体是否多格式强同步 100% 一致？
- [ ] **Gate 5 交付资产可溯源性验证**：
  - `Master_Research_Database.xlsx` 各工作表是否包含数据源列与自动汇总公式？
  - Word 文档表格是否全部注入 XML `<w:tblHeader/>` 与 `<w:cantSplit/>`？
  - `verification/` 目录下是否已生成 `verification_audit_report.json` 与 `verification_audit_report.md`？
- [ ] **字符编码安全扫描**：
  - 脚本与输出文本是否强制 UTF-8？是否存在 `?`、乱码或破折号异常？
- [ ] **6 大格式完整性**：
  - PNG、SVG、PDF、DOCX、PPTX、XLSX 以及 Audit Report 是否全部在本地磁盘生成就绪？

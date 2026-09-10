# GitHub Copilot Instructions: Sci-NMA Reproduction Framework

This repository provides an industrial-grade autonomous agent framework for reproducing and synthesizing systematic reviews, pairwise/network meta-analyses, and narrative reviews for top clinical medicine journals (Lancet, JAMA, BMJ, NEJM, Critical Care).

When modifying or generating code in this repository:
1. Always maintain the 5-Tier Verification Gates contract.
2. When creating PRISMA 2020 flow diagrams, verify that identification, screening, full-text review, and inclusion numbers form an exact mathematical identity (L ≡ 0).
3. In meta-analysis modules, use Restricted Maximum Likelihood (REML) or DerSimonian-Laird with Knapp-Hartung adjustment. Use logit/inverse-logit transformations for bounded metrics (AUROC, prevalence, event rates).
4. When exporting Matplotlib figures:
   - Always set `plt.rcParams['svg.fonttype'] = 'none'` to retain live XML `<text>` tags.
   - Always set `plt.rcParams['pdf.fonttype'] = 42` to embed Type 42 TrueType fonts.
5. In Word document generation (`python-docx`), always inject XML `<w:tblHeader>` into the header row and `<w:cantSplit>` into all table rows to prevent cross-page table splits.
6. Master Excel sheets must include frozen panes, column formatting, and live formulas (`SUM`, `AVERAGE`, `COUNTIF`).
7. Always maintain UTF-8 encoding across all scripts and CLI outputs (`sys.stdout.reconfigure(encoding='utf-8')`).

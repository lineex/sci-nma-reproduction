---
name: lit-intelligence-mining
description: Comprehensive academic intelligence mining through forward (citing) and backward (reference) literature analysis. Trace academic genealogy, identify foundational works, track paradigm shifts, discover research fronts, and uncover high-value research gaps.
---

# Literature Intelligence Mining (Forward & Backward Citation Analysis)

Use this skill when you need to analyze the bibliographic network of a scientific paper, domain, or clinical topic to:
1. Trace foundational ancestral studies (Backward Reference Mining).
2. Track recent downstream applications, clinical translations, and research fronts (Forward Citing Mining).
3. Identify unaddressed research gaps, conflicting evidence, and emerging methodology.

---

## 1. Backward Reference Mining (Academic Genealogy)

### Objectives
- Identify pioneer and landmark trials (e.g. initial discovery, RCTs that changed guidelines).
- Map theoretical and methodological pillars across domains.
- Construct the chronological evolution of concepts and diagnostic criteria.

### Analytical Dimensions
1. **Foundational Work Identification**: Flag seminal papers published in top journals (IF >= 10, Lancet, NEJM, JAMA) or cited > 500 times.
2. **Methodology Genealogy**: Identify where the statistical, analytical, or clinical intervention protocol originated.
3. **Temporal Landmark Timeline**: Build a timeline from the earliest foundational reference to the present day.

---

## 2. Forward Citing Literature Mining (Research Fronts)

### Objectives
- Discover where the field moved after key trial publications.
- Detect recent clinical trials, meta-analyses, and secondary subgroup analyses.
- Uncover emerging controversies, safety signals, or resistance patterns.

### Analytical Dimensions
1. **Citation Velocity & Trajectory**: Track year-by-year citation growth and international adoption.
2. **Sub-specialty Expansion**: Detect whether findings from critical care were adopted in anesthesia, cardiology, nephrology, or emergency medicine.
3. **Identified Research Gaps**: Extract limitations explicitly stated in citing works to justify a new systematic review or network meta-analysis.

---

## 3. Structured Output Template

When executing this skill, output a structured Academic Intelligence Dossier:
```markdown
# Academic Intelligence Dossier

## 1. Foundational Pillars & Historical Genealogy
- Landmark RCT 1: [DOI / Title / Year / Impact]
- Landmark RCT 2: [DOI / Title / Year / Impact]

## 2. Methodological Evolution Timeline
- [Year]: [Milestone concept or diagnostic criteria change]
- [Year]: [First major multi-center RCT]
- [Year]: [First Cochrane Review or International Guideline]

## 3. Downstream Clinical Adoption & Research Fronts
- Frontier Cluster A: [Description of emerging research branch]
- Frontier Cluster B: [New biomarker or technology integration]

## 4. Unaddressed Clinical Gaps & Rationales for New Review
- Gap 1: [Underpowered subgroup or conflicting outcome definition]
- Gap 2: [Lack of head-to-head comparison between newer interventions -> NMA rationale]
```

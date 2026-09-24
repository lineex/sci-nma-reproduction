---
name: sci-nma-reproduction
version: 2026-09-25
description: Routes new clinical systematic reviews and meta-analyses through a protocol-first Cochrane-based workflow with Zotero full-text provenance. Loads the separate publication-reproduction and calibration module only when the user explicitly asks to reproduce or calibrate an already-published study.
---

# Evidence Synthesis Workflow Router

First classify the requested work, then load only its workflow module:

- **New review question, systematic review, pairwise meta-analysis, or network
  meta-analysis:** use [the new-review module](modules/new-systematic-review.md).
- **Reproduce, replicate, or calibrate a named published study or its analysis:**
  use [the publication-reproduction module](modules/publication-reproduction.md).
- A new review is not a reproduction task. Do not load reproduction-only
  instructions, calibration fixtures, or example-study assumptions for it.

For new reviews, follow the project's approved protocol and the stage ledger;
dispatch one executor and two independent reviewers for each release gate.
Screening, extraction, and risk-of-bias decisions must retain their own paired
independent decisions. An agent's recommendation is not a stage approval; the
orchestrator records the decision after reviewing the required reports.

Use the current Cochrane Handbook chapters mapped in
[`docs/COCHRANE_AGENT_REQUIREMENTS.md`](../../docs/COCHRANE_AGENT_REQUIREMENTS.md).
That document distinguishes Handbook methods from project choices such as
Zotero, AI role cards, and the two-reviewer ledger. Preserve the approved
project figure/table contract; change it only when the project owner asks.

Do not load all role cards up front. For each new-review stage, assemble only
the generic executor or reviewer card, the relevant stage-method row, the
approved protocol, and that stage's declared inputs.

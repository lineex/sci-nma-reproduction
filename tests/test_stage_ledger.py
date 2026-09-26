import hashlib
import json
from pathlib import Path


import pytest

from sci_nma_agent.workflow.stage_ledger import AgentStageLedger, StageLedgerError
from sci_nma_agent.workflow.protocol_validation import (
    validate_analysis_manifest,
    validate_analysis_manifest_binding,
    validate_analysis_manifest_file,
    validate_fact_status_manifest,
    validate_full_text_screening_manifest,
    validate_full_text_fact_state,
    validate_full_text_retrieval_manifest,
    validate_methods_source_log,
    validate_review_protocol,
    validate_title_abstract_screening_manifest,
)
import sci_nma_agent.workflow.stage_ledger as stage_ledger_module
from sci_nma_agent.databases.zotero_mcp import ToolCallEvidence
from sci_nma_agent.workflow.manual_fulltext_queue import confirm_zotero_attachment


def _write(project, relative, text):
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return relative


def _mcp_call_record(tool_name, arguments, raw_response):
    canonical = json.dumps(raw_response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "provenance": {
            "source": "zotero_mcp",
            "tool_name": tool_name,
            "arguments": arguments,
            "called_at": "2026-09-25T12:00:00Z",
        },
        "raw_response": raw_response,
        "raw_response_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _valid_protocol_text():
    template = Path(__file__).parents[1] / "data" / "templates" / "review_protocol_template.json"
    protocol = json.loads(template.read_text(encoding="utf-8"))
    values = {
        "project.id": "review-1",
        "project.title": "Test review",
        "project.lead": "Lead reviewer",
        "project.created_date": "2026-09-25",
        "question.population": "Adults admitted to hospital",
        "question.intervention_or_exposure": "Intervention A",
        "question.comparator": "Usual care",
        "question.clinical_context": "Acute care",
        "question.objective": "Estimate the comparative effect on mortality",
        "methods_sources.chapter_scope_rationale": "Chapters 1-11 and 14 cover protocol, selection, analysis, NMA context, and certainty for this intervention review.",
        "eligibility.multiple_reports_linkage_rule": "Link reports sharing trial registration or cohort identifiers",
        "eligibility.report_characteristics.publication_status": "Peer-reviewed and preprint reports",
        "eligibility.report_characteristics.language_policy": "No language restriction",
        "eligibility.report_characteristics.date_limits": "From database inception to planned search date",
        "eligibility.report_characteristics.restriction_rationale": "No date or language restrictions are planned",
        "search.planned_date_range": "Database inception to 2026-09-30",
        "search.planned_search_date": "2026-09-30",
        "search.restrictions_and_rationale": "No restrictions planned",
        "search.search_peer_review_plan": "Second information specialist checks all strategies before execution",
        "selection.adjudicator": "Third reviewer",
        "selection.conflict_resolution": "Disagreements are discussed, then resolved by the adjudicator",
        "full_text.collection_name": "Review full text",
        "full_text.attachment_policy": "Retain source attachment and archive a byte-identical project copy",
        "full_text.identity_matching_policy": "Match DOI, then PMID, then manually verify title and authors",
        "full_text.unavailable_report_policy": "Attempt available routes and keep unresolved reports not_assessed_pending_full_text",
        "full_text.fact_classification_rule": "Access, review, and fact states are separate; unavailable text is not evidence of non-reporting",
        "full_text.ocr_policy": "Flag scanned PDFs for OCR and verify page alignment manually",
        "data_collection.independent_verification_rule": "Two extractors work independently and reconcile every difference",
        "data_collection.pilot_and_training_plan": "Pilot the form on three varied eligible reports and refine before full extraction",
        "data_collection.author_contact_policy": "Contact corresponding authors twice at least two weeks apart",
        "risk_of_bias.disagreement_resolution": "Discuss domain judgments and refer unresolved differences to an adjudicator",
        "synthesis.clinical_methodological_compatibility_rule": "Pool only studies aligned on population, intervention, comparator, outcome and estimand",
        "synthesis.model_and_estimator": "Random-effects REML with Hartung-Knapp adjustment",
        "synthesis.confidence_interval_method": "95% confidence intervals using Hartung-Knapp adjustment",
        "synthesis.multi_arm_study_rule": "Use a model that accounts for within-study correlation across arms",
        "synthesis.multiple_outcome_rule": "Use the prespecified measure and time point; model dependency or select one estimate by rule",
        "synthesis.missing_data_rule": "Use reported denominators, contact authors, and run prespecified sensitivity scenarios",
        "synthesis.heterogeneity_rationale": "Report tau-squared and I-squared with confidence intervals where supported",
        "synthesis.subgroups_and_meta_regression_rationale": "No exploratory moderators unless the data support the prespecified interaction analysis",
        "synthesis.sensitivity_analysis_rationale": "Repeat using the prespecified alternative estimator and high-risk studies excluded",
        "synthesis.small_study_effects_plan": "Assess only when sufficient studies are available; otherwise report not assessed",
        "synthesis.software_and_version": "R 4.5.1, meta 8.1-0",
        "synthesis.analysis_manifest_path": "verification/analysis_manifest.json",
        "synthesis.software.primary_engine.version": "4.5.1",
        "synthesis.software.primary_engine.role": "Primary production engine for pairwise synthesis and prespecified NMA",
        "synthesis.software.primary_engine.packages": ["meta 8.1-0"],
        "synthesis.software.certainty_tools": ["GRADEpro GDT 2026.1"],
        "synthesis.software.runtime_lock_paths": ["renv.lock"],
        "synthesis.software.random_seed": "20260926",
        "certainty.framework": "GRADE",
        "certainty.downgrade_upgrade_rules": "Apply the five GRADE domains with outcome-level rationale",
        "agent_governance.human_accountable_lead": "Principal investigator",
        "figure_table_contract.contract_path": "data/nma_figure_table_spec_template.json",
    }
    for path, value in values.items():
        current = protocol
        parts = path.split(".")
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = value
    protocol["eligibility"]["inclusion_criteria"] = ["Adults", "Eligible study design"]
    protocol["eligibility"]["exclusion_criteria"] = ["Ineligible population", "No eligible outcome"]
    protocol["eligibility"]["eligible_study_designs"] = ["Randomized controlled trials"]
    protocol["search"]["sources"] = ["MEDLINE", "Embase"]
    protocol["methods_sources"]["cochrane_chapters_used"] = [
        "chapter-01", "chapter-02", "chapter-03", "chapter-04", "chapter-05", "chapter-06",
        "chapter-07", "chapter-08", "chapter-09", "chapter-10", "chapter-11", "chapter-14",
    ]
    protocol["selection"]["title_abstract_reviewers"] = ["Screener A", "Screener B"]
    protocol["selection"]["full_text_reviewers"] = ["Full-text reviewer A", "Full-text reviewer B"]
    protocol["selection"]["full_text_exclusion_reasons"] = ["Wrong population", "Wrong study design"]
    protocol["data_collection"]["extractors"] = ["Extractor A", "Extractor B"]
    protocol["risk_of_bias"]["tool_by_design"] = {"Randomized controlled trials": "RoB 2"}
    protocol["risk_of_bias"]["reviewers"] = ["RoB reviewer A", "RoB reviewer B"]
    protocol["synthesis"]["synthesis_groups"] = ["Randomized trials, primary outcome"]
    protocol["synthesis"]["pairwise_meta_analysis"]["enabled"] = True
    protocol["synthesis"]["effect_measures"] = {"mortality": "Risk ratio"}
    protocol["synthesis"]["heterogeneity_assessment"] = ["Tau-squared", "I-squared"]
    protocol["certainty"]["critical_outcomes"] = ["All-cause mortality"]
    protocol["outcomes"][0].update(
        {
            "name": "All-cause mortality",
            "definition": "Death from any cause",
            "measurement": "Number of participants who died",
            "time_window": "Longest follow-up within 30 days",
            "timepoint_selection_rule": "Use the longest follow-up not exceeding 30 days",
            "measure_selection_rule": "Prefer intention-to-treat results with the stated denominator",
            "preferred_effect_measure": "Risk ratio",
            "clinical_importance": "Critical outcome for patients and clinicians",
            "related_effect_handling": "Prefer one prespecified timepoint; model multiple correlated estimates if available",
        }
    )
    protocol["registration"].update(
        {"status": "not_registered", "not_registered_rationale": "Registration will be submitted after protocol approval and before screening"}
    )
    protocol["synthesis"]["network_meta_analysis"]["not_planned_rationale"] = "No connected network is currently anticipated; NMA requires a prespecified network and transitivity review"
    return json.dumps(protocol, ensure_ascii=False, indent=2)


def _valid_methods_source_log_text(chapter_ids=None):
    chapter_ids = chapter_ids or [
        "chapter-01", "chapter-02", "chapter-03", "chapter-04", "chapter-05", "chapter-06",
        "chapter-07", "chapter-08", "chapter-09", "chapter-10", "chapter-11", "chapter-14",
    ]
    sources = []
    for chapter_id in chapter_ids:
        chapter_number = chapter_id[-2:]
        sources.append(
            {
                "source_id": f"cochrane-{chapter_id}",
                "source_type": "cochrane_handbook",
                "chapter_id": chapter_id,
                "citation": f"Cochrane Handbook for Systematic Reviews of Interventions, Chapter {int(chapter_number)}",
                "url": f"https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/{chapter_id}",
                "relevant_sections": [f"Chapter {int(chapter_number)}"],
                "version_or_update_date": "Update date recorded or not stated on chapter page",
                "accessed_date": "2026-09-25",
                "access_status": "verified",
                "verified_by": "Methods reviewer",
                "verification_notes": None,
            }
        )
    sources.append(
        {
            "source_id": "jslhr-tutorial-2022",
            "source_type": "tutorial",
            "citation": "Zhang et al. JSLHR. 2022. doi:10.1044/2022_JSLHR-21-00607",
            "url": "https://doi.org/10.1044/2022_JSLHR-21-00607",
            "relevant_sections": ["Pages 3-21"],
            "version_or_update_date": "2022",
            "accessed_date": "2026-09-25",
            "access_status": "verified",
            "verified_by": "Methods reviewer",
            "verification_notes": None,
        }
    )
    return json.dumps(
        {"schema_version": 1, "sources": sources}, ensure_ascii=False, indent=2
    )


def _start(ledger, stage, agent, rerun=False):
    next_run = ledger.load()["stages"][stage]["run_count"] + 1
    return ledger.start(stage, agent, f"{agent}-session-{next_run}", rerun=rerun)


def _submit(ledger, stage, agent, artifacts, summary):
    session = ledger.load()["stages"][stage]["executor_session"]
    return ledger.submit(stage, agent, session, artifacts, summary)


def _submit_protocol(ledger, tmp_path, agent, protocol_artifact, summary):
    protocol = json.loads((tmp_path / protocol_artifact).read_text(encoding="utf-8"))
    source_log = _write(
        tmp_path,
        "verification/methods_source_log.json",
        _valid_methods_source_log_text(protocol["methods_sources"]["cochrane_chapters_used"]),
    )
    return _submit(ledger, "protocol", agent, [protocol_artifact, source_log], summary)


def _review(ledger, stage, reviewer, verdict, report, findings=""):
    if not findings:
        findings = "All assigned review criteria pass with no unresolved blocker"
    return ledger.review(stage, reviewer, f"{reviewer}-session", verdict, report, findings)


def _approve(ledger, tmp_path, stage, agent, artifacts):
    _start(ledger, stage, agent)
    _submit(ledger, stage, agent, artifacts, f"{stage} complete")
    safe_stage = stage.replace("_", "-")
    _review(
        ledger,
        stage,
        f"{safe_stage}-reviewer-a",
        "approve",
        _write(tmp_path, f"verification/{safe_stage}-review-a.md", "Independent review A passed"),
    )
    _review(
        ledger,
        stage,
        f"{safe_stage}-reviewer-b",
        "approve",
        _write(tmp_path, f"verification/{safe_stage}-review-b.md", "Independent review B passed"),
    )


def _ta_record(report_id, decision):
    return {
        "study_id": "S1",
        "report_id": report_id,
        "report_identity": {
            "doi": f"10.1000/{report_id.lower()}",
            "pmid": "",
            "title": f"Report {report_id}",
            "year": "2022",
        },
        "reviewer_decisions": [
            {"reviewer_id": "screen-a", "decision": decision},
            {"reviewer_id": "screen-b", "decision": decision},
        ],
        "final_decision": decision,
    }


def test_included_screening_record_requires_approved_report_identity():
    study_report_map = {"schema_version": 1, "studies": [{"study_id": "S1", "report_ids": ["R1"]}]}
    manifest = {"schema_version": 1, "records": [_ta_record("R1", "include_for_full_text")]}
    assert validate_title_abstract_screening_manifest(manifest, study_report_map) == []

    manifest["records"][0].pop("report_identity")
    errors = validate_title_abstract_screening_manifest(manifest, study_report_map)
    assert any("report_identity must contain approved citation identity fields" in error for error in errors)

    manifest["records"][0]["report_identity"] = {"doi": "", "pmid": "", "title": "Report R1", "year": ""}
    errors = validate_title_abstract_screening_manifest(manifest, study_report_map)
    assert any("requires DOI or PMID, or both title and publication year" in error for error in errors)


def test_stage_requires_two_distinct_independent_approvals(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    report_a = _write(tmp_path, "verification/reviews/a.md", "pass A")
    report_b = _write(tmp_path, "verification/reviews/b.md", "pass B")

    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "search", "search-agent")

    _start(ledger, "protocol", "protocol-agent")
    with pytest.raises(StageLedgerError, match="methods_source_log.json"):
        _submit(ledger, "protocol", "protocol-agent", [artifact], "Protocol drafted")
    incomplete_log = _write(
        tmp_path,
        "verification/methods_source_log.json",
        _valid_methods_source_log_text(["chapter-04"]),
    )
    with pytest.raises(StageLedgerError, match="chapter set does not match protocol declaration"):
        _submit(ledger, "protocol", "protocol-agent", [artifact, incomplete_log], "Protocol drafted")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol drafted")
    with pytest.raises(StageLedgerError, match="cannot review its own"):
        ledger.review("protocol", "protocol-agent", "protocol-agent-session-1", "approve", report_a)

    first = _review(ledger, "protocol", "reviewer-a", "approve", report_a)
    assert first["stages"]["protocol"]["status"] == "awaiting_review"
    with pytest.raises(StageLedgerError, match="already reviewed"):
        _review(ledger, "protocol", "reviewer-a", "approve", report_b)

    second = _review(ledger, "protocol", "reviewer-b", "approve", report_b)
    assert second["stages"]["protocol"]["status"] == "approved"
    assert ledger.verify_integrity()

    _start(ledger, "search", "search-agent")
    assert ledger.load()["stages"]["search"]["status"] == "in_progress"


def test_protocol_preflight_rejects_template_and_requires_nma_assumptions():
    template_path = Path(__file__).parents[1] / "data" / "templates" / "review_protocol_template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert validate_review_protocol(template)

    protocol = json.loads(_valid_protocol_text())
    assert validate_review_protocol(protocol) == []
    protocol["synthesis"]["network_meta_analysis"]["enabled"] = True
    protocol["synthesis"]["network_meta_analysis"]["transitivity_assessment"] = ""
    errors = validate_review_protocol(protocol)
    assert any("transitivity_assessment" in error for error in errors)


def test_synthesis_templates_default_primary_engine_to_r():
    repo_root = Path(__file__).parents[1]
    protocol_templates = [
        repo_root / "data" / "templates" / "review_protocol_template.json",
        repo_root / "sci_nma_agent" / "templates" / "review_protocol_template.json",
    ]
    manifest_templates = [
        repo_root / "data" / "templates" / "analysis_manifest_template.json",
        repo_root / "sci_nma_agent" / "templates" / "analysis_manifest_template.json",
    ]

    for path in protocol_templates:
        template = json.loads(path.read_text(encoding="utf-8"))
        assert template["synthesis"]["software"]["primary_engine"]["name"] == "R"

    for path in manifest_templates:
        template = json.loads(path.read_text(encoding="utf-8"))
        assert template["software"]["primary_engine"]["name"] == "R"


def test_analysis_manifest_requires_methods_software_and_hashed_outputs(tmp_path):
    output = tmp_path / "results" / "pooled_effects.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"estimate": 0.82}\n', encoding="utf-8")
    output_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    input_snapshot = tmp_path / "data" / "locked_input_snapshot.json"
    input_snapshot.parent.mkdir(parents=True)
    input_snapshot.write_text('{"study_ids":["S1"]}\n', encoding="utf-8")
    input_snapshot_hash = hashlib.sha256(input_snapshot.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "project_id": "review-1",
        "stage_id": "synthesis",
        "protocol_sha256": "a" * 64,
        "input_snapshot_path": "data/locked_input_snapshot.json",
        "input_snapshot_sha256": input_snapshot_hash,
        "code_commit": "deadbeef",
        "estimands": ["30-day all-cause mortality"],
        "effect_measure_by_outcome": {"mortality_30d": "RR"},
        "pairwise": {
            "primary_model": "random effects",
            "primary_estimator": "REML",
            "interval_method": "Hartung-Knapp",
            "heterogeneity_statistics": ["tau2", "I2", "Q"],
            "prediction_interval": "95% prediction interval",
            "zero_event_rule": "Prespecified exact/GLMM sensitivity; no silent continuity correction",
            "multi_arm_and_dependency_rule": "Retain covariance or use robust variance",
            "missing_data_rule": "Contact authors and run prespecified sensitivity scenarios",
            "sensitivity_analyses": ["Paule-Mandel estimator"],
        },
        "network_meta_analysis": {
            "planned": False,
            "not_planned_rationale": "No connected intervention network is in scope",
        },
        "software": {
            "primary_engine": {
                "name": json.loads(
                    (Path(__file__).parents[1] / "data" / "templates" / "analysis_manifest_template.json")
                    .read_text(encoding="utf-8")
                )["software"]["primary_engine"]["name"],
                "version": "4.5.1",
                "packages": ["meta 8.1-0", "metafor 4.8-0"],
                "role": "Primary production pairwise synthesis",
            },
            "verification_engines": ["Stata 18 meta"],
                "certainty_tools": ["GRADEpro GDT 2026.1"],
            "runtime_lock_paths": ["renv.lock"],
            "random_seed": "20260926",
        },
        "diagnostics": ["leave-one-out", "prediction interval"],
        "deviations": [],
        "outputs": [{"path": "results/pooled_effects.json", "sha256": output_hash}],
        "review_signoff": {"executor": "statistician"},
    }
    assert validate_analysis_manifest(manifest) == []
    manifest_path = tmp_path / "analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_analysis_manifest_file(manifest_path, tmp_path) == []

    manifest["outputs"][0]["sha256"] = "c" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_analysis_manifest_file(manifest_path, tmp_path)
    assert any("does not match its file" in error for error in errors)


def test_analysis_manifest_binds_input_snapshot_and_allows_nma_only_plan(tmp_path):
    output = tmp_path / "results" / "nma.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"network":"connected"}\n', encoding="utf-8")
    snapshot = tmp_path / "data" / "locked.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('{"extracted":true}\n', encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "project_id": "review-1",
        "stage_id": "synthesis",
        "protocol_sha256": "a" * 64,
        "input_snapshot_path": "data/locked.json",
        "input_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "code_commit": "deadbeef",
        "estimands": ["30-day mortality"],
        "effect_measure_by_outcome": {"mortality": "Risk ratio"},
        "pairwise": {"planned": False, "not_planned_rationale": "Only a connected treatment network is estimable"},
        "network_meta_analysis": {
                "planned": True,
                "model": "Frequentist random-effects contrast-based NMA",
                "node_definitions": "Each corticosteroid regimen is a distinct intervention node; combination regimens remain separate",
                "connectivity": "All nodes connected to placebo",
                "transitivity": "Baseline risk and severity assessed",
                "transitivity_effect_modifiers": ["baseline severity", "baseline mortality risk"],
                "inconsistency": "Design-by-treatment and node-splitting",
            "multi_arm_covariance": "Preserve within-study covariance",
            "heterogeneity": "Common random-effects heterogeneity",
            "ranking_uncertainty": "Rank probabilities with intervals",
                "certainty_method": "CINeMA",
                "assumption_failure_plan": "Downgrade certainty and report direct and indirect estimates separately when assumptions fail",
        },
        "software": {
                "primary_engine": {"name": "R", "version": "4.5.1", "packages": ["netmeta 3.2-0"], "role": "Primary production NMA"},
            "verification_engines": [],
                "certainty_tools": ["CINeMA 1.1"],
            "runtime_lock_paths": ["renv.lock"],
            "random_seed": "20260926",
        },
        "diagnostics": ["node-splitting"],
        "intermediate_outputs": [],
        "convergence": {"status": "not_applicable", "details": "Frequentist model"},
        "deviations": [],
        "outputs": [{"path": "results/nma.json", "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}],
    }
    manifest_path = tmp_path / "analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_analysis_manifest_file(manifest_path, tmp_path) == []

    snapshot.write_text('{"extracted":false}\n', encoding="utf-8")
    errors = validate_analysis_manifest_file(manifest_path, tmp_path)
    assert any("input_snapshot_sha256 does not match" in error for error in errors)


def test_analysis_manifest_rejects_python_as_primary_production_engine():
    manifest = {
        "schema_version": 1,
        "stage_id": "synthesis",
        "project_id": "review-1",
        "protocol_sha256": "a" * 64,
        "input_snapshot_path": "data/locked.json",
        "input_snapshot_sha256": "b" * 64,
        "code_commit": "deadbeef",
        "estimands": ["mortality"],
        "effect_measure_by_outcome": {"mortality": "RR"},
        "pairwise": {"planned": False, "not_planned_rationale": "NMA only"},
        "network_meta_analysis": {"planned": True, "connectivity": "connected", "transitivity": "assessed", "inconsistency": "checked", "multi_arm_covariance": "modeled", "heterogeneity": "common", "ranking_uncertainty": "reported", "certainty_method": "CINeMA"},
        "software": {"primary_engine": {"name": "Python", "version": "3.13", "packages": [], "role": "Primary production engine"}, "verification_engines": [], "certainty_tools": [], "runtime_lock_paths": [], "random_seed": "1"},
        "diagnostics": [], "intermediate_outputs": [], "convergence": {}, "deviations": [],
        "outputs": [{"path": "results.json", "sha256": "c" * 64}],
    }
    errors = validate_analysis_manifest(manifest)
    assert any("cannot be Python" in error for error in errors)


def test_protocol_preflight_rejects_python_as_primary_production_engine():
    protocol = json.loads(_valid_protocol_text())
    protocol["synthesis"]["software"]["primary_engine"]["name"] = "Python"
    errors = validate_review_protocol(protocol)
    assert any("synthesis.software.primary_engine cannot be Python" in error for error in errors)


def test_protocol_preflight_allows_explicit_validated_stata_override():
    protocol = json.loads(_valid_protocol_text())
    protocol["synthesis"]["software"]["primary_engine"].update(
        {
            "name": "Stata",
            "version": "18.0",
            "packages": ["meta 1.0", "network 1.0"],
            "role": "Explicit validated production engine",
        }
    )
    errors = validate_review_protocol(protocol)
    assert errors == []


def test_analysis_manifest_binding_rejects_estimator_interval_role_and_extra_outcome():
    protocol = json.loads(_valid_protocol_text())
    manifest = {
        "project_id": "review-1",
        "effect_measure_by_outcome": {"mortality": "Risk ratio", "unplanned_extra": "OR"},
        "pairwise": {
            "planned": True,
            "primary_model": "random effects",
            "primary_estimator": "DerSimonian-Laird",
            "interval_method": "Wald normal interval",
        },
        "network_meta_analysis": {"planned": False},
        "software": {
            "primary_engine": {
                "name": "R",
                "version": "4.5.1",
                "packages": [],
                "role": "QA only",
            }
        },
    }
    errors = validate_analysis_manifest_binding(manifest, protocol)
    assert any("estimator does not match" in error for error in errors)
    assert any("interval method does not match" in error for error in errors)
    assert any("software role" in error for error in errors)
    assert any("outcomes not declared" in error for error in errors)


def test_analysis_manifest_binding_exactly_binds_nma_decisions():
    protocol = json.loads(_valid_protocol_text())
    protocol_nma = protocol["synthesis"]["network_meta_analysis"]
    protocol_nma.update(
        {
            "enabled": True,
            "intervention_node_definitions": "Each regimen is a distinct node",
            "transitivity_effect_modifiers": ["baseline severity", "baseline risk"],
            "transitivity_assessment": "Compare severity and baseline risk across designs",
            "network_connectivity_and_geometry": "All nodes connected to placebo",
            "incoherence_assessment": "Design-by-treatment and node-splitting",
            "model_specification": "Frequentist random-effects contrast-based NMA",
            "model_and_multi_arm_handling": "Common heterogeneity with covariance-preserving multi-arm handling",
            "ranking_interpretation": "Rank probabilities with uncertainty intervals",
            "certainty_framework": "CINeMA",
            "assumption_failure_plan": "Separate direct and indirect evidence and downgrade certainty",
        }
    )
    protocol["synthesis"]["pairwise_meta_analysis"]["enabled"] = False
    protocol["synthesis"]["software"]["primary_engine"] = {
        "name": "R",
        "version": "4.5.1",
        "packages": ["netmeta 3.2-0"],
        "role": "Primary production NMA",
    }
    protocol["synthesis"]["software"]["certainty_tools"] = ["CINeMA 1.1"]
    manifest = {
        "project_id": "review-1",
        "effect_measure_by_outcome": {"mortality": "Risk ratio"},
        "pairwise": {"planned": False},
        "network_meta_analysis": {
            "planned": True,
            "model": "Frequentist random-effects contrast-based NMA",
            "node_definitions": "Each regimen is a distinct node",
            "transitivity_effect_modifiers": ["baseline severity", "baseline risk"],
            "connectivity": "All nodes connected to placebo",
            "transitivity": "Compare severity and baseline risk across designs",
            "inconsistency": "Design-by-treatment and node-splitting",
            "multi_arm_covariance": "Common heterogeneity with covariance-preserving multi-arm handling",
            "heterogeneity": "Common random-effects heterogeneity",
            "ranking_uncertainty": "Rank probabilities with uncertainty intervals",
            "certainty_method": "CINeMA",
            "assumption_failure_plan": "Separate direct and indirect evidence and downgrade certainty",
        },
        "software": {
            "primary_engine": {"name": "R", "version": "4.5.1", "packages": ["netmeta 3.2-0"], "role": "Primary production NMA"},
            "certainty_tools": ["CINeMA 1.1"],
            "runtime_lock_paths": ["renv.lock"],
            "random_seed": "20260926",
        },
    }
    assert validate_analysis_manifest_binding(manifest, protocol) == []

    manifest["network_meta_analysis"]["certainty_method"] = "GRADE"
    errors = validate_analysis_manifest_binding(manifest, protocol)
    assert any("certainty_method does not exactly match" in error for error in errors)
    manifest["network_meta_analysis"]["certainty_method"] = "CINeMA"
    manifest["network_meta_analysis"]["transitivity_effect_modifiers"] = ["age only"]
    errors = validate_analysis_manifest_binding(manifest, protocol)
    assert any("transitivity_effect_modifiers does not exactly match" in error for error in errors)


def test_methods_source_log_requires_handbook_chapter_dates_and_tutorial_provenance():
    manifest = json.loads(_valid_methods_source_log_text())
    protocol = json.loads(_valid_protocol_text())
    chapters = protocol["methods_sources"]["cochrane_chapters_used"]
    assert validate_methods_source_log(manifest, chapters) == []
    errors = validate_methods_source_log(manifest, chapters[:-1])
    assert any("chapter set does not match protocol declaration" in error for error in errors)
    manifest["sources"][3]["url"] = manifest["sources"][3]["url"].replace("chapter-04", "chapter-25")
    errors = validate_methods_source_log(manifest, chapters)
    assert any("chapter_id must match the chapter number in its URL" in error for error in errors)
    manifest = json.loads(_valid_methods_source_log_text())
    manifest["sources"][0]["accessed_date"] = "not-a-date"
    manifest["sources"].pop()
    errors = validate_methods_source_log(manifest)
    assert any("accessed_date must be a real date" in error for error in errors)
    assert any("must include at least one tutorial record" in error for error in errors)


def test_methods_source_log_rejects_duplicate_and_undeclared_chapters():
    protocol = json.loads(_valid_protocol_text())
    chapters = protocol["methods_sources"]["cochrane_chapters_used"]

    duplicate = json.loads(_valid_methods_source_log_text())
    duplicate_source = duplicate["sources"][1]
    duplicate_source["chapter_id"] = "chapter-01"
    duplicate_source["url"] = duplicate_source["url"].replace("chapter-02", "chapter-01")
    errors = validate_methods_source_log(duplicate, chapters)
    assert any("chapter_id must be unique" in error for error in errors)

    undeclared = json.loads(_valid_methods_source_log_text())
    extra_source = dict(undeclared["sources"][0])
    extra_source["source_id"] = "cochrane-chapter-25"
    extra_source["chapter_id"] = "chapter-25"
    extra_source["citation"] = "Cochrane Handbook for Systematic Reviews of Interventions, Chapter 25"
    extra_source["url"] = extra_source["url"].replace("chapter-01", "chapter-25")
    extra_source["relevant_sections"] = ["Chapter 25"]
    undeclared["sources"].append(extra_source)
    errors = validate_methods_source_log(undeclared, chapters)
    assert any("chapter set does not match protocol declaration" in error for error in errors)
    assert "undeclared=['chapter-25']" in next(error for error in errors if "chapter set does not match" in error)


def test_packaged_init_protocol_template_matches_validated_data_template():
    root = Path(__file__).parents[1]
    data_template = json.loads((root / "data" / "templates" / "review_protocol_template.json").read_text(encoding="utf-8"))
    packaged_template = json.loads((root / "sci_nma_agent" / "templates" / "review_protocol_template.json").read_text(encoding="utf-8"))
    assert packaged_template == data_template
    errors = validate_review_protocol(packaged_template)
    assert errors
    assert not any(
        marker in error
        for error in errors
        for marker in ("retrieval statuses", "review statuses", "fact statuses", "required_provenance")
    )


@pytest.mark.parametrize(
    "template_name",
    [
        "title_abstract_screening_manifest_template.json",
        "full_text_retrieval_manifest_template.json",
        "full_text_screening_manifest_template.json",
        "fact_status_manifest_template.json",
        "methods_source_log_template.json",
    ],
)
def test_packaged_stage_manifests_match_data_templates(template_name):
    root = Path(__file__).parents[1]
    data_template = json.loads((root / "data" / "templates" / template_name).read_text(encoding="utf-8"))
    packaged_template = json.loads((root / "sci_nma_agent" / "templates" / template_name).read_text(encoding="utf-8"))

    assert packaged_template == data_template


def test_protocol_preflight_rejects_wrong_types_placeholders_and_design_mismatch():
    protocol = json.loads(_valid_protocol_text())
    protocol["project"]["title"] = []
    protocol["eligibility"]["inclusion_criteria"] = [{}]
    protocol["selection"]["adjudicator"] = "ADJUDICATOR"
    protocol["risk_of_bias"]["tool_by_design"] = {"unlisted design": "RoB 2"}

    errors = validate_review_protocol(protocol)
    assert any("project.title" in error for error in errors)
    assert any("eligibility.inclusion_criteria" in error for error in errors)
    assert any("selection.adjudicator" in error for error in errors)
    assert any("tool_by_design keys" in error for error in errors)


def test_fulltext_fact_state_never_conflates_failed_retrieval_with_not_reported():
    assert validate_full_text_fact_state(
        "awaiting_manual_acquisition", "not_started", "not_assessed_pending_full_text"
    ) == []
    assert validate_full_text_fact_state(
        "awaiting_manual_acquisition", "not_started", "not_reported_in_reviewed_report"
    )
    assert validate_full_text_fact_state(
        "manual_acquired_unconfirmed", "complete_after_adjudication", "not_reported_in_reviewed_report"
    )
    assert validate_full_text_fact_state(
        "not_started", "review_in_progress", "not_assessed_pending_full_text"
    )
    assert validate_full_text_fact_state(
        "manual_acquired_unconfirmed", "review_in_progress", "not_assessed_pending_full_text"
    )
    assert validate_full_text_fact_state(
        "manual_confirmed", "pending_independent_review", "pending_full_text_review"
    ) == []
    assert validate_full_text_fact_state(
        "manual_confirmed", "complete_after_adjudication", "not_reported_in_reviewed_report"
    ) == []
    assert validate_full_text_fact_state(
        "automatic_retrieval_succeeded", "review_in_progress", "pending_full_text_review"
    ) == []
    assert validate_full_text_fact_state(
        "automatic_retrieval_succeeded", "complete_after_adjudication", "not_reported_in_reviewed_report"
    ) == []
    assert validate_full_text_fact_state(
        "manual_confirmed", "complete_after_adjudication", "not_assessed_pending_full_text"
    )


def test_fact_status_manifest_requires_complete_linked_source_review_for_study_absence():
    study_report_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"]}],
    }
    manifest = {
        "schema_version": 1,
        "study_report_map_sha256": "a" * 64,
        "facts": [{
            "study_id": "S1",
            "report_id": "R1",
            "field_id": "mortality_30d",
            "fact_scope": "study",
            "retrieval_status": "automatic_retrieval_succeeded",
            "full_text_review_status": "complete_after_adjudication",
            "fact_status": "not_reported_after_all_linked_sources_review",
            "all_linked_sources_reviewed": True,
            "linked_report_ids": ["R1", "R2"],
            "linked_source_review_evidence": [
                {
                    "report_id": report_id,
                    "retrieval_status": "automatic_retrieval_succeeded",
                    "full_text_review_status": "complete_after_adjudication",
                    "review_coverage": ["Methods pp. 2-4", "Results pp. 5-7"],
                }
                for report_id in ("R1", "R2")
            ],
            "review_coverage": ["Methods pp. 2-4", "Results pp. 5-7"],
        }],
    }
    retrieval_manifest = {
        "schema_version": 1,
        "records": [
            {
                "study_id": "S1",
                "report_id": report_id,
                "retrieval_status": "automatic_retrieval_succeeded",
            }
            for report_id in ("R1", "R2")
        ],
    }
    screening_manifest = {
        "schema_version": 1,
        "records": [
            {
                "study_id": "S1",
                "report_id": report_id,
                "eligibility_status": "included",
                "full_text_review_status": "complete_after_adjudication",
            }
            for report_id in ("R1", "R2")
        ],
    }

    assert validate_fact_status_manifest(
        manifest, study_report_map, retrieval_manifest, screening_manifest
    ) == []
    manifest["facts"][0]["linked_report_ids"] = ["R1"]
    errors = validate_fact_status_manifest(
        manifest, study_report_map, retrieval_manifest, screening_manifest
    )
    assert any("approved study/report map" in error for error in errors)
    manifest["facts"][0]["linked_report_ids"] = ["R1", "R2"]
    manifest["facts"][0]["events"] = 0
    errors = validate_fact_status_manifest(
        manifest, study_report_map, retrieval_manifest, screening_manifest
    )
    assert any("must not carry an extracted numeric value" in error for error in errors)


@pytest.mark.parametrize(
    "fact_status",
    ["not_reported_in_reviewed_report", "cannot_tell_after_full_text_review"],
)
def test_report_level_missing_fact_states_require_nonblank_review_coverage(fact_status):
    fact = {
        "study_id": "S1",
        "report_id": "R1",
        "field_id": "mortality_30d",
        "fact_scope": "report",
        "retrieval_status": "automatic_retrieval_succeeded",
        "full_text_review_status": "complete_after_adjudication",
        "fact_status": fact_status,
        "review_coverage": [""],
    }
    if fact_status == "cannot_tell_after_full_text_review":
        fact["uncertainty_reason"] = "The report does not clearly distinguish outcome timing."
    manifest = {"schema_version": 1, "facts": [fact]}
    study_report_map = {"schema_version": 1, "studies": [{"study_id": "S1", "report_ids": ["R1"]}]}
    retrieval_manifest = {
        "schema_version": 1,
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "retrieval_status": "automatic_retrieval_succeeded",
        }],
    }
    screening_manifest = {
        "schema_version": 1,
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "eligibility_status": "included",
            "full_text_review_status": "complete_after_adjudication",
        }],
    }

    errors = validate_fact_status_manifest(manifest, study_report_map, retrieval_manifest, screening_manifest)
    assert any("reviewed-section/page coverage" in error for error in errors)


def test_fulltext_manifest_rejects_report_ids_outside_approved_map():
    study_report_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1"]}],
    }
    manifest = {
        "schema_version": 1,
        "records": [{"study_id": "S1", "report_id": "R2"}],
    }

    errors = validate_full_text_retrieval_manifest(manifest, study_report_map)
    assert any("not present in the approved study/report map" in error for error in errors)


def test_manually_confirmed_zotero_attachment_requires_actor_and_timestamp():
    study_report_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1"]}],
    }
    screening_scope = {
        "schema_version": 1,
        "records": [_ta_record("R1", "include_for_full_text")],
    }
    record = {
        "study_id": "S1",
        "report_id": "R1",
        "retrieval_status": "manual_confirmed",
        "full_text_review_status": "not_started",
        "fact_status": "pending_full_text_review",
        "zotero_item_key": "ITEM1",
        "attachment_key": "ATTACH1",
        "local_file_sha256": "a" * 64,
        "local_file_name": "paper.pdf",
        "local_file_path": "original_materials/manual_fulltext/run-0001/study__report__id__local_copy.pdf",
        "local_file_relation_status": "unverified_user_supplied",
        "content_sha256": hashlib.sha256(b"Full text").hexdigest(),
        "content_path": "original_materials/manual_fulltext/run-0001/study__report__id.txt",
        "content_file_sha256": "b" * 64,
        "identity_match_status": "unique_match",
        "manual_confirmation": {
            "actor": "manual-confirming-user",
            "confirmed_at": "2026-09-25T12:00:00Z",
            "zotero_item_key": "ITEM1",
            "attachment_key": "ATTACH1",
            "local_file_name": "paper.pdf",
            "local_file_path": "original_materials/manual_fulltext/run-0001/study__report__id__local_copy.pdf",
            "local_file_sha256": "a" * 64,
            "local_file_relation_status": "unverified_user_supplied",
            "content_path": "original_materials/manual_fulltext/run-0001/study__report__id.txt",
            "content_file_sha256": "b" * 64,
            "content_sha256": hashlib.sha256(b"Full text").hexdigest(),
            "item_details_call": _mcp_call_record(
                "get_item_details", {"item_key": "ITEM1"}, {"item": {"key": "ITEM1"}}
            ),
            "content_call": _mcp_call_record(
                "get_content",
                {"item_key": "ITEM1", "attachment_key": "ATTACH1", "mode": "complete"},
                {"text": "Full text"},
            ),
        },
    }
    manifest = {"schema_version": 1, "records": [record]}

    assert validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope) == []
    record["content_sha256"] = "c" * 64
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    assert any("content_sha256 does not match text extracted" in error for error in errors)
    record["content_sha256"] = hashlib.sha256(b"Full text").hexdigest()
    record["manual_confirmation"]["content_sha256"] = "d" * 64
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    assert any("manual_confirmation.content_sha256 does not match content_call.raw_response" in error for error in errors)
    record["manual_confirmation"]["content_sha256"] = hashlib.sha256(b"Full text").hexdigest()
    content_call = record["manual_confirmation"]["content_call"]
    content_call["raw_response"] = {"text": "Changed MCP response"}
    canonical_response = json.dumps(
        content_call["raw_response"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    content_call["raw_response_sha256"] = hashlib.sha256(canonical_response.encode("utf-8")).hexdigest()
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    assert any("content_sha256 does not match text extracted" in error for error in errors)
    record["manual_confirmation"]["content_call"] = _mcp_call_record(
        "get_content",
        {"item_key": "ITEM1", "attachment_key": "ATTACH1", "mode": "complete"},
        {"text": "Full text"},
    )
    record["manual_confirmation"].pop("actor")
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    assert any("manual_confirmation must record the confirming user and timestamp" in error for error in errors)


def test_retrieval_coverage_uses_approved_reports_sought_not_entire_map():
    study_report_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"]}],
    }
    screening_scope = {
        "schema_version": 1,
        "records": [
            _ta_record("R1", "include_for_full_text"),
            _ta_record("R2", "exclude"),
        ],
    }
    retrieval_record = {
        "study_id": "S1",
        "report_id": "R1",
        "retrieval_status": "automatic_retrieval_succeeded",
        "full_text_review_status": "not_started",
        "fact_status": "pending_full_text_review",
        "zotero_item_key": "ITEM1",
        "attachment_key": "ATTACH1",
        "attachment_sha256": "a" * 64,
        "identity_match_status": "unique_match",
    }
    manifest = {"schema_version": 1, "records": [retrieval_record]}

    assert validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope) == []
    screening_scope["records"][1]["final_decision"] = "include_for_full_text"
    screening_scope["records"][1]["reviewer_decisions"] = [
        {"reviewer_id": "screen-a", "decision": "include_for_full_text"},
        {"reviewer_id": "screen-b", "decision": "include_for_full_text"},
    ]
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    assert any("every report sought" in error for error in errors)


def test_fulltext_exclusions_require_protocol_reason_and_report_locator():
    study_report_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1"]}],
    }
    retrieval_manifest = {
        "schema_version": 1,
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "retrieval_status": "automatic_retrieval_succeeded",
        }],
    }
    fulltext_manifest = {
        "schema_version": 1,
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "eligibility_status": "excluded",
            "full_text_review_status": "complete_after_adjudication",
            "reviewer_decisions": [
                {"reviewer_id": "fulltext-a", "decision": "exclude"},
                {"reviewer_id": "fulltext-b", "decision": "exclude"},
            ],
        }],
    }

    errors = validate_full_text_screening_manifest(fulltext_manifest, study_report_map, retrieval_manifest)
    assert any("exclusion_reason is required" in error for error in errors)
    assert any("source_locator is required" in error for error in errors)
    fulltext_manifest["records"][0]["exclusion_reason"] = "Wrong population"
    fulltext_manifest["records"][0]["source_locator"] = "Methods, p. 2"
    assert validate_full_text_screening_manifest(fulltext_manifest, study_report_map, retrieval_manifest) == []


def test_stage_submissions_require_fulltext_and_extraction_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_ledger_module, "STAGES", [("fulltext_retrieval", "Full-text retrieval")])
    monkeypatch.setattr(stage_ledger_module, "STAGE_IDS", ["fulltext_retrieval"])
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    _start(ledger, "fulltext_retrieval", "retrieval-agent")
    generic = _write(tmp_path, "retrieval/result.json", "{}")
    with pytest.raises(StageLedgerError, match="full_text_retrieval_manifest.json"):
        _submit(ledger, "fulltext_retrieval", "retrieval-agent", [generic], "Retrieved")


def test_retrieval_submission_is_bound_to_approved_study_report_map(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stage_ledger_module,
        "STAGES",
        [
            ("deduplication", "Deduplication"),
            ("title_abstract_screening", "Title/abstract screening"),
            ("fulltext_retrieval", "Full-text retrieval"),
        ],
    )
    monkeypatch.setattr(
        stage_ledger_module,
        "STAGE_IDS",
        ["deduplication", "title_abstract_screening", "fulltext_retrieval"],
    )
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    map_data = {"schema_version": 1, "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"]}]}
    map_artifact = _write(
        tmp_path, "corpus/study_report_map.json", json.dumps(map_data, ensure_ascii=False)
    )
    _approve(ledger, tmp_path, "deduplication", "dedup-agent", [map_artifact])
    screening_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "records": [_ta_record("R1", "include_for_full_text"), _ta_record("R2", "include_for_full_text")],
    }
    screening_artifact = _write(
        tmp_path,
        "screening/title_abstract_screening_manifest.json",
        json.dumps(screening_manifest, ensure_ascii=False),
    )
    _approve(ledger, tmp_path, "title_abstract_screening", "screening-agent", [screening_artifact])
    _start(ledger, "fulltext_retrieval", "retrieval-agent")

    retrieval_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "title_abstract_screening_manifest_sha256": stage_ledger_module._sha256(tmp_path / screening_artifact),
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "retrieval_status": "automatic_retrieval_succeeded",
            "full_text_review_status": "not_started",
            "fact_status": "pending_full_text_review",
            "zotero_item_key": "ITEM1",
            "attachment_key": "ATTACH1",
            "attachment_sha256": "a" * 64,
            "identity_match_status": "unique_match",
        }],
    }
    retrieval_artifact = _write(
        tmp_path,
        "retrieval/full_text_retrieval_manifest.json",
        json.dumps(retrieval_manifest, ensure_ascii=False),
    )
    with pytest.raises(StageLedgerError, match="every report sought"):
        _submit(ledger, "fulltext_retrieval", "retrieval-agent", [retrieval_artifact], "Retrieved")

    retrieval_manifest["records"][0]["report_id"] = "R2"
    (tmp_path / retrieval_artifact).write_text(json.dumps(retrieval_manifest), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="every report sought"):
        _submit(ledger, "fulltext_retrieval", "retrieval-agent", [retrieval_artifact], "Retrieved")

    retrieval_manifest["records"] = [
        {
            "study_id": "S1",
            "report_id": "R1",
            "retrieval_status": "automatic_retrieval_succeeded",
            "full_text_review_status": "not_started",
            "fact_status": "pending_full_text_review",
            "zotero_item_key": "ITEM1",
            "attachment_key": "ATTACH1",
            "attachment_sha256": "a" * 64,
            "identity_match_status": "unique_match",
        },
        {
            "study_id": "S1",
            "report_id": "R2",
            "retrieval_status": "awaiting_manual_acquisition",
            "full_text_review_status": "not_started",
            "fact_status": "not_assessed_pending_full_text",
            "unresolved_reason": "No attachment is available in the Zotero collection yet",
            "route_attempts": [{"route": "zotero_mcp", "status": "no_match"}],
        },
    ]
    (tmp_path / retrieval_artifact).write_text(json.dumps(retrieval_manifest), encoding="utf-8")
    result = _submit(ledger, "fulltext_retrieval", "retrieval-agent", [retrieval_artifact], "Retrieved")
    assert result["stages"]["fulltext_retrieval"]["status"] == "awaiting_review"


def test_retrieval_resume_review_gate(tmp_path, monkeypatch):
    # Keep the test independent of pytest's platform-specific temporary path naming.
    tmp_path = tmp_path / "resume-project"
    tmp_path.mkdir()
    stages = [
        ("deduplication", "Deduplication"),
        ("title_abstract_screening", "Title/abstract screening"),
        ("fulltext_retrieval", "Full-text retrieval"),
        ("fulltext_screening", "Full-text screening"),
    ]
    monkeypatch.setattr(stage_ledger_module, "STAGES", stages)
    monkeypatch.setattr(stage_ledger_module, "STAGE_IDS", [stage_id for stage_id, _ in stages])
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))

    map_data = {"schema_version": 1, "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"]}]}
    map_artifact = _write(tmp_path, "corpus/study_report_map.json", json.dumps(map_data))
    _approve(ledger, tmp_path, "deduplication", "dedup-agent", [map_artifact])
    screening_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "records": [
            _ta_record("R1", "include_for_full_text"),
            _ta_record("R2", "include_for_full_text"),
        ],
    }
    screening_artifact = _write(
        tmp_path,
        "screening/title_abstract_screening_manifest.json",
        json.dumps(screening_manifest, ensure_ascii=False),
    )
    _approve(ledger, tmp_path, "title_abstract_screening", "screening-agent", [screening_artifact])
    _start(ledger, "fulltext_retrieval", "retrieval-agent")

    retrieval_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "title_abstract_screening_manifest_sha256": stage_ledger_module._sha256(tmp_path / screening_artifact),
        "records": [
            {
                "study_id": "S1",
                "report_id": "R1",
                "retrieval_status": "automatic_retrieval_succeeded",
                "full_text_review_status": "not_started",
                "fact_status": "pending_full_text_review",
                "zotero_item_key": "ITEM1",
                "attachment_key": "ATTACH1",
                "attachment_sha256": "a" * 64,
                "identity_match_status": "unique_match",
            },
            {
                "study_id": "S1",
                "report_id": "R2",
                "retrieval_status": "awaiting_manual_acquisition",
                "full_text_review_status": "not_started",
                "fact_status": "not_assessed_pending_full_text",
                "unresolved_reason": "No attachment is available in Zotero yet",
                "route_attempts": [{"route": "zotero_mcp", "status": "no_match"}],
            },
        ],
    }
    retrieval_artifact = _write(
        tmp_path,
        "screening/full_text_retrieval_manifest.json",
        json.dumps(retrieval_manifest, ensure_ascii=False),
    )
    initial_submission = _submit(
        ledger, "fulltext_retrieval", "retrieval-agent", [retrieval_artifact], "Retrieval attempted"
    )
    assert initial_submission["stages"]["fulltext_retrieval"]["status"] == "awaiting_review"
    initial_stage = initial_submission["stages"]["fulltext_retrieval"]
    queue_artifact = next(
        record["path"] for record in initial_stage["artifact_manifest"]
        if Path(record["path"]).name == "manual_fulltext_queue.json"
    )
    preflight_before = ledger.path.read_bytes()
    preflight = ledger.validate_resume(
        "fulltext_retrieval", "retrieval-agent-v2", "retrieval-session-v2"
    )
    assert preflight["action"] == "new_attempt"
    assert preflight_before == ledger.path.read_bytes()

    class _ZoteroConfirmationClient:
        async def read_item_details(self, item_key):
            return ToolCallEvidence(
                "get_item_details",
                {"item_key": item_key},
                {
                    "structuredContent": {
                        "item": {
                            "key": item_key,
                            "data": {"title": "Report R2", "DOI": "10.1000/r2", "date": "2022"},
                            "attachments": [{"key": "ATTACH2", "filename": "paper.pdf"}],
                        }
                    }
                },
                "2026-09-25T00:00:00Z",
            )

        async def read_item_content(self, item_key, attachment_key=None):
            return ToolCallEvidence(
                "get_content",
                {"item_key": item_key, "attachment_key": attachment_key, "mode": "complete"},
                {
                    "structuredContent": {
                        "text": "Full text states the primary outcome.",
                        "pageLocators": [{"page": 4}],
                    }
                },
                "2026-09-25T00:01:00Z",
            )

    attachment = tmp_path / "downloads" / "paper.pdf"
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b"%PDF-1.7\nmanual Zotero attachment")
    resumed_artifacts = __import__("asyncio").run(confirm_zotero_attachment(
        project_dir=str(tmp_path),
        retrieval_manifest_path=retrieval_artifact,
        queue_path=queue_artifact,
        study_id="S1",
        report_id="R2",
        item_key="ITEM2",
        attachment_key="ATTACH2",
        actor="review-lead",
        identity_evidence="Matched DOI and title to the approved screening record.",
        attachment_file=str(attachment),
        client=_ZoteroConfirmationClient(),
        study_report_map_path=map_artifact,
        screening_manifest_path=screening_artifact,
        output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
        output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
        expected_run=2,
    ))
    confirmed_manifest = json.loads(Path(resumed_artifacts["retrieval_manifest_path"]).read_text(encoding="utf-8"))
    confirmed_row = next(row for row in confirmed_manifest["records"] if row["report_id"] == "R2")
    archived_pdf = tmp_path / confirmed_row["local_file_path"]
    assert archived_pdf.read_bytes() == attachment.read_bytes()
    assert hashlib.sha256(archived_pdf.read_bytes()).hexdigest() == confirmed_row["local_file_sha256"]
    assert confirmed_row["local_file_relation_status"] == "unverified_user_supplied"
    assert confirmed_row["manual_confirmation"]["actor"] == "review-lead"

    ledger.resume("fulltext_retrieval", "retrieval-agent-v2", "retrieval-session-v2")
    resumed_stage = ledger.load()["stages"]["fulltext_retrieval"]
    assert resumed_stage["run_count"] == 2
    assert resumed_stage["reviews"] == []
    submitted = _submit(
        ledger,
        "fulltext_retrieval",
        "retrieval-agent-v2",
        [resumed_artifacts["retrieval_manifest_path"], resumed_artifacts["queue_path"]],
        "Manual attachment confirmed; retrieval complete",
    )
    active = submitted["stages"]["fulltext_retrieval"]
    assert active["status"] == "awaiting_review"
    assert {confirmed_row["local_file_path"], confirmed_row["content_path"]}.issubset(
        {record["path"] for record in active["artifact_manifest"]}
    )

    _review(
        ledger,
        "fulltext_retrieval",
        "retrieval-reviewer-a",
        "approve",
        _write(tmp_path, "verification/retrieval-review-a.md", "Independent retrieval review A passed"),
    )
    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "fulltext_screening", "fulltext-screening-agent")
    _review(
        ledger,
        "fulltext_retrieval",
        "retrieval-reviewer-b",
        "approve",
        _write(tmp_path, "verification/retrieval-review-b.md", "Independent retrieval review B passed"),
    )
    assert ledger.load()["stages"]["fulltext_retrieval"]["status"] == "approved"
    assert _start(ledger, "fulltext_screening", "fulltext-screening-agent")["current_stage"] == "fulltext_screening"


def test_extraction_submission_matches_approved_retrieval_and_eligibility(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stage_ledger_module,
        "STAGES",
        [
            ("deduplication", "Deduplication"),
            ("title_abstract_screening", "Title/abstract screening"),
            ("fulltext_retrieval", "Full-text retrieval"),
            ("fulltext_screening", "Full-text screening"),
            ("data_extraction", "Data extraction"),
        ],
    )
    monkeypatch.setattr(
        stage_ledger_module,
        "STAGE_IDS",
        ["deduplication", "title_abstract_screening", "fulltext_retrieval", "fulltext_screening", "data_extraction"],
    )
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    map_data = {"schema_version": 1, "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"]}]}
    map_artifact = _write(
        tmp_path, "corpus/study_report_map.json", json.dumps(map_data, ensure_ascii=False)
    )
    _approve(ledger, tmp_path, "deduplication", "dedup-agent", [map_artifact])
    screening_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "records": [_ta_record("R1", "include_for_full_text"), _ta_record("R2", "include_for_full_text")],
    }
    screening_artifact = _write(
        tmp_path,
        "screening/title_abstract_screening_manifest.json",
        json.dumps(screening_manifest, ensure_ascii=False),
    )
    _approve(ledger, tmp_path, "title_abstract_screening", "screening-agent", [screening_artifact])
    retrieval_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "title_abstract_screening_manifest_sha256": stage_ledger_module._sha256(tmp_path / screening_artifact),
        "records": [
            {
                "study_id": "S1",
                "report_id": "R1",
                "retrieval_status": "automatic_retrieval_succeeded",
                "full_text_review_status": "not_started",
                "fact_status": "pending_full_text_review",
                "zotero_item_key": "ITEM1",
                "attachment_key": "ATTACH1",
                "attachment_sha256": "a" * 64,
                "identity_match_status": "unique_match",
            },
            {
                "study_id": "S1",
                "report_id": "R2",
                "retrieval_status": "awaiting_manual_acquisition",
                "full_text_review_status": "not_started",
                "fact_status": "not_assessed_pending_full_text",
                "unresolved_reason": "No attachment is available in Zotero",
                "route_attempts": [],
            },
        ],
    }
    retrieval_artifact = _write(
        tmp_path,
        "retrieval/full_text_retrieval_manifest.json",
        json.dumps(retrieval_manifest, ensure_ascii=False),
    )
    _approve(ledger, tmp_path, "fulltext_retrieval", "retrieval-agent", [retrieval_artifact])
    fulltext_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "full_text_retrieval_manifest_sha256": stage_ledger_module._sha256(tmp_path / retrieval_artifact),
        "records": [
            {
                "study_id": "S1",
                "report_id": "R1",
                "eligibility_status": "included",
                "full_text_review_status": "complete_after_adjudication",
                "reviewer_decisions": [
                    {"reviewer_id": "ft-a", "decision": "include"},
                    {"reviewer_id": "ft-b", "decision": "include"},
                ],
            },
            {
                "study_id": "S1",
                "report_id": "R2",
                "eligibility_status": "awaiting_classification",
                "full_text_review_status": "not_started",
                "reviewer_decisions": [],
            },
        ],
    }
    fulltext_artifact = _write(
        tmp_path,
        "screening/full_text_screening_manifest.json",
        json.dumps(fulltext_manifest, ensure_ascii=False),
    )
    _approve(ledger, tmp_path, "fulltext_screening", "fulltext-agent", [fulltext_artifact])
    _start(ledger, "data_extraction", "extractor")

    fact_manifest = {
        "schema_version": 1,
        "study_report_map_sha256": stage_ledger_module._sha256(tmp_path / map_artifact),
        "full_text_retrieval_manifest_sha256": stage_ledger_module._sha256(tmp_path / retrieval_artifact),
        "full_text_screening_manifest_sha256": stage_ledger_module._sha256(tmp_path / fulltext_artifact),
        "facts": [{
            "study_id": "S1",
            "report_id": "R1",
            "field_id": "mortality_30d",
            "fact_scope": "report",
            "retrieval_status": "automatic_retrieval_succeeded",
            "full_text_review_status": "complete_after_adjudication",
            "fact_status": "reported",
            "value": 12,
            "source_quote": "12 participants died by day 30.",
            "source_locator": "Results, Table 2, p. 5",
        }],
    }
    fact_artifact = _write(
        tmp_path, "extraction/fact_status_manifest.json", json.dumps(fact_manifest, ensure_ascii=False)
    )
    fact_manifest["facts"][0]["report_id"] = "R9"
    (tmp_path / fact_artifact).write_text(json.dumps(fact_manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="study/report ID pair"):
        _submit(ledger, "data_extraction", "extractor", [fact_artifact], "Extraction complete")

    fact_manifest["facts"][0]["report_id"] = "R1"
    fact_manifest["facts"][0]["retrieval_status"] = "manual_confirmed"
    (tmp_path / fact_artifact).write_text(json.dumps(fact_manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="does not match the approved retrieval manifest"):
        _submit(ledger, "data_extraction", "extractor", [fact_artifact], "Extraction complete")

    fact_manifest["facts"][0]["retrieval_status"] = "automatic_retrieval_succeeded"
    fact_manifest["facts"][0]["report_id"] = "R2"
    fact_manifest["facts"][0]["retrieval_status"] = "awaiting_manual_acquisition"
    fact_manifest["facts"][0]["full_text_review_status"] = "not_started"
    fact_manifest["facts"][0]["fact_status"] = "not_assessed_pending_full_text"
    fact_manifest["facts"][0].pop("value")
    fact_manifest["facts"][0].pop("source_quote")
    fact_manifest["facts"][0].pop("source_locator")
    (tmp_path / fact_artifact).write_text(json.dumps(fact_manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="unless full-text eligibility is included"):
        _submit(ledger, "data_extraction", "extractor", [fact_artifact], "Extraction complete")

    fact_manifest["facts"] = [{
        "study_id": "S1",
        "report_id": "R1",
        "field_id": "mortality_30d",
        "fact_scope": "report",
        "retrieval_status": "automatic_retrieval_succeeded",
        "full_text_review_status": "complete_after_adjudication",
        "fact_status": "reported",
        "value": 12,
        "source_quote": "12 participants died by day 30.",
        "source_locator": "Results, Table 2, p. 5",
    }]
    (tmp_path / fact_artifact).write_text(json.dumps(fact_manifest, ensure_ascii=False), encoding="utf-8")
    result = _submit(ledger, "data_extraction", "extractor", [fact_artifact], "Extraction complete")
    assert result["stages"]["data_extraction"]["status"] == "awaiting_review"


def test_revision_vote_blocks_downstream_and_new_attempt_clears_votes(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    report = _write(tmp_path, "verification/reviews/revise.md", "missing outcome definitions")

    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol draft")
    result = _review(ledger, "protocol", "reviewer-a", "revise", report, "Add outcome timing")
    assert result["stages"]["protocol"]["status"] == "needs_revision"
    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "search", "search-agent")

    _start(ledger, "protocol", "protocol-agent")
    assert ledger.load()["stages"]["protocol"]["reviews"] == []
    assert ledger.load()["stages"]["protocol"]["history"][0]["reviews"][0]["findings"] == "Add outcome timing"


def test_rerun_invalidates_downstream_and_artifact_hashes_are_checked(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    report_a = _write(tmp_path, "verification/reviews/a.md", "pass A")
    report_b = _write(tmp_path, "verification/reviews/b.md", "pass B")
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol done")
    _review(ledger, "protocol", "reviewer-a", "approve", report_a)
    _review(ledger, "protocol", "reviewer-b", "approve", report_b)
    _start(ledger, "search", "search-agent")

    rerun = _start(ledger, "protocol", "protocol-agent", rerun=True)
    assert rerun["stages"]["protocol"]["status"] == "in_progress"
    assert rerun["stages"]["search"]["status"] == "pending"
    assert ledger.verify_integrity()

    raw = json.loads(ledger.path.read_text(encoding="utf-8"))
    raw["events"][0]["payload"]["stage_count"] = 0
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    assert not ledger.verify_integrity()


def test_artifacts_must_be_inside_project_and_exist(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    _start(ledger, "protocol", "protocol-agent")
    with pytest.raises(StageLedgerError, match="does not exist"):
        _submit(ledger, "protocol", "protocol-agent", ["missing.txt"], "No artifact")


@pytest.mark.parametrize(
    "malformed",
    [
        [],
        None,
        {"schema_version": 2, "stages": {}, "events": [], "event_chain_head": "0" * 64},
    ],
)
def test_load_converts_malformed_ledger_roots_to_stage_ledger_error(tmp_path, malformed):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    ledger.path.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(StageLedgerError):
        ledger.load()


def test_load_rejects_malformed_nested_ledger_records(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    raw = json.loads(ledger.path.read_text(encoding="utf-8"))
    raw["stages"]["protocol"]["attempts"] = [None]
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(StageLedgerError, match="malformed history entries"):
        ledger.load()

    raw["stages"]["protocol"]["attempts"] = []
    raw["events"] = [None]
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed event record"):
        ledger.load()

    AgentStageLedger.initialize(str(tmp_path), overwrite=True)
    _start(ledger, "protocol", "protocol-agent")
    protocol = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    _submit_protocol(ledger, tmp_path, "protocol-agent", protocol, "Protocol complete")
    report = _write(tmp_path, "verification/reviews/reviewer.md", "Independent review")
    _review(ledger, "protocol", "reviewer-a", "approve", report)
    raw = json.loads(ledger.path.read_text(encoding="utf-8"))
    raw["stages"]["protocol"]["reviews"][0]["report"] = {}
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed review record"):
        ledger.load()

    raw["stages"]["protocol"]["reviews"][0]["report"] = ledger._artifact_record(report)
    raw["stages"]["protocol"]["history"] = None
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed stage history"):
        ledger.load()

    raw["stages"]["protocol"]["history"] = []
    raw["stages"]["protocol"]["attempts"][0]["artifact_manifest"] = [{}]
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed attempt artifacts"):
        ledger.load()

    raw["stages"]["protocol"]["attempts"][0]["artifact_manifest"] = raw["stages"]["protocol"]["artifact_manifest"]
    raw["stages"]["protocol"]["attempts"][0]["reviews"] = [{}]
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed attempt reviews"):
        ledger.load()


def test_review_and_next_stage_reject_changed_evidence(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    report_a = _write(tmp_path, "verification/reviews/a.md", "pass A")
    report_b = _write(tmp_path, "verification/reviews/b.md", "pass B")

    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol done")
    (tmp_path / artifact).write_text("changed after submission", encoding="utf-8")
    with pytest.raises(StageLedgerError, match="changed after submission"):
        _review(ledger, "protocol", "reviewer-a", "approve", report_a)

    (tmp_path / artifact).write_text(_valid_protocol_text(), encoding="utf-8")
    _review(ledger, "protocol", "reviewer-a", "revise", report_a)
    _start(ledger, "protocol", "protocol-agent")
    revised_protocol = json.loads(_valid_protocol_text())
    revised_protocol["project"]["version"] = "0.2"
    (tmp_path / artifact).write_text(json.dumps(revised_protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol revised")
    _review(ledger, "protocol", "reviewer-a", "approve", report_a)
    _review(ledger, "protocol", "reviewer-b", "approve", report_b)
    (tmp_path / artifact).write_text("changed after approval", encoding="utf-8")
    with pytest.raises(StageLedgerError, match="changed after submission"):
        _start(ledger, "search", "search-agent")


def test_state_tampering_invalidates_event_chain_and_blocks_next_stage(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    raw = json.loads(ledger.path.read_text(encoding="utf-8"))
    raw["stages"]["protocol"]["status"] = "approved"
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")

    assert not ledger.verify_integrity()
    with pytest.raises(StageLedgerError, match="event hash chain is invalid"):
        _start(ledger, "search", "search-agent")


def test_malformed_ledger_root_and_event_shapes_raise_domain_error(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    ledger.path.write_text("[]", encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed stage ledger schema"):
        ledger.status()

    AgentStageLedger.initialize(str(tmp_path), overwrite=True)
    raw = json.loads(ledger.path.read_text(encoding="utf-8"))
    raw["events"] = [None]
    ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="malformed event record"):
        ledger.status()


def test_reviewer_sessions_and_report_artifacts_must_be_distinct(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    report = _write(tmp_path, "verification/reviews/review.md", "independent review")

    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol done")
    _review(ledger, "protocol", "reviewer-a", "approve", report)
    with pytest.raises(StageLedgerError, match="Reviewer ID or session"):
        ledger.review("protocol", "reviewer-b", "reviewer-a-session", "approve", "verification/reviews/other.md")
    with pytest.raises(StageLedgerError, match="distinct report artifact"):
        _review(ledger, "protocol", "reviewer-b", "approve", report)


def test_downstream_gates_recheck_all_upstream_evidence(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    protocol_text = _valid_protocol_text()
    protocol_artifact = _write(tmp_path, "review_protocol.json", protocol_text)
    report_a = _write(tmp_path, "verification/reviews/a.md", "protocol review A")
    report_b = _write(tmp_path, "verification/reviews/b.md", "protocol review B")
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", protocol_artifact, "Protocol complete")
    _review(ledger, "protocol", "reviewer-a", "approve", report_a)
    _review(ledger, "protocol", "reviewer-b", "approve", report_b)
    _start(ledger, "search", "search-agent")

    search_artifact = _write(tmp_path, "search/search_log.json", "{}")
    (tmp_path / protocol_artifact).write_text(protocol_text.replace("\"version\": \"0.1\"", "\"version\": \"0.2\""), encoding="utf-8")
    with pytest.raises(StageLedgerError, match="changed after submission"):
        _submit(ledger, "search", "search-agent", [search_artifact], "Search complete")

    status = ledger.status()
    assert status["integrity_valid"]
    assert not status["evidence_integrity_valid"]


def test_review_rejects_empty_or_identical_review_artifacts(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    empty_report = _write(tmp_path, "verification/reviews/empty.md", "  \n")
    report_a = _write(tmp_path, "verification/reviews/a.md", "Same review text")
    report_b = _write(tmp_path, "verification/reviews/b.md", "Same review text")
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", artifact, "Protocol complete")

    with pytest.raises(StageLedgerError, match="non-empty UTF-8"):
        _review(ledger, "protocol", "reviewer-a", "approve", empty_report)
    _review(ledger, "protocol", "reviewer-a", "approve", report_a)
    with pytest.raises(StageLedgerError, match="distinct report artifact with different content"):
        _review(ledger, "protocol", "reviewer-b", "approve", report_b)


def test_resume_hands_off_unsubmitted_in_progress_attempt_without_resetting_it(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    _start(ledger, "protocol", "protocol-agent")
    before = ledger.load()
    started_at = before["stages"]["protocol"]["started_at"]

    resumed = ledger.resume("protocol", "replacement-agent", "replacement-session")
    stage = resumed["stages"]["protocol"]

    assert stage["status"] == "in_progress"
    assert stage["executor"] == "replacement-agent"
    assert stage["executor_session"] == "replacement-session"
    assert stage["started_at"] == started_at
    assert stage["run_count"] == 1
    assert len(stage["attempts"]) == 1
    assert len(stage["attempts"][0]["handoffs"]) == 1
    handoff = stage["attempts"][0]["handoffs"][0]
    assert handoff["from_executor"] == "protocol-agent"
    assert handoff["from_session"] == "protocol-agent-session-1"
    assert handoff["to_executor"] == "replacement-agent"
    assert handoff["to_session"] == "replacement-session"
    protocol_artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    source_log = _write(
        tmp_path,
        "verification/methods_source_log.json",
        _valid_methods_source_log_text(),
    )
    with pytest.raises(StageLedgerError, match="does not own active stage"):
        ledger.submit(
            "protocol", "protocol-agent", "protocol-agent-session-1",
            [protocol_artifact, source_log], "Stale executor submission",
        )
    submitted = ledger.submit(
        "protocol", "replacement-agent", "replacement-session",
        [protocol_artifact, source_log], "Protocol submitted by handoff executor",
    )
    attempt = submitted["stages"]["protocol"]["attempts"][0]
    assert attempt["executor"] == "protocol-agent"
    assert attempt["submitted_by"] == "replacement-agent"
    assert attempt["submitted_by_session"] == "replacement-session"
    submission_event = submitted["events"][-1]
    assert submission_event["event_type"] == "stage_submitted"
    assert submission_event["payload"]["agent"] == "replacement-agent"
    assert submission_event["payload"]["agent_session"] == "replacement-session"
    assert ledger.verify_integrity()
    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "search", "search-agent")


def test_validate_resume_is_read_only_and_checks_upstream_and_handoff_eligibility(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    before = ledger.path.read_bytes()

    with pytest.raises(StageLedgerError, match="upstream stage 'protocol'.*not approved"):
        ledger.validate_resume("search", "search-agent", "search-session")
    assert ledger.path.read_bytes() == before

    _start(ledger, "protocol", "protocol-agent")
    before = ledger.path.read_bytes()
    result = ledger.validate_resume("protocol", "replacement-agent", "replacement-session")

    assert result == {
        "stage_id": "protocol",
        "action": "handoff",
        "status": "in_progress",
        "run_count": 1,
    }
    assert ledger.path.read_bytes() == before


def test_validate_resume_rejects_stale_current_artifacts_before_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_ledger_module, "STAGES", [("search", "Search")])
    monkeypatch.setattr(stage_ledger_module, "STAGE_IDS", ["search"])
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    _start(ledger, "search", "search-agent")
    artifact = _write(tmp_path, "search/search_log.json", "original submission")
    _submit(ledger, "search", "search-agent", [artifact], "Search complete")
    before = ledger.path.read_bytes()
    (tmp_path / artifact).write_text("modified after submission", encoding="utf-8")

    with pytest.raises(StageLedgerError, match="changed after submission"):
        ledger.validate_resume("search", "replacement-agent", "replacement-session")
    assert ledger.path.read_bytes() == before


def test_resume_awaiting_review_archives_old_evidence_and_requires_two_new_approvals(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    protocol_artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    old_review = _write(tmp_path, "verification/reviews/old-review.md", "Independent review one")
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", protocol_artifact, "Protocol drafted")
    _review(ledger, "protocol", "reviewer-a", "approve", old_review)
    before = ledger.load()["stages"]["protocol"]
    old_evidence = [*before["artifact_manifest"], before["reviews"][0]["report"]]

    resumed = ledger.resume("protocol", "protocol-agent-v2", "protocol-session-v2")
    stage = resumed["stages"]["protocol"]

    assert stage["status"] == "in_progress"
    assert stage["run_count"] == 2
    assert stage["artifact_manifest"] == []
    assert stage["reviews"] == []
    assert resumed["stages"]["search"]["status"] == "pending"
    for record in old_evidence:
        archived = tmp_path / "verification" / "history" / "protocol" / "run-0001" / (
            "reviews" if record == before["reviews"][0]["report"] else "artifacts"
        ) / Path(record["path"])
        assert archived.is_file()
        assert archived.stat().st_size == record["size_bytes"]
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == record["sha256"]

    revised_protocol = json.loads(_valid_protocol_text())
    revised_protocol["project"]["version"] = "0.2"
    _write(tmp_path, protocol_artifact, json.dumps(revised_protocol, ensure_ascii=False, indent=2))
    _submit_protocol(ledger, tmp_path, "protocol-agent-v2", protocol_artifact, "Protocol revised")
    _review(ledger, "protocol", "reviewer-c", "approve", _write(tmp_path, "verification/reviews/new-review-c.md", "Independent review C"))
    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "search", "search-agent")
    _review(ledger, "protocol", "reviewer-d", "approve", _write(tmp_path, "verification/reviews/new-review-d.md", "Independent review D"))
    assert ledger.load()["stages"]["protocol"]["status"] == "approved"
    assert ledger.verify_integrity()


def test_resume_approved_stage_archives_prior_run_and_invalidates_downstream(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    protocol_artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", protocol_artifact, "Protocol complete")
    _review(ledger, "protocol", "reviewer-a", "approve", _write(tmp_path, "verification/protocol-review-a.md", "Independent review A passed"))
    _review(ledger, "protocol", "reviewer-b", "approve", _write(tmp_path, "verification/protocol-review-b.md", "Independent review B passed"))
    _start(ledger, "search", "search-agent")
    before = ledger.load()["stages"]["protocol"]
    approved_evidence = [*before["artifact_manifest"], *(review["report"] for review in before["reviews"])]

    resumed = ledger.resume("protocol", "protocol-agent-v2", "protocol-session-v2")

    assert resumed["stages"]["protocol"]["status"] == "in_progress"
    assert resumed["stages"]["protocol"]["run_count"] == 2
    assert resumed["stages"]["search"]["status"] == "pending"
    assert resumed["current_stage"] == "protocol"
    for record in approved_evidence:
        bucket = "reviews" if any(record == review["report"] for review in before["reviews"]) else "artifacts"
        archived = tmp_path / "verification" / "history" / "protocol" / "run-0001" / bucket / Path(record["path"])
        assert archived.is_file()
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == record["sha256"]
    with pytest.raises(StageLedgerError, match="not approved"):
        _start(ledger, "search", "search-agent")
    assert ledger.verify_integrity()


def test_stage_transitions_reject_tampered_historical_evidence(tmp_path):
    AgentStageLedger.initialize(str(tmp_path))
    ledger = AgentStageLedger(str(tmp_path))
    protocol_artifact = _write(tmp_path, "review_protocol.json", _valid_protocol_text())
    _start(ledger, "protocol", "protocol-agent")
    _submit_protocol(ledger, tmp_path, "protocol-agent", protocol_artifact, "Protocol complete")
    _review(ledger, "protocol", "reviewer-a", "approve", _write(tmp_path, "verification/protocol-review-a.md", "Review A passed"))
    _review(ledger, "protocol", "reviewer-b", "approve", _write(tmp_path, "verification/protocol-review-b.md", "Review B passed"))

    ledger.resume("protocol", "protocol-agent-v2", "protocol-session-v2")
    _submit_protocol(ledger, tmp_path, "protocol-agent-v2", protocol_artifact, "Protocol revalidated")
    _review(ledger, "protocol", "reviewer-c", "approve", _write(tmp_path, "verification/protocol-review-c.md", "Review C passed"))
    _review(ledger, "protocol", "reviewer-d", "approve", _write(tmp_path, "verification/protocol-review-d.md", "Review D passed"))

    archived_protocol = tmp_path / "verification/history/protocol/run-0001/artifacts/review_protocol.json"
    assert archived_protocol.is_file()
    archived_protocol.write_text("tampered historical protocol", encoding="utf-8")
    assert ledger.status()["evidence_integrity_valid"] is False

    with pytest.raises(StageLedgerError, match="changed after submission"):
        ledger.start("search", "search-agent", "search-session")
    with pytest.raises(StageLedgerError, match="changed after submission"):
        ledger.validate_resume("protocol", "protocol-agent-v3", "protocol-session-v3")

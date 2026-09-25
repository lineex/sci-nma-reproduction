"""
End-to-End integration tests for the sci-nma-agent framework.
Verifies full pipeline execution as well as step-by-step gated acceptance and error fusing.
"""

import os
import json
import pytest
from sci_nma_agent.core.audit_runner import AuditRunner
from sci_nma_agent.workflow.pipeline import SOPPipeline, StepAcceptanceError


def test_case_study_audit():
    project_dir = os.path.join("examples", "case_study_corticosteroids_nma")
    assert os.path.exists(project_dir), f"Case study directory not found: {project_dir}"

    auditor = AuditRunner(project_dir)
    report = auditor.run_full_audit()

    assert report.overall_passed is True, f"Audit failed: {report.gates}"
    assert report.gates["gate1"]["passed"] is True
    assert report.gates["gate2"]["passed"] is True
    assert report.gates["gate3"]["passed"] is True
    assert report.gates["gate4"]["passed"] is True
    assert report.gates["gate5"]["passed"] is True


def test_step_by_step_gated_acceptance():
    project_dir = os.path.join("examples", "case_study_corticosteroids_nma")
    pipeline = SOPPipeline(project_dir)
    pico_path = os.path.join(project_dir, "config_pico.json")
    data_path = os.path.join(project_dir, "data", "extraction_dataset.json")
    flow_path = os.path.join(project_dir, "data", "prisma_flow_data.json")

    # Step 1: Search queries
    queries = pipeline.step1_search(pico_path)
    assert len(queries) >= 4

    # Step 2: PRISMA flow
    flow_data = pipeline.step2_flow(flow_path)
    assert flow_data["flow_loss"] == 0

    # Step 3: Extraction & Statistics
    ma_res, nma_res, dataset = pipeline.step3_extract_and_synthesize(data_path)
    assert ma_res["k"] == 29
    assert "Hydrocortisone + Fludrocortisone" in nma_res["sucra_scores"]

    # Step 4: Render Figures & Gate 4 Audit
    fig_info = pipeline.step4_render_figures(flow_data, ma_res, dataset)
    assert fig_info["metrics"]["figures_audited"] >= 3

    # Step 5: Office Suites & Gate 5 Audit
    with open(pico_path, "r", encoding="utf-8") as f:
        pico_config = json.load(f)
    office_info = pipeline.step5_office_suite(pico_config, flow_data, ma_res, nma_res, dataset)
    assert os.path.exists(office_info["docx"])
    assert os.path.exists(office_info["xlsx"])
    assert os.path.exists(office_info["pptx"])

    # Step 6: Global Audit & AI Reviewer
    final_info = pipeline.step6_audit_and_peer_review(pico_config)
    assert final_info["overall_passed"] is True


def test_step_acceptance_fuse_on_invalid_flow(tmp_path):
    # Setup temporary project with invalid flow data (conservation broken)
    broken_flow = {
        "databases": {"PubMed": 100},
        "total_identified": 100,
        "duplicates_removed": 10,
        "records_screened": 80,  # Deliberate mismatch: 100 - 10 = 90 != 80
        "screening_excluded": 50,
        "reports_sought": 30,
        "reports_not_retrieved": 0,
        "reports_assessed": 30,
        "fulltext_excluded": 10,
        "studies_included": 20
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    flow_file = data_dir / "prisma_flow_data.json"
    flow_file.write_text(json.dumps(broken_flow), encoding="utf-8")

    pipeline = SOPPipeline(str(tmp_path))

    # Must raise StepAcceptanceError and abort immediately
    with pytest.raises(StepAcceptanceError) as excinfo:
        pipeline.step2_flow(str(flow_file))

    assert "Stage 2 Acceptance FAILED" in str(excinfo.value)
    assert "Screening mismatch" in str(excinfo.value)


def test_locked_production_results_resolve_relative_to_project_and_are_release_marked(tmp_path):
    result_path = tmp_path / "results" / "locked.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "pairwise": {
                    "engine_role": "r_production",
                    "production_use": "release",
                    "pooled_estimate": 0.82,
                    "ci_lower": 0.60,
                    "ci_upper": 1.10,
                    "i2_percent": 42.1,
                    "tau2": 0.03,
                    "p_value": 0.01,
                    "studies": [{"study_id": "S1", "effect_size": 0.82}],
                },
            }
        ),
        encoding="utf-8",
    )
    pairwise, network = SOPPipeline(str(tmp_path))._load_production_results("results/locked.json")
    assert pairwise["engine_role"] == "r_production"
    assert network["planned"] is False


def test_locked_production_results_reject_planned_network_without_results(tmp_path):
    result_path = tmp_path / "locked.json"
    result_path.write_text(
        json.dumps(
            {
                "pairwise": {
                    "engine_role": "r_production", "production_use": "release",
                    "pooled_estimate": 0.82, "ci_lower": 0.60, "ci_upper": 1.10,
                    "i2_percent": 42.1, "tau2": 0.03, "p_value": 0.01,
                    "studies": [{"study_id": "S1"}],
                },
                "network": {"engine_role": "r_production", "production_use": "release"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StepAcceptanceError, match="non-empty rankings"):
        SOPPipeline(str(tmp_path))._load_production_results("locked.json")


def test_locked_production_results_accept_complete_planned_network(tmp_path):
    result_path = tmp_path / "locked.json"
    result_path.write_text(
        json.dumps(
            {
                "pairwise": {
                    "engine_role": "r_production", "production_use": "release",
                    "pooled_estimate": 0.82, "ci_lower": 0.60, "ci_upper": 1.10,
                    "i2_percent": 42.1, "tau2": 0.03, "p_value": 0.01,
                    "studies": [{"study_id": "S1"}],
                },
                "network": {
                    "planned": True, "engine_role": "r_production", "production_use": "release",
                    "treatments": [
                        {"id": "A", "sample_size": 100, "color": "#2563EB"},
                        {"id": "B", "sample_size": 120, "color": "#059669"},
                    ],
                    "rankings": [{
                        "treatment": "A", "rank": 1, "sucra_percent": 82.0,
                        "relative_or_vs_ref": 0.72, "ci_lower": 0.51, "ci_upper": 1.01,
                    }, {
                        "treatment": "B", "rank": 2, "sucra_percent": 18.0,
                        "relative_or_vs_ref": 1.38, "ci_lower": 0.99, "ci_upper": 1.96,
                    }],
                    "comparisons": [{"t1": "A", "t2": "B", "trial_count": 2}],
                },
            }
        ),
        encoding="utf-8",
    )
    _, network = SOPPipeline(str(tmp_path))._load_production_results("locked.json")
    assert network["planned"] is True
    assert network["rankings"]


def test_locked_production_results_reject_network_geometry_contract_violations(tmp_path):
    base = {
        "pairwise": {
            "engine_role": "r_production", "production_use": "release",
            "pooled_estimate": 0.82, "ci_lower": 0.60, "ci_upper": 1.10,
            "i2_percent": 42.1, "tau2": 0.03, "p_value": 0.01,
            "studies": [{"study_id": "S1"}],
        },
        "network": {
            "planned": True, "engine_role": "r_production", "production_use": "release",
            "treatments": [
                {"id": "A", "sample_size": 100, "color": "#2563EB"},
                {"id": "B", "sample_size": 120, "color": "#059669"},
            ],
            "rankings": [
                {"treatment": "A", "rank": 1, "sucra_percent": 82.0,
                 "relative_or_vs_ref": 0.72, "ci_lower": 0.51, "ci_upper": 1.01},
                {"treatment": "B", "rank": 2, "sucra_percent": 18.0,
                 "relative_or_vs_ref": 1.38, "ci_lower": 0.99, "ci_upper": 1.96},
            ],
            "comparisons": [{"t1": "A", "t2": "B", "trial_count": 2}],
        },
    }
    missing_treatments = json.loads(json.dumps(base))
    del missing_treatments["network"]["treatments"]
    (tmp_path / "missing.json").write_text(json.dumps(missing_treatments), encoding="utf-8")
    with pytest.raises(StepAcceptanceError, match="non-empty treatments"):
        SOPPipeline(str(tmp_path))._load_production_results("missing.json")

    unknown_endpoint = json.loads(json.dumps(base))
    unknown_endpoint["network"]["comparisons"] = [{"t1": "A", "t2": "C", "trial_count": 2}]
    (tmp_path / "unknown.json").write_text(json.dumps(unknown_endpoint), encoding="utf-8")
    with pytest.raises(StepAcceptanceError, match="undeclared treatment"):
        SOPPipeline(str(tmp_path))._load_production_results("unknown.json")

    invalid_not_planned = json.loads(json.dumps(base))
    invalid_not_planned["network"] = {"planned": False, "engine_role": "python", "production_use": "release"}
    (tmp_path / "invalid_not_planned.json").write_text(json.dumps(invalid_not_planned), encoding="utf-8")
    with pytest.raises(StepAcceptanceError, match="non-planned network"):
        SOPPipeline(str(tmp_path))._load_production_results("invalid_not_planned.json")


def test_locked_production_results_reject_qa_or_incomplete_payload(tmp_path):
    result_path = tmp_path / "locked.json"
    result_path.write_text(
        json.dumps(
            {
                "pairwise": {"engine_role": "python", "production_use": "release"},
                "network": {"engine_role": "r_production", "production_use": "release"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StepAcceptanceError, match="QA/not-for-release"):
        SOPPipeline(str(tmp_path))._load_production_results("locked.json")


def test_locked_production_results_support_explicit_pairwise_not_planned(tmp_path):
    result_path = tmp_path / "locked.json"
    result_path.write_text(
        json.dumps(
            {
                "pairwise": {"planned": False, "engine_role": "not_planned", "production_use": "not_applicable"},
                "network": {
                    "planned": True, "engine_role": "r_production", "production_use": "release",
                    "treatments": [
                        {"id": "A", "sample_size": 100, "color": "#2563EB"},
                        {"id": "B", "sample_size": 120, "color": "#059669"},
                    ],
                    "rankings": [{
                        "treatment": "A", "rank": 1, "sucra_percent": 82.0,
                        "relative_or_vs_ref": 0.72, "ci_lower": 0.51, "ci_upper": 1.01,
                    }, {
                        "treatment": "B", "rank": 2, "sucra_percent": 18.0,
                        "relative_or_vs_ref": 1.38, "ci_lower": 0.99, "ci_upper": 1.96,
                    }],
                    "comparisons": [{"t1": "A", "t2": "B", "trial_count": 2}],
                },
            }
        ),
        encoding="utf-8",
    )
    pairwise, network = SOPPipeline(str(tmp_path))._load_production_results("locked.json")
    assert pairwise["planned"] is False
    assert network["planned"] is True


def test_production_office_outputs_use_locked_labels_and_support_pairwise_only(monkeypatch, tmp_path):
    """Formal office outputs must not retain QA-only labels after a locked hand-off."""
    captured = {}
    pairwise = {
        "planned": True,
        "engine_role": "r_production",
        "production_use": "release",
        "pooled_estimate": 0.82,
        "ci_lower": 0.60,
        "ci_upper": 1.10,
        "i2_percent": 42.1,
        "tau2": 0.03,
        "p_value": 0.01,
        "studies": [{
            "study_id": "S1", "effect_size": 0.82,
            "ci_lower": 0.60, "ci_upper": 1.10,
        }],
    }
    network = {"planned": False, "engine_role": "not_planned", "production_use": "not_applicable"}
    pipeline = SOPPipeline(str(tmp_path))
    monkeypatch.setattr(pipeline, "_load_production_results", lambda _: (pairwise, network))
    monkeypatch.setattr(pipeline, "_require_production_synthesis", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.DocxManuscriptGenerator.generate",
        lambda data, path: captured.setdefault("docx", data),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.MasterExcelGenerator.generate",
        lambda data, path: captured.setdefault("excel", data),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.PresentationGenerator.generate",
        lambda data, path: captured.setdefault("pptx", data),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.Gate5OfficeAudit.audit_docx_file",
        lambda _: (True, [], {}),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.Gate5OfficeAudit.audit_excel_file",
        lambda _: (True, [], {"sheet_count": 2, "formula_cells_count": 1}),
    )

    pipeline.step5_office_suite(
        {"title": "Locked review"},
        {"studies_included": 1, "total_identified": 1},
        {"pooled_estimate": 1.0, "ci_lower": 0.5, "ci_upper": 2.0, "i2_percent": 0.0, "tau2": 0.0},
        {"rankings": []},
        [{
            "study_id": "S1", "events_treatment": 1, "total_treatment": 10,
            "events_control": 2, "total_control": 10,
        }],
        production=True,
        production_results_path="results/locked.json",
    )

    assert "Primary_Outcome_Mortality" in captured["excel"]
    assert "QA_Primary_Outcome_Mortality" not in captured["excel"]
    assert all(not name.startswith("QA_") for name in captured["excel"])
    assert "NMA_Rankings" not in captured["excel"]
    assert "locked production engine" in captured["docx"]["abstract"]["Methods"]
    assert "QA fixture" not in captured["docx"]["abstract"]["Methods"]
    assert "not a production synthesis" not in captured["docx"]["abstract"]["Results"]
    assert "not a production result" not in " ".join(
        captured["pptx"]["slides"][2]["bullet_points"]
    )
    discussion_text = " ".join(captured["docx"]["sections"][-1]["paragraphs"])
    assert "QA fixture" not in discussion_text
    assert "locked production" in discussion_text


def test_nma_only_production_stage4_renders_not_estimable_pairwise_figure(monkeypatch, tmp_path):
    """NMA-only release keeps Figure 2's files without fabricating pairwise data."""
    calls = []
    network_calls = []
    pipeline = SOPPipeline(str(tmp_path))
    production_network = {
        "planned": True,
        "engine_role": "r_production",
        "production_use": "release",
        "treatments": [
            {"id": "A", "sample_size": 100, "color": "#2563EB"},
            {"id": "B", "sample_size": 120, "color": "#059669"},
        ],
        "rankings": [{
            "treatment": "A", "rank": 1, "sucra_percent": 80.0,
            "relative_or_vs_ref": 0.8, "ci_lower": 0.5, "ci_upper": 1.2,
        }, {
            "treatment": "B", "rank": 2, "sucra_percent": 20.0,
            "relative_or_vs_ref": 1.25, "ci_lower": 0.83, "ci_upper": 2.0,
        }],
        "comparisons": [{"t1": "A", "t2": "B", "trial_count": 2}],
    }
    production_pairwise = {
        "planned": False,
        "engine_role": "not_planned",
        "production_use": "not_applicable",
    }
    monkeypatch.setattr(
        pipeline, "_load_production_results", lambda _: (production_pairwise, production_network)
    )
    monkeypatch.setattr(pipeline, "_require_production_synthesis", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.PRISMADiagramGenerator.generate",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.ForestPlotGenerator.generate_not_estimable",
        lambda *args, **kwargs: calls.append(("not_estimable", args, kwargs)) or {},
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.ForestPlotGenerator.generate",
        lambda *args, **kwargs: calls.append(("pairwise", args, kwargs)) or {},
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.NetworkGeometryGenerator.generate",
        lambda *args, **_kwargs: network_calls.append(args) or {},
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.Gate4FigureVector.audit_figures_directory",
        lambda _: (True, [], {"figures_audited": 3, "png_count": 3, "svg_count": 3, "pdf_count": 3}),
    )

    result = pipeline.step4_render_figures(
        {"total_identified": 1, "records_screened": 1, "reports_sought": 1,
         "reports_assessed": 1, "studies_included": 1},
        {"planned": True},
        [],
        production=True,
        production_results_path="results/locked.json",
    )

    assert result["metrics"]["figures_audited"] == 3
    not_estimable_calls = [call for call in calls if call[0] == "not_estimable"]
    assert len(not_estimable_calls) == 3
    assert not [call for call in calls if call[0] == "pairwise"]
    assert all("no pooled pairwise estimate" in call[2]["message"] for call in not_estimable_calls)
    assert len(network_calls) == 3
    assert all(call[0] == production_network["treatments"] for call in network_calls)
    assert all(call[1] == production_network["comparisons"] for call in network_calls)


def test_nma_only_production_office_keeps_empty_pairwise_sheet(monkeypatch, tmp_path):
    """NMA-only production workbooks preserve the sheet name without dummy rows."""
    captured = {}
    pairwise = {"planned": False, "engine_role": "not_planned", "production_use": "not_applicable"}
    network = {
        "planned": True, "engine_role": "r_production", "production_use": "release",
        "treatments": [
            {"id": "A", "sample_size": 100, "color": "#2563EB"},
            {"id": "B", "sample_size": 120, "color": "#059669"},
        ],
        "rankings": [{
            "treatment": "A", "rank": 1, "sucra_percent": 80.0,
            "relative_or_vs_ref": 0.8, "ci_lower": 0.5, "ci_upper": 1.2,
        }, {
            "treatment": "B", "rank": 2, "sucra_percent": 20.0,
            "relative_or_vs_ref": 1.25, "ci_lower": 0.83, "ci_upper": 2.0,
        }],
        "comparisons": [{"t1": "A", "t2": "B", "trial_count": 2}],
    }
    pipeline = SOPPipeline(str(tmp_path))
    monkeypatch.setattr(pipeline, "_load_production_results", lambda _: (pairwise, network))
    monkeypatch.setattr(pipeline, "_require_production_synthesis", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.DocxManuscriptGenerator.generate",
        lambda data, path: None,
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.MasterExcelGenerator.generate",
        lambda data, path: captured.setdefault("excel", data),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.PresentationGenerator.generate",
        lambda data, path: None,
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.Gate5OfficeAudit.audit_docx_file",
        lambda _: (True, [], {}),
    )
    monkeypatch.setattr(
        "sci_nma_agent.workflow.pipeline.Gate5OfficeAudit.audit_excel_file",
        lambda _: (True, [], {"sheet_count": 3, "formula_cells_count": 1}),
    )

    pipeline.step5_office_suite(
        {"title": "NMA-only review"},
        {"studies_included": 1, "total_identified": 1},
        {"planned": True},
        {"planned": True},
        [{
            "study_id": "S1", "events_treatment": 1, "total_treatment": 10,
            "events_control": 2, "total_control": 10,
        }],
        production=True,
        production_results_path="results/locked.json",
    )

    assert "Primary_Outcome_Mortality" in captured["excel"]
    assert captured["excel"]["Primary_Outcome_Mortality"]["rows"] == []
    assert captured["excel"]["NMA_Rankings"]["rows"]

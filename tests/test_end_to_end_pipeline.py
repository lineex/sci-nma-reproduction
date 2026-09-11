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

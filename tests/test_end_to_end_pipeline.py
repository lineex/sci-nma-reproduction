"""
End-to-End integration tests for the sci-nma-agent framework.
"""

import os
import pytest
from sci_nma_agent.core.audit_runner import AuditRunner


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

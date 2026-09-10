"""
Unit tests for Gate 5: Office Suite XML Engineering & Master Database.
"""

import os
import pytest
from docx import Document
from sci_nma_agent.core.gate5_office_audit import Gate5OfficeAudit
from sci_nma_agent.generators.master_excel import MasterExcelGenerator


def test_docx_xml_injection_and_audit(tmp_path):
    doc = Document()
    table = doc.add_table(rows=3, cols=2)
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = f"R{r_idx}C{c_idx}"

    # Inject XML
    Gate5OfficeAudit.apply_table_engineering_rules(table)
    docx_file = tmp_path / "test_table.docx"
    doc.save(str(docx_file))

    passed, errors, metrics = Gate5OfficeAudit.audit_docx_file(str(docx_file))
    assert passed is True
    assert metrics["header_repeats_valid"] == 1
    assert metrics["cant_split_valid_rows"] == 3


def test_excel_formula_audit(tmp_path):
    sheets = {
        "Data": {
            "headers": ["Name", "Score"],
            "rows": [["Alice", 90], ["Bob", 85]],
            "has_summary_row": True,
            "numeric_cols": [2]
        },
        "Secondary": {
            "headers": ["Category", "Count"],
            "rows": [["A", 10], ["B", 20]]
        }
    }
    xlsx_file = tmp_path / "test_database.xlsx"
    MasterExcelGenerator.generate(sheets, str(xlsx_file))

    passed, errors, metrics = Gate5OfficeAudit.audit_excel_file(str(xlsx_file))
    assert passed is True
    assert metrics["sheet_count"] == 2
    assert metrics["formula_cells_count"] >= 1

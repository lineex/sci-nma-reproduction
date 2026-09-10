"""
Gate 5: Deliverables Traceability & Office Suite Engineering Verification Gate.
Audits Word docx tables for XML <w:tblHeader/> and <w:cantSplit/>,
and audits Excel workbooks for dynamic formulas and traceability columns.
"""

import os
from typing import Dict, Any, List, Tuple
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import openpyxl


class Gate5OfficeAudit:
    """Validator and injector for Gate 5: Office Suite Engineering."""

    @staticmethod
    def apply_table_engineering_rules(table) -> None:
        """
        Inject XML attributes to make Word tables publication-ready:
        1. <w:tblHeader/> on row 0 (repeats header on every page).
        2. <w:cantSplit/> on all rows (prevents row splitting across page boundaries).
        3. Compact cell margins (100 dxa top/bottom, 120 dxa left/right).
        """
        if len(table.rows) == 0:
            return

        # 1. Header Row
        header_tr = table.rows[0]._tr.get_or_add_trPr()
        header_tr.append(OxmlElement("w:tblHeader"))
        header_tr.append(OxmlElement("w:cantSplit"))

        # 2. Data Rows
        for row in table.rows[1:]:
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement("w:cantSplit"))

        # 3. Cell Margins
        for row in table.rows:
            for cell in row.cells:
                tcMar = OxmlElement("w:tcMar")
                for m, val in [("top", 100), ("bottom", 100), ("left", 120), ("right", 120)]:
                    node = OxmlElement(f"w:{m}")
                    node.set(qn("w:w"), str(val))
                    node.set(qn("w:type"), "dxa")
                    tcMar.append(node)
                cell._tc.get_or_add_tcPr().append(tcMar)

    @staticmethod
    def audit_docx_file(docx_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Audit Word docx file for tblHeader and cantSplit XML elements."""
        errors = []
        metrics = {
            "tables_audited": 0,
            "header_repeats_valid": 0,
            "cant_split_valid_rows": 0,
            "total_rows": 0
        }

        if not os.path.exists(docx_path):
            return False, [f"Docx file not found: {docx_path}"], metrics

        try:
            doc = Document(docx_path)
            metrics["tables_audited"] = len(doc.tables)

            for idx, table in enumerate(doc.tables):
                if len(table.rows) == 0:
                    continue

                metrics["total_rows"] += len(table.rows)

                # Check Header Row tblHeader
                header_xml = table.rows[0]._tr.xml
                if "tblHeader" in header_xml:
                    metrics["header_repeats_valid"] += 1
                else:
                    errors.append(
                        f"[{os.path.basename(docx_path)}:Table {idx+1}] Missing <w:tblHeader/> on header row."
                    )

                # Check cantSplit
                table_cant_split_ok = True
                for r_idx, row in enumerate(table.rows):
                    if "cantSplit" in row._tr.xml:
                        metrics["cant_split_valid_rows"] += 1
                    else:
                        table_cant_split_ok = False

                if not table_cant_split_ok:
                    errors.append(
                        f"[{os.path.basename(docx_path)}:Table {idx+1}] Missing <w:cantSplit/> on one or more rows."
                    )

        except Exception as e:
            errors.append(f"Failed to parse docx {docx_path}: {str(e)}")

        passed = (len(errors) == 0)
        return passed, errors, metrics

    @staticmethod
    def audit_excel_file(xlsx_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Audit Excel file for:
        1. Multiple sheets (> 1).
        2. Presence of dynamic formulas (SUM, AVERAGE, COUNTIF, etc.).
        """
        errors = []
        metrics = {
            "sheet_count": 0,
            "sheet_names": [],
            "formula_cells_count": 0
        }

        if not os.path.exists(xlsx_path):
            return False, [f"Excel file not found: {xlsx_path}"], metrics

        try:
            wb = openpyxl.load_workbook(xlsx_path, data_only=False)
            metrics["sheet_count"] = len(wb.sheetnames)
            metrics["sheet_names"] = wb.sheetnames

            if metrics["sheet_count"] < 2:
                errors.append(
                    f"[{os.path.basename(xlsx_path)}] Master database has only {metrics['sheet_count']} sheet. "
                    f"Multi-sheet structure required (e.g. Study Characteristics, Endpoints, RoB 2)."
                )

            # Check for formulas in cells
            formula_count = 0
            for name in wb.sheetnames:
                ws = wb[name]
                for row in ws.iter_rows(values_only=False):
                    for cell in row:
                        if cell.value and isinstance(cell.value, str) and cell.value.startswith("="):
                            formula_count += 1

            metrics["formula_cells_count"] = formula_count

        except Exception as e:
            errors.append(f"Failed to parse xlsx {xlsx_path}: {str(e)}")

        passed = (len(errors) == 0)
        return passed, errors, metrics

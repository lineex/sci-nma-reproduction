"""
Master Research Database Excel Generator.
Builds publication-grade multi-sheet Excel databases (.xlsx) with frozen panes,
styled headers, and dynamic formulas (=SUM, =AVERAGE, =COUNTIF).
"""

import os
from typing import Dict, Any, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class MasterExcelGenerator:
    """Generates traceable, formula-backed Master Research Database workbooks."""

    @classmethod
    def generate(
        cls,
        sheets_data: Dict[str, Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        sheets_data schema:
        {
            "SheetName": {
                "headers": ["Col1", "Col2", "Events", "Total"],
                "rows": [["Study A", 2020, 15, 100], ["Study B", 2022, 22, 120]],
                "has_summary_row": True,
                "numeric_cols": [3, 4]  # 1-based index
            }
        }
        """
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default blank sheet

        # Styles
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        summary_font = Font(name="Arial", size=10, bold=True, color="0F172A")
        summary_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
        cell_font = Font(name="Arial", size=9.5)
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for sheet_name, s_data in sheets_data.items():
            ws = wb.create_sheet(title=sheet_name)
            ws.freeze_panes = "A2"

            headers = s_data.get("headers", [])
            rows = s_data.get("rows", [])
            has_summary = s_data.get("has_summary_row", False)
            numeric_cols = s_data.get("numeric_cols", [])

            # Write Headers
            for col_idx, h_text in enumerate(headers, start=1):
                c = ws.cell(row=1, column=col_idx, value=h_text)
                c.font = header_font
                c.fill = header_fill
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = border_thin

            ws.row_dimensions[1].height = 26

            # Write Data Rows
            for r_idx, row_vals in enumerate(rows, start=2):
                for c_idx, val in enumerate(row_vals, start=1):
                    c = ws.cell(row=r_idx, column=c_idx, value=val)
                    c.font = cell_font
                    c.border = border_thin
                    if c_idx in numeric_cols:
                        c.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        c.alignment = Alignment(horizontal="left", vertical="center")
                ws.row_dimensions[r_idx].height = 20

            # Optional Dynamic Formula Summary Row
            if has_summary and len(rows) > 0:
                summary_row_idx = len(rows) + 2
                ws.cell(row=summary_row_idx, column=1, value="Total / Pooled Summary").font = summary_font
                ws.cell(row=summary_row_idx, column=1).fill = summary_fill
                ws.cell(row=summary_row_idx, column=1).border = border_thin

                for c_idx in range(2, len(headers) + 1):
                    col_letter = get_column_letter(c_idx)
                    cell = ws.cell(row=summary_row_idx, column=c_idx)
                    cell.font = summary_font
                    cell.fill = summary_fill
                    cell.border = border_thin

                    if c_idx in numeric_cols:
                        # Add live dynamic Excel formula =SUM(col2:colN)
                        cell.value = f"=SUM({col_letter}2:{col_letter}{summary_row_idx-1})"
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.value = ""

                ws.row_dimensions[summary_row_idx].height = 22

            # Auto-fit column widths
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        wb.save(output_path)
        return output_path

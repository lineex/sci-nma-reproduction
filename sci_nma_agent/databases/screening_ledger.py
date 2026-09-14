"""
Two-Stage Unified Screening Ledger & Flow Reconciliation Engine.
Generates publication-grade Master Screening Workbooks (Excel) with drop-down data validations
and reconciles Title/Abstract and Full-Text screening decisions with PRISMA Flow Conservation (L ≡ 0).
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

from .corpus_repository import CanonicalRecord
from ..core.gate1_search_flow import Gate1SearchFlow


class ScreeningLedger:
    """
    Manages the two-stage screening process (Title/Abstract -> Full-Text) and validates PRISMA flow closure.
    """

    STANDARD_FULLTEXT_EXCLUDE_REASONS = [
        "Wrong Population",
        "Wrong Intervention",
        "No Control Group",
        "Ineligible Study Design",
        "Duplicate Cohort"
    ]

    STANDARD_TIAB_EXCLUDE_REASONS = [
        "Irrelevant topic / Non-clinical",
        "Animal or in vitro study",
        "Narrative review / Editorial / Letter",
        "Pediatric or out-of-scope population",
        "Case report or case series (<5 cases)"
    ]

    @classmethod
    def generate_screening_workbook(
        cls,
        unique_records: List[CanonicalRecord],
        output_xlsx_path: str
    ) -> str:
        """
        Export Master Unified Screening Workbook with pre-configured dropdowns and two-stage columns.
        """
        os.makedirs(os.path.dirname(output_xlsx_path), exist_ok=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Master Screening Table"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        tiab_header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        ft_header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        bold_font = Font(name="Arial", size=9, bold=True)
        norm_font = Font(name="Arial", size=9)
        thin_border = Border(
            left=Side(style="thin", color="E0E0E0"),
            right=Side(style="thin", color="E0E0E0"),
            top=Side(style="thin", color="E0E0E0"),
            bottom=Side(style="thin", color="E0E0E0")
        )

        # Header Columns
        headers = [
            ("Master ID", header_fill, 14),
            ("Sources", header_fill, 25),
            ("PMID", header_fill, 12),
            ("Embase PUI", header_fill, 14),
            ("WoS UID", header_fill, 22),
            ("Cochrane ID", header_fill, 16),
            ("DOI", header_fill, 25),
            ("Title", header_fill, 45),
            ("First Author", header_fill, 16),
            ("Journal", header_fill, 20),
            ("Year", header_fill, 8),
            ("Abstract", header_fill, 50),
            # Stage 1: TiAb Screening
            ("TiAb Decision (INCLUDE/EXCLUDE)", tiab_header_fill, 22),
            ("TiAb Exclude Reason", tiab_header_fill, 28),
            # Stage 2: Full-Text Screening
            ("Full-Text Sought (YES/NO)", ft_header_fill, 16),
            ("Full-Text Retrieved (YES/NO)", ft_header_fill, 18),
            ("Full-Text Decision (INCLUDE/EXCLUDE)", ft_header_fill, 24),
            ("Full-Text Exclude Reason (Standard Reason)", ft_header_fill, 32),
            ("Study ID (for Meta-Analysis)", ft_header_fill, 20),
            ("Reviewer Notes", header_fill, 25)
        ]

        ws.row_dimensions[1].height = 28
        for col_idx, (h_title, fill_style, width) in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=h_title)
            cell.font = header_font
            cell.fill = fill_style
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        # Data rows
        for row_idx, rec in enumerate(unique_records, start=2):
            ws.row_dimensions[row_idx].height = 20

            pmid = rec.db_ids.get("pubmed_pmid", "") or ""
            pui = rec.db_ids.get("embase_pui", "") or ""
            wos = rec.db_ids.get("wos_uid", "") or ""
            cochrane = rec.db_ids.get("cochrane_id", "") or ""
            first_author = rec.authors[0] if rec.authors else ""

            row_data = [
                rec.master_id,
                "; ".join(rec.sources),
                str(pmid),
                str(pui),
                str(wos),
                str(cochrane),
                rec.doi or "",
                rec.title,
                first_author,
                rec.journal,
                rec.year or "",
                rec.abstract,
                "",  # TiAb Decision
                "",  # TiAb Exclude Reason
                "",  # Full-Text Sought
                "",  # Full-Text Retrieved
                "",  # Full-Text Decision
                "",  # Full-Text Exclude Reason
                "",  # Study ID
                ""   # Notes
            ]

            for c_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=c_idx, value=val)
                cell.font = bold_font if c_idx == 1 else norm_font
                cell.border = thin_border
                if c_idx in (1, 3, 4, 11):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif c_idx in (8, 12):
                    cell.alignment = Alignment(vertical="center", wrap_text=False)
                else:
                    cell.alignment = Alignment(vertical="center")

        # Add Data Validation Dropdowns
        max_row = len(unique_records) + 1
        if max_row >= 2:
            # 1. TiAb Decision (Col M / 13)
            dv_tiab = DataValidation(type="list", formula1='"INCLUDE,EXCLUDE"', allow_blank=True)
            ws.add_data_validation(dv_tiab)
            dv_tiab.add(f"M2:M{max_row}")

            # 2. TiAb Exclude Reasons (Col N / 14)
            tiab_reasons_str = f'"{",".join(cls.STANDARD_TIAB_EXCLUDE_REASONS)}"'
            dv_tiab_reasons = DataValidation(type="list", formula1=tiab_reasons_str, allow_blank=True)
            ws.add_data_validation(dv_tiab_reasons)
            dv_tiab_reasons.add(f"N2:N{max_row}")

            # 3. Full-Text Sought (Col O / 15)
            dv_sought = DataValidation(type="list", formula1='"YES,NO"', allow_blank=True)
            ws.add_data_validation(dv_sought)
            dv_sought.add(f"O2:O{max_row}")

            # 4. Full-Text Retrieved (Col P / 16)
            dv_ret = DataValidation(type="list", formula1='"YES,NO"', allow_blank=True)
            ws.add_data_validation(dv_ret)
            dv_ret.add(f"P2:P{max_row}")

            # 5. Full-Text Decision (Col Q / 17)
            dv_ft = DataValidation(type="list", formula1='"INCLUDE,EXCLUDE"', allow_blank=True)
            ws.add_data_validation(dv_ft)
            dv_ft.add(f"Q2:Q{max_row}")

            # 6. Full-Text Standard Exclude Reasons (Col R / 18)
            ft_reasons_str = f'"{",".join(cls.STANDARD_FULLTEXT_EXCLUDE_REASONS)}"'
            dv_ft_reasons = DataValidation(type="list", formula1=ft_reasons_str, allow_blank=True)
            ws.add_data_validation(dv_ft_reasons)
            dv_ft_reasons.add(f"R2:R{max_row}")

        wb.save(output_xlsx_path)
        return output_xlsx_path

    @classmethod
    def reconcile_screening_decisions(
        cls,
        screening_xlsx_path: str,
        prisma_flow_path: str
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Read back decisions from the master screening workbook, compute exact flow metrics,
        update prisma_flow.json, and verify Gate 1 Flow Conservation (L ≡ 0).
        """
        if not os.path.exists(screening_xlsx_path):
            return False, {}, [f"Screening workbook not found at {screening_xlsx_path}"]

        wb = openpyxl.load_workbook(screening_xlsx_path, data_only=True)
        ws = wb.active

        total_screened = 0
        tiab_excluded = 0
        tiab_reasons: Dict[str, int] = {}
        reports_sought = 0
        reports_not_retrieved = 0
        reports_assessed = 0
        fulltext_excluded = 0
        fulltext_reasons: Dict[str, int] = {r: 0 for r in cls.STANDARD_FULLTEXT_EXCLUDE_REASONS}
        studies_included = 0
        included_studies: List[Dict[str, Any]] = []

        for row in range(2, ws.max_row + 1):
            master_id = ws.cell(row=row, column=1).value
            if not master_id:
                continue

            total_screened += 1
            tiab_dec = str(ws.cell(row=row, column=13).value or "").strip().upper()
            tiab_reason = str(ws.cell(row=row, column=14).value or "").strip()
            sought_val = str(ws.cell(row=row, column=15).value or "").strip().upper()
            ret_val = str(ws.cell(row=row, column=16).value or "").strip().upper()
            ft_dec = str(ws.cell(row=row, column=17).value or "").strip().upper()
            ft_reason = str(ws.cell(row=row, column=18).value or "").strip()
            study_id = str(ws.cell(row=row, column=19).value or "").strip()
            title = str(ws.cell(row=row, column=8).value or "").strip()
            doi = str(ws.cell(row=row, column=7).value or "").strip()

            # Stage 1: TiAb Evaluation
            if tiab_dec == "EXCLUDE":
                tiab_excluded += 1
                if tiab_reason:
                    tiab_reasons[tiab_reason] = tiab_reasons.get(tiab_reason, 0) + 1
            else:
                # Included in TiAb -> Full-Text Sought
                reports_sought += 1
                # Stage 2: Retrieval & Full-Text Assessment
                if ret_val == "NO":
                    reports_not_retrieved += 1
                else:
                    reports_assessed += 1
                    if ft_dec == "EXCLUDE":
                        fulltext_excluded += 1
                        matched_reason = "Ineligible Study Design"
                        for std_r in cls.STANDARD_FULLTEXT_EXCLUDE_REASONS:
                            if std_r.lower() in ft_reason.lower():
                                matched_reason = std_r
                                break
                        fulltext_reasons[matched_reason] += 1
                    elif ft_dec == "INCLUDE":
                        studies_included += 1
                        included_studies.append({
                            "master_id": master_id,
                            "study_id": study_id or f"Study_{master_id}",
                            "title": title,
                            "doi": doi
                        })

        # Load existing flow to preserve total_identified and duplicates_removed
        with open(prisma_flow_path, "r", encoding="utf-8") as f:
            flow_data = json.load(f)

        flow_data["records_screened"] = total_screened
        flow_data["screening_excluded"] = tiab_excluded
        flow_data["screening_exclusion_reasons"] = tiab_reasons
        flow_data["reports_sought"] = reports_sought
        flow_data["reports_not_retrieved"] = reports_not_retrieved
        flow_data["reports_assessed"] = reports_assessed
        flow_data["fulltext_excluded"] = fulltext_excluded
        flow_data["fulltext_exclusion_reasons"] = fulltext_reasons
        flow_data["studies_included"] = studies_included

        # Validate with Gate 1
        passed, errors, metrics = Gate1SearchFlow.validate_prisma_flow(flow_data)

        # Save updated flow
        with open(prisma_flow_path, "w", encoding="utf-8") as f:
            json.dump(flow_data, f, indent=2)

        return passed, {
            "metrics": metrics,
            "included_studies_count": len(included_studies),
            "included_studies": included_studies
        }, errors

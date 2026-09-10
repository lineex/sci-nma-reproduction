"""
Submission-Ready Word Manuscript Generator.
Builds complete academic manuscripts with injected XML <w:tblHeader/> and <w:cantSplit/>
to prevent cross-page table splits, adhering to Lancet and Critical Care author guidelines.
"""

import os
from typing import Dict, Any, List
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from ..core.gate5_office_audit import Gate5OfficeAudit


class DocxManuscriptGenerator:
    """Generates complete submission-ready Word manuscripts with engineered tables."""

    @classmethod
    def generate(
        cls,
        manuscript_data: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        Generate Word .docx manuscript.
        manuscript_data schema:
        - title: str
        - running_title: str
        - authors: List[str]
        - affiliations: List[str]
        - abstract: Dict[str, str] (Background, Methods, Results, Conclusions)
        - sections: List[Dict[str, Any]] (heading, paragraphs, optional table)
        """
        doc = Document()

        # Page Setup (Standard Letter, 1 inch margins)
        for sec in doc.sections:
            sec.top_margin = Inches(1.0)
            sec.bottom_margin = Inches(1.0)
            sec.left_margin = Inches(1.0)
            sec.right_margin = Inches(1.0)

        # 1. Title
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(12)
        title_run = title_p.add_run(manuscript_data.get("title", "Clinical Research Manuscript"))
        title_run.font.name = "Arial"
        title_run.font.size = Pt(18)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(15, 23, 42)

        # 2. Authors
        authors = manuscript_data.get("authors", ["Author One, MD", "Author Two, PhD"])
        auth_p = doc.add_paragraph()
        auth_p.paragraph_format.space_after = Pt(6)
        auth_run = auth_p.add_run(", ".join(authors))
        auth_run.font.name = "Arial"
        auth_run.font.size = Pt(11)
        auth_run.font.bold = True

        # Affiliations
        affils = manuscript_data.get("affiliations", ["Department of Intensive Care Medicine"])
        for aff in affils:
            aff_p = doc.add_paragraph()
            aff_p.paragraph_format.space_after = Pt(3)
            aff_run = aff_p.add_run(aff)
            aff_run.font.name = "Arial"
            aff_run.font.size = Pt(9.5)
            aff_run.font.italic = True
            aff_run.font.color.rgb = RGBColor(100, 116, 139)

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

        # 3. Structured Abstract
        doc.add_heading("Abstract", level=1)
        abstract = manuscript_data.get("abstract", {})
        for heading, text in abstract.items():
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            h_run = p.add_run(f"{heading}: ")
            h_run.font.name = "Arial"
            h_run.font.size = Pt(10.5)
            h_run.font.bold = True
            t_run = p.add_run(text)
            t_run.font.name = "Arial"
            t_run.font.size = Pt(10.5)

        doc.add_page_break()

        # 4. Main Body Sections & Tables
        sections = manuscript_data.get("sections", [])
        for sec in sections:
            heading = sec.get("heading")
            if heading:
                doc.add_heading(heading, level=1)

            paragraphs = sec.get("paragraphs", [])
            for par in paragraphs:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(8)
                p.paragraph_format.line_spacing = 1.25
                run = p.add_run(par)
                run.font.name = "Arial"
                run.font.size = Pt(11)

            # Optional Table in section
            table_info = sec.get("table")
            if table_info:
                t_title = table_info.get("title", "Table 1")
                t_p = doc.add_paragraph()
                t_p.paragraph_format.space_before = Pt(12)
                t_p.paragraph_format.space_after = Pt(4)
                t_run = t_p.add_run(t_title)
                t_run.font.name = "Arial"
                t_run.font.size = Pt(10.5)
                t_run.font.bold = True

                headers = table_info.get("headers", [])
                rows = table_info.get("rows", [])

                table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
                table.alignment = WD_TABLE_ALIGNMENT.CENTER

                # Set header cells
                for col_idx, h_text in enumerate(headers):
                    cell = table.cell(0, col_idx)
                    cell.text = h_text
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.name = "Arial"
                            r.font.size = Pt(9.5)
                            r.font.bold = True

                # Set body cells
                for r_idx, row_data in enumerate(rows):
                    for c_idx, val in enumerate(row_data):
                        cell = table.cell(r_idx + 1, c_idx)
                        cell.text = str(val)
                        for p in cell.paragraphs:
                            for r in p.runs:
                                r.font.name = "Arial"
                                r.font.size = Pt(9)

                # CRITICAL: Apply Gate 5 XML table engineering
                Gate5OfficeAudit.apply_table_engineering_rules(table)

                # Footnote
                footnote = table_info.get("footnote")
                if footnote:
                    fn_p = doc.add_paragraph()
                    fn_p.paragraph_format.space_before = Pt(4)
                    fn_p.paragraph_format.space_after = Pt(12)
                    fn_run = fn_p.add_run(footnote)
                    fn_run.font.name = "Arial"
                    fn_run.font.size = Pt(8.5)
                    fn_run.font.italic = True
                    fn_run.font.color.rgb = RGBColor(100, 116, 139)

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        doc.save(output_path)
        return output_path

"""
Unit tests for ScreeningLedger and PRISMA Flow Decision Reconciliation.
"""

import os
import json
from contextlib import nullcontext
import openpyxl
import pytest

from sci_nma_agent.databases.corpus_repository import CanonicalRecord
from sci_nma_agent.databases.screening_ledger import ScreeningLedger
from sci_nma_agent.core.gate1_search_flow import Gate1SearchFlow


def test_screening_workbook_generation_and_reconciliation(tmp_path):
    with nullcontext(str(tmp_path)) as tmpdir:
        # Create mock unique records
        records = [
            CanonicalRecord(
                master_id="REC-00001",
                sources=["PubMed", "Embase"],
                db_ids={"pubmed_pmid": "35123456", "embase_pui": "2019887701"},
                doi="10.1056/nejmoa2112345",
                title="Vasopressin in Septic Shock",
                authors=["Gordon, AC"],
                journal="NEJM",
                year=2022,
                abstract="RCT of 400 septic shock patients."
            ),
            CanonicalRecord(
                master_id="REC-00002",
                sources=["PubMed"],
                db_ids={"pubmed_pmid": "35654321"},
                doi="10.1016/s0140-6736(23)00555-5",
                title="Corticosteroids in Severe Pneumonia",
                authors=["Dequin, PF"],
                journal="Lancet",
                year=2023,
                abstract="RCT of 800 patients."
            ),
            CanonicalRecord(
                master_id="REC-00003",
                sources=["Embase", "Web of Science"],
                db_ids={"wos_uid": "WOS:000678901200001"},
                doi="10.1097/ccm.0000000000004999",
                title="Angiotensin II in Septic Shock",
                authors=["Khanna, A"],
                journal="Crit Care Med",
                year=2021,
                abstract="Study of synthetic angiotensin II."
            ),
            CanonicalRecord(
                master_id="REC-00004",
                sources=["Web of Science"],
                db_ids={"wos_uid": "WOS:000554433200001"},
                doi="10.1016/j.chest.2020.02.066",
                title="Vitamin C in Sepsis",
                authors=["Marik, PE"],
                journal="Chest",
                year=2020,
                abstract="Observational cohort of 100 patients."
            )
        ]

        # 1. Generate workbook
        xlsx_path = os.path.join(tmpdir, "master_screening_table.xlsx")
        ScreeningLedger.generate_screening_workbook(records, xlsx_path)
        assert os.path.exists(xlsx_path)

        # 2. Create baseline prisma_flow_data.json
        # Total identified = 6, Duplicates = 2, Screened = 4
        flow_path = os.path.join(tmpdir, "prisma_flow_data.json")
        flow_initial = {
            "databases": {"PubMed": 2, "Embase": 2, "Web of Science": 2, "Cochrane Library": 0},
            "registries_or_citations": 0,
            "total_identified": 6,
            "duplicates_removed": 2,
            "records_screened": 4,
            "screening_excluded": 0,
            "reports_sought": 4,
            "reports_not_retrieved": 0,
            "reports_assessed": 4,
            "fulltext_excluded": 0,
            "fulltext_exclusion_reasons": {r: 0 for r in ScreeningLedger.STANDARD_FULLTEXT_EXCLUDE_REASONS},
            "studies_included": 0
        }
        with open(flow_path, "w", encoding="utf-8") as f:
            json.dump(flow_initial, f, indent=2)

        # 3. Simulate Reviewer decisions in Excel
        # REC-00001: INCLUDE in TiAb, RETRIEVED, INCLUDE in FullText -> Included
        # REC-00002: INCLUDE in TiAb, RETRIEVED, INCLUDE in FullText -> Included
        # REC-00003: INCLUDE in TiAb, RETRIEVED, EXCLUDE in FullText (Wrong Population) -> Excluded FT
        # REC-00004: EXCLUDE in TiAb (Observational/Review) -> Excluded TiAb
        wb = openpyxl.load_workbook(xlsx_path)
        ws = wb.active

        # REC-00001 (Row 2)
        ws.cell(row=2, column=13, value="INCLUDE")
        ws.cell(row=2, column=15, value="YES")
        ws.cell(row=2, column=16, value="YES")
        ws.cell(row=2, column=17, value="INCLUDE")
        ws.cell(row=2, column=19, value="Gordon 2022")

        # REC-00002 (Row 3)
        ws.cell(row=3, column=13, value="INCLUDE")
        ws.cell(row=3, column=15, value="YES")
        ws.cell(row=3, column=16, value="YES")
        ws.cell(row=3, column=17, value="INCLUDE")
        ws.cell(row=3, column=19, value="Dequin 2023")

        # REC-00003 (Row 4)
        ws.cell(row=4, column=13, value="INCLUDE")
        ws.cell(row=4, column=15, value="YES")
        ws.cell(row=4, column=16, value="YES")
        ws.cell(row=4, column=17, value="EXCLUDE")
        ws.cell(row=4, column=18, value="Wrong Population")

        # REC-00004 (Row 5)
        ws.cell(row=5, column=13, value="EXCLUDE")
        ws.cell(row=5, column=14, value="Animal or in vitro study")

        wb.save(xlsx_path)

        # 4. Reconcile decisions
        passed, res, errors = ScreeningLedger.reconcile_screening_decisions(xlsx_path, flow_path)
        assert passed is True
        assert len(errors) == 0

        metrics = res["metrics"]
        # Screened = 4
        # TiAb Excluded = 1 (REC-00004)
        # Reports Sought = 3 (REC-00001, 2, 3)
        # Reports Not Retrieved = 0
        # Reports Assessed = 3
        # FullText Excluded = 1 (REC-00003: Wrong Population)
        # Studies Included = 2 (REC-00001, REC-00002)
        # Global Flow Loss L: 6 - (2 dups + 1 tiab + 0 not_ret + 1 ft + 2 incl) = 6 - 6 = 0
        assert metrics["flow_loss"] == 0
        assert metrics["records_screened"] == 4
        assert metrics["reports_sought"] == 3
        assert metrics["reports_assessed"] == 3
        assert metrics["studies_included"] == 2
        assert len(res["included_studies"]) == 2
        assert res["included_studies"][0]["study_id"] == "Gordon 2022"
        assert res["included_studies"][1]["study_id"] == "Dequin 2023"

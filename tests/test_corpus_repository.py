"""
Unit tests for CorpusRepository, FormatParsers, ProvenanceDeduplicator, and SearchAuditLedger.
"""

import os
from contextlib import nullcontext
import pytest

from sci_nma_agent.databases.corpus_repository import CanonicalRecord, FormatParsers, CorpusRepository
from sci_nma_agent.databases.deduplicator import ProvenanceDeduplicator
from sci_nma_agent.databases.audit_ledger import SearchAuditLedger


def test_doi_normalization():
    assert FormatParsers.normalize_doi("https://doi.org/10.1056/NEJMoa2112345") == "10.1056/nejmoa2112345"
    assert FormatParsers.normalize_doi("doi: 10.1016/j.jcrc.2023.154321.") == "10.1016/j.jcrc.2023.154321"
    assert FormatParsers.normalize_doi(None) is None


def test_format_parsers_and_corpus_scan(tmp_path):
    with nullcontext(str(tmp_path)) as tmpdir:
        pubmed_dir = os.path.join(tmpdir, "pubmed")
        embase_dir = os.path.join(tmpdir, "embase")
        wos_dir = os.path.join(tmpdir, "wos")
        cochrane_dir = os.path.join(tmpdir, "cochrane")

        for d in (pubmed_dir, embase_dir, wos_dir, cochrane_dir):
            os.makedirs(d, exist_ok=True)

        # 1. Mock PubMed NBIB
        nbib_content = """PMID- 35123456
TI  - Vasopressin versus Norepinephrine in Septic Shock Trial
AB  - Randomized controlled trial of 400 patients with septic shock.
AU  - Gordon, AC
AU  - Mason, AJ
TA  - N Engl J Med
DP  - 2022
LID - 10.1056/NEJMoa2112345 [doi]
MH  - Shock, Septic/drug therapy
MH  - Vasopressins/therapeutic use

PMID- 35654321
TI  - Corticosteroids in Severe Community-Acquired Pneumonia
AB  - Hydrocortisone improved 28-day mortality in ICU patients.
AU  - Dequin, PF
TA  - Lancet
DP  - 2023
LID - 10.1016/S0140-6736(23)00555-5 [doi]
"""
        with open(os.path.join(pubmed_dir, "pubmed_hits.nbib"), "w", encoding="utf-8") as f:
            f.write(nbib_content)

        # 2. Mock Embase RIS (contains duplicate of PMID 35123456 plus a unique one)
        ris_content = """TY  - JOUR
TI  - Vasopressin versus Norepinephrine in Septic Shock Trial
AB  - Double blind trial of early vasopressin infusion.
AU  - Gordon, A.C.
JO  - New England Journal of Medicine
PY  - 2022
DO  - 10.1056/nejmoa2112345
ID  - 2019887701
C1  - PMID: 35123456
ER  - 

TY  - JOUR
TI  - Angiotensin II for refractory septic shock: a randomized trial
AB  - ATHOS-3 trial evaluated synthetic human angiotensin II.
AU  - Khanna, A.
JO  - Crit Care Med
PY  - 2021
DO  - 10.1097/CCM.0000000000004999
ID  - 2019887702
ER  - 
"""
        with open(os.path.join(embase_dir, "embase_batch1.ris"), "w", encoding="utf-8") as f:
            f.write(ris_content)

        # 3. Mock WoS plain text
        wos_content = """PT J
TI Angiotensin II for refractory septic shock: a randomized trial
AU Khanna, A; Leite, HP
SO CRITICAL CARE MEDICINE
PY 2021
DI 10.1097/CCM.0000000000004999
UT WOS:000678901200001
ER

PT J
TI Vitamin C and Thiamine in Sepsis
AU Marik, PE
SO CHEST
PY 2020
DI 10.1016/j.chest.2020.02.066
UT WOS:000554433200001
ER
"""
        with open(os.path.join(wos_dir, "wos_core.txt"), "w", encoding="utf-8") as f:
            f.write(wos_content)

        # Ingest
        ingest_res = CorpusRepository.scan_and_ingest(tmpdir)
        assert ingest_res["total_raw_records"] == 6  # 2 + 2 + 2
        assert ingest_res["databases"]["PubMed"]["record_count"] == 2
        assert ingest_res["databases"]["Embase"]["record_count"] == 2
        assert ingest_res["databases"]["Web of Science"]["record_count"] == 2

        # Deduplicate with Provenance Retention
        unique_recs, metrics, audit_log = ProvenanceDeduplicator.deduplicate(ingest_res["records"])
        # Total 6 raw records -> Gordon 2022 is in PubMed & Embase (1 dup)
        # Khanna 2021 is in Embase & WoS (1 dup)
        # Unique records should be 4: Gordon 2022, Dequin 2023, Khanna 2021, Marik 2020
        assert metrics["total_raw_records"] == 6
        assert metrics["unique_records"] == 4
        assert metrics["duplicates_removed"] == 2
        assert len(unique_recs) == 4

        # Check Provenance Retention for Gordon 2022
        gordon_rec = next(r for r in unique_recs if "Gordon" in str(r.authors))
        assert "PubMed" in gordon_rec.sources
        assert "Embase" in gordon_rec.sources
        assert gordon_rec.db_ids.get("pubmed_pmid") == "35123456"
        assert gordon_rec.db_ids.get("embase_pui") == "2019887701"

        # Check Provenance Retention for Khanna 2021
        khanna_rec = next(r for r in unique_recs if "Khanna" in str(r.authors))
        assert "Embase" in khanna_rec.sources
        assert "Web of Science" in khanna_rec.sources
        assert khanna_rec.db_ids.get("wos_uid") == "WOS:000678901200001"

        # Check SearchAuditLedger
        ledger = SearchAuditLedger.compile_audit_ledger(
            search_queries={"PubMed": "septic shock", "Embase": "septic shock", "Web of Science": "septic shock"},
            db_hit_counts={"PubMed": 2, "Embase": 2, "Web of Science": 2, "Cochrane Library": 0},
            ingestion_metadata=ingest_res,
            dedup_metrics=metrics
        )
        assert ledger["conservation_status"] == "PASSED (L ≡ 0)"
        assert ledger["total_identified"] == 6
        assert ledger["duplicates_removed"] == 2
        assert ledger["records_to_screen"] == 4

        # Test Excel export
        xlsx_out = os.path.join(tmpdir, "Search_Audit_Table.xlsx")
        SearchAuditLedger.export_excel_audit_table(ledger, xlsx_out)
        assert os.path.exists(xlsx_out)
        assert os.path.getsize(xlsx_out) > 3000

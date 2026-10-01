
import csv
import json
from pathlib import Path

from sci_nma_agent.workflow.fulltext_acquisition import (
    ScanSciPDFAdapter,
    build_acquisition_queue,
    compare_identity,
    normalize_doi,
    resolve_doi,
    update_queue_with_download,
    write_discrepancy_table,
)


class _Article:
    def __init__(self, pmid, doi, title, year):
        self.pmid = pmid
        self.doi = doi
        self.title = title
        self.year = year


class _Fetcher:
    def article_by_pmid(self, pmid):
        assert pmid == "12345678"
        return _Article(pmid, "10.1000/ABC", "Exact Report", "2022")

    def pmids_for_query(self, query, retmax=10):
        return []


def test_normalize_doi_and_metapub_resolution():
    assert normalize_doi("https://doi.org/10.1000/ABC.") == "10.1000/ABC"
    result = resolve_doi(
        {"pmid": "PMID: 12345678", "title": "Exact Report", "year": "2022"},
        fetcher_factory=_Fetcher,
    )
    assert result["status"] == "resolved"
    assert result["doi"] == "10.1000/ABC"
    assert result["source"] == "metapub_pmid"


def test_existing_doi_is_not_relooked_up():
    result = resolve_doi({"doi": "10.1000/existing"}, fetcher_factory=lambda: (_ for _ in ()).throw(AssertionError()))
    assert result["status"] == "present"
    assert result["doi"] == "10.1000/existing"


def test_acquisition_queue_retains_missing_doi_as_distinct_state():
    queue = build_acquisition_queue(
        {"records": [
            {"study_id": "S1", "report_id": "R1", "pmid": "12345678"},
            {"study_id": "S1", "report_id": "R2", "title": "Unknown report"},
        ]},
        fetcher_factory=_Fetcher,
        source_path="screening/full_text_retrieval_manifest.json",
    )
    assert queue["records"][0]["doi"] == "10.1000/ABC"
    assert queue["records"][0]["download"]["status"] == "planned"
    assert queue["records"][1]["doi_resolution"]["status"] == "not_found"
    assert queue["records"][1]["download"]["status"] == "manual_doi_or_identifier_required"
    assert queue["defaults"]["paywall_route"] == "institutional_CARSI_user_action_then_resume"


def test_scan_sci_adapter_reports_missing_provider(tmp_path):
    adapter = ScanSciPDFAdapter(executable="definitely-not-installed-scansci-pdf")
    result = adapter.download("10.1000/test", tmp_path)
    assert result.status == "provider_unavailable"
    assert result.route == "scansci_pdf"


def test_compare_identity_and_discrepancy_table(tmp_path):
    rows = compare_identity(
        {"doi": "10.1000/abc", "title": "Exact Report", "year": "2022"},
        {"DOI": "10.1000/wrong", "title": "Other Report", "date": "2021"},
    )
    assert {row["field"] for row in rows} == {"doi", "title", "year"}
    path = tmp_path / "verification" / "zotero_metadata_discrepancies.csv"
    digest = write_discrepancy_table(
        [{"study_id": "S1", "report_id": "R1", "item_key": "ITEM1", **row} for row in rows],
        path,
    )
    assert path.exists() and len(digest) == 64
    with path.open(encoding="utf-8-sig", newline="") as handle:
        values = list(csv.DictReader(handle))
    assert values[0]["field"] == "doi"
    assert values[0]["status"] == "open"


def test_update_queue_records_carsi_checkpoint():
    queue = {"records": [{"study_id": "S1", "report_id": "R1", "download": {}, "institutional_access": {}, "route_attempts": []}]}
    result = ScanSciPDFAdapter.__new__(ScanSciPDFAdapter)
    from sci_nma_agent.workflow.fulltext_acquisition import ScanSciResult
    update_queue_with_download(
        queue,
        ("S1", "R1"),
        ScanSciResult("carsi_user_action_required", "scansci_pdf", ["scansci-pdf", "get", "10.1000/test"], error="login required"),
    )
    record = queue["records"][0]
    assert record["institutional_access"]["status"] == "user_action_required"
    assert record["download"]["status"] == "carsi_user_action_required"

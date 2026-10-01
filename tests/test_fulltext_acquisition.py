
import csv
import json
from pathlib import Path
from types import SimpleNamespace

from sci_nma_agent.workflow.fulltext_acquisition import (
    ScanSciPDFAdapter,
    build_acquisition_queue,
    compare_identity,
    normalize_doi,
    resolve_doi,
    retrieval_manifest_base_hash,
    update_queue_with_download,
    write_discrepancy_table,
    write_json,
)
from sci_nma_agent.workflow.protocol_validation import (
    retrieval_manifest_base_hash as validated_retrieval_manifest_base_hash,
    validate_retrieval_acquisition_queue_binding,
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


def test_metapub_pmid_result_requires_identity_match():
    class WrongFetcher:
        def article_by_pmid(self, pmid):
            return _Article("99999999", "10.1000/wrong", "Different report", "2021")

        def pmids_for_query(self, query, retmax=10):
            return []

    result = resolve_doi(
        {"pmid": "12345678", "title": "Exact Report", "year": "2022"},
        fetcher_factory=WrongFetcher,
    )
    assert result["status"] == "not_found"
    assert result["attempts"][0]["status"] == "identity_mismatch"


def test_metapub_title_candidate_without_expected_year_is_rejected():
    class NoYearFetcher:
        def pmids_for_query(self, query, retmax=10):
            return ["123"]

        def article_by_pmid(self, pmid):
            return _Article("123", "10.1000/no-year", "Exact Report", "")

    result = resolve_doi(
        {"title": "Exact Report", "year": "2022"},
        fetcher_factory=NoYearFetcher,
    )
    assert result["status"] == "not_found"


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


def test_acquisition_queue_binds_to_manifest_base_hash():
    manifest = {
        "schema_version": 1,
        "records": [{"study_id": "S1", "report_id": "R1"}],
        "acquisition_queue_path": "screening/full_text_acquisition_queue.json",
        "acquisition_queue_sha256": "a" * 64,
    }
    queue = build_acquisition_queue(manifest, fetcher_factory=_Fetcher)
    assert queue["source_manifest_sha256"] == retrieval_manifest_base_hash(manifest)
    changed = dict(manifest)
    changed["acquisition_queue_sha256"] = "b" * 64
    assert retrieval_manifest_base_hash(changed) == queue["source_manifest_sha256"]


def test_retrieval_manifest_queue_binding_is_hash_and_scope_checked(tmp_path):
    manifest = {
        "schema_version": 1,
        "records": [{
            "study_id": "S1",
            "report_id": "R1",
            "acquisition_queue_status": {"download": {"status": "succeeded"}},
        }],
    }
    queue = build_acquisition_queue(manifest)
    assert queue["source_manifest_sha256"] == validated_retrieval_manifest_base_hash(manifest)
    queue_path = tmp_path / "screening" / "full_text_acquisition_queue.json"
    write_json(queue_path, queue)
    manifest["acquisition_queue_path"] = "screening/full_text_acquisition_queue.json"
    manifest["acquisition_queue_sha256"] = __import__("hashlib").sha256(queue_path.read_bytes()).hexdigest()
    assert validate_retrieval_acquisition_queue_binding(manifest, tmp_path) == []
    queue["records"].append({"study_id": "S9", "report_id": "R9"})
    write_json(queue_path, queue)
    assert validate_retrieval_acquisition_queue_binding(manifest, tmp_path)


def test_scan_sci_adapter_reports_missing_provider(tmp_path):
    adapter = ScanSciPDFAdapter(executable="definitely-not-installed-scansci-pdf")
    result = adapter.download("10.1000/test", tmp_path)
    assert result.status == "provider_unavailable"
    assert result.route == "scansci_pdf"


def test_scan_sci_rejects_nonzero_exit_even_if_pdf_appears(tmp_path, monkeypatch):
    executable = tmp_path / "scansci-pdf"
    executable.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr("sci_nma_agent.workflow.fulltext_acquisition.shutil.which", lambda _: str(executable))

    def run(command, cwd, capture_output, text, timeout, check):
        Path(cwd, "unexpected.pdf").write_bytes(b"%PDF-1.4 fixture")
        return SimpleNamespace(returncode=2, stdout="failed", stderr="bad")

    monkeypatch.setattr("sci_nma_agent.workflow.fulltext_acquisition.subprocess.run", run)
    result = ScanSciPDFAdapter().download("10.1000/test", tmp_path)
    assert result.status == "provider_error"
    assert result.returncode == 2


def test_compare_identity_normalizes_doi_case_and_date_year():
    assert compare_identity(
        {"doi": "10.1000/ABC", "year": "2022-05-01"},
        {"DOI": "10.1000/abc", "date": "Spring 2022"},
    ) == []


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

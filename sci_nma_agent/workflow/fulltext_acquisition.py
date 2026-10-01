"""Auditable post-screening full-text acquisition orchestration.

The module keeps four questions separate:

* is a DOI present in the screened record;
* was a DOI lookup attempted and what did it return;
* was a PDF acquired through the configured ScanSci PDF connector; and
* does the Zotero record read back with the approved report identity.

The DOI resolver is optional (``metapub``).  PDF retrieval and Zotero writes
are connector boundaries: this project records commands, responses, hashes,
and user-action checkpoints rather than embedding publisher credentials.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_doi(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi\s*:\s*", "", text, flags=re.I).strip()
    text = text.rstrip(".,;)]")
    return text if DOI_RE.fullmatch(text) else None


def normalize_pmid(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^pmid\s*:\s*", "", text, flags=re.I).strip()
    return text if text.isdigit() else None


def normalize_title(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _first(record: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def record_identity(record: Mapping[str, Any]) -> Dict[str, str]:
    nested = record.get("report_identity")
    sources: List[Mapping[str, Any]] = []
    if isinstance(nested, Mapping):
        sources.append(nested)
    layers: List[Mapping[str, Any]] = [record]
    current: Any = record
    seen = {id(record)}
    while isinstance(current, Mapping) and isinstance(current.get("data"), Mapping) and id(current["data"]) not in seen:
        current = current["data"]
        seen.add(id(current))
        layers.append(current)
    sources.extend(reversed(layers))
    result: Dict[str, str] = {}
    aliases = {
        "doi": ("doi", "DOI"),
        "pmid": ("pmid", "PMID", "pubmed_id", "pubmedId"),
        "title": ("title", "report_title", "article_title", "name"),
        "year": ("year", "publication_year", "date", "publicationDate", "publication_date"),
    }
    for field, names in aliases.items():
        for source in sources:
            value = _first(source, *names)
            if not value:
                continue
            if field == "doi":
                value = normalize_doi(value) or value
            elif field == "pmid":
                value = normalize_pmid(value) or value
            result[field] = value
            break
    return result


def _article_value(article: Any, *names: str) -> Optional[str]:
    for name in names:
        value = getattr(article, name, None)
        if value not in (None, ""):
            return str(value).strip()
        if isinstance(article, Mapping) and article.get(name) not in (None, ""):
            return str(article[name]).strip()
    return None


def _article_metadata(article: Any) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    doi = normalize_doi(_article_value(article, "doi", "DOI"))
    pmid = normalize_pmid(_article_value(article, "pmid", "PMID"))
    title = _article_value(article, "title", "article_title")
    year = _article_value(article, "year", "publication_year", "pubdate")
    if doi:
        metadata["doi"] = doi
    if pmid:
        metadata["pmid"] = pmid
    if title:
        metadata["title"] = title
    if year:
        match = re.search(r"(?<!\d)(\d{4})(?!\d)", year)
        if match:
            metadata["year"] = match.group(1)
    return metadata


def _same_year(left: Any, right: Any) -> bool:
    l = re.search(r"(?<!\d)(\d{4})(?!\d)", str(left or ""))
    r = re.search(r"(?<!\d)(\d{4})(?!\d)", str(right or ""))
    return bool(l and r and l.group(1) == r.group(1))


def resolve_doi(
    record: Mapping[str, Any],
    *,
    fetcher_factory: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    """Resolve a missing DOI using Metapub when available.

    No DOI is invented from a title.  A lookup-unavailable state is distinct
    from a completed lookup with no DOI so the evidence ledger never turns a
    connector failure into a bibliographic fact.
    """
    identity = record_identity(record)
    existing = normalize_doi(identity.get("doi"))
    if existing:
        return {
            "status": "present",
            "fact_status": "present_in_screened_record",
            "doi": existing,
            "source": "screened_record",
            "attempts": [],
        }

    attempts: List[Dict[str, Any]] = []
    if fetcher_factory is None:
        try:
            from metapub import PubMedFetcher  # type: ignore
        except ImportError:
            return {
                "status": "lookup_unavailable",
                "fact_status": "doi_not_present_lookup_unavailable",
                "doi": None,
                "source": "metapub_not_installed",
                "attempts": [{"route": "metapub", "status": "not_installed"}],
            }
        fetcher_factory = PubMedFetcher

    pmid = normalize_pmid(identity.get("pmid"))
    if pmid:
        try:
            fetcher = fetcher_factory()
            article = fetcher.article_by_pmid(pmid)
            metadata = _article_metadata(article)
            attempts.append({"route": "metapub_pmid", "pmid": pmid, "status": "completed", "metadata": metadata})
            doi = normalize_doi(metadata.get("doi"))
            if doi:
                return {
                    "status": "resolved",
                    "fact_status": "resolved_by_metapub",
                    "doi": doi,
                    "source": "metapub_pmid",
                    "attempts": attempts,
                }
        except Exception as exc:  # connector failures remain auditable
            attempts.append({"route": "metapub_pmid", "pmid": pmid, "status": "error", "error": str(exc)})

    title = identity.get("title")
    if title:
        try:
            fetcher = fetcher_factory()
            query = title
            pmids = list(fetcher.pmids_for_query(query, retmax=10))
            candidates: List[Dict[str, str]] = []
            for candidate_pmid in pmids:
                try:
                    article = fetcher.article_by_pmid(str(candidate_pmid))
                    metadata = _article_metadata(article)
                except Exception as exc:
                    attempts.append({"route": "metapub_title_candidate", "pmid": str(candidate_pmid), "status": "error", "error": str(exc)})
                    continue
                if normalize_title(metadata.get("title")) != normalize_title(title):
                    continue
                if identity.get("year") and metadata.get("year") and not _same_year(identity.get("year"), metadata.get("year")):
                    continue
                if metadata.get("doi"):
                    candidates.append(metadata)
            attempts.append({"route": "metapub_title", "status": "completed", "candidate_count": len(candidates)})
            unique = {normalize_doi(c.get("doi")) for c in candidates}
            unique.discard(None)
            if len(unique) == 1:
                doi = next(iter(unique))
                return {
                    "status": "resolved",
                    "fact_status": "resolved_by_metapub_title",
                    "doi": doi,
                    "source": "metapub_title",
                    "attempts": attempts,
                }
            if len(unique) > 1:
                return {
                    "status": "conflict",
                    "fact_status": "multiple_metapub_doi_candidates",
                    "doi": None,
                    "source": "metapub_title",
                    "attempts": attempts,
                    "candidates": sorted(unique),
                }
        except Exception as exc:
            attempts.append({"route": "metapub_title", "status": "error", "error": str(exc)})

    return {
        "status": "not_found",
        "fact_status": "doi_not_found_after_metapub_lookup",
        "doi": None,
        "source": "metapub",
        "attempts": attempts,
    }


def build_acquisition_queue(
    retrieval_manifest: Mapping[str, Any],
    *,
    fetcher_factory: Optional[Callable[[], Any]] = None,
    source_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a versionable route plan from a full-text retrieval manifest."""
    records = retrieval_manifest.get("records") if isinstance(retrieval_manifest, Mapping) else None
    if not isinstance(records, list):
        raise ValueError("retrieval manifest must contain a records list")
    queue_records: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        identity = record_identity(record)
        doi_result = resolve_doi(record, fetcher_factory=fetcher_factory)
        doi = doi_result.get("doi")
        route_attempts = list(record.get("route_attempts") or [])
        route_attempts.append({"route": "metapub_doi_resolution", "status": doi_result["status"], "attempted_at": now_iso(), "fact_status": doi_result["fact_status"]})
        queue_records.append({
            "study_id": str(record.get("study_id", "")).strip(),
            "report_id": str(record.get("report_id", "")).strip(),
            "expected_identity": identity,
            "doi_resolution": doi_result,
            "doi": doi,
            "download": {
                "provider": "scansci_pdf",
                "status": "planned" if doi else "manual_doi_or_identifier_required",
                "pdf_path": None,
                "pdf_sha256": None,
                "duplicate_of": None,
            },
            "institutional_access": {
                "status": "not_started",
                "route": "carsi_user_action_checkpoint",
                "publisher_or_proxy": None,
                "session_evidence": None,
            },
            "zotero": {
                "status": "pending",
                "item_key": None,
                "attachment_key": None,
                "metadata_readback": None,
                "verification_status": "not_started",
            },
            "discrepancy_status": "none",
            "discrepancies": [],
            "route_attempts": route_attempts,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "source_manifest_path": source_path,
        "source_manifest_sha256": None,
        "defaults": {
            "doi_lookup": "metapub_optional",
            "pdf_provider": "scansci_pdf",
            "paywall_route": "institutional_CARSI_user_action_then_resume",
            "zotero_route": "zotero_mcp_write_then_readback",
            "deduplication": "doi_then_sha256",
        },
        "records": queue_records,
    }


def _find_pdf_files(output_dir: Path) -> List[Path]:
    return sorted(path for path in output_dir.rglob("*.pdf") if path.is_file() and path.stat().st_size > 0)


def _cached_pdf_for_doi(output_dir: Path, doi: str) -> Optional[Path]:
    index_path = output_dir / ".doi_index.json"
    if not index_path.is_file():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entries = payload if isinstance(payload, list) else payload.get("records", payload.get("items", [])) if isinstance(payload, Mapping) else []
    if isinstance(entries, Mapping):
        entries = [entries]
    normalized = normalize_doi(doi)
    for entry in entries or []:
        if not isinstance(entry, Mapping) or normalize_doi(entry.get("doi")) != normalized:
            continue
        raw_path = entry.get("file") or entry.get("path") or entry.get("pdf_path")
        if not raw_path:
            continue
        candidate = (output_dir / str(raw_path)).resolve()
        try:
            candidate.relative_to(output_dir.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.casefold() == ".pdf" and candidate.stat().st_size > 0:
            return candidate
    return None


@dataclass
class ScanSciResult:
    status: str
    route: str
    command: List[str]
    returncode: Optional[int] = None
    pdf_path: Optional[str] = None
    pdf_sha256: Optional[str] = None
    duplicate_of: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


class ScanSciPDFAdapter:
    """Run the installed ScanSci PDF CLI without embedding publisher logins."""

    def __init__(self, executable: str = "scansci-pdf", timeout_sec: int = 300):
        self.executable = executable
        self.timeout_sec = timeout_sec

    def download(self, doi: str, output_dir: Path, known_hashes: Optional[Mapping[str, str]] = None) -> ScanSciResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        executable_path = shutil.which(self.executable)
        if executable_path is None:
            local_executable = Path(self.executable).expanduser()
            executable_path = str(local_executable.resolve()) if local_executable.is_file() else None
        command = [executable_path or self.executable, "get", doi]
        if executable_path is None:
            return ScanSciResult("provider_unavailable", "scansci_pdf", command, error="ScanSci PDF executable was not found")
        before = set(_find_pdf_files(output_dir))
        try:
            completed = subprocess.run(command, cwd=str(output_dir), capture_output=True, text=True, timeout=self.timeout_sec, check=False)
        except subprocess.TimeoutExpired as exc:
            return ScanSciResult("timeout", "scansci_pdf", command, stdout=str(exc.stdout or ""), stderr=str(exc.stderr or ""), error="ScanSci PDF timed out")
        except OSError as exc:
            return ScanSciResult("provider_error", "scansci_pdf", command, error=str(exc))
        after = _find_pdf_files(output_dir)
        candidates = [path for path in after if path not in before]
        if not candidates:
            cached = _cached_pdf_for_doi(output_dir, doi)
            if cached is not None:
                digest = sha256_file(cached)
                return ScanSciResult("cache_hit", "scansci_pdf_cache", command, completed.returncode, str(cached), digest, stdout=completed.stdout, stderr=completed.stderr)
        if candidates:
            pdf = max(candidates, key=lambda p: p.stat().st_mtime_ns)
            digest = sha256_file(pdf)
            for known_doi, known_hash in (known_hashes or {}).items():
                if known_hash and known_hash == digest:
                    return ScanSciResult("duplicate", "scansci_pdf", command, completed.returncode, str(pdf), digest, known_doi, completed.stdout, completed.stderr)
            return ScanSciResult("succeeded", "scansci_pdf", command, completed.returncode, str(pdf), digest, stdout=completed.stdout, stderr=completed.stderr)
        text = f"{completed.stdout}\n{completed.stderr}".casefold()
        if any(token in text for token in ("paywall", "carsi", "institution", "login", "authentication", "access denied")):
            return ScanSciResult("carsi_user_action_required", "scansci_pdf", command, completed.returncode, stdout=completed.stdout, stderr=completed.stderr, error="Institutional access is required; complete CARSI/WebVPN in the user browser and resume")
        return ScanSciResult("failed", "scansci_pdf", command, completed.returncode, stdout=completed.stdout, stderr=completed.stderr, error="No PDF was produced")


def compare_identity(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return a table-ready discrepancy list; empty means identity agrees."""
    rows: List[Dict[str, Any]] = []
    expected_doi = normalize_doi(expected.get("doi"))
    observed_doi = normalize_doi(observed.get("doi") or observed.get("DOI"))
    expected_pmid = normalize_pmid(expected.get("pmid"))
    observed_pmid = normalize_pmid(observed.get("pmid") or observed.get("PMID"))
    expected_title = normalize_title(expected.get("title"))
    observed_title = normalize_title(observed.get("title") or observed.get("name"))
    expected_year = str(expected.get("year") or "")[:4]
    observed_year_match = re.search(r"(?<!\d)(\d{4})(?!\d)", str(observed.get("year") or observed.get("date") or ""))
    observed_year = observed_year_match.group(1) if observed_year_match else ""
    for field, left, right in (("doi", expected_doi, observed_doi), ("pmid", expected_pmid, observed_pmid), ("title", expected_title, observed_title), ("year", expected_year, observed_year)):
        if left and right and left != right:
            rows.append({"field": field, "expected": left, "observed": right, "severity": "high" if field in {"doi", "pmid"} else "medium", "status": "open"})
        elif left and not right:
            rows.append({"field": field, "expected": left, "observed": "", "severity": "medium", "status": "open", "reason": "Zotero readback omitted an expected field"})
    return rows


def write_discrepancy_table(rows: Iterable[Mapping[str, Any]], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["study_id", "report_id", "item_key", "field", "expected", "observed", "severity", "status", "reason", "evidence_locator"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_queue_with_download(queue: Dict[str, Any], record_key: Tuple[str, str], result: ScanSciResult) -> None:
    for record in queue.get("records", []):
        if not isinstance(record, dict):
            continue
        if (record.get("study_id"), record.get("report_id")) != record_key:
            continue
        record["download"].update({
            "status": result.status,
            "command": result.command,
            "pdf_path": result.pdf_path,
            "pdf_sha256": result.pdf_sha256,
            "duplicate_of": result.duplicate_of,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.error,
            "completed_at": now_iso(),
        })
        record.setdefault("route_attempts", []).append({
            "route": "scansci_pdf",
            "status": result.status,
            "attempted_at": now_iso(),
            "pdf_sha256": result.pdf_sha256,
            "error": result.error,
        })
        if result.status == "carsi_user_action_required":
            record["institutional_access"].update({
                "status": "user_action_required",
                "route": "carsi_user_action_checkpoint",
                "next_action": "Complete institutional CARSI/WebVPN login in the user browser, then rerun this record.",
            })
        return
    raise KeyError(f"Unknown acquisition record: {record_key}")


def load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)

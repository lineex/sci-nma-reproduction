"""
Corpus Repository & Multi-Database Batch File Ingestion Engine.
Enforces the Zero Relevance Truncation policy: preserves 100% of hit records
across all landed export batches from PubMed, Embase, Web of Science, and Cochrane Library.
"""

import os
import re
import csv
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class CanonicalRecord:
    """Standardized representation of a bibliographic hit across all databases."""
    master_id: str
    sources: List[str] = field(default_factory=list)
    db_ids: Dict[str, Optional[str]] = field(default_factory=dict)
    doi: Optional[str] = None
    title: str = ""
    abstract: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    year: Optional[int] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    raw_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FormatParsers:
    """Parsers for all standard institutional session export formats."""

    @staticmethod
    def normalize_doi(doi_str: Optional[str]) -> Optional[str]:
        if not doi_str:
            return None
        doi = doi_str.strip().lower()
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        doi = re.sub(r"^doi:\s*", "", doi)
        m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", doi)
        return m.group(0).rstrip(".,;") if m else None

    @classmethod
    def parse_nbib(cls, file_path: str) -> List[CanonicalRecord]:
        """Parse PubMed MEDLINE / NBIB format."""
        records = []
        if not os.path.exists(file_path):
            return records

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        entries = re.split(r"\n(?=PMID- )", content)
        for idx, entry in enumerate(entries):
            entry = entry.strip()
            if not entry:
                continue

            pmid, title, abstract, authors, journal, year, doi = None, "", "", [], "", None, None
            keywords = []

            curr_tag = None
            curr_val = []

            for line in entry.splitlines():
                if len(line) >= 5 and line[4] == "-":
                    if curr_tag:
                        val = " ".join(curr_val).strip()
                        if curr_tag == "PMID":
                            pmid = val
                        elif curr_tag == "TI":
                            title = val
                        elif curr_tag == "AB":
                            abstract = val
                        elif curr_tag == "AU":
                            authors.append(val)
                        elif curr_tag in ("TA", "JT"):
                            if not journal:
                                journal = val
                        elif curr_tag == "DP":
                            m = re.search(r"\b(19|20)\d{2}\b", val)
                            if m:
                                year = int(m.group(0))
                        elif curr_tag in ("LID", "AID") and "doi" in line.lower():
                            doi = cls.normalize_doi(val)
                        elif curr_tag == "MH":
                            keywords.append(val)

                    curr_tag = line[:4].strip()
                    curr_val = [line[5:].strip()]
                else:
                    if curr_tag:
                        curr_val.append(line.strip())

            # Last field
            if curr_tag:
                val = " ".join(curr_val).strip()
                if curr_tag == "PMID":
                    pmid = val
                elif curr_tag == "TI":
                    title = val
                elif curr_tag == "AB":
                    abstract = val
                elif curr_tag == "AU":
                    authors.append(val)
                elif curr_tag in ("TA", "JT") and not journal:
                    journal = val
                elif curr_tag == "DP" and not year:
                    m = re.search(r"\b(19|20)\d{2}\b", val)
                    if m:
                        year = int(m.group(0))
                elif curr_tag in ("LID", "AID") and "doi" in val.lower() and not doi:
                    doi = cls.normalize_doi(val)
                elif curr_tag == "MH":
                    keywords.append(val)

            rec = CanonicalRecord(
                master_id=f"PUBMED-{pmid or idx+1:05d}" if isinstance(pmid, int) else f"PUBMED-{pmid or idx+1}",
                sources=["PubMed"],
                db_ids={"pubmed_pmid": pmid},
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                keywords=keywords,
                raw_file=os.path.basename(file_path)
            )
            records.append(rec)

        return records

    @classmethod
    def parse_ris(cls, file_path: str, default_source: str = "Embase") -> List[CanonicalRecord]:
        """Parse RIS format from Embase, Cochrane, or other institutional databases."""
        records = []
        if not os.path.exists(file_path):
            return records

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        entries = re.split(r"\nER  -", content)
        for idx, entry in enumerate(entries):
            entry = entry.strip()
            if not entry or "TY  -" not in entry:
                continue

            title, abstract, authors, journal, year, doi = "", "", [], "", None, None
            pui, pmid, central_id = None, None, None
            keywords = []

            for line in entry.splitlines():
                line_s = line.strip()
                if len(line_s) < 6 or line_s[2:5] != "  -":
                    continue
                tag = line_s[:2].strip()
                val = line_s[6:].strip()

                if tag in ("TI", "T1"):
                    title = f"{title} {val}".strip() if title else val
                elif tag in ("AB", "N2"):
                    abstract = f"{abstract} {val}".strip() if abstract else val
                elif tag in ("AU", "A1"):
                    authors.append(val)
                elif tag in ("JO", "JF", "JA", "T2"):
                    if not journal:
                        journal = val
                elif tag in ("PY", "Y1"):
                    m = re.search(r"\b(19|20)\d{2}\b", val)
                    if m and not year:
                        year = int(m.group(0))
                elif tag == "DO":
                    doi = cls.normalize_doi(val)
                elif tag in ("ID", "AN"):
                    pui = val
                    if "CN-" in val:
                        central_id = val
                elif tag in ("C1", "M3") and "pmid" in val.lower():
                    m = re.search(r"\b\d{7,9}\b", val)
                    if m:
                        pmid = m.group(0)
                elif tag == "KW":
                    keywords.append(val)

            db_ids = {}
            if "embase" in default_source.lower():
                db_ids["embase_pui"] = pui
            elif "cochrane" in default_source.lower():
                db_ids["cochrane_id"] = central_id or pui
            if pmid:
                db_ids["pubmed_pmid"] = pmid

            rec = CanonicalRecord(
                master_id=f"{default_source.upper()}-{pui or idx+1}",
                sources=[default_source],
                db_ids=db_ids,
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                keywords=keywords,
                raw_file=os.path.basename(file_path)
            )
            records.append(rec)

        return records

    @classmethod
    def parse_wos_plaintext(cls, file_path: str) -> List[CanonicalRecord]:
        """Parse Clarivate Web of Science plain text export (tagged or tab-delimited)."""
        records = []
        if not os.path.exists(file_path):
            return records

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Check if tab-delimited
        if lines and ("PT\t" in lines[0] or "UT\t" in lines[0] or "\tTI\t" in lines[0]):
            reader = csv.DictReader(lines, delimiter="\t")
            for idx, row in enumerate(reader):
                ut = row.get("UT", "").strip()
                title = row.get("TI", "").strip()
                abstract = row.get("AB", "").strip()
                authors_str = row.get("AU", "") or row.get("AF", "")
                authors = [a.strip() for a in authors_str.split(";") if a.strip()]
                journal = row.get("SO", "").strip()
                year_str = row.get("PY", "").strip()
                year = int(year_str) if year_str.isdigit() else None
                doi = cls.normalize_doi(row.get("DI", "").strip())
                pmid = row.get("PM", "").strip() or None
                kw = [k.strip() for k in (row.get("ID", "") + ";" + row.get("DE", "")).split(";") if k.strip()]

                rec = CanonicalRecord(
                    master_id=f"WOS-{ut or idx+1}",
                    sources=["Web of Science"],
                    db_ids={"wos_uid": ut, "pubmed_pmid": pmid},
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    journal=journal,
                    year=year,
                    keywords=kw,
                    raw_file=os.path.basename(file_path)
                )
                records.append(rec)
            return records

        # Field-tagged format (PT J, TI ..., UT WOS:..., ER)
        content = "".join(lines)
        entries = re.split(r"\nER(?:\n|$)", content)
        for idx, entry in enumerate(entries):
            entry = entry.strip()
            if not entry or "PT " not in entry:
                continue

            ut, title, abstract, authors, journal, year, doi, pmid = None, "", "", [], "", None, None, None
            keywords = []
            curr_tag = None
            curr_val = []

            for line in entry.splitlines():
                if len(line) >= 3 and line[2] == " ":
                    if curr_tag:
                        val = " ".join(curr_val).strip()
                        if curr_tag == "UT":
                            ut = val
                        elif curr_tag == "TI":
                            title = val
                        elif curr_tag == "AB":
                            abstract = val
                        elif curr_tag in ("AU", "AF"):
                            authors.extend([a.strip() for a in val.split(";") if a.strip()])
                        elif curr_tag == "SO":
                            journal = val
                        elif curr_tag == "PY" and val.isdigit():
                            year = int(val)
                        elif curr_tag == "DI":
                            doi = cls.normalize_doi(val)
                        elif curr_tag == "PM":
                            pmid = val
                        elif curr_tag in ("DE", "ID"):
                            keywords.extend([k.strip() for k in val.split(";") if k.strip()])

                    curr_tag = line[:2].strip()
                    curr_val = [line[3:].strip()]
                else:
                    if curr_tag:
                        curr_val.append(line.strip())

            if curr_tag:
                val = " ".join(curr_val).strip()
                if curr_tag == "UT":
                    ut = val
                elif curr_tag == "TI":
                    title = val
                elif curr_tag == "AB":
                    abstract = val
                elif curr_tag in ("AU", "AF"):
                    authors.extend([a.strip() for a in val.split(";") if a.strip()])
                elif curr_tag == "SO":
                    journal = val
                elif curr_tag == "PY" and val.isdigit():
                    year = int(val)
                elif curr_tag == "DI":
                    doi = cls.normalize_doi(val)
                elif curr_tag == "PM":
                    pmid = val
                elif curr_tag in ("DE", "ID"):
                    keywords.extend([k.strip() for k in val.split(";") if k.strip()])

            rec = CanonicalRecord(
                master_id=f"WOS-{ut or idx+1}",
                sources=["Web of Science"],
                db_ids={"wos_uid": ut, "pubmed_pmid": pmid},
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                keywords=keywords,
                raw_file=os.path.basename(file_path)
            )
            records.append(rec)

        return records

    @classmethod
    def parse_cochrane_csv(cls, file_path: str) -> List[CanonicalRecord]:
        """Parse Cochrane Library CSV export format."""
        records = []
        if not os.path.exists(file_path):
            return records

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                # Look for common Cochrane column variations
                title = row.get("Title", "") or row.get("Record Title", "") or row.get("Article Title", "")
                abstract = row.get("Abstract", "")
                authors_str = row.get("Author(s)", "") or row.get("Authors", "")
                authors = [a.strip() for a in authors_str.split(";") if a.strip()]
                doi = cls.normalize_doi(row.get("DOI", ""))
                rec_id = row.get("Cochrane ID", "") or row.get("ID", "") or row.get("Accession Number", "")
                journal = row.get("Source", "") or row.get("Journal", "")
                year_str = row.get("Publication Year", "") or row.get("Year", "")
                year = int(year_str) if year_str.isdigit() else None

                rec = CanonicalRecord(
                    master_id=f"COCHRANE-{rec_id or idx+1}",
                    sources=["Cochrane Library"],
                    db_ids={"cochrane_id": rec_id},
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    journal=journal,
                    year=year,
                    raw_file=os.path.basename(file_path)
                )
                records.append(rec)

        return records


class CorpusRepository:
    """
    Scans, ingests, and catalogs all landed raw export batch files across databases.
    """

    @classmethod
    def scan_and_ingest(cls, raw_exports_dir: str) -> Dict[str, Any]:
        """
        Scan raw_exports/{pubmed, embase, wos, cochrane} for batch export files
        and return canonical records with batch ingestion audit metadata.
        """
        result = {
            "databases": {
                "PubMed": {"file_count": 0, "record_count": 0, "files": []},
                "Embase": {"file_count": 0, "record_count": 0, "files": []},
                "Web of Science": {"file_count": 0, "record_count": 0, "files": []},
                "Cochrane Library": {"file_count": 0, "record_count": 0, "files": []}
            },
            "total_raw_records": 0,
            "records": []
        }

        if not os.path.exists(raw_exports_dir):
            return result

        for root, _, files in os.walk(raw_exports_dir):
            rel_dir = os.path.relpath(root, raw_exports_dir).lower()

            for f in files:
                file_path = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()

                target_db = None
                parsed_records = []

                if "pubmed" in rel_dir or ext in (".nbib", ".medline"):
                    target_db = "PubMed"
                    parsed_records = FormatParsers.parse_nbib(file_path)
                elif "embase" in rel_dir:
                    target_db = "Embase"
                    if ext == ".ris":
                        parsed_records = FormatParsers.parse_ris(file_path, default_source="Embase")
                elif "wos" in rel_dir or "web of science" in rel_dir or ext in (".ciw",):
                    target_db = "Web of Science"
                    parsed_records = FormatParsers.parse_wos_plaintext(file_path)
                elif "cochrane" in rel_dir:
                    target_db = "Cochrane Library"
                    if ext == ".csv":
                        parsed_records = FormatParsers.parse_cochrane_csv(file_path)
                    elif ext == ".ris":
                        parsed_records = FormatParsers.parse_ris(file_path, default_source="Cochrane Library")
                elif ext == ".ris":
                    target_db = "Embase"
                    parsed_records = FormatParsers.parse_ris(file_path, default_source="Embase")
                elif ext == ".csv":
                    target_db = "Cochrane Library"
                    parsed_records = FormatParsers.parse_cochrane_csv(file_path)

                if target_db and parsed_records:
                    db_stat = result["databases"][target_db]
                    db_stat["file_count"] += 1
                    db_stat["record_count"] += len(parsed_records)
                    db_stat["files"].append({
                        "filename": f,
                        "path": file_path,
                        "records": len(parsed_records)
                    })
                    result["records"].extend(parsed_records)

        result["total_raw_records"] = len(result["records"])
        return result

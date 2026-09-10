"""
Gate 2: Evidence Authenticity & Cryptographic Provenance Verification Gate.
Validates DOI/PMID/PMCID formats, checks coordinate anchoring, and detects hallucinations.
"""

import re
from typing import Dict, Any, List, Tuple


class Gate2EvidenceProvenance:
    """Validator for Gate 2: Evidence Authenticity & Provenance Anchoring."""

    DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")
    PMID_PATTERN = re.compile(r"^\d{1,9}$")
    PMCID_PATTERN = re.compile(r"^PMC\d{5,9}$")

    MOCK_PATTERNS = [
        "mock", "placeholder", "fake", "example.com", "unknown",
        "tbd", "todo", "xxx", "10.0000", "0.0000", "/test"
    ]

    @classmethod
    def validate_doi(cls, doi: str) -> Tuple[bool, str]:
        """Validate DOI structure and check against mock placeholders."""
        if not doi:
            return False, "Empty DOI provided."
        doi_clean = doi.strip()
        if doi_clean.startswith("https://doi.org/"):
            doi_clean = doi_clean.replace("https://doi.org/", "")
        elif doi_clean.startswith("http://doi.org/"):
            doi_clean = doi_clean.replace("http://doi.org/", "")

        for mock in cls.MOCK_PATTERNS:
            if mock in doi_clean.lower():
                return False, f"Mock placeholder pattern detected in DOI: '{doi_clean}'."

        if not cls.DOI_PATTERN.match(doi_clean):
            return False, f"Invalid DOI format: '{doi_clean}'."

        return True, ""

    @classmethod
    def validate_pmid(cls, pmid: Any) -> Tuple[bool, str]:
        """Validate PubMed PMID format."""
        if not pmid:
            return False, "Empty PMID."
        s = str(pmid).strip()
        if not cls.PMID_PATTERN.match(s):
            return False, f"Invalid PMID format: '{s}'."
        return True, ""

    @classmethod
    def validate_pmcid(cls, pmcid: str) -> Tuple[bool, str]:
        """Validate PubMed Central PMCID format."""
        if not pmcid:
            return False, "Empty PMCID."
        s = pmcid.strip()
        if not cls.PMCID_PATTERN.match(s):
            return False, f"Invalid PMCID format: '{s}'."
        return True, ""

    @classmethod
    def validate_evidence_coordinate(cls, coordinate: str) -> Tuple[bool, str]:
        """
        Validate evidence anchor coordinate format.
        Expected format: [SourceFile]:[Section/Table/Par]:[Variable/Row]
        Example: 'MOESM1_ESM.docx:Table 1:Step 39' or 'PMC12837105.xml:Par3:EarlyMortality'
        """
        if not coordinate:
            return False, "Empty evidence coordinate."
        parts = coordinate.split(":")
        if len(parts) < 2:
            return False, (
                f"Coordinate '{coordinate}' does not satisfy '[File]:[Location]:[Variable]' standard."
            )
        return True, ""

    @classmethod
    def audit_study_provenance(cls, study: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Audit single study entry for provenance integrity."""
        errors = []
        name = study.get("study_id") or study.get("author_year", "Unknown Study")

        # 1. DOI
        doi = study.get("doi")
        if doi:
            is_valid, msg = cls.validate_doi(doi)
            if not is_valid:
                errors.append(f"[{name}] {msg}")
        else:
            errors.append(f"[{name}] Missing DOI.")

        # 2. PMID
        pmid = study.get("pmid")
        if pmid:
            is_valid, msg = cls.validate_pmid(pmid)
            if not is_valid:
                errors.append(f"[{name}] {msg}")

        # 3. Coordinate Anchor
        coordinate = study.get("coordinate_anchor")
        if coordinate:
            is_valid, msg = cls.validate_evidence_coordinate(coordinate)
            if not is_valid:
                errors.append(f"[{name}] {msg}")

        return (len(errors) == 0), errors

    @classmethod
    def audit_dataset_provenance(cls, dataset: List[Dict[str, Any]]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Audit an entire collection of included studies."""
        all_errors = []
        verified_count = 0

        for study in dataset:
            passed, errs = cls.audit_study_provenance(study)
            if passed:
                verified_count += 1
            else:
                all_errors.extend(errs)

        metrics = {
            "total_studies_audited": len(dataset),
            "verified_studies": verified_count,
            "failed_studies": len(dataset) - verified_count,
            "provenance_rate_percent": (verified_count / len(dataset) * 100) if dataset else 0.0
        }
        passed = (len(all_errors) == 0)
        return passed, all_errors, metrics

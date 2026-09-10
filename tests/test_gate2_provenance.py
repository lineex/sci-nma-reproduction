"""
Unit tests for Gate 2: Evidence Authenticity & Cryptographic Provenance.
"""

import pytest
from sci_nma_agent.core.gate2_evidence_provenance import Gate2EvidenceProvenance


def test_doi_valid():
    valid_dois = [
        "10.1001/jama.288.7.862",
        "10.1056/NEJMoa1705835",
        "10.1186/s13054-021-03612-4",
        "https://doi.org/10.1016/j.jped.2016.08.005"
    ]
    for doi in valid_dois:
        is_valid, msg = Gate2EvidenceProvenance.validate_doi(doi)
        assert is_valid is True, f"Failed on valid DOI: {doi} ({msg})"


def test_doi_mock_rejection():
    mock_dois = [
        "10.1000/mock123",
        "10.1234/placeholder",
        "10.0000/test",
        "fake_doi_string"
    ]
    for doi in mock_dois:
        is_valid, msg = Gate2EvidenceProvenance.validate_doi(doi)
        assert is_valid is False, f"Mock DOI passed unexpectedly: {doi}"


def test_pmid_validation():
    assert Gate2EvidenceProvenance.validate_pmid("29347369")[0] is True
    assert Gate2EvidenceProvenance.validate_pmid("abc12345")[0] is False


def test_coordinate_anchor():
    valid_coord = "MOESM1_ESM.docx:Table 1:Step 39"
    invalid_coord = "plain_string_without_colons"
    assert Gate2EvidenceProvenance.validate_evidence_coordinate(valid_coord)[0] is True
    assert Gate2EvidenceProvenance.validate_evidence_coordinate(invalid_coord)[0] is False

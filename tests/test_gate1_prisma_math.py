"""
Unit tests for Gate 1: Search Syntax & PRISMA Mathematical Flow Conservation.
"""

import pytest
from sci_nma_agent.core.gate1_search_flow import Gate1SearchFlow


def test_prisma_flow_valid_conservation():
    valid_flow = {
        "databases": {"PubMed": 100, "Embase": 200, "Cochrane": 50},
        "registries_or_citations": 10,
        "total_identified": 360,
        "duplicates_removed": 60,
        "records_screened": 300,
        "screening_excluded": 250,
        "screening_exclusion_reasons": {"Reason A": 150, "Reason B": 100},
        "reports_sought": 50,
        "reports_not_retrieved": 5,
        "reports_assessed": 45,
        "fulltext_excluded": 30,
        "fulltext_exclusion_reasons": {"Non-RCT": 20, "No Outcome": 10},
        "studies_included": 15,
        "reports_included": 15,
        "flow_loss": 0
    }
    passed, errors, metrics = Gate1SearchFlow.validate_prisma_flow(valid_flow)
    assert passed is True
    assert len(errors) == 0
    assert metrics["flow_loss"] == 0
    assert metrics["studies_included"] == 15


def test_prisma_flow_violation_detection():
    # Deliberate mismatch: records_screened is off by 10
    invalid_flow = {
        "databases": {"PubMed": 100, "Embase": 200},
        "total_identified": 300,
        "duplicates_removed": 50,
        "records_screened": 260,  # Should be 250
        "screening_excluded": 200,
        "reports_sought": 50,
        "reports_not_retrieved": 0,
        "reports_assessed": 50,
        "fulltext_excluded": 30,
        "studies_included": 20
    }
    passed, errors, metrics = Gate1SearchFlow.validate_prisma_flow(invalid_flow)
    assert passed is False
    assert any("Screening mismatch" in e for e in errors)


def test_search_syntax_parentheses():
    query_unbalanced = "(sepsis OR septic shock AND (corticosteroids)"
    passed, errors = Gate1SearchFlow.validate_search_syntax("PubMed", query_unbalanced)
    assert passed is False
    assert any("Unbalanced parentheses" in e for e in errors)


def test_search_syntax_lowercase_boolean():
    query_lowercase = '"septic shock"[tiab] and "hydrocortisone"[tiab]'
    passed, errors = Gate1SearchFlow.validate_search_syntax("PubMed", query_lowercase)
    assert passed is False
    assert any("Lowercase boolean" in e for e in errors)

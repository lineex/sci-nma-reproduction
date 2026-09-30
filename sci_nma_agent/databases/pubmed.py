"""
PubMed / MEDLINE Query Builder & E-utilities Client.
Implements MeSH indexing, field tags, and the Cochrane Highly Sensitive Search Strategy for RCTs.
"""

from typing import List, Dict, Any, Optional
import requests


class PubMedQueryBuilder:
    """Constructs native PubMed search syntax from clinical keywords and MeSH terms."""

    COCHRANE_RCT_FILTER = (
        '("randomized controlled trial"[pt] OR "controlled clinical trial"[pt] OR '
        '"randomized"[tiab] OR "placebo"[tiab] OR "clinical trials as topic"[mesh:noexp] OR '
        '"randomly"[tiab] OR "trial"[ti]) NOT ("animals"[mh] NOT "humans"[mh])'
    )

    @staticmethod
    def _format_terms(
        terms: List[str],
        mesh_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        if not terms:
            raise ValueError("PubMed search terms must contain at least one value")
        clauses = []
        for term in terms:
            value = str(term).strip()
            if not value:
                continue
            clauses.append(f'"{value}"[tiab]')
            if mesh_mapping and value in mesh_mapping:
                clauses.append(f'"{mesh_mapping[value]}"[MeSH Terms]')
        if not clauses:
            raise ValueError("PubMed search terms must contain at least one non-empty value")
        return f"({' OR '.join(clauses)})"

    @classmethod
    def build_concept_clause(
        cls,
        terms: List[str],
        mesh_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        """Return a native PubMed concept block without filters or limits."""
        return cls._format_terms(terms, mesh_mapping)

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        mesh_mapping: Optional[Dict[str, str]] = None,
        apply_rct_filter: bool = True,
        year_range: Optional[tuple] = None,
        english_only: bool = True,
        outcome_terms: Optional[List[str]] = None,
    ) -> str:
        """
        Build publication-grade PubMed search string.
        """
        pop_clause = cls.build_concept_clause(population_terms, mesh_mapping)
        int_clause = cls.build_concept_clause(intervention_terms, mesh_mapping)

        parts = [pop_clause, int_clause]

        if comparison_terms:
            parts.append(cls.build_concept_clause(comparison_terms, mesh_mapping))
        if outcome_terms:
            parts.append(cls.build_concept_clause(outcome_terms, mesh_mapping))

        full_query = " AND ".join(parts)

        if apply_rct_filter:
            full_query = f"({full_query}) AND ({cls.COCHRANE_RCT_FILTER})"

        if english_only:
            full_query = f"({full_query}) AND english[la]"

        if year_range:
            start_yr, end_yr = year_range
            full_query = f"({full_query}) AND ({start_yr}:{end_yr}[dp])"

        return full_query

    @classmethod
    def search_eutilities(
        cls, query: str, retmax: int = 50, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute esearch against NCBI E-utilities.
        """
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax
        }
        if api_key:
            params["api_key"] = api_key

        try:
            resp = requests.get(base_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("esearchresult", {})
                return {
                    "count": int(data.get("count", 0)),
                    "pmids": data.get("idlist", []),
                    "query_translation": data.get("querytranslation", "")
                }
        except Exception:
            pass

        return {"count": 0, "pmids": [], "query_translation": ""}

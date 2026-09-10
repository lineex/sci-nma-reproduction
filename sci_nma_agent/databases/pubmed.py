"""
PubMed / MEDLINE Query Builder & E-utilities Client.
Implements MeSH indexing, field tags, and the Cochrane Highly Sensitive Search Strategy for RCTs.
"""

from typing import List, Dict, Any, Optional
import urllib.parse
import requests


class PubMedQueryBuilder:
    """Constructs native PubMed search syntax from clinical keywords and MeSH terms."""

    COCHRANE_RCT_FILTER = (
        '("randomized controlled trial"[pt] OR "controlled clinical trial"[pt] OR '
        '"randomized"[tiab] OR "placebo"[tiab] OR "clinical trials as topic"[mesh:noexp] OR '
        '"randomly"[tiab] OR "trial"[ti]) NOT ("animals"[mh] NOT "humans"[mh])'
    )

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        mesh_mapping: Optional[Dict[str, str]] = None,
        apply_rct_filter: bool = True,
        year_range: Optional[tuple] = None,
        english_only: bool = True
    ) -> str:
        """
        Build publication-grade PubMed search string.
        """
        def format_terms(terms: List[str]) -> str:
            clauses = []
            for t in terms:
                # Add title/abstract tag
                clauses.append(f'"{t}"[tiab]')
                # If mapped to MeSH, add MeSH tag
                if mesh_mapping and t in mesh_mapping:
                    clauses.append(f'"{mesh_mapping[t]}"[MeSH Terms]')
            return f"({' OR '.join(clauses)})"

        pop_clause = format_terms(population_terms)
        int_clause = format_terms(intervention_terms)

        parts = [pop_clause, int_clause]

        if comparison_terms:
            comp_clause = format_terms(comparison_terms)
            parts.append(comp_clause)

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

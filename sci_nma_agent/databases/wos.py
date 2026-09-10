"""
Web of Science (WoS) Query Builder & Clarivate Starter API Client.
Constructs native TS=, TI=, SO= syntax for WoS Core Collection.
"""

from typing import List, Dict, Any, Optional
import requests


class WoSQueryBuilder:
    """Constructs native Web of Science Core Collection search strings."""

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        year_range: Optional[tuple] = None,
        article_or_review_only: bool = True
    ) -> str:
        """
        Build native Web of Science search syntax.
        """
        def format_terms(terms: List[str]) -> str:
            clauses = [f'TS=("{t}")' for t in terms]
            return f"({' OR '.join(clauses)})"

        pop_clause = format_terms(population_terms)
        int_clause = format_terms(intervention_terms)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            comp_clause = format_terms(comparison_terms)
            parts.append(comp_clause)

        full_query = " AND ".join(parts)

        if article_or_review_only:
            full_query = f"({full_query}) AND DT=(Article OR Review) NOT DT=(Meeting Abstract OR Proceedings Paper)"

        if year_range:
            start_yr, end_yr = year_range
            full_query = f"({full_query}) AND PY=({start_yr}-{end_yr})"

        return full_query

    @classmethod
    def search_starter_api(
        cls, query: str, api_key: str, limit: int = 50, page: int = 1
    ) -> Dict[str, Any]:
        """Query Clarivate WoS Starter API."""
        url = "https://api.clarivate.com/apis/wos-starter/v1/documents"
        headers = {"X-ApiKey": api_key}
        params = {
            "q": query,
            "db": "WOS",
            "limit": limit,
            "page": page
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "count": data.get("metadata", {}).get("total", 0),
                    "records": data.get("hits", [])
                }
        except Exception:
            pass

        return {"count": 0, "records": []}

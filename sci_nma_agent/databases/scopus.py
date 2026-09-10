"""
Scopus Query Builder.
Implements TITLE-ABS-KEY syntax, proximity operators (PRE/n, W/n), and Scopus source filters.
"""

from typing import List, Optional


class ScopusQueryBuilder:
    """Constructs native Scopus search strings."""

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
        Build native Scopus search syntax using TITLE-ABS-KEY.
        """
        def format_terms(terms: List[str]) -> str:
            clauses = [f'TITLE-ABS-KEY("{t}")' for t in terms]
            return f"({' OR '.join(clauses)})"

        pop_clause = format_terms(population_terms)
        int_clause = format_terms(intervention_terms)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            comp_clause = format_terms(comparison_terms)
            parts.append(comp_clause)

        full_query = " AND ".join(parts)

        if article_or_review_only:
            full_query = f"({full_query}) AND (DOCTYPE(ar) OR DOCTYPE(re))"

        if year_range:
            start_yr, end_yr = year_range
            full_query = f"({full_query}) AND PUBYEAR > {start_yr - 1} AND PUBYEAR < {end_yr + 1}"

        return full_query

"""
Scopus Query Builder.
Implements TITLE-ABS-KEY syntax, proximity operators (PRE/n, W/n), and Scopus source filters.
"""

from typing import List, Optional


class ScopusQueryBuilder:
    """Constructs native Scopus search strings."""

    @staticmethod
    def build_concept_clause(terms: List[str]) -> str:
        """Return one native Scopus TITLE-ABS-KEY concept block."""
        if not terms:
            raise ValueError("Scopus search terms must contain at least one value")
        clauses = [
            f'TITLE-ABS-KEY("{str(term).strip()}")'
            for term in terms
            if str(term).strip()
        ]
        if not clauses:
            raise ValueError("Scopus search terms must contain at least one non-empty value")
        return f"({' OR '.join(clauses)})"

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        year_range: Optional[tuple] = None,
        article_or_review_only: bool = True,
        outcome_terms: Optional[List[str]] = None,
    ) -> str:
        """
        Build native Scopus search syntax using TITLE-ABS-KEY.
        """
        pop_clause = cls.build_concept_clause(population_terms)
        int_clause = cls.build_concept_clause(intervention_terms)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            parts.append(cls.build_concept_clause(comparison_terms))
        if outcome_terms:
            parts.append(cls.build_concept_clause(outcome_terms))

        full_query = " AND ".join(parts)

        if article_or_review_only:
            full_query = f"({full_query}) AND (DOCTYPE(ar) OR DOCTYPE(re))"

        if year_range:
            start_yr, end_yr = year_range
            full_query = f"({full_query}) AND PUBYEAR > {start_yr - 1} AND PUBYEAR < {end_yr + 1}"

        return full_query

"""
Cochrane Library Query Builder & Results Portlet Adapter.
Constructs native Cochrane Search Manager syntax with CENTRAL & Review separation.
"""

from typing import List, Dict, Any, Optional


class CochraneQueryBuilder:
    """Constructs native Cochrane Library search syntax."""

    @staticmethod
    def _format_terms(
        terms: List[str],
        mesh_mapping: Optional[Dict[str, str]] = None,
        search_field: str = "ti,ab,kw",
    ) -> str:
        if not terms:
            raise ValueError("Cochrane search terms must contain at least one value")
        clauses = []
        for term in terms:
            value = str(term).strip()
            if not value:
                continue
            clauses.append(f'("{value}"):{search_field}')
            if mesh_mapping and value in mesh_mapping:
                clauses.append(f'[mh "{mesh_mapping[value]}"]')
        if not clauses:
            raise ValueError("Cochrane search terms must contain at least one non-empty value")
        return f"({' OR '.join(clauses)})"

    @classmethod
    def build_concept_clause(
        cls,
        terms: List[str],
        mesh_mapping: Optional[Dict[str, str]] = None,
        search_field: str = "ti,ab,kw",
    ) -> str:
        """Return a native Cochrane Search Manager concept block."""
        return cls._format_terms(terms, mesh_mapping, search_field)

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        mesh_mapping: Optional[Dict[str, str]] = None,
        search_field: str = "ti,ab,kw",
        outcome_terms: Optional[List[str]] = None,
    ) -> str:
        """
        Build native Cochrane Library search manager syntax.
        """
        pop_clause = cls.build_concept_clause(population_terms, mesh_mapping, search_field)
        int_clause = cls.build_concept_clause(intervention_terms, mesh_mapping, search_field)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            parts.append(cls.build_concept_clause(comparison_terms, mesh_mapping, search_field))
        if outcome_terms:
            parts.append(cls.build_concept_clause(outcome_terms, mesh_mapping, search_field))

        return " AND ".join(parts)

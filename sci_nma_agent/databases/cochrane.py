"""
Cochrane Library Query Builder & Results Portlet Adapter.
Constructs native Cochrane Search Manager syntax with CENTRAL & Review separation.
"""

from typing import List, Dict, Any, Optional


class CochraneQueryBuilder:
    """Constructs native Cochrane Library search syntax."""

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        mesh_mapping: Optional[Dict[str, str]] = None,
        search_field: str = "ti,ab,kw"
    ) -> str:
        """
        Build native Cochrane Library search manager syntax.
        """
        def format_terms(terms: List[str]) -> str:
            clauses = []
            for t in terms:
                clauses.append(f'("{t}"):{search_field}')
                if mesh_mapping and t in mesh_mapping:
                    clauses.append(f'[mh "{mesh_mapping[t]}"]')
            return f"({' OR '.join(clauses)})"

        pop_clause = format_terms(population_terms)
        int_clause = format_terms(intervention_terms)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            comp_clause = format_terms(comparison_terms)
            parts.append(comp_clause)

        return " AND ".join(parts)

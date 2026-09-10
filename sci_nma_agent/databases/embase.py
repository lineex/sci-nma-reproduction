"""
Embase Query Builder & REST Session Adapter.
Implements Emtree explosions, field tags (:ti,ab,kw), and Embase clinical trial filters.
"""

from typing import List, Dict, Any, Optional


class EmbaseQueryBuilder:
    """Constructs native Embase search syntax from clinical keywords and Emtree terms."""

    EMBASE_RCT_FILTER = (
        "('randomized controlled trial'/exp OR 'controlled clinical trial'/exp OR "
        "'randomization'/exp OR 'double-blind procedure'/exp OR 'single-blind procedure'/exp OR "
        "'crossover procedure'/exp OR random*:ti,ab OR placebo*:ti,ab OR trial:ti)"
    )

    @classmethod
    def build_query(
        cls,
        population_terms: List[str],
        intervention_terms: List[str],
        comparison_terms: Optional[List[str]] = None,
        emtree_mapping: Optional[Dict[str, str]] = None,
        apply_rct_filter: bool = True,
        year_range: Optional[tuple] = None,
        english_only: bool = True,
        humans_only: bool = True
    ) -> str:
        """
        Build publication-grade Embase search string.
        """
        def format_terms(terms: List[str]) -> str:
            clauses = []
            for t in terms:
                clauses.append(f"'{t}':ti,ab,kw")
                if emtree_mapping and t in emtree_mapping:
                    clauses.append(f"'{emtree_mapping[t]}'/exp")
            return f"({' OR '.join(clauses)})"

        pop_clause = format_terms(population_terms)
        int_clause = format_terms(intervention_terms)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            comp_clause = format_terms(comparison_terms)
            parts.append(comp_clause)

        full_query = " AND ".join(parts)

        if apply_rct_filter:
            full_query = f"({full_query}) AND ({cls.EMBASE_RCT_FILTER})"

        limits = []
        if humans_only:
            limits.append("[humans]/lim")
        if english_only:
            limits.append("[english]/lim")
        if year_range:
            start_yr, end_yr = year_range
            limits.append(f"[{start_yr}-{end_yr}]/py")

        if limits:
            full_query = f"{full_query} AND " + " AND ".join(limits)

        return full_query

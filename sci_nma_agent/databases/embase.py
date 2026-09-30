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

    @staticmethod
    def _format_terms(
        terms: List[str],
        emtree_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        if not terms:
            raise ValueError("Embase search terms must contain at least one value")
        clauses = []
        for term in terms:
            value = str(term).strip()
            if not value:
                continue
            clauses.append(f"'{value}':ti,ab,kw")
            if emtree_mapping and value in emtree_mapping:
                clauses.append(f"'{emtree_mapping[value]}'/exp")
        if not clauses:
            raise ValueError("Embase search terms must contain at least one non-empty value")
        return f"({' OR '.join(clauses)})"

    @classmethod
    def build_concept_clause(
        cls,
        terms: List[str],
        emtree_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        """Return a native Embase concept block without filters or limits."""
        return cls._format_terms(terms, emtree_mapping)

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
        humans_only: bool = True,
        outcome_terms: Optional[List[str]] = None,
    ) -> str:
        """
        Build publication-grade Embase search string.
        """
        pop_clause = cls.build_concept_clause(population_terms, emtree_mapping)
        int_clause = cls.build_concept_clause(intervention_terms, emtree_mapping)
        parts = [pop_clause, int_clause]

        if comparison_terms:
            parts.append(cls.build_concept_clause(comparison_terms, emtree_mapping))
        if outcome_terms:
            parts.append(cls.build_concept_clause(outcome_terms, emtree_mapping))

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

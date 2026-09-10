"""
Cross-Database Query Harmonizer.
Translates a structured PICO definition into native search queries across
PubMed, Embase, Cochrane Library, Web of Science, and Scopus.
"""

from typing import Dict, Any, List, Optional
from .pubmed import PubMedQueryBuilder
from .embase import EmbaseQueryBuilder
from .cochrane import CochraneQueryBuilder
from .wos import WoSQueryBuilder
from .scopus import ScopusQueryBuilder


class QueryHarmonizer:
    """Translates PICO specification into multi-database search strings."""

    @classmethod
    def harmonize(cls, pico: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate search strings for all 4 core databases + Scopus from PICO dictionary.

        pico schema:
        {
            "population": ["septic shock", "severe sepsis"],
            "intervention": ["corticosteroids", "hydrocortisone", "fludrocortisone"],
            "comparison": ["placebo", "standard care"],
            "year_range": [1990, 2026],
            "mesh_mapping": {"septic shock": "Shock, Septic", "corticosteroids": "Adrenal Cortex Hormones"},
            "emtree_mapping": {"septic shock": "septic shock", "corticosteroids": "corticosteroid"}
        }
        """
        pop = pico.get("population", [])
        interv = pico.get("intervention", [])
        comp = pico.get("comparison")
        yr = tuple(pico["year_range"]) if "year_range" in pico else None
        mesh = pico.get("mesh_mapping", {})
        emtree = pico.get("emtree_mapping", {})

        queries = {
            "PubMed": PubMedQueryBuilder.build_query(
                population_terms=pop,
                intervention_terms=interv,
                comparison_terms=comp,
                mesh_mapping=mesh,
                year_range=yr,
                apply_rct_filter=True
            ),
            "Embase": EmbaseQueryBuilder.build_query(
                population_terms=pop,
                intervention_terms=interv,
                comparison_terms=comp,
                emtree_mapping=emtree,
                year_range=yr,
                apply_rct_filter=True
            ),
            "Cochrane_CENTRAL": CochraneQueryBuilder.build_query(
                population_terms=pop,
                intervention_terms=interv,
                comparison_terms=comp,
                mesh_mapping=mesh
            ),
            "Web_of_Science": WoSQueryBuilder.build_query(
                population_terms=pop,
                intervention_terms=interv,
                comparison_terms=comp,
                year_range=yr
            ),
            "Scopus": ScopusQueryBuilder.build_query(
                population_terms=pop,
                intervention_terms=interv,
                comparison_terms=comp,
                year_range=yr
            )
        }
        return queries

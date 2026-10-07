"""
Cross-Database Query Harmonizer.

The harmonizer keeps the high-sensitivity search design separate from the
one-line execution payload. New searches default to population + intervention.
Comparator, outcome, study-design, language, human, and date restrictions are
opt-in and must be explicitly justified in the protocol.
"""

from __future__ import annotations

import json
import hashlib
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pubmed import PubMedQueryBuilder
from .embase import EmbaseQueryBuilder
from .cochrane import CochraneQueryBuilder
from .wos import WoSQueryBuilder
from .scopus import ScopusQueryBuilder


class QueryHarmonizer:
    """Translate a structured PICOS definition into database-native plans."""

    DEFAULT_SEARCH_POLICY = {
        "include_comparator": False,
        "include_outcome": False,
        "include_study_design_filter": False,
        "include_language_limit": False,
        "include_humans_limit": False,
        "include_date_limit": False,
        "include_document_type_limit": False,
    }

    @classmethod
    def _bool_setting(cls, value: Any, field: str) -> bool:
        """Parse a protocol boolean without treating ``"false"`` as true."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        raise ValueError(f"{field} must be a boolean")

    @classmethod
    def _terms(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, dict):
            return cls._terms(value.get("terms", value.get("name", [])))
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @classmethod
    def _first_configured(cls, pico: Dict[str, Any], *keys: str) -> Any:
        """Read a canonical top-level field with protocol-template fallbacks."""
        question = pico.get("question", {})
        if not isinstance(question, dict):
            question = {}

        def has_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (list, tuple, set, dict)):
                return bool(value)
            return True

        for key in keys:
            value = pico.get(key)
            if has_value(value):
                return value
            value = question.get(key)
            if has_value(value):
                return value
        return None

    @classmethod
    def _outcome_terms(cls, pico: Dict[str, Any]) -> List[str]:
        search = pico.get("search", {})
        if not isinstance(search, dict):
            search = {}
        explicit = search.get("outcome_terms", pico.get("outcome_terms"))
        if explicit:
            return cls._terms(explicit)
        outcomes = pico.get("outcomes")
        if isinstance(outcomes, list):
            names = []
            for outcome in outcomes:
                if isinstance(outcome, dict):
                    names.extend(cls._terms(outcome.get("name")))
                else:
                    names.extend(cls._terms(outcome))
            return names
        names = []
        names.extend(cls._terms(pico.get("primary_outcome")))
        names.extend(cls._terms(pico.get("secondary_outcomes")))
        if names:
            return names
        # Do not silently turn the manuscript's outcome narrative into a
        # retrieval block. Outcome searching is opt-in because it can miss
        # eligible studies whose outcomes are absent from title/abstract.
        return []

    @classmethod
    def resolve_search_policy(cls, pico: Dict[str, Any]) -> Dict[str, Any]:
        configured = pico.get("search", {})
        if not isinstance(configured, dict):
            configured = {}
        policy = dict(cls.DEFAULT_SEARCH_POLICY)
        # Resolve each policy target once.  A nested ``search`` setting takes
        # precedence over legacy top-level aliases, and the canonical nested
        # name takes precedence over its aliases.  Iterating aliases one by
        # one would let a later legacy key silently overwrite an explicit
        # nested decision.
        aliases = {
            "include_comparator": ("include_comparator", "search_comparator"),
            "include_outcome": ("include_outcome", "search_outcome"),
            "include_study_design_filter": (
                "include_study_design_filter",
                "study_design_filter",
            ),
            "include_language_limit": ("include_language_limit",),
            "include_humans_limit": ("include_humans_limit", "humans_only"),
            "include_date_limit": ("include_date_limit", "date_limit", "apply_date_limit"),
            "include_document_type_limit": (
                "include_document_type_limit",
                "document_type_limit",
            ),
        }
        for target, sources in aliases.items():
            nested_source = next((source for source in sources if source in configured), None)
            if nested_source is not None:
                policy[target] = cls._bool_setting(
                    configured[nested_source], f"search.{nested_source}"
                )
                continue
            top_level_source = next((source for source in sources if source in pico), None)
            if top_level_source is not None:
                policy[target] = cls._bool_setting(pico[top_level_source], top_level_source)
        policy["outcome_terms_available"] = bool(cls._outcome_terms(pico))
        policy["comparator_terms_available"] = bool(
            cls._terms(cls._first_configured(pico, "comparison", "comparator"))
        )
        policy["comparator_search_rationale"] = str(
            configured.get(
                "comparator_search_rationale",
                pico.get("comparator_search_rationale", ""),
            )
        ).strip()
        policy["outcome_search_rationale"] = str(
            configured.get(
                "outcome_search_rationale",
                pico.get("outcome_search_rationale", ""),
            )
        ).strip()
        policy["restriction_rationale"] = str(
            configured.get(
                "restrictions_and_rationale",
                pico.get("restrictions_and_rationale", ""),
            )
        ).strip()
        return policy

    @classmethod
    def _common_inputs(cls, pico: Dict[str, Any]) -> Dict[str, Any]:
        policy = cls.resolve_search_policy(pico)
        return {
            "population": cls._terms(cls._first_configured(pico, "population")),
            "intervention": cls._terms(
                cls._first_configured(pico, "intervention", "intervention_or_exposure")
            ),
            "comparison": cls._terms(
                cls._first_configured(pico, "comparison", "comparator")
            ) if policy["include_comparator"] else None,
            "outcome": cls._outcome_terms(pico) if policy["include_outcome"] else None,
            "year_range": tuple(pico["year_range"]) if (
                policy["include_date_limit"] and "year_range" in pico
            ) else None,
            "mesh_mapping": pico.get("mesh_mapping", {}),
            "emtree_mapping": pico.get("emtree_mapping", {}),
            "policy": policy,
        }

    @classmethod
    def harmonize(cls, pico: Dict[str, Any]) -> Dict[str, str]:
        """Return one-line execution queries for backward compatibility.

        The one-line values are execution artifacts. Use
        :meth:`harmonize_with_strategy` for the journal/supplement line-by-line
        native syntax and concept-policy record.
        """
        return {
            database: plan["execution_query"]
            for database, plan in cls.harmonize_with_strategy(pico)["databases"].items()
        }

    @classmethod
    def harmonize_with_strategy(cls, pico: Dict[str, Any]) -> Dict[str, Any]:
        """Build executable queries plus database-native line strategies."""
        inputs = cls._common_inputs(pico)
        p = inputs["population"]
        i = inputs["intervention"]
        c = inputs["comparison"]
        o = inputs["outcome"]
        year_range = inputs["year_range"]
        mesh = inputs["mesh_mapping"]
        emtree = inputs["emtree_mapping"]
        policy = inputs["policy"]
        if not p or not i:
            raise ValueError("PICOS search generation requires non-empty population and intervention terms")
        if policy["include_comparator"] and not inputs["comparison"]:
            raise ValueError(
                "include_comparator=True requires non-empty comparison terms"
            )
        if policy["include_comparator"] and not policy["comparator_search_rationale"]:
            raise ValueError(
                "include_comparator=True requires comparator_search_rationale"
            )
        if policy["include_outcome"] and not inputs["outcome"]:
            raise ValueError(
                "include_outcome=True requires non-empty outcome terms"
            )
        if policy["include_outcome"] and not policy["outcome_search_rationale"]:
            raise ValueError(
                "include_outcome=True requires outcome_search_rationale"
            )
        enabled_restrictions = (
            "include_study_design_filter",
            "include_language_limit",
            "include_humans_limit",
            "include_date_limit",
            "include_document_type_limit",
        )
        if any(policy[name] for name in enabled_restrictions) and not policy["restriction_rationale"]:
            raise ValueError(
                "enabled search restrictions require restrictions_and_rationale"
            )
        if policy["include_date_limit"] and not year_range:
            raise ValueError(
                "include_date_limit=True requires year_range"
            )

        pubmed = PubMedQueryBuilder.build_query(
            p, i, c, mesh, apply_rct_filter=policy["include_study_design_filter"],
            year_range=year_range, english_only=policy["include_language_limit"], outcome_terms=o,
        )
        embase = EmbaseQueryBuilder.build_query(
            p, i, c, emtree, apply_rct_filter=policy["include_study_design_filter"],
            year_range=year_range, english_only=policy["include_language_limit"],
            humans_only=policy["include_humans_limit"], outcome_terms=o,
        )
        cochrane = CochraneQueryBuilder.build_query(p, i, c, mesh, outcome_terms=o)
        wos = WoSQueryBuilder.build_query(
            p, i, c, year_range=year_range,
            article_or_review_only=policy["include_document_type_limit"], outcome_terms=o,
        )
        scopus = ScopusQueryBuilder.build_query(
            p, i, c, year_range=year_range,
            article_or_review_only=policy["include_document_type_limit"], outcome_terms=o,
        )
        queries = {
            "PubMed": pubmed,
            "Embase": embase,
            "Cochrane_CENTRAL": cochrane,
            "Web_of_Science": wos,
            "Scopus": scopus,
        }
        builders = {
            "PubMed": cls._pubmed_lines,
            "Embase": cls._embase_lines,
            "Cochrane_CENTRAL": cls._cochrane_lines,
            "Web_of_Science": cls._wos_lines,
            "Scopus": cls._scopus_lines,
        }
        databases = {}
        for database, query in queries.items():
            lines = builders[database](inputs)
            applied, not_applied = cls._restriction_status(database, policy)
            databases[database] = {
                "database": database,
                "execution_query": query,
                "native_lines": lines,
                "restriction_status": {
                    "applied": applied,
                    "not_applied": not_applied,
                },
                "appendix_policy": {
                    "display_final_execution_query": False,
                    "display_native_lines": True,
                    "component_execution": "count_only",
                    "final_combination_execution": "export_full_records",
                    "final_export_scope": "final_combination_only",
                    "execution_artifact": f"search_strategies/{database}_search.txt",
                    "execution_artifact_is_hashed_separately": True,
                    "strategy_status": "planned_generated",
                    "exact_run_record_required": True,
                },
            }
        return {
            "framework": "PICOS",
            "search_policy": policy,
            "concept_blocks": {
                "required": ["P", "I"],
                "optional": ["C", "O"],
                "included": ["P", "I"]
                + (["C"] if c else [])
                + (["O"] if o else []),
                "omitted_by_default": ["C", "O"],
            },
            "databases": databases,
        }

    @staticmethod
    def _restriction_status(
        database: str, policy: Dict[str, Any]
    ) -> tuple[List[str], List[str]]:
        """Describe database-specific restriction application explicitly."""
        applied: List[str] = []
        not_applied: List[str] = []
        if database in {"PubMed", "Embase"}:
            if policy["include_study_design_filter"]:
                applied.append("validated_RCT_design_filter")
        elif policy["include_study_design_filter"]:
            not_applied.append("validated_RCT_design_filter")
        if database in {"Web_of_Science", "Scopus"} and policy["include_document_type_limit"]:
            applied.append("document_type_limit")
        elif policy["include_document_type_limit"]:
            not_applied.append("document_type_limit")
        if database in {"PubMed", "Embase"} and policy["include_language_limit"]:
            applied.append("language_limit")
        elif policy["include_language_limit"]:
            not_applied.append("language_limit")
        if database == "Embase" and policy["include_humans_limit"]:
            applied.append("humans_limit")
        elif policy["include_humans_limit"]:
            not_applied.append("humans_limit")
        if database != "Cochrane_CENTRAL" and policy["include_date_limit"]:
            applied.append("date_limit")
        elif policy["include_date_limit"]:
            not_applied.append("date_limit")
        return applied, not_applied

    @classmethod
    def appendix_safe_strategy(cls, pico: Dict[str, Any]) -> Dict[str, Any]:
        """Return the native line strategy without collapsed execution queries."""
        plan = copy.deepcopy(cls.harmonize_with_strategy(pico))
        for item in plan["databases"].values():
            item.pop("execution_query", None)
        return plan

    @staticmethod
    def _line(number: int, line_type: str, block: str, syntax: str, **extra: Any) -> Dict[str, Any]:
        return {
            "line_number": number,
            "line_type": line_type,
            "concept_block": block,
            "native_syntax": syntax,
            **extra,
        }

    @classmethod
    def _concept_inputs(cls, inputs: Dict[str, Any]) -> List[tuple]:
        blocks = [("P", inputs["population"]), ("I", inputs["intervention"])]
        if inputs["comparison"]:
            blocks.append(("C", inputs["comparison"]))
        if inputs["outcome"]:
            blocks.append(("O", inputs["outcome"]))
        return blocks

    @classmethod
    def _pubmed_lines(cls, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = []
        for number, (block, terms) in enumerate(cls._concept_inputs(inputs), start=1):
            lines.append(cls._line(number, "concept", block, PubMedQueryBuilder.build_concept_clause(terms, inputs["mesh_mapping"])))
        next_number = len(lines) + 1
        if inputs["policy"]["include_study_design_filter"]:
            lines.append(cls._line(next_number, "filter", "S", PubMedQueryBuilder.COCHRANE_RCT_FILTER))
            next_number += 1
        if inputs["policy"]["include_language_limit"]:
            lines.append(cls._line(next_number, "limit", "L", "english[la]"))
            next_number += 1
        if inputs["year_range"]:
            start, end = inputs["year_range"]
            lines.append(cls._line(next_number, "limit", "L", f"({start}:{end}[dp])"))
            next_number += 1
        refs = " AND ".join(f"#{n}" for n in range(1, next_number))
        lines.append(cls._line(next_number, "combination", "ALL", refs, interface_set_syntax=True))
        return lines

    @classmethod
    def _embase_lines(cls, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = []
        for number, (block, terms) in enumerate(cls._concept_inputs(inputs), start=1):
            lines.append(cls._line(number, "concept", block, EmbaseQueryBuilder.build_concept_clause(terms, inputs["emtree_mapping"])))
        next_number = len(lines) + 1
        if inputs["policy"]["include_study_design_filter"]:
            lines.append(cls._line(next_number, "filter", "S", EmbaseQueryBuilder.EMBASE_RCT_FILTER))
            next_number += 1
        limits = []
        if inputs["policy"]["include_humans_limit"]:
            limits.append("[humans]/lim")
        if inputs["policy"]["include_language_limit"]:
            limits.append("[english]/lim")
        if inputs["year_range"]:
            start, end = inputs["year_range"]
            limits.append(f"[{start}-{end}]/py")
        for limit in limits:
            lines.append(cls._line(next_number, "limit", "L", limit))
            next_number += 1
        # Embase.com Search History uses hash-prefixed set references.
        refs = " AND ".join(f"#{n}" for n in range(1, next_number))
        lines.append(cls._line(next_number, "combination", "ALL", refs, interface_set_syntax=True))
        return lines

    @classmethod
    def _cochrane_lines(cls, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = []
        for number, (block, terms) in enumerate(cls._concept_inputs(inputs), start=1):
            lines.append(cls._line(number, "concept", block, CochraneQueryBuilder.build_concept_clause(terms, inputs["mesh_mapping"])))
        number = len(lines) + 1
        refs = " AND ".join(f"#{n}" for n in range(1, number))
        lines.append(cls._line(number, "combination", "ALL", refs, interface_set_syntax=True))
        return lines

    @classmethod
    def _wos_lines(cls, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = []
        for number, (block, terms) in enumerate(cls._concept_inputs(inputs), start=1):
            lines.append(cls._line(number, "concept", block, WoSQueryBuilder._format_field_terms("TS", terms)))
        number = len(lines) + 1
        if inputs["policy"]["include_document_type_limit"]:
            lines.append(cls._line(number, "filter", "S", "DT=(Article OR Review) NOT DT=(Meeting Abstract OR Proceedings Paper)"))
            number += 1
        if inputs["year_range"]:
            start, end = inputs["year_range"]
            lines.append(cls._line(number, "limit", "L", f"PY=({start}-{end})"))
            number += 1
        refs = " AND ".join(f"#{n}" for n in range(1, number))
        lines.append(cls._line(number, "combination", "ALL", refs, interface_set_syntax=True))
        return lines

    @classmethod
    def _scopus_lines(cls, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = []
        for number, (block, terms) in enumerate(cls._concept_inputs(inputs), start=1):
            lines.append(cls._line(number, "concept", block, ScopusQueryBuilder.build_concept_clause(terms)))
        number = len(lines) + 1
        if inputs["policy"]["include_document_type_limit"]:
            lines.append(cls._line(number, "filter", "S", "(DOCTYPE(ar) OR DOCTYPE(re))"))
            number += 1
        if inputs["year_range"]:
            start, end = inputs["year_range"]
            lines.append(cls._line(number, "limit", "L", f"PUBYEAR > {start - 1} AND PUBYEAR < {end + 1}"))
            number += 1
        refs = " AND ".join(f"#{n}" for n in range(1, number))
        lines.append(cls._line(number, "combination", "ALL", refs, interface_set_syntax=True))
        return lines

    @classmethod
    def write_strategy_artifacts(cls, pico: Dict[str, Any], project_dir: str) -> Dict[str, str]:
        """Write internal execution queries and appendix-safe native plans."""
        plan = cls.harmonize_with_strategy(pico)
        root = Path(project_dir).expanduser().resolve()
        search_dir = root / "search_strategies"
        search_dir.mkdir(parents=True, exist_ok=True)
        written = {}
        for database, item in plan["databases"].items():
            query_path = search_dir / f"{database}_search.txt"
            query_bytes = item["execution_query"].encode("utf-8")
            query_path.write_bytes(query_bytes)
            appendix_item = {
                "database": database,
                "framework": plan["framework"],
                "search_policy": plan["search_policy"],
                "concept_blocks": plan["concept_blocks"],
                "native_lines": item["native_lines"],
                "execution_artifact": query_path.relative_to(root).as_posix(),
                "execution_artifact_sha256": hashlib.sha256(query_bytes).hexdigest(),
                "display_final_execution_query": False,
                "component_execution": "count_only",
                "final_combination_execution": "export_full_records",
                "final_export_scope": "final_combination_only",
                "strategy_status": "planned_generated",
                "exact_run_record_required": True,
                "restriction_status": item["restriction_status"],
            }
            strategy_path = search_dir / f"{database}_native_strategy.json"
            strategy_path.write_text(json.dumps(appendix_item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written[database] = str(strategy_path)
        return written

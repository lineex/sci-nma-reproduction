"""
Gate 1: Search Strategy & PRISMA Mathematical Flow Verification Gate.
Enforces Boolean search logic validity and strict mathematical flow conservation (L ≡ 0).
"""

import re
from typing import Dict, Any, List, Tuple


class Gate1SearchFlow:
    """Validator for Gate 1: Search Strategy & PRISMA Flow Conservation."""

    @staticmethod
    def validate_prisma_flow(flow_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate PRISMA 2020 flow numbers for strict mathematical conservation.

        Expected keys in flow_data:
        - databases: Dict[str, int]  (e.g., {'PubMed': 88, 'Embase': 279, 'Cochrane': 117, 'WoS': 210})
        - registries_or_citations: int
        - duplicates_removed: int
        - screening_excluded: int
        - screening_exclusion_reasons: Dict[str, int] (optional)
        - reports_sought: int
        - reports_not_retrieved: int
        - reports_assessed: int
        - fulltext_excluded: int
        - fulltext_exclusion_reasons: Dict[str, int]
        - studies_included: int
        - reports_included: int (optional; report-level flow count)
        - included_study_ids: list[str] (optional; unique study-level count)
        - fulltext_pending: int (optional; reports assessed but not yet classified)
        """
        errors = []
        metrics = {}

        # 1. Total Identified Calculation
        databases = flow_data.get("databases", {})
        db_sum = sum(databases.values())
        registries = flow_data.get("registries_or_citations", 0)
        expected_identified = db_sum + registries

        total_identified = flow_data.get("total_identified", expected_identified)
        if total_identified != expected_identified:
            errors.append(
                f"Identification mismatch: Sum of databases ({db_sum}) + other ({registries}) = "
                f"{expected_identified}, but total_identified is {total_identified}."
            )
        metrics["total_identified"] = total_identified

        # 2. Duplicates & Screening
        duplicates = flow_data.get("duplicates_removed", 0)
        screened = flow_data.get("records_screened", total_identified - duplicates)
        if screened != (total_identified - duplicates):
            errors.append(
                f"Screening mismatch: total_identified ({total_identified}) - duplicates ({duplicates}) = "
                f"{total_identified - duplicates}, but records_screened is {screened}."
            )
        metrics["records_screened"] = screened

        # 3. Screening Exclusion
        screen_excluded = flow_data.get("screening_excluded", 0)
        screen_reasons = flow_data.get("screening_exclusion_reasons", {})
        if screen_reasons and sum(screen_reasons.values()) != screen_excluded:
            errors.append(
                f"Screening exclusion sub-reasons sum ({sum(screen_reasons.values())}) does not equal "
                f"screening_excluded ({screen_excluded})."
            )

        expected_sought = screened - screen_excluded
        sought = flow_data.get("reports_sought", expected_sought)
        if sought != expected_sought:
            errors.append(
                f"Reports sought mismatch: screened ({screened}) - screen_excluded ({screen_excluded}) = "
                f"{expected_sought}, but reports_sought is {sought}."
            )
        metrics["reports_sought"] = sought

        # 4. Retrieval & Assessment
        not_retrieved = flow_data.get("reports_not_retrieved", 0)
        expected_assessed = sought - not_retrieved
        assessed = flow_data.get("reports_assessed", expected_assessed)
        if assessed != expected_assessed:
            errors.append(
                f"Reports assessed mismatch: sought ({sought}) - not_retrieved ({not_retrieved}) = "
                f"{expected_assessed}, but reports_assessed is {assessed}."
            )
        metrics["reports_assessed"] = assessed

        # 5. Fulltext Exclusion & Sub-reasons Sum
        fulltext_excluded = flow_data.get("fulltext_excluded", 0)
        fulltext_reasons = flow_data.get("fulltext_exclusion_reasons", {})
        if fulltext_reasons:
            reasons_sum = sum(fulltext_reasons.values())
            if reasons_sum != fulltext_excluded:
                errors.append(
                    f"Fulltext exclusion sub-reasons sum ({reasons_sum}) does not equal "
                    f"fulltext_excluded ({fulltext_excluded})."
                )

        # Reports and studies are different PRISMA units.  Keep the flow
        # conservation equation at report level, then derive the study count
        # from unique study IDs when the new workflow supplies them.
        pending = flow_data.get("fulltext_pending", 0)
        if not isinstance(pending, int) or pending < 0:
            errors.append("fulltext_pending must be a non-negative integer")
            pending = 0
        expected_reports_included = assessed - fulltext_excluded - pending
        # ``reports_included`` historically also represented the descriptive
        # count of reports belonging to included studies.  Use the explicit
        # flow field for conservation; legacy fixtures remain readable.
        flow_reports_included = flow_data.get(
            "reports_included_in_flow",
            flow_data.get("reports_included", expected_reports_included)
            if "included_study_ids" in flow_data
            else expected_reports_included,
        )
        reports_included = flow_reports_included
        if reports_included != expected_reports_included:
            errors.append(
                f"Included reports mismatch: assessed ({assessed}) - fulltext_excluded ({fulltext_excluded}) "
                f"- fulltext_pending ({pending}) = {expected_reports_included}, "
                f"but reports_included is {reports_included}."
            )
        metrics["reports_included"] = reports_included
        metrics["fulltext_pending"] = pending

        included_ids = flow_data.get("included_study_ids")
        if isinstance(included_ids, list):
            normalized_ids = [str(value).strip() for value in included_ids if str(value).strip()]
            if len(set(normalized_ids)) != len(normalized_ids):
                errors.append("included_study_ids must be unique")
            included = len(set(normalized_ids))
        else:
            # Legacy callers supplied a study count but not a report-to-study
            # map. Preserve that interface while no longer using it to close
            # the report-level flow equation.
            included = flow_data.get("studies_included", reports_included)
            if not isinstance(included, int) or included < 0:
                errors.append("studies_included must be a non-negative integer")
                included = 0
        metrics["studies_included"] = included

        # 7. Global Flow Conservation Loss (L ≡ 0)
        # Flow loss is defined on reports, not unique studies.
        flow_loss = total_identified - (
            duplicates + screen_excluded + not_retrieved + fulltext_excluded
            + pending + reports_included
        )
        metrics["flow_loss"] = flow_loss
        if flow_loss != 0:
            errors.append(f"Global PRISMA flow loss violation: L = {flow_loss} (Expected L ≡ 0).")

        passed = (len(errors) == 0)
        return passed, errors, metrics

    @staticmethod
    def validate_search_syntax(database: str, query: str) -> Tuple[bool, List[str]]:
        """
        Validate boolean syntax, tag formatting, and parentheses balance for medical databases.
        """
        errors = []
        # Check parentheses balance
        open_parens = query.count("(")
        close_parens = query.count(")")
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open vs {close_parens} close.")

        # Check for lowercase boolean operators outside quoted phrases
        # Remove quoted strings first
        unquoted = re.sub(r'"[^"]*"', '', query)
        unquoted = re.sub(r"'[^']*'", '', unquoted)

        for op in [r"\band\b", r"\bor\b", r"\bnot\b"]:
            if re.search(op, unquoted):
                errors.append(f"Lowercase boolean operator detected ('{op.strip(r'b')}') - must be uppercase.")

        # Database specific checks
        db_lower = database.lower()
        if "pubmed" in db_lower:
            # Check for invalid tags
            tags = re.findall(r"\[([a-zA-Z\s/-]+)\]", query)
            valid_tags = {
                "mesh", "mesh terms", "mesh:noexp", "mh", "tiab", "title/abstract",
                "title", "ti", "abstract", "ab", "author", "au", "journal", "ta",
                "publication type", "pt", "date - publication", "dp", "language", "la"
            }
            for tag in tags:
                if tag.strip().lower() not in valid_tags:
                    errors.append(f"Potentially invalid PubMed field tag: [{tag}]")

        elif "embase" in db_lower:
            # Embase typically uses /exp, /de, or :ti,ab,kw
            if "/exp" not in query and ":ti,ab" not in query and "exp " not in query:
                # Warning or notice, not necessarily fatal error
                pass

        elif "cochrane" in db_lower:
            pass

        elif "wos" in db_lower or "web of science" in db_lower:
            # Check for TS=, TI=, etc.
            if not re.search(r"\b(TS|TI|AU|SO|DO|PY)=", query):
                errors.append("Web of Science query lacks field tags (e.g., TS=, TI=).")

        passed = (len(errors) == 0)
        return passed, errors

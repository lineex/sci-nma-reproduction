"""
Web of Science (WoS) Query Builder & Clarivate Starter API Client.
Constructs valid native TS=, TI=, SO= syntax for WoS Core Collection.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

import requests


class WoSQueryBuilder:
    """Construct native Web of Science Core Collection search strings.

    WoS field tags apply to a parenthesized expression.  Emitting one ``TS=``
    tag per term (``TS=(a) OR TS=(b)``) can be rejected by the Query Builder
    after a verification/challenge round-trip, so terms are grouped as
    ``TS=(a OR b)`` before the request is sent.
    """

    _FIELD_TAG = re.compile(r"^[A-Z]{2,5}\s*=", re.IGNORECASE)

    @classmethod
    def _quote_term(cls, term: str) -> str:
        value = str(term).strip()
        if not value:
            raise ValueError("WoS search terms must not be empty")
        # Accept an already-authored advanced expression, but quote ordinary
        # phrases so spaces are treated as one concept in the grouped clause.
        if cls._FIELD_TAG.match(value) or "NEAR/" in value.upper() or " SAME " in value.upper():
            return value
        if value.startswith('"') and value.endswith('"'):
            return value
        return '"' + value.replace('"', '\\"') + '"'

    @classmethod
    def _format_field_terms(cls, field: str, terms: List[str]) -> str:
        if not terms:
            raise ValueError(f"WoS {field} terms must contain at least one value")
        normalized_field = str(field).strip().upper()
        if not re.fullmatch(r"[A-Z]{2,5}", normalized_field):
            raise ValueError(f"Invalid WoS field tag: {field!r}")
        return f"{normalized_field}=({' OR '.join(cls._quote_term(term) for term in terms)})"

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
        """Build a valid native WoS search query.

        A year range wider than five years is accepted for compatibility, but
        callers should partition broad reviews by year because Clarivate warns
        that long ranges can be slow and return unproductive results.
        """
        parts = [
            cls._format_field_terms("TS", population_terms),
            cls._format_field_terms("TS", intervention_terms),
        ]

        if comparison_terms:
            parts.append(cls._format_field_terms("TS", comparison_terms))
        if outcome_terms:
            parts.append(cls._format_field_terms("TS", outcome_terms))

        full_query = " AND ".join(parts)

        if article_or_review_only:
            full_query = f"({full_query}) AND DT=(Article OR Review) NOT DT=(Meeting Abstract OR Proceedings Paper)"

        if year_range:
            if len(year_range) != 2:
                raise ValueError("year_range must contain (start_year, end_year)")
            start_yr, end_yr = (int(year_range[0]), int(year_range[1]))
            if start_yr > end_yr:
                raise ValueError("year_range start must be <= end")
            full_query = f"({full_query}) AND PY=({start_yr}-{end_yr})"

        return full_query

    @classmethod
    def partition_year_range(cls, start_year: int, end_year: int, span: int = 5) -> List[tuple]:
        """Return inclusive year partitions suitable for separate WoS runs."""
        start_year, end_year, span = int(start_year), int(end_year), int(span)
        if start_year > end_year:
            raise ValueError("start_year must be <= end_year")
        if span < 1:
            raise ValueError("span must be at least one year")
        return [
            (start, min(start + span - 1, end_year))
            for start in range(start_year, end_year + 1, span)
        ]

    @classmethod
    def search_starter_api(
        cls,
        query: str,
        api_key: str,
        limit: int = 50,
        page: int = 1,
        max_retries: int = 3,
        timeout_sec: int = 20,
        backoff_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = time.sleep,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        """Query Clarivate's Starter API with observable transient-error handling.

        The previous implementation converted every network/auth/server failure
        into an empty result, which could silently corrupt a PRISMA search count.
        The result now preserves status/error/attempt metadata while retaining
        the original ``count`` and ``records`` keys for callers.
        """
        if not str(query).strip():
            raise ValueError("WoS query must not be empty")
        if not str(api_key).strip():
            raise ValueError("Clarivate API key must not be empty")
        if not 1 <= int(limit) <= 50:
            raise ValueError("WoS Starter API limit must be between 1 and 50")
        if int(page) < 1:
            raise ValueError("WoS Starter API page must be at least 1")
        url = "https://api.clarivate.com/apis/wos-starter/v1/documents"
        headers = {"X-ApiKey": api_key}
        params = {"q": query, "db": "WOS", "limit": int(limit), "page": int(page)}
        client = session or requests
        result: Dict[str, Any] = {
            "count": 0,
            "records": [],
            "status_code": None,
            "attempts": 0,
            "error": None,
            "retryable": False,
        }

        for attempt in range(1, int(max_retries) + 1):
            result["attempts"] = attempt
            try:
                resp = client.get(url, headers=headers, params=params, timeout=timeout_sec)
                result["status_code"] = resp.status_code
                if resp.status_code == 200:
                    data = resp.json()
                    result.update(
                        {
                            "count": data.get("metadata", {}).get("total", 0),
                            "records": data.get("hits", []),
                            "error": None,
                            "retryable": False,
                        }
                    )
                    return result
                retryable = resp.status_code == 429 or 500 <= resp.status_code < 600
                result["retryable"] = retryable
                result["error"] = f"Clarivate WoS API returned HTTP {resp.status_code}"
                if not retryable or attempt >= int(max_retries):
                    return result
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else float(backoff_seconds) * (2 ** (attempt - 1))
                except (TypeError, ValueError):
                    delay = float(backoff_seconds) * (2 ** (attempt - 1))
                sleep_fn(max(0.0, delay))
            except (requests.RequestException, ValueError) as exc:
                result["retryable"] = True
                result["error"] = f"Clarivate WoS API request failed: {exc}"
                if attempt >= int(max_retries):
                    return result
                sleep_fn(max(0.0, float(backoff_seconds) * (2 ** (attempt - 1))))

        return result

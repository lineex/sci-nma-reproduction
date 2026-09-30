from __future__ import annotations

import pytest

from sci_nma_agent.databases.session_manager import (
    BrowserSessionManager,
    InstitutionalSessionStatus,
)
from sci_nma_agent.databases.wos import WoSQueryBuilder


def test_wos_query_builder_groups_terms_under_one_field_tag():
    query = WoSQueryBuilder.build_query(
        ["traumatic hemorrhage", "traumatic haemorrhage", "hemorrhagic shock"],
        ["tranexamic acid", "TXA"],
    )

    assert 'TS=("traumatic hemorrhage" OR "traumatic haemorrhage" OR "hemorrhagic shock")' in query
    assert 'TS=("tranexamic acid" OR "TXA")' in query
    assert query.count("TS=") == 2
    assert 'TS=("traumatic hemorrhage") OR TS=("traumatic haemorrhage")' not in query


def test_wos_query_builder_rejects_empty_terms_and_bad_year_range():
    with pytest.raises(ValueError, match="must contain at least one"):
        WoSQueryBuilder.build_query([], ["intervention"])
    with pytest.raises(ValueError, match="start must be <= end"):
        WoSQueryBuilder.build_query(["population"], ["intervention"], year_range=(2025, 2020))


def test_wos_year_partition_is_inclusive():
    assert WoSQueryBuilder.partition_year_range(2018, 2026, span=5) == [
        (2018, 2022),
        (2023, 2026),
    ]


class _FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return _FakeResponse(503)
        return _FakeResponse(
            200,
            {"metadata": {"total": 1}, "hits": [{"uid": "WOS:1"}]},
        )


def test_wos_api_retry_is_observable_and_does_not_turn_server_error_into_zero():
    session = _FakeSession()
    result = WoSQueryBuilder.search_starter_api(
        "TS=(shock)",
        "API_KEY",
        session=session,
        sleep_fn=lambda _: None,
    )

    assert session.calls == 2
    assert result["status_code"] == 200
    assert result["attempts"] == 2
    assert result["count"] == 1
    assert result["records"] == [{"uid": "WOS:1"}]
    assert result["error"] is None


def test_wos_api_preserves_terminal_http_error():
    class TerminalSession:
        def get(self, *args, **kwargs):
            return _FakeResponse(401)

    result = WoSQueryBuilder.search_starter_api(
        "TS=(shock)",
        "API_KEY",
        session=TerminalSession(),
        sleep_fn=lambda _: None,
    )

    assert result["count"] == 0
    assert result["records"] == []
    assert result["status_code"] == 401
    assert "HTTP 401" in result["error"]
    assert result["retryable"] is False


def test_session_probe_classifies_post_verification_server_error_before_wos_ok():
    manager = BrowserSessionManager()
    status, message = manager.probe_database_access(
        "Web of Science",
        "Clarivate Web of Science Core Collection Search Server.unexpectedError",
        "https://www.webofscience.com/wos/woscc/basic-search",
    )

    assert status == InstitutionalSessionStatus.SERVER_ERROR
    assert "transient server error" in message
    assert manager.is_recoverable_status(status)


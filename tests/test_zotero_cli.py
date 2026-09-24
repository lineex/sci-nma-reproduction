import json
from contextlib import asynccontextmanager, redirect_stdout
from io import StringIO
from types import SimpleNamespace

import pytest

from sci_nma_agent import cli
from sci_nma_agent.databases.zotero_mcp import MCPToolCallError, ToolCallEvidence


def test_zotero_mcp_check_lists_discovered_tools_without_library_calls(monkeypatch):
    @asynccontextmanager
    async def fake_connect(url):
        assert url == "http://127.0.0.1:23120/mcp"
        yield SimpleNamespace(
            tools=[
                SimpleNamespace(
                    as_dict=lambda: {
                        "name": "get_collections",
                        "description": "Read collections",
                        "input_schema": {"type": "object"},
                    }
                )
            ]
        )

    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", fake_connect)
    monkeypatch.setattr(cli.sys, "argv", ["sci-nma-agent", "zotero-mcp-check"])
    output = StringIO()
    with redirect_stdout(output):
        cli.main()

    result = json.loads(output.getvalue())
    assert result["endpoint"] == "http://127.0.0.1:23120/mcp"
    assert result["tools"][0]["name"] == "get_collections"


def test_zotero_mcp_export_persists_through_user_callable_cli(monkeypatch, tmp_path):
    calls = []

    class FakeClient:
        async def export_collection(self, project, collection, page_size, match_by):
            calls.append((project, collection, page_size, match_by))
            return {
                "manifest_path": str(tmp_path / "original_materials/zotero_mcp/manifest.json"),
                "corpus_path": str(tmp_path / "original_materials/zotero_mcp/corpus.jsonl"),
                "pagination_status": "complete",
            }

    @asynccontextmanager
    async def fake_connect(url):
        assert url == "http://127.0.0.1:23120/mcp"
        yield FakeClient()

    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", fake_connect)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "sci-nma-agent",
            "zotero-mcp-export",
            "--project",
            str(tmp_path),
            "--collection",
            "Eligible",
            "--match-by",
            "name",
            "--page-size",
            "25",
        ],
    )
    output = StringIO()
    with redirect_stdout(output), pytest.raises(SystemExit) as exc_info:
        cli.main()

    result = json.loads(output.getvalue())
    assert exc_info.value.code == 0
    assert result["pagination_status"] == "complete"
    assert calls == [(str(tmp_path), "Eligible", 25, "name")]


def test_zotero_mcp_export_returns_nonzero_for_incomplete_paging(monkeypatch, tmp_path):
    class FakeClient:
        async def export_collection(self, project, collection, page_size, match_by):
            return {"pagination_status": "incomplete", "item_count": 3}

    @asynccontextmanager
    async def fake_connect(url):
        yield FakeClient()

    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", fake_connect)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["sci-nma-agent", "zotero-mcp-export", "--project", str(tmp_path), "--collection", "Eligible"],
    )
    output = StringIO()
    with redirect_stdout(output), pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    assert json.loads(output.getvalue())["pagination_status"] == "incomplete"


def test_zotero_mcp_export_reports_mcp_tool_error_separately(monkeypatch, tmp_path):
    class FakeClient:
        async def export_collection(self, project, collection, page_size, match_by):
            raise MCPToolCallError(
                ToolCallEvidence(
                    "get_collection_items",
                    {"collection_key": "COLL1"},
                    SimpleNamespace(isError=True, content=[SimpleNamespace(text="server failure")]),
                    "2026-09-25T00:00:00+00:00",
                )
            )

    @asynccontextmanager
    async def fake_connect(url):
        yield FakeClient()

    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", fake_connect)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["sci-nma-agent", "zotero-mcp-export", "--project", str(tmp_path), "--collection", "Eligible"],
    )
    output = StringIO()
    with redirect_stdout(output), pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert "Zotero MCP server tool error" in output.getvalue()
    assert "server failure" in output.getvalue()

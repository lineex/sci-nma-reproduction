import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from sci_nma_agent.databases.zotero_mcp import (
    AttachmentSelectionRequired,
    CollectionNotFound,
    MCPToolCallError,
    MissingToolCapability,
    PaginationError,
    ZoteroMCPReadClient,
)


def _tool(name, description, properties=None, required=None, annotations=None):
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
        },
        "annotations": {} if annotations is None else annotations,
    }


class MockSession:
    def __init__(self, tools, responses=None):
        self.tools = tools
        self.responses = responses or {}
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        index = len([call for call in self.calls if call[0] == name]) - 1
        response = self.responses.get((name, index), self.responses.get((name, 0)))
        if response is None:
            raise AssertionError(f"No mock response configured for {name} call {index}")
        if callable(response):
            response = response(dict(arguments))
        return response


def _run(coro):
    return asyncio.run(coro)


def test_discovery_exposes_current_tool_names_descriptions_and_schemas():
    raw_tool = _tool("get_item", "Read one Zotero item", {"item_key": {"type": "string"}}, ["item_key"])
    session = MockSession([raw_tool])
    client = ZoteroMCPReadClient(session)

    tools = _run(client.discover_tools())

    assert len(tools) == 1
    assert tools[0].name == "get_item"
    assert tools[0].description == "Read one Zotero item"
    assert tools[0].input_schema["properties"]["item_key"] == {"type": "string"}
    assert tools[0].raw_tool is raw_tool
    assert tools[0].as_dict()["input_schema"] == raw_tool["inputSchema"]
    assert tools[0].read_only_hint is None
    assert tools[0].as_dict()["annotations"] == {}


def test_absent_capability_is_reported_without_calling_other_tools():
    session = MockSession([_tool("list_collections", "List Zotero collections")])
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    with pytest.raises(MissingToolCapability, match="item content"):
        _run(client.read_item_content("ITEM1"))
    with pytest.raises(MissingToolCapability, match="full-text cache status"):
        _run(client.check_fulltext_cache("ITEM1"))
    assert session.calls == []


def test_collection_resolution_matches_exact_name_or_key_and_retains_response():
    raw_response = SimpleNamespace(
        structuredContent={
            "collections": [
                {"key": "COLL1", "name": "Included studies"},
                {"key": "COLL2", "name": "Excluded studies"},
            ]
        },
        content=[],
    )
    session = MockSession(
        [_tool("list_collections", "List Zotero collections")],
        {("list_collections", 0): raw_response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    resolved = _run(client.resolve_collection("Included studies", match_by="name"))

    assert resolved.key == "COLL1"
    assert resolved.name == "Included studies"
    assert resolved.raw_collection == {"key": "COLL1", "name": "Included studies"}
    assert resolved.evidence.raw_response is raw_response
    assert resolved.evidence.provenance["tool_name"] == "list_collections"
    assert session.calls == [("list_collections", {})]
    with pytest.raises(CollectionNotFound):
        _run(client.resolve_collection("not here", match_by="name"))


def test_recursive_collection_listing_maps_optional_query_and_resolves_nested_record():
    response = SimpleNamespace(
        structuredContent={
            "collections": [
                {
                    "key": "PARENT",
                    "name": "Review",
                    "subcollections": [
                        {"key": "CHILD", "name": "Included studies", "children": []}
                    ],
                }
            ]
        },
        content=[],
    )
    session = MockSession(
        [
            _tool(
                "get_collections",
                "List Zotero collections recursively",
                {
                    "q": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "limit": {"type": "integer"},
                },
            )
        ],
        {("get_collections", 0): response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    resolved = _run(client.resolve_collection("Included studies", match_by="name"))

    assert resolved.key == "CHILD"
    assert resolved.name == "Included studies"
    assert session.calls == [
        ("get_collections", {"q": "Included studies", "recursive": True, "limit": 500})
    ]


def test_collection_name_search_maps_optional_q_parameter():
    response = SimpleNamespace(
        structuredContent={"collections": [{"key": "COLL1", "name": "Included studies"}]},
        content=[],
    )
    session = MockSession(
        [_tool("search_collections", "Search Zotero collections", {"q": {"type": "string"}})],
        {("search_collections", 0): response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    resolved = _run(client.resolve_collection("Included studies", match_by="name"))

    assert resolved.key == "COLL1"
    assert session.calls == [("search_collections", {"q": "Included studies"})]


def test_key_resolution_prefers_recursive_listing_over_name_search():
    listing_response = SimpleNamespace(
        structuredContent={"collections": [{"key": "COLLKEY", "name": "Included studies"}]},
        content=[],
    )
    search_response = SimpleNamespace(structuredContent={"collections": []}, content=[])
    session = MockSession(
        [
            _tool(
                "get_collections",
                "List Zotero collections",
                {"q": {"type": "string"}, "recursive": {"type": "boolean"}},
            ),
            _tool("search_collections", "Search collections by name", {"q": {"type": "string"}}),
        ],
        {
            ("get_collections", 0): listing_response,
            ("search_collections", 0): search_response,
        },
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    resolved = _run(client.resolve_collection("COLLKEY", match_by="key"))

    assert resolved.key == "COLLKEY"
    assert session.calls == [("get_collections", {"q": "COLLKEY", "recursive": True})]


def test_direct_collection_lookup_maps_plain_key_schema():
    raw_response = SimpleNamespace(
        structuredContent={"collection": {"key": "COLL1", "name": "Included studies"}},
        content=[],
    )
    session = MockSession(
        [
            _tool(
                "get_collection",
                "Get one collection by key",
                {"key": {"type": "string"}},
                ["key"],
            )
        ],
        {("get_collection", 0): raw_response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    resolved = _run(client.resolve_collection("COLL1", match_by="key"))

    assert resolved.key == "COLL1"
    assert resolved.name == "Included studies"
    assert session.calls == [("get_collection", {"key": "COLL1"})]


def test_direct_collection_lookup_requires_exact_response_identity_and_cardinality():
    wrong_identity = SimpleNamespace(
        structuredContent={"collection": {"key": "OTHER", "name": "Different"}}, content=[]
    )
    session = MockSession(
        [_tool("get_collection", "Get one collection by key", {"key": {"type": "string"}}, ["key"])],
        {("get_collection", 0): wrong_identity},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())
    with pytest.raises(CollectionNotFound) as exc_info:
        _run(client.resolve_collection("COLL1", match_by="key"))
    assert exc_info.value.evidence.raw_response is wrong_identity

    duplicate_response = SimpleNamespace(
        structuredContent={
            "collections": [
                {"key": "COLL1", "name": "Same"},
                {"key": "COLL2", "name": "Same"},
            ]
        },
        content=[],
    )
    session = MockSession(
        [_tool("list_collections", "List Zotero collections")],
        {("list_collections", 0): duplicate_response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())
    with pytest.raises(CollectionNotFound, match="2 exact matches"):
        _run(client.resolve_collection("Same", match_by="name"))


def test_collection_items_page_schema_mapping_and_async_paging():
    list_tool = _tool(
        "get_collection_items",
        "Get Zotero items belonging to a collection",
        {
            "collectionKey": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        ["collectionKey", "offset", "limit"],
    )

    def page_response(arguments):
        start = arguments["offset"]
        # Server caps a requested page of 4 to 2 records.
        stop = min(start + 2, 5)
        return SimpleNamespace(
            structuredContent={
                "items": [{"key": f"I{i}"} for i in range(start, stop)],
                "total": 5,
                "hasMore": stop < 5,
            },
            content=[],
        )

    session = MockSession([list_tool], {("get_collection_items", 0): page_response})
    # Reuse the same factory for each page while keeping responses keyed by call index.
    session.responses = {
        ("get_collection_items", index): page_response for index in range(3)
    }
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=4)]

    pages = _run(collect())

    assert [len(page.raw_response.structuredContent["items"]) for page in pages] == [2, 2, 1]
    assert session.calls == [
        ("get_collection_items", {"collectionKey": "COLL1", "offset": 0, "limit": 4}),
        ("get_collection_items", {"collectionKey": "COLL1", "offset": 2, "limit": 4}),
        ("get_collection_items", {"collectionKey": "COLL1", "offset": 4, "limit": 4}),
    ]


def test_cursor_pagination_uses_next_cursor_and_stops_on_has_more_false():
    tool = _tool(
        "get_collection_items",
        "Get collection items",
        {
            "collection_key": {"type": "string"},
            "cursor": {"type": "string"},
            "limit": {"type": "integer"},
        },
        ["collection_key", "limit"],
    )
    session = MockSession(
        [tool],
        {
            ("get_collection_items", 0): SimpleNamespace(
                structuredContent={"items": [{"key": "I1"}], "nextCursor": "CURSOR2", "hasMore": True},
                content=[],
            ),
            ("get_collection_items", 1): SimpleNamespace(
                structuredContent={"items": [{"key": "I2"}], "hasMore": False}, content=[]
            ),
        },
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=20)]

    pages = _run(collect())
    assert len(pages) == 2
    assert session.calls == [
        ("get_collection_items", {"collection_key": "COLL1", "limit": 20}),
        ("get_collection_items", {"collection_key": "COLL1", "cursor": "CURSOR2", "limit": 20}),
    ]


def test_page_count_field_is_not_treated_as_total_when_has_more_is_true():
    tool = _tool(
        "get_collection_items",
        "Get collection items",
        {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
        ["collection_key", "offset", "limit"],
    )
    session = MockSession(
        [tool],
        {
            ("get_collection_items", 0): SimpleNamespace(
                structuredContent={"items": [{"key": "I1"}, {"key": "I2"}], "count": 2, "hasMore": True},
                content=[],
            ),
            ("get_collection_items", 1): SimpleNamespace(
                structuredContent={"items": [{"key": "I3"}], "count": 1, "hasMore": False},
                content=[],
            ),
        },
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=2)]

    pages = _run(collect())
    assert len(pages) == 2
    assert [call[1]["offset"] for call in session.calls] == [0, 2]


def test_pagination_rejects_rows_exceeding_explicit_total_without_has_more():
    tool = _tool(
        "get_collection_items",
        "Get collection items",
        {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
        ["collection_key", "offset", "limit"],
    )
    response = SimpleNamespace(
        structuredContent={"items": [{"key": "I1"}, {"key": "I2"}], "total": 1},
        content=[],
    )
    session = MockSession([tool], {("get_collection_items", 0): response})
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=20)]

    with pytest.raises(PaginationError, match="exceeding total=1") as exc_info:
        _run(collect())
    assert exc_info.value.evidence.raw_response is response


def test_paging_does_not_silently_stop_on_short_server_capped_pages_without_metadata():
    tool = _tool(
        "get_collection_items",
        "Get collection items",
        {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
        ["collection_key", "offset", "limit"],
    )

    def capped(arguments):
        start = arguments["offset"]
        items = [{"key": f"I{i}"} for i in range(start, min(start + 2, 5))]
        return SimpleNamespace(structuredContent={"items": items}, content=[])

    session = MockSession([tool], {("get_collection_items", 0): capped})
    session.responses = {("get_collection_items", i): capped for i in range(4)}
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=10)]

    pages = _run(collect())
    assert [len(page.raw_response.structuredContent["items"]) for page in pages] == [2, 2, 1, 0]
    assert [call[1]["offset"] for call in session.calls] == [0, 2, 4, 5]


def test_repeated_pages_raise_pagination_error_instead_of_truncating():
    tool = _tool(
        "get_collection_items",
        "Get collection items",
        {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
        ["collection_key", "offset", "limit"],
    )
    repeated = SimpleNamespace(structuredContent={"items": [{"key": "I1"}]}, content=[])
    session = MockSession([tool], {("get_collection_items", 0): repeated})
    session.responses = {("get_collection_items", i): repeated for i in range(3)}
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    async def collect():
        return [page async for page in client.iter_collection_items("COLL1", page_size=10)]

    with pytest.raises(PaginationError, match="same item-key sequence") as exc_info:
        _run(collect())
    assert exc_info.value.evidence.raw_response is repeated


def test_item_content_uses_advertised_schema_and_preserves_raw_mcp_result():
    raw_response = SimpleNamespace(
        structuredContent={"item_key": "ITEM1", "text": "Full-text body"},
        content=[SimpleNamespace(type="text", text="Full-text body")],
    )
    session = MockSession(
        [
            _tool(
                "get_item_fulltext",
                "Read cached full text for a Zotero item",
                {"itemKey": {"type": "string"}},
                ["itemKey"],
            )
        ],
        {("get_item_fulltext", 0): raw_response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    evidence = _run(client.read_item_content("ITEM1"))

    assert evidence.raw_response is raw_response
    assert evidence.tool_name == "get_item_fulltext"
    assert evidence.arguments == {"itemKey": "ITEM1"}
    assert session.calls == [("get_item_fulltext", {"itemKey": "ITEM1"})]


def test_mutation_import_and_tag_tools_are_never_invoked():
    session = MockSession(
        [
            _tool("create_collection", "Create a Zotero collection", {"name": {"type": "string"}}, ["name"]),
            _tool("import_items", "Import items into Zotero"),
            _tool("add_item_tag", "Add a tag to a Zotero item"),
        ]
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    with pytest.raises(MissingToolCapability, match="collection listing or lookup"):
        _run(client.resolve_collection("TARGET"))
    assert session.calls == []


def test_missing_optional_read_only_hint_is_allowed_only_for_read_allowlisted_names():
    response = SimpleNamespace(structuredContent={"item_key": "ITEM1"}, content=[])
    session = MockSession(
        [
            _tool("get_item_details", "Read item metadata", {"item_key": {"type": "string"}}),
            _tool("item_operation", "Read item metadata", {"item_key": {"type": "string"}}),
            _tool("get_item", "Read item, then download and attach a PDF", {"item_key": {"type": "string"}}),
            _tool(
                "get_collection_items",
                "List collection items",
                {"collection_key": {"type": "string"}},
                annotations={"readOnlyHint": False},
            ),
        ],
        {("get_item_details", 0): response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    evidence = _run(client.read_item_details("ITEM1"))
    assert evidence.tool_name == "get_item_details"
    assert session.calls == [("get_item_details", {"item_key": "ITEM1"})]


def test_fulltext_database_selects_only_a_safe_advertised_action_enum():
    tool = _tool(
        "fulltext_database",
        "Read the full-text database or mutate its records, depending on action",
        {
            "item_key": {"type": "string"},
            "action": {
                "type": "string",
                "enum": ["insert_record", "get_fulltext", "delete_record", "read_and_delete"],
            },
        },
        ["item_key", "action"],
    )
    response = SimpleNamespace(structuredContent={"text": "cached text"}, content=[])
    session = MockSession([tool], {("fulltext_database", 0): response})
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    evidence = _run(client.check_fulltext_cache("ITEM1"))

    assert evidence.arguments == {"item_key": "ITEM1", "action": "get_fulltext"}
    assert evidence.raw_response is response
    assert session.calls == [("fulltext_database", {"item_key": "ITEM1", "action": "get_fulltext"})]


def test_fulltext_database_rejects_mixed_read_and_mutation_action():
    tool = _tool(
        "fulltext_database",
        "Read or remove cached full text depending on action",
        {
            "item_key": {"type": "string"},
            "action": {"type": "string", "enum": ["read_and_delete"]},
        },
        ["item_key", "action"],
    )
    session = MockSession([tool])
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    with pytest.raises(MissingToolCapability, match="full-text cache status"):
        _run(client.check_fulltext_cache("ITEM1"))
    assert session.calls == []


def test_content_mode_optional_enum_and_attachment_key_are_schema_mapped():
    tool = _tool(
        "get_content",
        "Read content for a Zotero item",
        {
            "item_key": {"type": "string"},
            "content_mode": {"type": "string", "enum": ["pdf_bytes", "plain_text"]},
            "attachment_key": {"type": "string"},
        },
        ["item_key"],
    )
    response = SimpleNamespace(structuredContent={"text": "body"}, content=[])
    session = MockSession([tool], {("get_content", 0): response})
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    evidence = _run(client.read_item_content("ITEM1", attachment_key="ATT1"))

    assert evidence.arguments == {
        "item_key": "ITEM1",
        "content_mode": "plain_text",
        "attachment_key": "ATT1",
    }


def test_content_read_uses_complete_mode_for_exact_item_and_attachment_schema():
    tool = _tool(
        "get_content",
        "Get full-text content from a Zotero attachment",
        {
            "itemKey": {"type": "string"},
            "attachmentKey": {"type": "string"},
            "mode": {"type": "string", "enum": ["minimal", "preview", "standard", "complete"]},
            "format": {"type": "string", "enum": ["json", "text"]},
        },
        ["itemKey", "attachmentKey"],
    )
    response = SimpleNamespace(structuredContent={"text": "complete document text"}, content=[])
    session = MockSession([tool], {("get_content", 0): response})
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    evidence = _run(client.read_item_content("ITEM1", attachment_key="ATT1"))

    assert evidence.arguments == {
        "itemKey": "ITEM1",
        "attachmentKey": "ATT1",
        "mode": "complete",
        "format": "text",
    }
    assert session.calls == [
        (
            "get_content",
            {"itemKey": "ITEM1", "attachmentKey": "ATT1", "mode": "complete", "format": "text"},
        )
    ]


def test_required_attachment_key_requires_explicit_unambiguous_choice():
    tool = _tool(
        "get_content",
        "Read item content",
        {"item_key": {"type": "string"}, "attachment_key": {"type": "string"}},
        ["item_key", "attachment_key"],
    )
    session = MockSession([tool])
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    with pytest.raises(AttachmentSelectionRequired, match="select a unique attachment"):
        _run(client.read_item_content("ITEM1"))
    assert session.calls == []


def test_is_error_result_raises_distinct_exception_with_raw_evidence():
    tool = _tool("get_item", "Read item", {"item_key": {"type": "string"}}, ["item_key"])
    raw_response = SimpleNamespace(isError=True, content=[SimpleNamespace(text="server says no")])
    session = MockSession([tool], {("get_item", 0): raw_response})
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    with pytest.raises(MCPToolCallError, match="server says no") as exc_info:
        _run(client.read_item_details("ITEM1"))
    assert exc_info.value.evidence.raw_response is raw_response


def test_export_persists_pages_item_evidence_text_hashes_and_explicit_locators(tmp_path):
    tools = [
        _tool("list_collections", "List Zotero collections"),
        _tool(
            "get_collection_items",
            "Get items in a Zotero collection",
            {
                "collection_key": {"type": "string"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            ["collection_key", "offset", "limit"],
        ),
        _tool("get_item_details", "Read item details", {"item_key": {"type": "string"}}, ["item_key"]),
        _tool(
            "get_content",
            "Read item content",
            {
                "item_key": {"type": "string"},
                "attachment_key": {"type": "string"},
                "content_mode": {"type": "string", "enum": ["plain_text", "pdf_bytes"]},
            },
            ["item_key", "attachment_key", "content_mode"],
        ),
    ]
    responses = {
        ("list_collections", 0): SimpleNamespace(
            structuredContent={"collections": [{"key": "COLL1", "name": "Eligible"}]}, content=[]
        ),
        ("get_collection_items", 0): SimpleNamespace(
            structuredContent={
                "items": [{"key": "ITEM1", "title": "Study title"}],
                "total": 1,
                "hasMore": False,
            },
            content=[],
        ),
        ("get_item_details", 0): SimpleNamespace(
            structuredContent={
                "item": {
                    "key": "ITEM1",
                    "attachments": [{"key": "ATT1", "contentType": "application/pdf"}],
                }
            },
            content=[],
        ),
        ("get_content", 0): SimpleNamespace(
            structuredContent={
                "text": "Line one\r\nLine two",
                "page_locators": [{"page": 2, "locator": "Results paragraph"}],
            },
            content=[],
        ),
    }
    session = MockSession(tools, responses)
    client = ZoteroMCPReadClient(session, endpoint="http://localhost:23120/mcp")
    _run(client.discover_tools())

    result = _run(client.export_collection(str(tmp_path), "Eligible", page_size=20, match_by="name"))

    manifest_path = tmp_path / "original_materials" / "zotero_mcp" / "manifest.json"
    corpus_path = tmp_path / "original_materials" / "zotero_mcp" / "corpus.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = json.loads(corpus_path.read_text(encoding="utf-8").splitlines()[0])
    assert result["pagination_status"] == "complete"
    assert manifest["source"]["endpoint"] == "http://localhost:23120/mcp"
    assert manifest["pages"][0]["provenance"]["arguments"] == {
        "collection_key": "COLL1",
        "offset": 0,
        "limit": 20,
    }
    assert manifest["pages"][0]["raw_response_sha256"]
    assert record["item_key"] == "ITEM1"
    assert record["attachment_identity"] == {
        "cardinality": 1,
        "identified_keys": ["ATT1"],
        "missing_key_count": 0,
        "status": "single_attachment",
        "selected_key": "ATT1",
    }
    assert record["content_status"] == "text_extracted"
    assert record["normalized_text"] == "Line one\nLine two"
    assert record["text_sha256"] == hashlib.sha256(b"Line one\nLine two").hexdigest()
    assert record["page_locators"] == [{"page": 2, "locator": "Results paragraph"}]
    assert record["details_evidence"]["raw_response_sha256"]
    assert record["content_evidence"]["provenance"]["arguments"] == {
        "item_key": "ITEM1",
        "attachment_key": "ATT1",
        "content_mode": "plain_text",
    }


def test_export_marks_multiple_attachments_ambiguous_without_selecting_first(tmp_path):
    tools = [
        _tool("list_collections", "List Zotero collections"),
        _tool(
            "get_collection_items",
            "Get collection items",
            {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
            ["collection_key", "offset", "limit"],
        ),
        _tool("get_item_details", "Read item details", {"item_key": {"type": "string"}}, ["item_key"]),
        _tool(
            "get_content",
            "Read item content",
            {"item_key": {"type": "string"}, "attachment_key": {"type": "string"}},
            ["item_key", "attachment_key"],
        ),
    ]
    responses = {
        ("list_collections", 0): SimpleNamespace(
            structuredContent={"collections": [{"key": "COLL1", "name": "Eligible"}]}, content=[]
        ),
        ("get_collection_items", 0): SimpleNamespace(
            structuredContent={"items": [{"key": "ITEM1"}], "hasMore": False}, content=[]
        ),
        ("get_item_details", 0): SimpleNamespace(
            structuredContent={
                "item": {"key": "ITEM1", "attachments": [{"key": "ATT1"}, {"key": "ATT2"}]}
            },
            content=[],
        ),
    }
    session = MockSession(tools, responses)
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    result = _run(client.export_collection(str(tmp_path), "Eligible"))
    record = json.loads(
        (tmp_path / "original_materials" / "zotero_mcp" / "corpus.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    assert result["item_count"] == 1
    assert record["attachment_identity"]["status"] == "multiple_attachments_ambiguous"
    assert record["attachment_identity"]["selected_key"] is None
    assert record["content_status"] == "attachment_identity_ambiguous"
    assert not any(name == "get_content" for name, _ in session.calls)


def test_export_distinguishes_empty_attachment_list_from_unavailable_inventory(tmp_path):
    tools = [
        _tool("list_collections", "List Zotero collections"),
        _tool(
            "get_collection_items",
            "Get collection items",
            {"collection_key": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
            ["collection_key", "offset", "limit"],
        ),
        _tool("get_item_details", "Read item details", {"item_key": {"type": "string"}}, ["item_key"]),
        _tool(
            "get_content",
            "Read item content",
            {"item_key": {"type": "string"}, "attachment_key": {"type": "string"}},
            ["item_key", "attachment_key"],
        ),
    ]
    responses = {
        ("list_collections", 0): SimpleNamespace(
            structuredContent={"collections": [{"key": "COLL1", "name": "Eligible"}]}, content=[]
        ),
        ("get_collection_items", 0): SimpleNamespace(
            structuredContent={"items": [{"key": "ITEM1"}], "hasMore": False}, content=[]
        ),
        ("get_item_details", 0): SimpleNamespace(
            structuredContent={"item": {"key": "ITEM1", "attachments": []}}, content=[]
        ),
    }
    session = MockSession(tools, responses)
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    _run(client.export_collection(str(tmp_path), "Eligible"))

    record = json.loads(
        (tmp_path / "original_materials" / "zotero_mcp" / "corpus.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert record["attachment_identity"]["status"] == "no_attachments"
    assert record["content_status"] == "no_attachments"
    assert not any(name == "get_content" for name, _ in session.calls)


def test_export_persists_collection_resolution_error_and_replaces_stale_snapshot(tmp_path):
    error_response = SimpleNamespace(
        isError=True,
        content=[SimpleNamespace(type="text", text="collection service failed")],
    )
    session = MockSession(
        [_tool("list_collections", "List Zotero collections")],
        {("list_collections", 0): error_response},
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())
    output_dir = tmp_path / "original_materials" / "zotero_mcp"
    output_dir.mkdir(parents=True)
    (output_dir / "manifest.json").write_text('{"run_id":"OLD"}', encoding="utf-8")
    (output_dir / "corpus.jsonl").write_text("stale record\n", encoding="utf-8")

    result = _run(client.export_collection(str(tmp_path), "Eligible"))

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert result["pagination_status"] == "incomplete"
    assert manifest["run_id"] == result["run_id"] != "OLD"
    assert manifest["source"]["collection"]["resolution_status"] == "not_resolved"
    assert manifest["error"]["evidence"]["raw_response"]["isError"] is True
    assert "collection service failed" in manifest["error"]["message"]
    assert (output_dir / "corpus.jsonl").read_text(encoding="utf-8") == ""


def test_export_persists_successful_pages_when_a_later_page_returns_is_error(tmp_path):
    page_error = SimpleNamespace(
        isError=True,
        content=[SimpleNamespace(type="text", text="second page failed")],
    )
    session = MockSession(
        [
            _tool("list_collections", "List Zotero collections"),
            _tool(
                "get_collection_items",
                "Get collection items",
                {
                    "collection_key": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                ["collection_key", "offset", "limit"],
            ),
        ],
        {
            ("list_collections", 0): SimpleNamespace(
                structuredContent={"collections": [{"key": "COLL1", "name": "Eligible"}]}, content=[]
            ),
            ("get_collection_items", 0): SimpleNamespace(
                structuredContent={
                    "items": [{"key": "ITEM1", "title": "Study title"}],
                    "total": 2,
                    "hasMore": True,
                },
                content=[],
            ),
            ("get_collection_items", 1): page_error,
        },
    )
    client = ZoteroMCPReadClient(session)
    _run(client.discover_tools())

    result = _run(client.export_collection(str(tmp_path), "Eligible", page_size=1))

    output_dir = tmp_path / "original_materials" / "zotero_mcp"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (output_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert result["pagination_status"] == "incomplete"
    assert manifest["pagination_status"] == "incomplete"
    assert manifest["page_count"] == 1
    assert manifest["item_count"] == 1
    assert manifest["error"]["evidence"]["raw_response"]["isError"] is True
    assert "second page failed" in manifest["error"]["message"]
    assert rows[0]["item_key"] == "ITEM1"

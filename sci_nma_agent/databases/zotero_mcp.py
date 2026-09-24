"""Read-only client facade for a configured Zotero MCP Streamable HTTP server.

The server's tools are discovered at runtime. This module deliberately does
not encode a particular Zotero MCP tool schema and never invokes tools whose
names indicate a mutation or import operation.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Sequence, Tuple


class ZoteroMCPError(RuntimeError):
    """Base error for the Zotero MCP read facade."""


class MissingToolCapability(ZoteroMCPError):
    """Raised when the connected server does not advertise a usable read tool."""


class CollectionNotFound(ZoteroMCPError):
    """Raised when a collection listing contains no unambiguous match."""

    def __init__(self, message: str, evidence: Optional["ToolCallEvidence"] = None):
        self.evidence = evidence
        super().__init__(message)


class MCPToolCallError(ZoteroMCPError):
    """A server tool returned ``isError``; the raw call remains available."""

    def __init__(self, evidence: "ToolCallEvidence"):
        self.evidence = evidence
        detail = _error_text(evidence.raw_response)
        super().__init__(
            f"Zotero MCP tool {evidence.tool_name!r} returned isError=true"
            + (f": {detail}" if detail else ".")
        )


class PaginationError(ZoteroMCPError):
    """Raised when the advertised paging contract cannot make verified progress."""

    def __init__(self, message: str, evidence: Optional["ToolCallEvidence"] = None):
        self.evidence = evidence
        super().__init__(message)


class AttachmentSelectionRequired(ZoteroMCPError):
    """Raised when a read endpoint requires an attachment key that is ambiguous."""


@dataclass(frozen=True)
class MCPToolDescriptor:
    """A tool as advertised by ``list_tools``, retaining its original object."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    annotations: Mapping[str, Any]
    read_only_hint: Optional[bool]
    raw_tool: Any

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "annotations": dict(self.annotations),
            "read_only_hint": self.read_only_hint,
        }


@dataclass(frozen=True)
class ToolCallEvidence:
    """One MCP read call with the exact raw response retained for audit."""

    tool_name: str
    arguments: Mapping[str, Any]
    raw_response: Any
    called_at: str

    @property
    def provenance(self) -> Dict[str, Any]:
        return {
            "source": "zotero_mcp",
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "called_at": self.called_at,
        }


@dataclass(frozen=True)
class CollectionResolution:
    """Resolved collection identity plus evidence from the resolving call."""

    identifier: str
    key: Optional[str]
    name: Optional[str]
    raw_collection: Any
    evidence: ToolCallEvidence


class ZoteroMCPReadClient:
    """Schema-aware, read-only facade over an initialized MCP client session.

    A session can be injected directly for tests or for hosts that manage MCP
    transport lifetimes themselves. ``connect`` lazily imports the optional
    official MCP SDK and owns a Streamable HTTP session for the context scope.
    """

    _READ_VERBS = {
        "get", "list", "read", "search", "find", "query", "fetch",
        "check", "has", "is", "resolve", "describe", "inspect", "retrieve",
    }
    _MUTATION_TOKENS = {
        "add", "added", "adding", "attach", "attached", "attaches", "attaching",
        "create", "created", "creates", "creating", "delete", "deleted", "deletes",
        "deleting", "download", "downloaded", "downloading", "downloads", "edit",
        "edited", "editing", "edits", "import", "imported", "importing", "imports",
        "insert", "inserted", "inserting", "modify", "modified", "modifies", "modifying",
        "move", "moved", "moves", "moving", "remove", "removed", "removes", "removing",
        "rename", "renamed", "renames", "renaming", "save", "saved", "saves", "saving",
        "set", "sets", "setting", "tag", "tagged", "tagging", "tags", "update",
        "updated", "updates", "updating", "upload", "uploaded", "uploading", "uploads",
        "write", "writes", "wrote", "writing",
    }

    def __init__(self, session: Any, endpoint: Optional[str] = None):
        self._session = session
        self.endpoint = endpoint
        self._tools: Tuple[MCPToolDescriptor, ...] = ()
        self._discovered = False

    @classmethod
    @asynccontextmanager
    async def connect(cls, url: str) -> AsyncIterator["ZoteroMCPReadClient"]:
        """Connect to a Streamable HTTP MCP endpoint using the optional SDK."""
        if sys.version_info < (3, 10):
            raise ZoteroMCPError(
                "Zotero MCP Streamable HTTP support requires Python 3.10 or later."
            )
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ZoteroMCPError(
                "Install the optional MCP dependency with `pip install sci-nma-agent[mcp]`."
            ) from exc

        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                client = cls(session, endpoint=url)
                await client.discover_tools()
                yield client

    @property
    def tools(self) -> Tuple[MCPToolDescriptor, ...]:
        """The latest server-advertised tool list, including read and write tools."""
        return self._tools

    async def discover_tools(self) -> Tuple[MCPToolDescriptor, ...]:
        """Fetch and expose current names, descriptions, and JSON schemas."""
        result = await self._session.list_tools()
        raw_tools = _field(result, "tools", default=[])
        descriptors: List[MCPToolDescriptor] = []
        for raw_tool in raw_tools or []:
            name = str(_field(raw_tool, "name", default="") or "").strip()
            if not name:
                continue
            description = str(_field(raw_tool, "description", default="") or "")
            schema = _field(raw_tool, "inputSchema", "input_schema", default={})
            if not isinstance(schema, Mapping):
                schema = _to_mapping(schema)
            annotations = _field(raw_tool, "annotations", default={})
            if not isinstance(annotations, Mapping):
                annotations = _to_mapping(annotations)
            read_only_hint = _field(annotations, "readOnlyHint", "read_only_hint", default=None)
            descriptors.append(
                MCPToolDescriptor(
                    name=name,
                    description=description,
                    input_schema=dict(schema),
                    annotations=dict(annotations),
                    read_only_hint=read_only_hint if isinstance(read_only_hint, bool) else None,
                    raw_tool=raw_tool,
                )
            )
        self._tools = tuple(descriptors)
        self._discovered = True
        return self._tools

    async def resolve_collection(
        self, identifier: str, match_by: Optional[str] = None
    ) -> CollectionResolution:
        """Resolve a collection by exact name or key using advertised read tools."""
        self._require_discovery()
        if match_by not in (None, "name", "key"):
            raise ValueError("match_by must be 'name', 'key', or None")
        listing = self._select_tool(
            "collection listing",
            lambda tool: _mentions(tool, "collection")
            and (
                _mentions(tool, "list", "get", "read", "fetch")
                or (match_by != "key" and _mentions(tool, "search"))
            ),
            score=lambda tool: 8 * _mentions(tool, "list")
            + 5 * _mentions(tool, "collection")
            + 2 * _mentions(tool, "search"),
        )
        if listing is not None and not _required_args(listing):
            arguments = _map_arguments(
                listing,
                {
                    "identifier": identifier,
                    "collection": identifier,
                    "match_by": match_by,
                    "limit": 500,
                    "recursive": True,
                },
            )
            evidence = await self._invoke(listing, arguments)
            matches = [
                record
                for record in _collection_records_from_response(evidence.raw_response)
                if _collection_matches(record, identifier, match_by)
            ]
            return _resolved_collection(identifier, matches, evidence)

        direct = self._select_tool(
            "collection lookup",
            lambda tool: _mentions(tool, "collection")
            and _mentions(tool, "get", "find", "search", "resolve", "read", "fetch")
            and (match_by != "key" or not _mentions(tool, "search"))
            and _has_identifier_parameter(tool),
            score=lambda tool: 8 * _mentions(tool, "get", "resolve")
            + 5 * _mentions(tool, "collection")
            + 2 * _mentions(tool, "find", "search"),
        )
        if direct is None:
            self._missing("resolve_collection", "a collection listing or lookup read tool")
        if match_by is not None and not _schema_supports_match_by(direct, match_by):
            raise MissingToolCapability(
                f"Tool {direct.name!r} cannot safely enforce match_by={match_by!r}; "
                "its discovered schema has no corresponding name/key selector."
            )
        arguments = _map_arguments(
            direct,
            {"identifier": identifier, "collection": identifier, "match_by": match_by},
        )
        evidence = await self._invoke(direct, arguments)
        records = _records_from_response(evidence.raw_response)
        if not records:
            response = _response_mapping(evidence.raw_response)
            records = [response] if response else []
        matches = [
            record
            for record in records
            if _collection_matches(record, identifier, match_by)
        ]
        return _resolved_collection(identifier, matches, evidence)

    async def list_collection_items(
        self,
        collection: Any,
        offset: int = 0,
        limit: int = 100,
        cursor: Optional[str] = None,
        page: Optional[int] = None,
    ) -> ToolCallEvidence:
        """Read one page from a collection using only schema-supported arguments."""
        self._require_discovery()
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be >= 0 and limit must be > 0")
        tool = self._collection_items_tool()
        arguments = self._collection_item_arguments(
            tool, collection, offset=offset, limit=limit, cursor=cursor, page=page
        )
        return await self._invoke(tool, arguments)

    async def iter_collection_items(
        self, collection: Any, page_size: int = 100, start_offset: int = 0
    ) -> AsyncIterator[ToolCallEvidence]:
        """Yield page evidence while advancing through a schema-supported offset."""
        self._require_discovery()
        if page_size <= 0 or start_offset < 0:
            raise ValueError("page_size must be > 0 and start_offset must be >= 0")
        tool = self._collection_items_tool()
        properties = tool.input_schema.get("properties", {})
        roles = {_argument_role(str(name)) for name in properties} if isinstance(properties, Mapping) else set()
        required_roles = {
            _argument_role(str(name)) for name in _required_args(tool)
        }
        if not roles.intersection({"cursor", "offset", "page"}):
            raise MissingToolCapability(
                "Zotero MCP capability 'iter_collection_items' is not advertised by the available schema: "
                f"tool {tool.name!r} must advertise cursor, page, or offset pagination."
            )
        if "cursor" in required_roles:
            raise MissingToolCapability(
                f"Tool {tool.name!r} requires a cursor before the first page; "
                "the server exposes no initial cursor value."
            )

        use_cursor = "cursor" in roles and not roles.intersection({"offset", "page"})
        use_offset = not use_cursor and "offset" in roles
        use_page = not use_cursor and not use_offset and "page" in roles
        offset = start_offset
        page = max(1, start_offset // page_size + 1)
        cursor = None
        delivered = start_offset
        page_signatures = set()
        pages_read = 0
        while True:
            evidence = await self._invoke(
                tool,
                self._collection_item_arguments(
                    tool,
                    collection,
                    offset=offset,
                    limit=page_size,
                    cursor=cursor,
                    page=page,
                ),
            )
            yield evidence
            pages_read += 1
            if pages_read > 10000:
                raise PaginationError(
                    "Pagination exceeded 10000 pages; stop and audit the server's continuation metadata.",
                    evidence,
                )
            rows = _records_from_response(evidence.raw_response)
            info = _pagination_info(evidence.raw_response)
            signature = _page_item_key_signature(rows)
            if signature is not None and signature in page_signatures:
                raise PaginationError(
                    f"Tool {tool.name!r} repeated a page with the same item-key sequence; pagination made no progress.",
                    evidence,
                )
            if signature is not None:
                page_signatures.add(signature)
            if rows:
                delivered += len(rows)

            next_cursor = info.get("next_cursor")
            has_more = info.get("has_more")
            total = info.get("total")
            if total is not None and delivered > total:
                raise PaginationError(
                    f"Tool {tool.name!r} returned {delivered} items, exceeding total={total}.",
                    evidence,
                )
            if total is not None and has_more is False and delivered != total:
                raise PaginationError(
                    f"Tool {tool.name!r} reports hasMore=false with total={total} but {delivered} items were returned.",
                    evidence,
                )
            if total is not None and has_more is True and delivered >= total:
                raise PaginationError(
                    f"Tool {tool.name!r} reports hasMore=true after {delivered} items reached total={total}.",
                    evidence,
                )
            if has_more is False or (total is not None and delivered >= total and has_more is not True):
                break
            if not rows:
                if next_cursor is not None and use_cursor and str(next_cursor) != str(cursor):
                    cursor = str(next_cursor)
                    continue
                if has_more is True or (total is not None and delivered < total):
                    raise PaginationError(
                        f"Tool {tool.name!r} indicates more items but returned an empty page without a usable continuation.",
                        evidence,
                    )
                break

            if next_cursor is not None and "cursor" in roles and str(next_cursor) != str(cursor):
                use_cursor = True
                use_offset = False
                use_page = False
                cursor = str(next_cursor)
                continue
            if use_cursor:
                if next_cursor is not None and str(next_cursor) != str(cursor):
                    cursor = str(next_cursor)
                    continue
                if has_more is True or (total is not None and delivered < total):
                    raise PaginationError(
                        f"Tool {tool.name!r} indicates more items but returned no new cursor.",
                        evidence,
                    )
                if has_more is None and total is None:
                    raise PaginationError(
                        f"Tool {tool.name!r} returned a cursor page without an end marker or next cursor.",
                        evidence,
                    )
                break
            if use_offset:
                offset += len(rows)
            elif use_page:
                page += 1

    def _collection_items_tool(self) -> MCPToolDescriptor:
        tool = self._select_tool(
            "collection items",
            lambda candidate: _mentions(candidate, "collection")
            and _mentions(candidate, "item", "items", "records")
            and _mentions(candidate, "list", "get", "read", "search", "fetch", "query"),
            score=lambda candidate: 8 * _mentions(candidate, "items")
            + 6 * _mentions(candidate, "collection")
            + 3 * _mentions(candidate, "list", "search"),
        )
        if tool is None:
            self._missing("list_collection_items", "a collection-items read tool")
        return tool

    @staticmethod
    def _collection_item_arguments(
        tool: MCPToolDescriptor,
        collection: Any,
        offset: int,
        limit: int,
        cursor: Optional[str] = None,
        page: Optional[int] = None,
    ) -> Dict[str, Any]:
        return _map_arguments(
            tool,
            {
                "collection": collection,
                "offset": offset,
                "limit": limit,
                "cursor": cursor,
                "page": page,
            },
        )

    async def read_item_details(self, item_key: str) -> ToolCallEvidence:
        """Read metadata/details for one item."""
        return await self._read_item_capability(
            "item details",
            item_key,
            lambda tool: _mentions(tool, "item")
            and _mentions(tool, "detail", "metadata", "get", "read", "fetch", "retrieve"),
            lambda tool: 7 * _mentions(tool, "detail", "metadata")
            + 5 * _mentions(tool, "item")
            + 3 * _mentions(tool, "get", "read"),
        )

    async def read_item_content(
        self, item_key: str, attachment_key: Optional[str] = None
    ) -> ToolCallEvidence:
        """Read item text/full text; this does not trigger an attachment download."""
        return await self._read_item_capability(
            "item content",
            item_key,
            lambda tool: _mentions(tool, "item", "fulltext", "full_text", "content", "text")
            and _mentions(tool, "content", "fulltext", "full_text", "text", "read", "get", "fetch"),
            lambda tool: 9 * _mentions(tool, "fulltext", "full_text")
            + 7 * _mentions(tool, "content", "text")
            + 3 * _mentions(tool, "item", "get", "read"),
            attachment_key=attachment_key,
            content_mode="complete",
            response_format="text",
        )

    async def check_fulltext_cache(
        self, item_key: str, attachment_key: Optional[str] = None
    ) -> ToolCallEvidence:
        """Check cache availability only when the server advertises such a read."""
        return await self._read_item_capability(
            "full-text cache status",
            item_key,
            lambda tool: (
                (
                    _mentions(tool, "cache")
                    and _mentions(tool, "fulltext", "full_text", "text", "content", "attachment")
                    and _mentions(tool, "check", "has", "is", "get", "read", "exists", "status")
                )
                or (_mentions(tool, "fulltext", "full_text") and _mentions(tool, "database")
                    and _has_safe_read_action_schema(tool))
            ),
            lambda tool: 10 * _mentions(tool, "cache")
            + 7 * _mentions(tool, "fulltext", "full_text")
            + 3 * _mentions(tool, "check", "has", "exists", "status")
            + 8 * _mentions(tool, "database"),
            attachment_key=attachment_key,
            action="check",
        )

    async def _read_item_capability(
        self,
        capability: str,
        item_key: str,
        predicate: Any,
        score: Any,
        attachment_key: Optional[str] = None,
        content_mode: Optional[str] = None,
        response_format: Optional[str] = None,
        action: Optional[str] = None,
    ) -> ToolCallEvidence:
        self._require_discovery()
        tool = self._select_tool(capability, predicate, score)
        if tool is None:
            self._missing(capability, f"an advertised {capability} read tool")
        arguments = _map_arguments(
            tool,
            {
                "item": item_key,
                "attachment_key": attachment_key,
                "content_mode": content_mode,
                "response_format": response_format,
                "action": action,
            },
        )
        return await self._invoke(tool, arguments)

    async def export_collection(
        self,
        project_dir: str,
        identifier: str,
        page_size: int = 100,
        match_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write durable MCP provenance and extracted text under the project.

        The export is kept separate from local PDF archival: MCP text responses
        are not treated as attachment bytes, study IDs, or reported facts.
        """
        self._require_discovery()
        output_dir = Path(project_dir).expanduser().resolve() / "original_materials" / "zotero_mcp"
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.json"
        corpus_path = output_dir / "corpus.jsonl"
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        pages: List[Dict[str, Any]] = []
        corpus_records: List[Dict[str, Any]] = []
        resolution: Optional[CollectionResolution] = None
        export_error: Optional[Dict[str, Any]] = None
        pagination_status = "in_progress"

        def persist_snapshot() -> Dict[str, Any]:
            collection = {
                "requested_identifier": identifier,
                "resolution_status": "resolved" if resolution else "not_resolved",
            }
            if resolution is not None:
                collection.update(
                    {
                        "key": resolution.key,
                        "name": resolution.name,
                        "raw_collection": _jsonable(resolution.raw_collection),
                        "resolution_evidence": _evidence_to_record(resolution.evidence),
                    }
                )
            manifest = {
                "schema_version": 1,
                "run_id": run_id,
                "source": {
                    "kind": "zotero_mcp",
                    "endpoint": self.endpoint,
                    "collection": collection,
                },
                "started_at": started_at,
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "pagination_status": pagination_status,
                "error": export_error,
                "page_count": len(pages),
                "item_count": len(corpus_records),
                "text_count": sum(1 for record in corpus_records if record.get("normalized_text")),
                "pages": pages,
                "records": [
                    {
                        "item_key": record.get("item_key"),
                        "content_status": record["content_status"],
                        "text_sha256": record.get("text_sha256"),
                        "attachment_identity": record["attachment_identity"],
                    }
                    for record in corpus_records
                ],
            }
            corpus_text = "".join(
                json.dumps(_jsonable(record), ensure_ascii=False, sort_keys=True) + "\n"
                for record in corpus_records
            )
            # The manifest is the commit marker; an interrupted run remains marked in_progress.
            _atomic_write_text(corpus_path, corpus_text)
            _atomic_write_json(manifest_path, manifest)
            return manifest

        _atomic_write_text(corpus_path, "")
        persist_snapshot()
        try:
            resolution = await self.resolve_collection(identifier, match_by=match_by)
            async for page_evidence in self.iter_collection_items(
                resolution, page_size=page_size
            ):
                page_record = _evidence_to_record(page_evidence)
                pages.append(page_record)
                for row_index, raw_item in enumerate(_records_from_response(page_evidence.raw_response)):
                    item_key = _first_string(
                        raw_item, "key", "itemKey", "item_key", "id", "itemId"
                    )
                    item_record: Dict[str, Any] = {
                        "item_key": item_key,
                        "item_identity_status": "identified" if item_key else "missing_item_key",
                        "collection_key": resolution.key,
                        "collection_name": resolution.name,
                        "page_index": len(pages) - 1,
                        "row_index": row_index,
                        "raw_list_item": _jsonable(raw_item),
                        "list_page_provenance": page_evidence.provenance,
                        "list_page_response_sha256": page_record["raw_response_sha256"],
                        "details_status": "not_attempted",
                        "content_status": "not_attempted",
                        "attachment_identity": {
                            "cardinality": None,
                            "identified_keys": [],
                            "missing_key_count": 0,
                            "status": "not_inspected",
                            "selected_key": None,
                        },
                        "normalized_text": None,
                        "text_sha256": None,
                        "page_locators": [],
                    }
                    details_evidence: Optional[ToolCallEvidence] = None
                    if item_key:
                        try:
                            details_evidence = await self.read_item_details(item_key)
                            item_record["details_status"] = "retrieved"
                            item_record["details_evidence"] = _evidence_to_record(details_evidence)
                        except MissingToolCapability as exc:
                            item_record["details_status"] = "capability_not_advertised"
                            item_record["details_error"] = str(exc)
                        except MCPToolCallError as exc:
                            details_evidence = exc.evidence
                            item_record["details_status"] = "tool_error"
                            item_record["details_evidence"] = _evidence_to_record(exc.evidence)
                            item_record["details_error"] = str(exc)

                    attachment_probe = _attachment_inventory(raw_item)
                    if details_evidence is not None:
                        detail_rows = _records_from_response(details_evidence.raw_response)
                        if detail_rows:
                            detail_inventory = _attachment_inventory(detail_rows[0])
                            if detail_inventory["observed"] or not attachment_probe["observed"]:
                                attachment_probe = detail_inventory
                    attachment_status, selected_attachment = _attachment_status(attachment_probe)
                    item_record["attachment_identity"] = {
                        "cardinality": attachment_probe["cardinality"],
                        "identified_keys": attachment_probe["keys"],
                        "missing_key_count": attachment_probe["missing_key_count"],
                        "status": attachment_status,
                        "selected_key": selected_attachment,
                    }

                    if not item_key:
                        item_record["content_status"] = "not_attempted_missing_item_key"
                    elif attachment_status == "multiple_attachments_ambiguous":
                        item_record["content_status"] = "attachment_identity_ambiguous"
                        item_record["content_error"] = (
                            "Content read skipped because multiple attachments require explicit selection."
                        )
                    elif attachment_status == "attachment_identity_missing":
                        item_record["content_status"] = "attachment_identity_missing"
                        item_record["content_error"] = (
                            "Content read skipped because the attachment has no stable key."
                        )
                    elif attachment_status == "no_attachments":
                        item_record["content_status"] = "no_attachments"
                    elif attachment_status == "attachment_inventory_unavailable":
                        item_record["content_status"] = "attachment_inventory_unavailable"
                    else:
                        try:
                            content_evidence = await self.read_item_content(
                                item_key, attachment_key=selected_attachment
                            )
                            item_record["content_evidence"] = _evidence_to_record(content_evidence)
                            extracted_text, locators = _extract_text_and_locators(
                                content_evidence.raw_response
                            )
                            item_record["normalized_text"] = extracted_text or None
                            item_record["text_sha256"] = (
                                hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
                                if extracted_text
                                else None
                            )
                            item_record["page_locators"] = locators
                            item_record["content_status"] = (
                                "text_extracted" if extracted_text else "retrieved_without_text"
                            )
                        except AttachmentSelectionRequired as exc:
                            item_record["content_status"] = "attachment_selection_required"
                            item_record["content_error"] = str(exc)
                        except MissingToolCapability as exc:
                            item_record["content_status"] = "capability_not_advertised"
                            item_record["content_error"] = str(exc)
                        except MCPToolCallError as exc:
                            item_record["content_status"] = "tool_error"
                            item_record["content_evidence"] = _evidence_to_record(exc.evidence)
                            item_record["content_error"] = str(exc)
                    corpus_records.append(item_record)
            pagination_status = "complete"
        except ZoteroMCPError as exc:
            pagination_status = "incomplete"
            evidence = getattr(exc, "evidence", None)
            export_error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "evidence": _evidence_to_record(evidence) if evidence else None,
            }
        except Exception as exc:
            pagination_status = "failed"
            export_error = {"type": type(exc).__name__, "message": str(exc), "evidence": None}
            raise
        finally:
            manifest = persist_snapshot()
        return {
            "manifest_path": str(manifest_path),
            "corpus_path": str(corpus_path),
            "page_count": len(pages),
            "item_count": len(corpus_records),
            "text_count": manifest["text_count"],
            "pagination_status": manifest["pagination_status"],
            "error": export_error,
            "run_id": run_id,
        }

    def _select_tool(self, capability: str, predicate: Any, score: Any) -> Optional[MCPToolDescriptor]:
        candidates = [tool for tool in self._tools if _is_read_tool(tool) and predicate(tool)]
        if not candidates:
            return None
        return max(candidates, key=lambda tool: (score(tool), tool.name))

    async def _invoke(
        self, tool: MCPToolDescriptor, arguments: Mapping[str, Any]
    ) -> ToolCallEvidence:
        if not _is_read_tool(tool):
            raise ZoteroMCPError(f"Blocked non-read-only MCP tool: {tool.name}")
        response = await self._session.call_tool(tool.name, dict(arguments))
        evidence = ToolCallEvidence(
            tool_name=tool.name,
            arguments=dict(arguments),
            raw_response=response,
            called_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        if _field(response, "isError", "is_error", default=False) is True:
            raise MCPToolCallError(evidence)
        return evidence

    def _require_discovery(self) -> None:
        if not self._discovered:
            raise ZoteroMCPError("Call discover_tools() before using the Zotero MCP facade.")

    @staticmethod
    def _missing(capability: str, requirement: str) -> None:
        raise MissingToolCapability(
            f"Zotero MCP capability {capability!r} is not advertised: server must provide {requirement}."
        )


def _field(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _to_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(by_alias=True)
        return dumped if isinstance(dumped, Mapping) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _tokens(value: str) -> set:
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return set(re.findall(r"[a-z0-9]+", normalized.lower()))


def _mentions(tool: MCPToolDescriptor, *terms: str) -> int:
    haystack = _tokens(tool.name + " " + tool.description)
    matched = 0
    for term in terms:
        term_tokens = _tokens(term)
        if term_tokens and all(
            token in haystack or (len(token) > 2 and token + "s" in haystack)
            for token in term_tokens
        ):
            matched += 1
    return matched


def _is_read_tool(tool: MCPToolDescriptor) -> bool:
    if tool.read_only_hint is False:
        return False
    name_tokens = _tokens(tool.name)
    if name_tokens & ZoteroMCPReadClient._MUTATION_TOKENS:
        return False
    if _schema_has_mutation_property(tool):
        return False
    if name_tokens & ZoteroMCPReadClient._READ_VERBS:
        return not bool(_tokens(tool.description) & ZoteroMCPReadClient._MUTATION_TOKENS)
    is_fulltext_database = (
        "fulltext" in name_tokens
        and "database" in name_tokens
        and _has_safe_read_action_schema(tool)
    )
    return is_fulltext_database


def _schema_has_mutation_property(tool: MCPToolDescriptor) -> bool:
    properties = tool.input_schema.get("properties", {})
    if not isinstance(properties, Mapping):
        return False
    for name in properties:
        if _tokens(str(name)) & ZoteroMCPReadClient._MUTATION_TOKENS:
            return True
    return False


def _required_args(tool: MCPToolDescriptor) -> Sequence[str]:
    required = tool.input_schema.get("required", [])
    return required if isinstance(required, Sequence) and not isinstance(required, str) else []


def _has_identifier_parameter(tool: MCPToolDescriptor) -> bool:
    properties = tool.input_schema.get("properties", {})
    if not isinstance(properties, Mapping):
        return False
    return any(
        _argument_role(str(name)) in {"identifier", "collection"}
        or (str(name).lower() in {"key", "id"} and _mentions(tool, "collection"))
        for name in properties
    )


def _argument_role(name: str) -> Optional[str]:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    if key in {"offset", "start", "skip", "startindex"}:
        return "offset"
    if key in {"limit", "pagesize", "maxresults", "perpage", "count", "take"}:
        return "limit"
    if key == "page":
        return "page"
    if key in {"matchby", "matchtype", "field"}:
        return "match_by"
    if key in {"cursor", "nextcursor", "pagetoken", "continuationtoken"}:
        return "cursor"
    if key in {"format", "contentformat", "responseformat"}:
        return "response_format"
    if key in {"mode", "contentmode", "responsemode"}:
        return "content_mode"
    if key == "action":
        return "action"
    if key == "recursive":
        return "recursive"
    if key in {"attachmentkey", "attachmentid", "attachmentidentifier"}:
        return "attachment_key"
    if key in {"identifier", "query", "q", "searchterm", "term"}:
        return "identifier"
    if "collection" in key or key in {"collection", "collectionid", "collectionkey"}:
        return "collection"
    if key in {"item", "itemid", "itemkey", "key", "id", "itemidentifier"} or "item" in key:
        return "item"
    return None


def _map_arguments(
    tool: MCPToolDescriptor, values: Mapping[str, Any]
) -> Dict[str, Any]:
    properties = tool.input_schema.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}
    arguments: Dict[str, Any] = {}
    for name in properties:
        role = _argument_role(str(name))
        if (
            str(name).lower() in {"key", "id"}
            and _mentions(tool, "collection")
            and "collection" in values
        ):
            role = "collection"
        if role not in values:
            continue
        value = values[role]
        if value is None:
            continue
        if role == "collection":
            value = _collection_argument_value(str(name), value)
        elif role == "item":
            value = _item_argument_value(value)
        elif role == "page":
            if values.get("page") is None:
                offset = int(values.get("offset", 0))
                limit = max(1, int(values.get("limit", 1)))
                value = offset // limit + 1
        elif role in {"content_mode", "action"}:
            purpose = "content" if role == "content_mode" else "cache"
            value = _safe_mode_value(properties.get(name), purpose)
            if value is None:
                continue
        elif role == "response_format":
            value = _safe_response_format_value(properties.get(name), str(value))
            if value is None:
                continue
        elif role == "recursive":
            value = bool(value)
        elif role == "match_by":
            value = _safe_match_by_value(properties.get(name), value)
            if value is None:
                continue
        arguments[str(name)] = value

    missing = [str(name) for name in _required_args(tool) if name not in arguments]
    attachment_missing = [
        str(name)
        for name in missing
        if _argument_role(str(name)) == "attachment_key"
    ]
    if attachment_missing:
        raise AttachmentSelectionRequired(
            f"Tool {tool.name!r} requires an attachment key ({', '.join(attachment_missing)}); "
            "select a unique attachment identity before reading content."
        )
    if missing:
        raise MissingToolCapability(
            f"Tool {tool.name!r} requires unsupported argument(s): {', '.join(missing)}. "
            "The advertised schema does not provide a safe mapping for this operation."
        )
    return arguments


def _collection_argument_value(name: str, collection: Any) -> Any:
    if not isinstance(collection, CollectionResolution):
        return collection
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    if "name" in normalized:
        return collection.name or collection.identifier
    if "key" in normalized or "id" in normalized:
        return collection.key or collection.identifier
    if "name" in normalized:
        return collection.name or collection.identifier
    return collection.key or collection.name or collection.identifier


def _item_argument_value(item: Any) -> Any:
    if isinstance(item, Mapping):
        return _first_string(item, "key", "itemKey", "item_key", "id", "itemId") or item
    return item


def _response_mapping(response: Any) -> Mapping[str, Any]:
    structured = _field(response, "structuredContent", "structured_content", default=None)
    if isinstance(structured, Mapping):
        return structured
    if isinstance(response, Mapping):
        return response
    content = _field(response, "content", default=[])
    for block in content or []:
        text = _field(block, "text", default=None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            return parsed
    return {}


def _records_from_response(response: Any) -> List[Mapping[str, Any]]:
    structured = _field(response, "structuredContent", "structured_content", default=None)
    if structured is None and isinstance(response, Mapping):
        structured = response
    if structured is None:
        content = _field(response, "content", default=[])
        for block in content or []:
            text = _field(block, "text", default=None)
            if isinstance(text, str):
                try:
                    structured = json.loads(text)
                    break
                except json.JSONDecodeError:
                    continue
    if isinstance(structured, list):
        return [record for record in structured if isinstance(record, Mapping)]
    if isinstance(structured, Mapping):
        for key in ("collection", "collections", "item", "items", "results", "data", "records"):
            nested = structured.get(key)
            if isinstance(nested, Mapping):
                return [nested]
            if isinstance(nested, list):
                return [record for record in nested if isinstance(record, Mapping)]
        return [structured]
    return []


def _collection_records_from_response(response: Any) -> List[Mapping[str, Any]]:
    records: List[Mapping[str, Any]] = []
    seen: set[int] = set()

    def visit(record: Mapping[str, Any]) -> None:
        identity = id(record)
        if identity in seen:
            return
        seen.add(identity)
        records.append(record)
        for name in ("children", "subcollections", "collections"):
            nested = record.get(name)
            if isinstance(nested, Mapping):
                visit(nested)
            elif isinstance(nested, list):
                for child in nested:
                    if isinstance(child, Mapping):
                        visit(child)

    for record in _records_from_response(response):
        visit(record)
    return records


def _collection_matches(
    record: Mapping[str, Any], identifier: str, match_by: Optional[str]
) -> bool:
    key_values = ("key", "collectionKey", "collection_key", "id", "collectionId")
    name_values = ("name", "collectionName", "collection_name", "title")
    candidates: List[str] = []
    if match_by in (None, "key"):
        candidates.extend(str(record[name]) for name in key_values if record.get(name) is not None)
    if match_by in (None, "name"):
        candidates.extend(str(record[name]) for name in name_values if record.get(name) is not None)
    needle = identifier.strip()
    return any(candidate.strip() == needle for candidate in candidates)


def _first_string(record: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _resolved_collection(
    identifier: str,
    matches: Sequence[Mapping[str, Any]],
    evidence: ToolCallEvidence,
) -> CollectionResolution:
    if len(matches) != 1:
        detail = "no exact match" if not matches else f"{len(matches)} exact matches"
        raise CollectionNotFound(
            f"Collection identifier {identifier!r} resolved to {detail}; exactly one identity is required.",
            evidence=evidence,
        )
    record = matches[0]
    key, name = _collection_identity(record)
    if not key and not name:
        raise CollectionNotFound(
            f"Collection identifier {identifier!r} matched a record without a nonempty key or name.",
            evidence=evidence,
        )
    return CollectionResolution(identifier, key, name, record, evidence)


def _collection_identity(record: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    key = _first_string(record, "key", "collectionKey", "collection_key", "id", "collectionId")
    name = _first_string(record, "name", "collectionName", "collection_name", "title")
    return key, name


def _schema_supports_match_by(tool: MCPToolDescriptor, match_by: str) -> bool:
    properties = tool.input_schema.get("properties", {})
    if not isinstance(properties, Mapping):
        return False
    for name, definition in properties.items():
        normalized = re.sub(r"[^a-z0-9]", "", str(name).lower())
        if normalized in {"matchby", "matchtype", "field"}:
            enum = definition.get("enum", []) if isinstance(definition, Mapping) else []
            if not enum:
                return True
            requested = "key" if match_by == "key" else "name"
            if any(_normalize_match_choice(value) == requested for value in enum):
                return True
        if match_by == "key" and ("key" in normalized or normalized in {"id", "collectionid"}):
            return True
        if match_by == "name" and "name" in normalized:
            return True
        if normalized in {"identifier", "query", "q", "searchterm", "term"}:
            return True
    return False


def _normalize_match_choice(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", str(value).lower())
    if "key" in normalized or normalized.endswith("id"):
        return "key"
    if "name" in normalized or normalized == "title":
        return "name"
    return normalized


def _safe_match_by_value(schema: Any, requested: Optional[str]) -> Optional[str]:
    if requested is None:
        return None
    if not isinstance(schema, Mapping) or not isinstance(schema.get("enum"), list):
        return requested
    for choice in schema["enum"]:
        if _normalize_match_choice(choice) == requested:
            return str(choice)
    return None


def _safe_mode_value(schema: Any, purpose: str) -> Optional[Any]:
    if not isinstance(schema, Mapping):
        return "text" if purpose == "content" else "check"
    enum = schema.get("enum")
    if enum is None and "const" in schema:
        enum = [schema["const"]]
    if isinstance(enum, list):
        candidates = []
        for value in enum:
            if not isinstance(value, str):
                continue
            if _tokens(value) & ZoteroMCPReadClient._MUTATION_TOKENS:
                continue
            normalized = re.sub(r"[^a-z0-9]", "", value.lower())
            if purpose == "content":
                content_modes = {
                    "complete": 110,
                    "full": 105,
                    "text": 100,
                    "plain": 100,
                    "plaintext": 100,
                    "textplain": 100,
                    "fulltext": 95,
                    "extractedtext": 95,
                    "markdown": 90,
                    "textmarkdown": 90,
                    "html": 80,
                    "content": 75,
                    "fulltextcontent": 75,
                    "extractedcontent": 75,
                }
                rank = content_modes.get(normalized)
                if rank:
                    candidates.append((rank, value))
            else:
                action_ranks = {
                    "check": 100, "status": 95, "exists": 90, "hascache": 88,
                    "read": 85, "get": 82, "query": 80, "search": 78,
                    "list": 75, "fetch": 70, "lookup": 68, "inspect": 60,
                    "cachestatus": 95, "fulltextstatus": 95, "getfulltext": 82,
                    "readfulltext": 85, "queryfulltext": 80, "searchfulltext": 78,
                    "hasfulltext": 88, "getfulltextcache": 82,
                    "checkfulltext": 100, "checkfulltextcache": 100,
                }
                rank = action_ranks.get(normalized, 0)
                if rank:
                    candidates.append((rank, value))
        return max(candidates, default=(0, None), key=lambda item: item[0])[1]
    default = schema.get("default")
    if isinstance(default, str):
        if _tokens(default) & ZoteroMCPReadClient._MUTATION_TOKENS:
            return None
        normalized = re.sub(r"[^a-z0-9]", "", default.lower())
        if purpose == "content" and normalized in {
            "text", "plain", "plaintext", "textplain", "fulltext", "extractedtext",
            "markdown", "textmarkdown", "html", "content", "fulltextcontent", "extractedcontent",
        }:
            return default
        if purpose == "cache" and normalized in {
            "check", "status", "exists", "hascache", "read", "get", "query", "search",
            "list", "fetch", "lookup", "inspect", "cachestatus", "fulltextstatus",
            "getfulltext", "readfulltext", "queryfulltext", "searchfulltext", "hasfulltext",
            "getfulltextcache", "checkfulltext", "checkfulltextcache",
        }:
            return default
    if schema.get("type") == "string" and purpose == "content":
        return "text"
    return None


def _safe_response_format_value(schema: Any, requested: str) -> Optional[Any]:
    if not isinstance(schema, Mapping):
        return requested
    enum = schema.get("enum")
    if enum is None and "const" in schema:
        enum = [schema["const"]]
    if isinstance(enum, list):
        preferences = {"text": 100, "plain": 95, "plaintext": 95, "json": 90}
        candidates = [
            (preferences.get(re.sub(r"[^a-z0-9]", "", str(value).lower()), 0), value)
            for value in enum
            if isinstance(value, str)
        ]
        return max(candidates, default=(0, None), key=lambda item: item[0])[1]
    default = schema.get("default")
    if isinstance(default, str):
        return default
    return requested if schema.get("type") == "string" else None


def _has_safe_read_action_schema(tool: MCPToolDescriptor) -> bool:
    properties = tool.input_schema.get("properties", {})
    if not isinstance(properties, Mapping):
        return False
    for name, definition in properties.items():
        if _argument_role(str(name)) == "action" and _safe_mode_value(definition, "cache") is not None:
            return True
    return False


def _attachment_inventory(value: Any) -> Dict[str, Any]:
    attachments: List[Mapping[str, Any]] = []
    observed = False

    def walk(node: Any) -> None:
        nonlocal observed
        if isinstance(node, Mapping):
            for key, nested in node.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized in {"attachments", "children"} and isinstance(nested, list):
                    observed = True
                    for child in nested:
                        if isinstance(child, Mapping):
                            child_type = str(_field(child, "itemType", "item_type", "type", default="")).lower()
                            if normalized == "attachments" or "attachment" in child_type:
                                attachments.append(child)
                elif isinstance(nested, Mapping):
                    walk(nested)
        elif isinstance(node, list):
            for nested in node:
                walk(nested)

    walk(value)
    keys = [
        key
        for attachment in attachments
        if (key := _first_string(attachment, "key", "attachmentKey", "attachment_key", "id", "attachmentId"))
    ]
    missing_key_count = len(attachments) - len(keys)
    return {
        "cardinality": len(attachments),
        "keys": keys,
        "missing_key_count": missing_key_count,
        "observed": observed,
    }


def _attachment_status(inventory: Mapping[str, Any]) -> Tuple[str, Optional[str]]:
    cardinality = int(inventory.get("cardinality") or 0)
    keys = list(inventory.get("keys") or [])
    missing = int(inventory.get("missing_key_count") or 0)
    if cardinality == 0:
        return ("no_attachments" if inventory.get("observed") else "attachment_inventory_unavailable"), None
    if cardinality > 1:
        return "multiple_attachments_ambiguous", None
    if missing or len(keys) != 1:
        return "attachment_identity_missing", None
    return "single_attachment", keys[0]


def _pagination_info(response: Any) -> Dict[str, Any]:
    data = _response_mapping(response)
    containers = [data]
    for key in ("pagination", "pageInfo", "page_info", "meta"):
        nested = data.get(key)
        if isinstance(nested, Mapping):
            containers.append(nested)
    total = None
    has_more = None
    next_cursor = None
    for container in containers:
        if total is None:
            for name in (
                "total", "totalCount", "total_count", "totalRecords", "total_records",
                "totalResults", "total_results",
            ):
                value = container.get(name)
                if isinstance(value, int) and value >= 0:
                    total = value
                    break
        if has_more is None:
            for name in ("hasMore", "has_more", "hasNextPage", "has_next_page"):
                value = container.get(name)
                if isinstance(value, bool):
                    has_more = value
                    break
        if next_cursor is None:
            for name in ("nextCursor", "next_cursor", "nextPageToken", "next_page_token", "continuationToken"):
                value = container.get(name)
                if value not in (None, ""):
                    next_cursor = str(value)
                    break
    return {"total": total, "has_more": has_more, "next_cursor": next_cursor}


def _error_text(response: Any) -> str:
    data = _response_mapping(response)
    for key in ("error", "message", "detail"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = _field(response, "content", default=[])
    return " ".join(
        text.strip()
        for block in content or []
        if isinstance((text := _field(block, "text", default=None)), str) and text.strip()
    )


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(nested) for nested in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump(mode="json", by_alias=True))
        except TypeError:
            return _jsonable(value.model_dump(by_alias=True))
    if hasattr(value, "dict"):
        return _jsonable(value.dict(by_alias=True))
    if hasattr(value, "__dict__"):
        return _jsonable(
            {key: nested for key, nested in vars(value).items() if not key.startswith("_")}
        )
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _page_item_key_signature(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    keys = [
        _first_string(row, "key", "itemKey", "item_key", "id", "itemId")
        for row in rows
    ]
    if not keys or any(key is None for key in keys):
        return None
    return _canonical_sha256(keys)


def _evidence_to_record(evidence: Optional[ToolCallEvidence]) -> Optional[Dict[str, Any]]:
    if evidence is None:
        return None
    raw_response = _jsonable(evidence.raw_response)
    return {
        "provenance": evidence.provenance,
        "raw_response": raw_response,
        "raw_response_sha256": _canonical_sha256(raw_response),
    }


def _extract_text_and_locators(response: Any) -> Tuple[str, List[Any]]:
    data = _response_mapping(response)
    text_candidates: List[str] = []
    locator_candidates: List[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if isinstance(value, str) and normalized in {
                    "text", "fulltext", "content", "contenttext", "plaintext", "markdown", "extractedtext", "body"
                }:
                    text_candidates.append(value)
                elif isinstance(value, list):
                    if normalized in {"pagelocators", "pagelocations"}:
                        locator_candidates.extend(_jsonable(value))
                    elif normalized in {"pages", "page"}:
                        for page in value:
                            if isinstance(page, Mapping) and any(
                                locator_key in page for locator_key in ("page", "pageNumber", "page_number", "locator")
                            ):
                                locator_candidates.append(_jsonable(page))
                            walk(page)
                    else:
                        for nested in value:
                            walk(nested)
                elif isinstance(value, Mapping):
                    walk(value)
        elif isinstance(node, list):
            for nested in node:
                walk(nested)

    walk(data)
    if not text_candidates:
        for block in _field(response, "content", default=[]) or []:
            text = _field(block, "text", default=None)
            if isinstance(text, str):
                text_candidates.append(text)
    text = "\n\n".join(part.replace("\r\n", "\n").replace("\r", "\n").strip() for part in text_candidates if part.strip())
    return text.strip(), locator_candidates


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
    os.replace(temp, path)

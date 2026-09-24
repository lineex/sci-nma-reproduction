import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sci_nma_agent.databases.zotero_mcp import ToolCallEvidence
from sci_nma_agent.workflow.manual_fulltext_queue import (
    ManualFullTextQueueError,
    build_manual_fulltext_queue,
    confirm_zotero_attachment,
    validate_manual_fulltext_queue,
    validate_manual_fulltext_queue_file,
    _identity_values_match,
)
from sci_nma_agent.workflow.protocol_validation import validate_full_text_retrieval_manifest_file


def _write_json(project: Path, relative: str, data):
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return relative


def _inputs(project: Path, *, identity=True):
    report_1 = {"report_id": "R1", "title": "Exact Report Title", "doi": "10.1000/abc", "year": "2022"}
    report_2 = {"report_id": "R2", "title": "Second Report", "pmid": "12345678", "year": "2023"}
    if not identity:
        report_1 = {"report_id": "R1"}
    study_map = {
        "schema_version": 1,
        "studies": [{"study_id": "S1", "report_ids": ["R1", "R2"], "reports": [report_1, report_2]}],
    }
    map_path = _write_json(project, "corpus/study_report_map.json", study_map)
    screening = {
        "schema_version": 1,
        "study_report_map_sha256": hashlib.sha256((project / map_path).read_bytes()).hexdigest(),
        "records": [
            {
                "study_id": "S1",
                "report_id": "R1",
                "final_decision": "include_for_full_text",
                "reviewer_decisions": [
                    {"reviewer_id": "screen-a", "decision": "include_for_full_text"},
                    {"reviewer_id": "screen-b", "decision": "include_for_full_text"},
                ],
                "report_identity": {"title": "Exact Report Title", "doi": "10.1000/abc", "year": "2022"},
            },
            {
                "study_id": "S1",
                "report_id": "R2",
                "final_decision": "include_for_full_text",
                "reviewer_decisions": [
                    {"reviewer_id": "screen-a", "decision": "include_for_full_text"},
                    {"reviewer_id": "screen-b", "decision": "include_for_full_text"},
                ],
                "report_identity": {"title": "Second Report", "pmid": "12345678", "year": "2023"},
            },
        ],
    }
    if not identity:
        screening["records"][0] = {
            key: value for key, value in screening["records"][0].items()
            if key not in {"report_identity"}
        }
    screening_path = _write_json(project, "screening/title_abstract_screening_manifest.json", screening)
    retrieval = {
        "schema_version": 1,
        "records": [
            {
                "study_id": "S1",
                "report_id": "R1",
                "retrieval_status": "awaiting_manual_acquisition",
                "full_text_review_status": "not_started",
                "fact_status": "not_assessed_pending_full_text",
                "unresolved_reason": "Zotero has not returned an attachment",
                "route_attempts": [{"route": "zotero_mcp", "status": "no_match", "attempted_at": "2026-09-25T00:00:00Z"}],
            },
            {
                "study_id": "S1",
                "report_id": "R2",
                "retrieval_status": "automatic_retrieval_succeeded",
                "full_text_review_status": "not_started",
                "fact_status": "pending_full_text_review",
                "zotero_item_key": "ITEM2",
                "attachment_key": "ATTACH2",
                "attachment_sha256": "a" * 64,
                "identity_match_status": "unique_match",
            },
        ],
    }
    retrieval_path = _write_json(project, "screening/full_text_retrieval_manifest.json", retrieval)
    return map_path, screening_path, retrieval_path


class _FakeClient:
    def __init__(
        self, *, item_key="ITEM1", attachment_key="ATTACH1", doi="10.1000/abc", title="Exact Report Title", year="2022",
        include_item_arg=True, content_item_key=None, include_attachment_arg=True,
        include_mode_arg=True, content_mode="complete", outer_identity=None, attachment_parent_item=None,
    ):
        self.item_key = item_key
        self.attachment_key = attachment_key
        self.doi = doi
        self.title = title
        self.year = year
        self.include_item_arg = include_item_arg
        self.content_item_key = content_item_key
        self.include_attachment_arg = include_attachment_arg
        self.include_mode_arg = include_mode_arg
        self.content_mode = content_mode
        self.outer_identity = dict(outer_identity or {})
        self.attachment_parent_item = attachment_parent_item

    async def read_item_details(self, item_key):
        item = {
            "key": self.item_key,
            "data": {"title": self.title, "DOI": self.doi, "date": self.year},
            "attachments": [{
                "key": self.attachment_key,
                "filename": "paper.pdf",
                **({"parentItem": self.attachment_parent_item} if self.attachment_parent_item else {}),
            }],
        }
        item.update(self.outer_identity)
        return ToolCallEvidence(
            "get_item_details", {"item_key": item_key}, {"item": item}, "2026-09-25T00:00:00Z"
        )

    async def read_item_content(self, item_key, attachment_key=None):
        arguments = {}
        if self.include_item_arg:
            arguments["item_key"] = self.content_item_key or item_key
        if self.include_attachment_arg:
            arguments["attachment_key"] = attachment_key
        if self.include_mode_arg:
            arguments["mode"] = self.content_mode
        return ToolCallEvidence(
            "get_content", arguments,
            {"structuredContent": {"text": "Full text states the primary outcome.", "pageLocators": [{"page": 4}]}},
            "2026-09-25T00:01:00Z",
        )


def test_queue_build_is_report_scoped_identity_bound_and_keeps_partial_availability(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    output = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )
    assert output["record_count"] == 1
    queue = json.loads((tmp_path / output["queue_path"]).read_text(encoding="utf-8"))
    assert [(row["study_id"], row["report_id"]) for row in queue["records"]] == [("S1", "R1")]
    assert queue["records"][0]["queue_status"] == "open"
    assert queue["records"][0]["expected_identity"]["doi"] == "10.1000/abc"
    assert any("DOI=10.1000/abc" in line for line in queue["records"][0]["instructions"])
    assert validate_manual_fulltext_queue_file(
        str(tmp_path / output["queue_path"]), str(tmp_path / retrieval_path),
        str(tmp_path / map_path), str(tmp_path / screening_path),
    ) == []

    queue["records"] = []
    errors = validate_manual_fulltext_queue(queue, json.loads((tmp_path / retrieval_path).read_text(encoding="utf-8")))
    assert any("unresolved but missing a manual queue row" in error for error in errors)


@pytest.mark.parametrize(
    ("bound_input", "expected_error"),
    [
        ("retrieval", "queue hash does not match the retrieval manifest"),
        ("map", "queue hash does not match the approved study/report map"),
        ("screening", "queue hash does not match approved title/abstract screening"),
    ],
)
def test_queue_rejects_stale_bound_inputs(tmp_path, bound_input, expected_error):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    paths = {
        "retrieval": retrieval_path,
        "map": map_path,
        "screening": screening_path,
    }
    input_path = tmp_path / paths[bound_input]
    input_path.write_bytes(input_path.read_bytes() + b"\n")

    errors = validate_manual_fulltext_queue_file(
        str(tmp_path / queue_path), str(tmp_path / retrieval_path),
        str(tmp_path / map_path), str(tmp_path / screening_path),
    )

    assert any(expected_error in error for error in errors)


def test_confirmation_revalidates_exact_item_attachment_and_writes_distinct_hashes(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "downloads" / "paper.pdf"
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b"%PDF-1.7\nselected attachment bytes")
    old_bytes = (tmp_path / retrieval_path).read_bytes()
    result = __import__("asyncio").run(confirm_zotero_attachment(
        project_dir=str(tmp_path),
        retrieval_manifest_path=retrieval_path,
        queue_path=queue_path,
        study_id="S1",
        report_id="R1",
        item_key="ITEM1",
        attachment_key="ATTACH1",
        actor="review-lead",
        identity_evidence="Matched the approved DOI and title to the Zotero item details.",
        attachment_file=str(attachment),
        client=_FakeClient(),
        study_report_map_path=map_path,
        screening_manifest_path=screening_path,
        output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
        output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
        expected_run=2,
    ))

    assert (tmp_path / retrieval_path).read_bytes() == old_bytes
    updated = json.loads(Path(result["retrieval_manifest_path"]).read_text(encoding="utf-8"))
    row = next(item for item in updated["records"] if item["report_id"] == "R1")
    assert row["retrieval_status"] == "manual_confirmed"
    assert row["full_text_review_status"] == "not_started"
    assert row["fact_status"] == "pending_full_text_review"
    assert row["manual_confirmation"]["actor"] == "review-lead"
    confirmation = row["manual_confirmation"]
    item_details_call = confirmation["item_details_call"]
    content_call = confirmation["content_call"]
    assert item_details_call["provenance"]["tool_name"] == "get_item_details"
    assert item_details_call["provenance"]["arguments"] == {"item_key": "ITEM1"}
    assert len(item_details_call["raw_response_sha256"]) == 64
    assert content_call["provenance"]["tool_name"] == "get_content"
    assert content_call["provenance"]["arguments"] == {
        "item_key": "ITEM1", "attachment_key": "ATTACH1", "mode": "complete"
    }
    assert len(content_call["raw_response_sha256"]) == 64
    assert row["local_file_sha256"] == hashlib.sha256(attachment.read_bytes()).hexdigest()
    assert row["local_file_relation_status"] == "unverified_user_supplied"
    archived_attachment = tmp_path / row["local_file_path"]
    assert archived_attachment.read_bytes() == attachment.read_bytes()
    assert row["local_file_sha256"] == hashlib.sha256(archived_attachment.read_bytes()).hexdigest()
    assert row["local_file_name"] == attachment.name
    assert row["manual_confirmation"]["local_file_path"] == row["local_file_path"]
    assert row["manual_confirmation"]["local_file_relation_status"] == "unverified_user_supplied"
    archived_text = tmp_path / row["content_path"]
    expected_text_bytes = b"Full text states the primary outcome.\n"
    assert archived_text.read_bytes() == expected_text_bytes
    assert row["content_file_sha256"] == hashlib.sha256(expected_text_bytes).hexdigest()
    assert validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    ) == []
    manifest_path = Path(result["retrieval_manifest_path"])
    original_manifest_bytes = manifest_path.read_bytes()
    tampered = json.loads(original_manifest_bytes.decode("utf-8"))
    tampered_call = tampered["records"][0]["manual_confirmation"]["content_call"]
    tampered_call["raw_response"]["structuredContent"]["text"] = "Changed MCP response"
    manifest_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    evidence_errors = validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    )
    assert any("content_call.raw_response_sha256 does not match" in error for error in evidence_errors)

    tampered = json.loads(original_manifest_bytes.decode("utf-8"))
    tampered["records"][0]["manual_confirmation"]["content_call"]["provenance"]["arguments"]["attachment_key"] = "OTHER"
    manifest_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    evidence_errors = validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    )
    assert any("content_call.provenance must bind the exact Zotero attachment key" in error for error in evidence_errors)
    manifest_path.write_bytes(original_manifest_bytes)
    assert row["content_sha256"] == hashlib.sha256(b"Full text states the primary outcome.").hexdigest()
    assert row["local_file_sha256"] != row["content_sha256"]
    assert Path(result["content_path"]).is_file()
    archived_text.write_bytes(b"tampered extracted text\n")
    text_errors = validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    )
    assert any("content_file_sha256 does not match" in error for error in text_errors)
    archived_text.write_bytes(expected_text_bytes)
    tampered_text = b"Different text with a matching file hash\n"
    archived_text.write_bytes(tampered_text)
    tampered_manifest = json.loads(original_manifest_bytes.decode("utf-8"))
    tampered_record = tampered_manifest["records"][0]
    tampered_text_hash = hashlib.sha256(tampered_text).hexdigest()
    tampered_record["content_file_sha256"] = tampered_text_hash
    tampered_record["manual_confirmation"]["content_file_sha256"] = tampered_text_hash
    manifest_path.write_text(json.dumps(tampered_manifest, ensure_ascii=False), encoding="utf-8")
    provenance_errors = validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    )
    assert any("content_path does not contain the text extracted" in error for error in provenance_errors)
    manifest_path.write_bytes(original_manifest_bytes)
    archived_text.write_bytes(expected_text_bytes)
    updated_queue = json.loads(Path(result["queue_path"]).read_text(encoding="utf-8"))
    assert next(item for item in updated_queue["records"] if item["report_id"] == "R1")["queue_status"] == "confirmed"
    assert next(item for item in updated_queue["records"] if item["report_id"] == "R1")["confirmation_history"]
    assert validate_manual_fulltext_queue_file(
        result["queue_path"], result["retrieval_manifest_path"],
        str(tmp_path / map_path), str(tmp_path / screening_path),
    ) == []
    archived_attachment.write_bytes(b"changed source bytes")
    errors = validate_full_text_retrieval_manifest_file(
        result["retrieval_manifest_path"], str(tmp_path / map_path), str(tmp_path / screening_path), str(tmp_path)
    )
    assert any("local_file_sha256 does not match the user-supplied local copy" in error for error in errors)


@pytest.mark.parametrize(
    ("client", "item_key", "attachment_key", "expected_error"),
    [
        (_FakeClient(item_key="OTHER"), "ITEM1", "ATTACH1", "did not return exactly the requested item key"),
        (_FakeClient(), "ITEM1", "OTHER_ATTACHMENT", "not currently attached"),
        (_FakeClient(doi="10.1000/wrong"), "ITEM1", "ATTACH1", "does not match the queue's expected identity"),
        (_FakeClient(include_attachment_arg=False), "ITEM1", "ATTACH1", "did not accept the exact selected attachment key"),
        (_FakeClient(include_item_arg=False), "ITEM1", "ATTACH1", "did not accept the exact selected item key"),
        (_FakeClient(content_item_key="OTHER"), "ITEM1", "ATTACH1", "did not accept the exact selected item key"),
        (_FakeClient(content_mode="standard"), "ITEM1", "ATTACH1", "did not accept complete mode"),
        (_FakeClient(include_mode_arg=False), "ITEM1", "ATTACH1", "did not accept complete mode"),
        (_FakeClient(attachment_parent_item="OTHER_PARENT"), "ITEM1", "ATTACH1", "different parent item"),
    ],
)
def test_confirmation_rejects_item_attachment_identity_or_content_ambiguity(
    tmp_path, client, item_key, attachment_key, expected_error
):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")
    with pytest.raises(ManualFullTextQueueError, match=expected_error):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key=item_key, attachment_key=attachment_key,
            actor="review-lead", identity_evidence="I checked the approved DOI and title.",
            attachment_file=str(attachment), client=client, study_report_map_path=map_path,
            screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
            output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
            expected_run=2,
        ))


def test_confirmation_rejects_mismatching_approved_publication_year(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["studies"][0]["reports"][0]["year"] = "2021"
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")
    screening_file = tmp_path / screening_path
    screening_data = json.loads(screening_file.read_text(encoding="utf-8"))
    screening_data["records"][0]["report_identity"]["year"] = "2021"
    screening_file.write_text(json.dumps(screening_data, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")

    with pytest.raises(ManualFullTextQueueError, match="Zotero item year does not match"):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
            actor="review-lead", identity_evidence="I checked the approved report year.",
            attachment_file=str(attachment), client=_FakeClient(year="2022"),
            study_report_map_path=map_path, screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
            output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
            expected_run=2,
        ))


def test_confirmation_distinguishes_different_chinese_titles(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    approved = map_data["studies"][0]["reports"][0]
    approved.pop("doi")
    approved.update({"title": "肺炎早期治疗", "year": "2022"})
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")
    screening_file = tmp_path / screening_path
    screening_data = json.loads(screening_file.read_text(encoding="utf-8"))
    screening_identity = screening_data["records"][0]["report_identity"]
    screening_identity.pop("doi")
    screening_identity.update({"title": "肺炎早期治疗", "year": "2022"})
    screening_file.write_text(json.dumps(screening_data, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")

    with pytest.raises(ManualFullTextQueueError, match="Zotero item identity revalidation failed: Zotero item title does not match"):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
            actor="review-lead", identity_evidence="I checked the approved Chinese title and year.",
            attachment_file=str(attachment), client=_FakeClient(doi="", title="脑卒中治疗"),
            study_report_map_path=map_path, screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
            output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
            expected_run=2,
        ))


@pytest.mark.parametrize(
    ("section", "field", "approved", "conflicting"),
    [
        ("reports", "doi", "10.1000/abc", "10.1000/conflict"),
        ("report_metadata", "pmid", "12345678", "87654321"),
        ("report_details", "title", "Approved report", "Different report"),
        ("report_metadata", "year", "2022", "2021"),
    ],
)
def test_queue_rejects_conflicting_identity_across_map_sections(tmp_path, section, field, approved, conflicting):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    report = map_data["studies"][0]["reports"][0]
    report[field] = approved
    if section == "reports":
        map_data["studies"][0]["reports"].append({"report_id": "R1", field: conflicting})
    else:
        map_data["studies"][0][section] = [{"report_id": "R1", field: conflicting}]
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ManualFullTextQueueError, match=f"identity sources conflict.*{field}"):
        build_manual_fulltext_queue(
            str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
        )


def test_queue_rejects_conflicting_nested_and_top_level_report_identity(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["studies"][0]["reports"][0]["report_identity"] = {"title": "Nested conflicting title"}
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ManualFullTextQueueError, match=r"Conflicting report identity values \(title\)"):
        build_manual_fulltext_queue(
            str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
        )


@pytest.mark.parametrize(
    ("identity_changes", "field"),
    [
        ({"title": "Different Zotero title"}, "title"),
        ({"DOI": "10.1000/conflict"}, "doi"),
        ({"date": "2021"}, "year"),
        ({"name": "Different Zotero alias"}, "title"),
    ],
)
def test_confirmation_rejects_conflicting_zotero_identity_layers_and_aliases(tmp_path, identity_changes, field):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")

    with pytest.raises(ManualFullTextQueueError, match=rf"Conflicting Zotero identity values \({field}\)"):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
            actor="review-lead", identity_evidence="The Zotero identity fields agree with the approved citation.",
            attachment_file=str(attachment), client=_FakeClient(outer_identity=identity_changes),
            study_report_map_path=map_path, screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
            output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
            expected_run=2,
        ))


def test_queue_rejects_conflicting_identity_aliases_within_map_record(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["studies"][0]["reports"][0]["report_title"] = "Different alias title"
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ManualFullTextQueueError, match=r"Conflicting report identity values \(title\)"):
        build_manual_fulltext_queue(
            str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
        )


def test_doi_identity_matching_preserves_structural_punctuation():
    assert _identity_values_match("doi", "10.1000/abc", "https://doi.org/10.1000/ABC")
    assert not _identity_values_match("doi", "10.10/0abc", "10.100/abc")


def test_confirmation_allows_identity_verified_correction_of_candidate_item(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    retrieval_file = tmp_path / retrieval_path
    retrieval = json.loads(retrieval_file.read_text(encoding="utf-8"))
    retrieval["records"][0]["zotero_item_key"] = "WRONG_CANDIDATE"
    retrieval_file.write_text(json.dumps(retrieval, ensure_ascii=False, indent=2), encoding="utf-8")
    map_file = tmp_path / map_path
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["studies"][0]["reports"][0]["year"] = "2022年"
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")

    result = __import__("asyncio").run(confirm_zotero_attachment(
        project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
        study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
        actor="review-lead", identity_evidence="The approved DOI and title identify the corrected Zotero item.",
        attachment_file=str(attachment), client=_FakeClient(year="2022年"), study_report_map_path=map_path,
        screening_manifest_path=screening_path,
        output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
        output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json", expected_run=2,
    ))

    updated = json.loads(Path(result["retrieval_manifest_path"]).read_text(encoding="utf-8"))
    row = next(item for item in updated["records"] if item["report_id"] == "R1")
    assert row["manual_confirmation"]["recorded_candidate_item_key"] == "WRONG_CANDIDATE"
    assert row["manual_confirmation"]["candidate_corrected"] is True
    assert row["manual_confirmation"]["zotero_item_key"] == "ITEM1"
    updated_queue = json.loads(Path(result["queue_path"]).read_text(encoding="utf-8"))
    queue_row = next(item for item in updated_queue["records"] if item["report_id"] == "R1")
    assert queue_row["candidate"]["zotero_item_key"] == "ITEM1"


def test_confirmation_rejects_identical_versioned_output_paths(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")

    with pytest.raises(ManualFullTextQueueError, match="output paths must be different"):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
            actor="review-lead", identity_evidence="The approved DOI identifies the Zotero item.",
            attachment_file=str(attachment), client=_FakeClient(), study_report_map_path=map_path,
            screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/shared.json",
            output_queue_path="screening/retrieval_attempts/run-0002/shared.json", expected_run=2,
        ))


def test_queue_rejects_conflicting_approved_identity_sources(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path)
    screening_file = tmp_path / screening_path
    screening_data = json.loads(screening_file.read_text(encoding="utf-8"))
    screening_data["records"][0]["report_identity"]["doi"] = "10.1000/conflict"
    screening_file.write_text(json.dumps(screening_data, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ManualFullTextQueueError, match="identity sources conflict"):
        build_manual_fulltext_queue(
            str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
        )


def test_confirmation_requires_identity_from_approved_sources(tmp_path):
    map_path, screening_path, retrieval_path = _inputs(tmp_path, identity=False)
    queue_path = build_manual_fulltext_queue(
        str(tmp_path), retrieval_path, map_path, screening_path, "screening/manual_fulltext_queue.json"
    )["queue_path"]
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"PDF bytes")
    with pytest.raises(ManualFullTextQueueError, match="Queue identity does not match the approved report identity evidence"):
        __import__("asyncio").run(confirm_zotero_attachment(
            project_dir=str(tmp_path), retrieval_manifest_path=retrieval_path, queue_path=queue_path,
            study_id="S1", report_id="R1", item_key="ITEM1", attachment_key="ATTACH1",
            actor="review-lead", identity_evidence="I verified the report in Zotero.",
            attachment_file=str(attachment), client=_FakeClient(), study_report_map_path=map_path,
            screening_manifest_path=screening_path,
            output_manifest_path="screening/retrieval_attempts/run-0002/full_text_retrieval_manifest.json",
            output_queue_path="screening/retrieval_attempts/run-0002/manual_fulltext_queue.json",
            expected_run=2,
        ))

"""Preflight validation for a project-specific systematic review protocol."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Union

from ..databases.zotero_mcp import _argument_role, _extract_text_and_locators


_PLACEHOLDERS = {
    "todo", "tbd", "unknown", "fill in", "fill this in", "adjudicator",
    "reviewer", "screener", "extractor",
}
_TOKEN_PLACEHOLDER = re.compile(r"^(?:[A-Z][A-Z0-9]*_)+[A-Z0-9]+$")
_RETRIEVAL_STATES = {
    "not_started",
    "automatic_retrieval_succeeded",
    "automatic_retrieval_failed",
    "awaiting_manual_acquisition",
    "manual_acquired_unconfirmed",
    "manual_confirmed",
    "not_retrieved_after_all_routes",
    "identity_ambiguous",
    "attachment_ambiguous",
}
_REVIEW_STATES = {
    "not_started",
    "pending_independent_review",
    "review_in_progress",
    "complete_after_adjudication",
}
_FACT_STATES = {
    "not_assessed_pending_full_text",
    "pending_full_text_review",
    "reported",
    "not_reported_in_reviewed_report",
    "not_reported_after_all_linked_sources_review",
    "cannot_tell_after_full_text_review",
    "not_applicable",
}
_RETRIEVED_STATES = {"automatic_retrieval_succeeded", "manual_confirmed"}
_REVIEWED_FACT_STATES = {
    "reported",
    "not_reported_in_reviewed_report",
    "not_reported_after_all_linked_sources_review",
    "cannot_tell_after_full_text_review",
    "not_applicable",
}
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


def _is_filled(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.strip()
        return bool(
            normalized
            and normalized.casefold() not in _PLACEHOLDERS
            and not _TOKEN_PLACEHOLDER.fullmatch(normalized)
            and not (normalized.startswith("<") and normalized.endswith(">"))
        )
    return False


def _manual_mcp_call_errors(
    call: Any,
    prefix: str,
    expected_item_key: str,
    expected_attachment_key: Optional[str] = None,
) -> List[str]:
    errors: List[str] = []
    if not isinstance(call, dict):
        return [f"{prefix} must retain an MCP call record"]
    provenance = call.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("source") != "zotero_mcp"
        or not _is_filled(provenance.get("tool_name"))
        or not _is_filled(provenance.get("called_at"))
    ):
        errors.append(f"{prefix}.provenance must identify the Zotero MCP tool and call time")
    raw_response = call.get("raw_response")
    expected_hash = call.get("raw_response_sha256")
    if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
        errors.append(f"{prefix}.raw_response_sha256 must be a SHA-256 hash")
    else:
        try:
            canonical = json.dumps(raw_response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        except (TypeError, ValueError):
            errors.append(f"{prefix}.raw_response must be JSON serializable")
        else:
            if actual_hash != expected_hash.lower():
                errors.append(f"{prefix}.raw_response_sha256 does not match its raw_response")
    arguments = provenance.get("arguments") if isinstance(provenance, dict) else None
    if not isinstance(arguments, dict):
        errors.append(f"{prefix}.provenance.arguments must be an object")
        return errors
    roles: Dict[str, str] = {}
    for name, value in arguments.items():
        role = _argument_role(str(name))
        if role not in {"item", "attachment_key", "content_mode"}:
            continue
        normalized = str(value).strip()
        if role in roles and roles[role] != normalized:
            errors.append(f"{prefix}.provenance contains conflicting {role} arguments")
        roles[role] = normalized
    if roles.get("item") != expected_item_key:
        errors.append(f"{prefix}.provenance must bind the exact Zotero item key")
    if expected_attachment_key is not None:
        if roles.get("attachment_key") != expected_attachment_key:
            errors.append(f"{prefix}.provenance must bind the exact Zotero attachment key")
        if roles.get("content_mode", "").casefold() != "complete":
            errors.append(f"{prefix}.provenance must request complete attachment content")
    return errors


def _value(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _need_text(data: Dict[str, Any], path: str, errors: List[str]) -> None:
    if not _is_filled(_value(data, path)):
        errors.append(f"{path} must be completed with a project-specific value")


def _need_list(data: Dict[str, Any], path: str, errors: List[str], minimum: int = 1) -> None:
    value = _value(data, path)
    if not isinstance(value, list) or len(value) < minimum or any(not _is_filled(item) for item in value):
        errors.append(f"{path} must contain at least {minimum} completed item(s)")


def _need_two_distinct(data: Dict[str, Any], path: str, errors: List[str]) -> None:
    value = _value(data, path)
    if (
        not isinstance(value, list)
        or len(value) < 2
        or any(not _is_filled(item) for item in value[:2])
        or len({str(item).strip().casefold() for item in value[:2]}) != 2
    ):
        errors.append(f"{path} must name two distinct, non-placeholder reviewers")


def validate_full_text_fact_state(
    retrieval_status: str,
    review_status: str,
    fact_status: str,
    fact_scope: str = "report",
    all_linked_sources_reviewed: bool = False,
) -> List[str]:
    """Validate one fact without turning missing access into missing evidence."""
    errors: List[str] = []
    if retrieval_status not in _RETRIEVAL_STATES:
        errors.append(f"unknown retrieval_status: {retrieval_status}")
    if review_status not in _REVIEW_STATES:
        errors.append(f"unknown full_text_review_status: {review_status}")
    if fact_status not in _FACT_STATES:
        errors.append(f"unknown fact_status: {fact_status}")
    if fact_scope not in {"report", "study"}:
        errors.append(f"unknown fact_scope: {fact_scope}")
    if not isinstance(all_linked_sources_reviewed, bool):
        errors.append("all_linked_sources_reviewed must be boolean")
    if errors:
        return errors

    if retrieval_status not in _RETRIEVED_STATES:
        if fact_status != "not_assessed_pending_full_text":
            errors.append("an unconfirmed or unavailable report must remain not_assessed_pending_full_text")
        if review_status != "not_started":
            errors.append("full-text review cannot start before retrieval succeeds and any manual attachment is confirmed")
    elif review_status != "complete_after_adjudication":
        if fact_status != "pending_full_text_review":
            errors.append("a retrieved report awaiting review must use pending_full_text_review")
    elif fact_status not in _REVIEWED_FACT_STATES:
        errors.append("a completed, adjudicated full-text review requires a reviewed fact status")
    if fact_status == "not_reported_in_reviewed_report" and fact_scope != "report":
        errors.append("not_reported_in_reviewed_report is a report-level status")
    if fact_status == "not_reported_after_all_linked_sources_review":
        if fact_scope != "study":
            errors.append("not_reported_after_all_linked_sources_review is a study-level status")
        if not all_linked_sources_reviewed:
            errors.append("study-level non-reporting requires all identified linked sources to be reviewed")
    if (
        fact_status == "cannot_tell_after_full_text_review"
        and fact_scope == "study"
        and not all_linked_sources_reviewed
    ):
        errors.append("study-level cannot-tell status requires all identified linked sources to be reviewed")
    return errors


def validate_full_text_retrieval_manifest(
    manifest: Dict[str, Any],
    study_report_map: Optional[Dict[str, Any]] = None,
    screening_scope: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Validate the machine-readable report retrieval ledger before stage review."""
    errors: List[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["full-text retrieval manifest schema_version must be 1"]
    records = manifest.get("records")
    if not isinstance(records, list) or (not records and screening_scope is None):
        return ["full-text retrieval manifest records must be a list matching the approved reports-sought scope"]

    seen_reports: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("study_id", "report_id"):
            if not _is_filled(record.get(field)):
                errors.append(f"{prefix}.{field} is required")
        report_key = (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip())
        if report_key in seen_reports:
            errors.append(f"{prefix} duplicates a study/report record")
        seen_reports.add(report_key)
        retrieval = record.get("retrieval_status")
        review = record.get("full_text_review_status")
        default_fact = (
            "pending_full_text_review" if retrieval in _RETRIEVED_STATES
            else "not_assessed_pending_full_text"
        )
        errors.extend(
            f"{prefix}: {error}"
            for error in validate_full_text_fact_state(retrieval, review, record.get("fact_status", default_fact))
        )
        if review != "not_started":
            errors.append(f"{prefix}.full_text_review_status must be not_started in the retrieval stage")

        if retrieval in _RETRIEVED_STATES or retrieval == "manual_acquired_unconfirmed":
            if not _is_filled(record.get("zotero_item_key")):
                errors.append(f"{prefix}.zotero_item_key is required for an attached report")
            if not _is_filled(record.get("attachment_key")):
                errors.append(f"{prefix}.attachment_key is required for an attached report")
            if not (_SHA256.fullmatch(str(record.get("attachment_sha256", "")))
                    or _SHA256.fullmatch(str(record.get("content_sha256", "")))):
                errors.append(f"{prefix} requires a verified attachment_sha256 or content_sha256")

        if retrieval == "automatic_retrieval_succeeded":
            if record.get("identity_match_status") != "unique_match":
                errors.append(f"{prefix} automatic retrieval requires a unique item/attachment identity match")
        elif retrieval == "manual_confirmed":
            confirmation = record.get("manual_confirmation")
            if (
                not isinstance(confirmation, dict)
                or not _is_filled(confirmation.get("actor"))
                or not _is_filled(confirmation.get("confirmed_at"))
            ):
                errors.append(f"{prefix}.manual_confirmation must record the confirming user and timestamp")
            local_file_path = record.get("local_file_path")
            local_file_name = record.get("local_file_name")
            content_path = record.get("content_path")
            if not _is_safe_project_relative_path(content_path):
                errors.append(f"{prefix}.content_path must be a project-relative extracted-text path")
            if not _SHA256.fullmatch(str(record.get("content_file_sha256", ""))):
                errors.append(f"{prefix}.content_file_sha256 must be a SHA-256 hash of the extracted-text file")
            if not _SHA256.fullmatch(str(record.get("content_sha256", ""))):
                errors.append(f"{prefix}.content_sha256 must hash text extracted from the retained Zotero MCP response")
            if not _is_safe_project_relative_path(local_file_path):
                errors.append(f"{prefix}.local_file_path must be a project-relative local copy path")
            if not _SHA256.fullmatch(str(record.get("local_file_sha256", ""))):
                errors.append(f"{prefix}.local_file_sha256 must hash the user-supplied local copy")
            if record.get("local_file_relation_status") != "unverified_user_supplied":
                errors.append(f"{prefix}.local_file_relation_status must disclose that the local copy is unverified")
            if not _is_filled(local_file_name) or PurePosixPath(str(local_file_name)).name != local_file_name:
                errors.append(f"{prefix}.local_file_name must record the local file basename")
            if isinstance(confirmation, dict):
                if confirmation.get("zotero_item_key") != record.get("zotero_item_key"):
                    errors.append(f"{prefix}.manual_confirmation.zotero_item_key must match the retrieval record")
                if confirmation.get("attachment_key") != record.get("attachment_key"):
                    errors.append(f"{prefix}.manual_confirmation.attachment_key must match the retrieval record")
                if confirmation.get("local_file_path") != local_file_path:
                    errors.append(f"{prefix}.manual_confirmation.local_file_path must match the local copy")
                if confirmation.get("local_file_name") != local_file_name:
                    errors.append(f"{prefix}.manual_confirmation.local_file_name must match the local basename")
                if confirmation.get("local_file_sha256") != record.get("local_file_sha256"):
                    errors.append(f"{prefix}.manual_confirmation.local_file_sha256 must match the local copy hash")
                if confirmation.get("local_file_relation_status") != "unverified_user_supplied":
                    errors.append(f"{prefix}.manual_confirmation.local_file_relation_status must disclose unverified status")
                if confirmation.get("content_path") != content_path:
                    errors.append(f"{prefix}.manual_confirmation.content_path must match the persisted extracted-text path")
                if confirmation.get("content_file_sha256") != record.get("content_file_sha256"):
                    errors.append(f"{prefix}.manual_confirmation.content_file_sha256 must match the extracted-text file hash")
                if confirmation.get("content_sha256") != record.get("content_sha256"):
                    errors.append(f"{prefix}.manual_confirmation.content_sha256 must match the retrieval record")
                content_call = confirmation.get("content_call")
                if isinstance(content_call, dict):
                    extracted_text, _ = _extract_text_and_locators(content_call.get("raw_response"))
                    if not extracted_text:
                        errors.append(f"{prefix}.manual_confirmation.content_call must retain extractable full text")
                    else:
                        extracted_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
                        if record.get("content_sha256") != extracted_hash:
                            errors.append(f"{prefix}.content_sha256 does not match text extracted from content_call.raw_response")
                        if confirmation.get("content_sha256") != extracted_hash:
                            errors.append(f"{prefix}.manual_confirmation.content_sha256 does not match content_call.raw_response")
                errors.extend(_manual_mcp_call_errors(
                    confirmation.get("item_details_call"),
                    f"{prefix}.manual_confirmation.item_details_call",
                    str(record.get("zotero_item_key", "")),
                ))
                errors.extend(_manual_mcp_call_errors(
                    confirmation.get("content_call"),
                    f"{prefix}.manual_confirmation.content_call",
                    str(record.get("zotero_item_key", "")),
                    str(record.get("attachment_key", "")),
                ))
        elif retrieval == "manual_acquired_unconfirmed":
            if record.get("manual_confirmation"):
                errors.append(f"{prefix} cannot remain unconfirmed while carrying a confirmation record")
        elif retrieval in {"automatic_retrieval_failed", "awaiting_manual_acquisition", "not_retrieved_after_all_routes", "identity_ambiguous", "attachment_ambiguous"}:
            if not _is_filled(record.get("unresolved_reason")):
                errors.append(f"{prefix}.unresolved_reason is required for unresolved retrieval")
            routes = record.get("route_attempts")
            if not isinstance(routes, list):
                errors.append(f"{prefix}.route_attempts must be a list")
            if retrieval == "not_retrieved_after_all_routes" and not routes:
                errors.append(f"{prefix} requires route attempts before marking retrieval exhausted")

        fact = record.get("fact_status")
        if fact is not None:
            errors.extend(
                f"{prefix}: {error}"
                for error in validate_full_text_fact_state(
                    retrieval,
                    review,
                    fact,
                    record.get("fact_scope", "report"),
                    record.get("all_linked_sources_reviewed", False),
                )
            )
    if study_report_map is not None:
        map_index, map_errors = _study_report_index(study_report_map)
        errors.extend(map_errors)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            study_id = str(record.get("study_id", "")).strip()
            report_id = str(record.get("report_id", "")).strip()
            if report_id and report_id not in map_index.get(study_id, set()):
                errors.append(f"records[{index}] is not present in the approved study/report map")
    if screening_scope is not None:
        errors.extend(validate_title_abstract_screening_manifest(screening_scope, study_report_map or {}))
        scope_records = screening_scope.get("records", []) if isinstance(screening_scope, dict) else []
        expected_pairs = {
            _report_pair(record)
            for record in scope_records
            if isinstance(record, dict) and record.get("final_decision") == "include_for_full_text"
        }
        if _manifest_report_pairs(records) != expected_pairs:
            errors.append("full-text retrieval manifest must record every report sought in the approved screening scope")
    return errors


def _study_report_index(study_report_map: Dict[str, Any]) -> tuple[Dict[str, set[str]], List[str]]:
    errors: List[str] = []
    if not isinstance(study_report_map, dict) or study_report_map.get("schema_version") != 1:
        return {}, ["study/report map schema_version must be 1"]
    studies = study_report_map.get("studies")
    if not isinstance(studies, list) or not studies:
        return {}, ["study/report map studies must be a non-empty list"]

    index: Dict[str, set[str]] = {}
    for position, study in enumerate(studies):
        prefix = f"study_report_map.studies[{position}]"
        if not isinstance(study, dict):
            errors.append(f"{prefix} must be an object")
            continue
        study_id = str(study.get("study_id", "")).strip()
        report_ids = study.get("report_ids")
        if not _is_filled(study_id):
            errors.append(f"{prefix}.study_id is required")
        if not isinstance(report_ids, list) or not report_ids or any(not _is_filled(item) for item in report_ids):
            errors.append(f"{prefix}.report_ids must contain at least one report ID")
            continue
        normalized = [str(item).strip() for item in report_ids]
        if len(set(normalized)) != len(normalized):
            errors.append(f"{prefix}.report_ids must be unique")
        if study_id in index:
            errors.append(f"duplicate study_id in study/report map: {study_id}")
        index[study_id] = set(normalized)
    return index, errors


def validate_study_report_map(manifest: Dict[str, Any]) -> List[str]:
    """Validate the immutable study-to-report linkage inventory."""
    _, errors = _study_report_index(manifest)
    return errors


def validate_methods_source_log(
    manifest: Dict[str, Any], required_chapter_ids: Optional[List[str]] = None
) -> List[str]:
    """Require edition/update and access provenance for each methods source."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["methods-source log schema_version must be 1"]
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["methods-source log sources must be a non-empty list"]
    errors: List[str] = []
    seen_ids: set[str] = set()
    seen_types: set[str] = set()
    seen_chapters: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in (
            "source_id",
            "source_type",
            "citation",
            "url",
            "version_or_update_date",
            "accessed_date",
            "access_status",
            "verified_by",
        ):
            if not _is_filled(source.get(field)):
                errors.append(f"{prefix}.{field} is required and must be project-specific")
        source_id = str(source.get("source_id", "")).strip()
        if source_id and source_id in seen_ids:
            errors.append(f"{prefix}.source_id must be unique")
        seen_ids.add(source_id)
        source_type = source.get("source_type")
        if not isinstance(source_type, str) or source_type not in {
            "cochrane_handbook", "tutorial", "guideline", "other"
        }:
            errors.append(f"{prefix}.source_type is not a supported source type")
        else:
            seen_types.add(source_type)
        url = str(source.get("url", "")).strip()
        if url and not re.match(r"^https?://\S+$", url, re.IGNORECASE):
            errors.append(f"{prefix}.url must be an http(s) URL")
        sections = source.get("relevant_sections")
        if not isinstance(sections, list) or not sections or any(not _is_filled(item) for item in sections):
            errors.append(f"{prefix}.relevant_sections must identify the chapters, sections, or pages used")
        accessed_date = str(source.get("accessed_date", "")).strip()
        if accessed_date:
            try:
                if date.fromisoformat(accessed_date).isoformat() != accessed_date:
                    raise ValueError
            except ValueError:
                errors.append(f"{prefix}.accessed_date must be a real date in YYYY-MM-DD format")
        access_status = source.get("access_status")
        if not isinstance(access_status, str) or access_status not in {
            "verified", "inaccessible", "authentication_required", "pending"
        }:
            errors.append(f"{prefix}.access_status is invalid")
        if access_status != "verified" and not _is_filled(source.get("verification_notes")):
            errors.append(f"{prefix}.verification_notes must explain why the source was not verified")
        if source_type == "cochrane_handbook" and isinstance(sections, list) and len(sections) != 1:
            errors.append(f"{prefix}.relevant_sections must identify one Handbook chapter per source record")
        if source_type == "cochrane_handbook":
            chapter_id = source.get("chapter_id")
            if not isinstance(chapter_id, str) or not re.fullmatch(r"chapter-\d{2}", chapter_id):
                errors.append(f"{prefix}.chapter_id must use chapter-NN format")
            else:
                if chapter_id in seen_chapters:
                    errors.append(f"{prefix}.chapter_id must be unique")
                seen_chapters.add(chapter_id)
                url_chapter = re.search(r"/chapter-(\d{2})(?:\b|/|#|$)", url, re.IGNORECASE)
                if not url_chapter or f"chapter-{url_chapter.group(1)}".lower() != chapter_id.lower():
                    errors.append(f"{prefix}.chapter_id must match the chapter number in its URL")
    for source_type in ("cochrane_handbook", "tutorial"):
        if source_type not in seen_types:
            errors.append(f"methods-source log must include at least one {source_type} record")
    if required_chapter_ids is not None:
        if not isinstance(required_chapter_ids, list) or any(
            not isinstance(chapter_id, str) or not re.fullmatch(r"chapter-\d{2}", chapter_id)
            for chapter_id in required_chapter_ids
        ):
            errors.append("protocol methods_sources.cochrane_chapters_used must contain chapter-NN IDs")
            expected_chapters: set[str] = set()
        else:
            expected_chapters = set(required_chapter_ids)
            if len(expected_chapters) != len(required_chapter_ids):
                errors.append("protocol methods_sources.cochrane_chapters_used must be unique")
        if seen_chapters != expected_chapters:
            missing = sorted(expected_chapters - seen_chapters)
            undeclared = sorted(seen_chapters - expected_chapters)
            errors.append(
                "methods-source log Handbook chapter set does not match protocol declaration"
                f" (missing={missing}, undeclared={undeclared})"
            )
    return errors


def _report_pair(record: Dict[str, Any]) -> tuple[str, str]:
    return (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip())


def _is_safe_project_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return (
        value == posix.as_posix()
        and not posix.is_absolute()
        and not windows.is_absolute()
        and not windows.drive
        and ".." not in posix.parts
    )


def _canonical_contract_value(value: Any) -> str:
    """Normalize a protocol/manifest decision for exact contract comparison."""
    if isinstance(value, list):
        return "[" + ",".join(_canonical_contract_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{_canonical_contract_value(key)}:{_canonical_contract_value(item)}"
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]).casefold())
        ) + "}"
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _contract_value_filled(value: Any) -> bool:
    """Return whether a scalar or structured protocol decision is populated."""
    if isinstance(value, list):
        return bool(value) and all(_contract_value_filled(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_contract_value_filled(item) for item in value.values())
    return _is_filled(value)


def _manifest_report_pairs(records: Any) -> set[tuple[str, str]]:
    if not isinstance(records, list):
        return set()
    return {_report_pair(record) for record in records if isinstance(record, dict)}


def validate_title_abstract_screening_manifest(
    manifest: Dict[str, Any], study_report_map: Dict[str, Any]
) -> List[str]:
    """Require one final dual-screening decision for every deduplicated report."""
    errors: List[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["title/abstract screening manifest schema_version must be 1"]
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        return ["title/abstract screening manifest records must be a non-empty list"]
    map_index, map_errors = _study_report_index(study_report_map)
    errors.extend(map_errors)
    expected_pairs = {(study_id, report_id) for study_id, report_ids in map_index.items() for report_id in report_ids}
    seen_pairs: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        pair = _report_pair(record)
        if not all(_is_filled(value) for value in pair):
            errors.append(f"{prefix} requires study_id and report_id")
        if pair in seen_pairs:
            errors.append(f"{prefix} duplicates a study/report record")
        seen_pairs.add(pair)
        if pair not in expected_pairs:
            errors.append(f"{prefix} is not present in the approved study/report map")
        decisions = record.get("reviewer_decisions")
        if not isinstance(decisions, list) or len(decisions) != 2 or any(not isinstance(item, dict) for item in decisions):
            errors.append(f"{prefix}.reviewer_decisions must contain two independent decisions")
            continue
        reviewer_ids = [str(item.get("reviewer_id", "")).strip() for item in decisions]
        reviewer_votes = [item.get("decision") for item in decisions]
        if any(not _is_filled(value) for value in reviewer_ids) or len(set(reviewer_ids)) != 2:
            errors.append(f"{prefix}.reviewer_decisions must identify two distinct reviewers")
        if any(value not in {"include_for_full_text", "exclude"} for value in reviewer_votes):
            errors.append(f"{prefix}.reviewer_decisions contain an invalid decision")
        final_decision = record.get("final_decision")
        if final_decision not in {"include_for_full_text", "exclude"}:
            errors.append(f"{prefix}.final_decision must be include_for_full_text or exclude")
        if final_decision == "include_for_full_text":
            identity = record.get("report_identity")
            if not isinstance(identity, dict):
                errors.append(f"{prefix}.report_identity must contain approved citation identity fields")
            else:
                stable_identifier = _is_filled(identity.get("doi")) or _is_filled(identity.get("pmid"))
                title_and_year = _is_filled(identity.get("title")) and _is_filled(identity.get("year"))
                if not stable_identifier and not title_and_year:
                    errors.append(
                        f"{prefix}.report_identity requires DOI or PMID, or both title and publication year"
                    )
        if reviewer_votes[0] == reviewer_votes[1] and final_decision != reviewer_votes[0]:
            errors.append(f"{prefix}.final_decision must match concordant reviewer decisions")
        if reviewer_votes[0] != reviewer_votes[1] and not _is_filled(record.get("adjudicator_id")):
            errors.append(f"{prefix}.adjudicator_id is required to resolve a screening conflict")
    if seen_pairs != expected_pairs:
        errors.append("title/abstract screening manifest must cover every report in the approved study/report map")
    return errors


def _validate_linked_source_review_evidence(
    fact: Dict[str, Any], prefix: str, study_report_map: Optional[Dict[str, Any]]
) -> List[str]:
    errors: List[str] = []
    linked_ids = fact.get("linked_report_ids")
    evidence = fact.get("linked_source_review_evidence")
    if not isinstance(linked_ids, list) or not linked_ids or any(not _is_filled(item) for item in linked_ids):
        return [f"{prefix}.linked_report_ids must list every report linked to the study"]
    linked_ids = [str(value).strip() for value in linked_ids]
    if len(set(linked_ids)) != len(linked_ids):
        errors.append(f"{prefix}.linked_report_ids must be unique")
    if not isinstance(evidence, list):
        return errors + [f"{prefix}.linked_source_review_evidence must be a list"]

    evidence_by_id: Dict[str, Dict[str, Any]] = {}
    for position, source in enumerate(evidence):
        source_prefix = f"{prefix}.linked_source_review_evidence[{position}]"
        if not isinstance(source, dict):
            errors.append(f"{source_prefix} must be an object")
            continue
        report_id = str(source.get("report_id", "")).strip()
        if not _is_filled(report_id):
            errors.append(f"{source_prefix}.report_id is required")
            continue
        if report_id in evidence_by_id:
            errors.append(f"{prefix} has duplicate linked-source evidence for {report_id}")
        evidence_by_id[report_id] = source
        if source.get("retrieval_status") not in _RETRIEVED_STATES:
            errors.append(f"{source_prefix} must document a retrieved and confirmed report")
        if source.get("full_text_review_status") != "complete_after_adjudication":
            errors.append(f"{source_prefix} must document completed review and adjudication")
        coverage = source.get("review_coverage")
        if not isinstance(coverage, list) or not coverage or any(not _is_filled(item) for item in coverage):
            errors.append(f"{source_prefix}.review_coverage must identify reviewed sections/pages")

    if set(linked_ids) != set(evidence_by_id):
        errors.append(f"{prefix} source-review evidence must cover every linked_report_id exactly once")

    if study_report_map is None:
        errors.append(f"{prefix} study-level absence/uncertainty requires the approved study/report map")
    else:
        index, map_errors = _study_report_index(study_report_map)
        errors.extend(map_errors)
        study_id = str(fact.get("study_id", "")).strip()
        expected_ids = index.get(study_id)
        if expected_ids is None:
            errors.append(f"{prefix}.study_id is absent from the approved study/report map")
        elif set(linked_ids) != expected_ids:
            errors.append(f"{prefix}.linked_report_ids do not match the approved study/report map")
    return errors


def validate_fact_status_manifest(
    manifest: Dict[str, Any],
    study_report_map: Optional[Dict[str, Any]] = None,
    retrieval_manifest: Optional[Dict[str, Any]] = None,
    screening_manifest: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Validate per-field extraction states and source-level absence claims."""
    errors: List[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["fact-status manifest schema_version must be 1"]
    facts = manifest.get("facts")
    if not isinstance(facts, list) or not facts:
        return ["fact-status manifest facts must be a non-empty list"]

    map_index: Dict[str, set[str]] = {}
    if study_report_map is not None:
        map_index, map_errors = _study_report_index(study_report_map)
        errors.extend(map_errors)
    retrieval_records = retrieval_manifest.get("records") if isinstance(retrieval_manifest, dict) else None
    screening_records = screening_manifest.get("records") if isinstance(screening_manifest, dict) else None
    if not isinstance(retrieval_records, list) or not isinstance(screening_records, list):
        errors.append("fact-status validation requires approved retrieval and full-text screening records")
        retrieval_records = retrieval_records if isinstance(retrieval_records, list) else []
        screening_records = screening_records if isinstance(screening_records, list) else []
    retrieval_by_pair = {
        _report_pair(record): record for record in retrieval_records if isinstance(record, dict)
    }
    screening_by_pair = {
        _report_pair(record): record for record in screening_records if isinstance(record, dict)
    }

    for index, fact in enumerate(facts):
        prefix = f"facts[{index}]"
        if not isinstance(fact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("study_id", "report_id", "field_id"):
            if not _is_filled(fact.get(field)):
                errors.append(f"{prefix}.{field} is required")
        retrieval = fact.get("retrieval_status")
        review = fact.get("full_text_review_status")
        status = fact.get("fact_status")
        scope = fact.get("fact_scope")
        linked_reviewed = fact.get("all_linked_sources_reviewed", False)
        pair = _report_pair(fact)
        if study_report_map is None or pair[1] not in map_index.get(pair[0], set()):
            errors.append(f"{prefix} study/report ID pair is not present in the approved study/report map")
        upstream_retrieval = retrieval_by_pair.get(pair)
        upstream_screening = screening_by_pair.get(pair)
        if upstream_retrieval is None:
            errors.append(f"{prefix} has no approved retrieval outcome")
        elif retrieval != upstream_retrieval.get("retrieval_status"):
            errors.append(f"{prefix}.retrieval_status does not match the approved retrieval manifest")
        if upstream_screening is None:
            errors.append(f"{prefix} has no approved full-text eligibility outcome")
        elif upstream_screening.get("eligibility_status") != "included":
            errors.append(f"{prefix} cannot be extracted unless full-text eligibility is included")
        elif review != upstream_screening.get("full_text_review_status"):
            errors.append(f"{prefix}.full_text_review_status does not match the approved full-text screening manifest")
        errors.extend(
            f"{prefix}: {error}"
            for error in validate_full_text_fact_state(retrieval, review, status, scope, linked_reviewed)
        )

        if status == "reported":
            if not _is_filled(fact.get("source_quote")) or not _is_filled(fact.get("source_locator")):
                errors.append(f"{prefix} reported values require a source quote and report locator")
        elif status == "not_reported_in_reviewed_report":
            coverage = fact.get("review_coverage")
            if not isinstance(coverage, list) or not coverage or any(not _is_filled(item) for item in coverage):
                errors.append(f"{prefix} report-level non-reporting requires reviewed-section/page coverage")
        elif status == "not_reported_after_all_linked_sources_review":
            errors.extend(_validate_linked_source_review_evidence(fact, prefix, study_report_map))
        elif status == "cannot_tell_after_full_text_review":
            if not _is_filled(fact.get("uncertainty_reason")):
                errors.append(f"{prefix}.uncertainty_reason is required for cannot-tell status")
            if scope == "study":
                errors.extend(_validate_linked_source_review_evidence(fact, prefix, study_report_map))
            elif (
                not isinstance(fact.get("review_coverage"), list)
                or not fact["review_coverage"]
                or any(not _is_filled(item) for item in fact["review_coverage"])
            ):
                errors.append(f"{prefix} report-level cannot-tell status requires reviewed-section/page coverage")
        elif status == "not_applicable" and not _is_filled(fact.get("not_applicable_reason")):
            errors.append(f"{prefix}.not_applicable_reason is required")
        if status != "reported" and any(
            fact.get(field) not in (None, "")
            for field in ("value", "effect_estimate", "events", "total", "mean", "sd", "standard_error", "ci_lower", "ci_upper")
        ):
            errors.append(f"{prefix} must not carry an extracted numeric value unless fact_status is reported")
        if scope == "study" and status in {
            "not_reported_after_all_linked_sources_review",
            "cannot_tell_after_full_text_review",
        }:
            for source in fact.get("linked_source_review_evidence", []):
                if not isinstance(source, dict):
                    continue
                source_pair = (pair[0], str(source.get("report_id", "")).strip())
                retrieval_source = retrieval_by_pair.get(source_pair)
                screening_source = screening_by_pair.get(source_pair)
                if retrieval_source is None or screening_source is None:
                    errors.append(f"{prefix} linked source is absent from approved retrieval/screening manifests")
                    continue
                if source.get("retrieval_status") != retrieval_source.get("retrieval_status"):
                    errors.append(f"{prefix} linked-source retrieval evidence conflicts with the approved manifest")
                if retrieval_source.get("retrieval_status") not in _RETRIEVED_STATES:
                    errors.append(f"{prefix} cannot classify study-level absence while a linked report is unavailable")
                if screening_source.get("eligibility_status") != "included":
                    errors.append(f"{prefix} cannot classify study-level absence while a linked report is not eligible")
                if source.get("full_text_review_status") != screening_source.get("full_text_review_status"):
                    errors.append(f"{prefix} linked-source review evidence conflicts with the approved screening manifest")
    return errors


def _validate_json_manifest_file(path: Union[str, Path], validator: Any, label: str) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read {label} JSON: {exc}"]
    return validator(manifest)


def validate_title_abstract_screening_manifest_file(
    path: Union[str, Path], study_report_map_path: Union[str, Path]
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        study_report_map = json.loads(Path(study_report_map_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read title/abstract screening or approved map JSON: {exc}"]
    if not isinstance(manifest, dict):
        return ["title/abstract screening manifest must be a JSON object"]
    map_hash = hashlib.sha256(Path(study_report_map_path).read_bytes()).hexdigest()
    if manifest.get("study_report_map_sha256") != map_hash:
        return ["title/abstract screening manifest study_report_map_sha256 does not match the approved map"]
    return validate_title_abstract_screening_manifest(manifest, study_report_map)


def validate_full_text_retrieval_manifest_file(
    path: Union[str, Path],
    study_report_map_path: Optional[Union[str, Path]] = None,
    screening_scope_path: Optional[Union[str, Path]] = None,
    project_dir: Optional[Union[str, Path]] = None,
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read full-text retrieval manifest JSON: {exc}"]
    study_report_map = None
    screening_scope = None
    if study_report_map_path is not None:
        try:
            study_report_map = json.loads(Path(study_report_map_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"Unable to read approved study/report map JSON: {exc}"]
        if not isinstance(manifest, dict):
            return ["full-text retrieval manifest must be a JSON object"]
        map_hash = hashlib.sha256(Path(study_report_map_path).read_bytes()).hexdigest()
        if manifest.get("study_report_map_sha256") != map_hash:
            return ["full-text retrieval manifest study_report_map_sha256 does not match the approved study/report map"]
    if screening_scope_path is not None:
        try:
            screening_scope = json.loads(Path(screening_scope_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"Unable to read approved title/abstract screening manifest JSON: {exc}"]
        scope_hash = hashlib.sha256(Path(screening_scope_path).read_bytes()).hexdigest()
        if not isinstance(manifest, dict):
            return ["full-text retrieval manifest must be a JSON object"]
        if manifest.get("title_abstract_screening_manifest_sha256") != scope_hash:
            return ["full-text retrieval manifest title/abstract screening hash does not match the approved screening scope"]
    errors = validate_full_text_retrieval_manifest(manifest, study_report_map, screening_scope)
    if project_dir is not None and isinstance(manifest, dict):
        project = Path(project_dir).expanduser().resolve()
        for index, record in enumerate(manifest.get("records", [])):
            if not isinstance(record, dict) or record.get("retrieval_status") != "manual_confirmed":
                continue
            for path_field, hash_field, label in (
                ("local_file_path", "local_file_sha256", "user-supplied local copy"),
                ("content_path", "content_file_sha256", "persisted extracted text"),
            ):
                relative = record.get(path_field)
                if not _is_safe_project_relative_path(relative):
                    continue
                archived_path = (project / Path(*PurePosixPath(relative).parts)).resolve()
                try:
                    archived_path.relative_to(project)
                except ValueError:
                    errors.append(f"records[{index}].{path_field} escaped the review project")
                    continue
                if not archived_path.is_file():
                    errors.append(f"records[{index}] {label} file is missing: {relative}")
                    continue
                actual_hash = hashlib.sha256(archived_path.read_bytes()).hexdigest()
                if actual_hash != record.get(hash_field):
                    errors.append(f"records[{index}].{hash_field} does not match the {label} file")
                if path_field == "content_path" and archived_path.is_file():
                    confirmation = record.get("manual_confirmation")
                    content_call = confirmation.get("content_call") if isinstance(confirmation, dict) else None
                    if isinstance(content_call, dict):
                        extracted_text, _ = _extract_text_and_locators(content_call.get("raw_response"))
                        if extracted_text and archived_path.read_bytes() != (extracted_text + "\n").encode("utf-8"):
                            errors.append(
                                f"records[{index}].content_path does not contain the text extracted from content_call.raw_response"
                            )
    return errors


def validate_full_text_screening_manifest(
    manifest: Dict[str, Any],
    study_report_map: Dict[str, Any],
    retrieval_manifest: Dict[str, Any],
) -> List[str]:
    """Require eligibility results or an explicit awaiting-classification state for every sought report."""
    errors: List[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["full-text screening manifest schema_version must be 1"]
    records = manifest.get("records")
    retrieval_records = retrieval_manifest.get("records") if isinstance(retrieval_manifest, dict) else None
    if not isinstance(records, list) or not isinstance(retrieval_records, list):
        return ["full-text screening and retrieval manifests must contain record lists"]
    map_index, map_errors = _study_report_index(study_report_map)
    errors.extend(map_errors)
    retrieval_by_pair = {
        _report_pair(record): record for record in retrieval_records if isinstance(record, dict)
    }
    screening_by_pair: Dict[tuple[str, str], Dict[str, Any]] = {}
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        pair = _report_pair(record)
        if pair in screening_by_pair:
            errors.append(f"{prefix} duplicates a study/report record")
        screening_by_pair[pair] = record
        if pair[1] not in map_index.get(pair[0], set()):
            errors.append(f"{prefix} is not present in the approved study/report map")
        retrieval = retrieval_by_pair.get(pair)
        if retrieval is None:
            errors.append(f"{prefix} has no approved retrieval outcome")
            continue

        retrieved = retrieval.get("retrieval_status") in _RETRIEVED_STATES
        eligibility = record.get("eligibility_status")
        review_status = record.get("full_text_review_status")
        decisions = record.get("reviewer_decisions", [])
        if retrieved:
            if eligibility not in {"included", "excluded"}:
                errors.append(f"{prefix}.eligibility_status must be included or excluded after retrieval")
            if review_status != "complete_after_adjudication":
                errors.append(f"{prefix}.full_text_review_status must be complete_after_adjudication")
            if not isinstance(decisions, list) or len(decisions) != 2 or any(not isinstance(item, dict) for item in decisions):
                errors.append(f"{prefix}.reviewer_decisions must contain two independent decisions")
                continue
            reviewer_ids = [str(item.get("reviewer_id", "")).strip() for item in decisions]
            votes = [item.get("decision") for item in decisions]
            if any(not _is_filled(value) for value in reviewer_ids) or len(set(reviewer_ids)) != 2:
                errors.append(f"{prefix}.reviewer_decisions must identify two distinct reviewers")
            if any(value not in {"include", "exclude"} for value in votes):
                errors.append(f"{prefix}.reviewer_decisions contain an invalid decision")
            expected = "included" if votes[0] == "include" else "excluded"
            if votes[0] == votes[1] and eligibility != expected:
                errors.append(f"{prefix}.eligibility_status must match concordant reviewer decisions")
            if votes[0] != votes[1] and not _is_filled(record.get("adjudicator_id")):
                errors.append(f"{prefix}.adjudicator_id is required to resolve a full-text conflict")
            if eligibility == "excluded":
                if not _is_filled(record.get("exclusion_reason")):
                    errors.append(f"{prefix}.exclusion_reason is required for a full-text exclusion")
                if not _is_filled(record.get("source_locator")):
                    errors.append(f"{prefix}.source_locator is required for a full-text exclusion")
        else:
            if eligibility != "awaiting_classification":
                errors.append(f"{prefix} cannot receive an eligibility decision before retrieval is confirmed")
            if review_status != "not_started":
                errors.append(f"{prefix}.full_text_review_status must remain not_started until retrieval is confirmed")
            if decisions:
                errors.append(f"{prefix} cannot contain reviewer decisions before retrieval is confirmed")

    if set(screening_by_pair) != set(retrieval_by_pair):
        errors.append("full-text screening manifest must account for every report in the retrieval manifest")
    return errors


def validate_full_text_screening_manifest_file(
    path: Union[str, Path],
    study_report_map_path: Union[str, Path],
    retrieval_manifest_path: Union[str, Path],
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        study_report_map = json.loads(Path(study_report_map_path).read_text(encoding="utf-8"))
        retrieval_manifest = json.loads(Path(retrieval_manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read full-text screening inputs: {exc}"]
    if not isinstance(manifest, dict):
        return ["full-text screening manifest must be a JSON object"]
    map_hash = hashlib.sha256(Path(study_report_map_path).read_bytes()).hexdigest()
    retrieval_hash = hashlib.sha256(Path(retrieval_manifest_path).read_bytes()).hexdigest()
    if manifest.get("study_report_map_sha256") != map_hash:
        return ["full-text screening manifest study_report_map_sha256 does not match the approved map"]
    if manifest.get("full_text_retrieval_manifest_sha256") != retrieval_hash:
        return ["full-text screening manifest hash does not match the approved retrieval manifest"]
    return validate_full_text_screening_manifest(manifest, study_report_map, retrieval_manifest)


def validate_study_report_map_file(path: Union[str, Path]) -> List[str]:
    return _validate_json_manifest_file(path, validate_study_report_map, "study/report map")


def validate_methods_source_log_file(path: Union[str, Path]) -> List[str]:
    return _validate_json_manifest_file(path, validate_methods_source_log, "methods-source log")


def validate_methods_source_log_for_protocol_file(
    path: Union[str, Path], protocol_path: Union[str, Path]
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read methods-source log or protocol JSON: {exc}"]
    if not isinstance(protocol, dict):
        return ["review protocol must be a JSON object to validate its methods-source chapter set"]
    method_sources = protocol.get("methods_sources")
    chapters = method_sources.get("cochrane_chapters_used") if isinstance(method_sources, dict) else None
    if not isinstance(chapters, list):
        return ["review protocol methods_sources.cochrane_chapters_used must be a list"]
    return validate_methods_source_log(manifest, chapters)


def validate_fact_status_manifest_file(
    path: Union[str, Path],
    study_report_map_path: Union[str, Path],
    retrieval_manifest_path: Union[str, Path],
    screening_manifest_path: Union[str, Path],
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        study_report_map = json.loads(Path(study_report_map_path).read_text(encoding="utf-8"))
        retrieval_manifest = json.loads(Path(retrieval_manifest_path).read_text(encoding="utf-8"))
        screening_manifest = json.loads(Path(screening_manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read fact-status manifest or approved upstream JSON: {exc}"]
    if not isinstance(manifest, dict):
        return ["fact-status manifest must be a JSON object"]
    for field, source_path, label in (
        ("study_report_map_sha256", study_report_map_path, "study/report map"),
        ("full_text_retrieval_manifest_sha256", retrieval_manifest_path, "retrieval manifest"),
        ("full_text_screening_manifest_sha256", screening_manifest_path, "full-text screening manifest"),
    ):
        expected_hash = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        if manifest.get(field) != expected_hash:
            return [f"fact-status manifest {field} does not match the approved {label}"]
    return validate_fact_status_manifest(manifest, study_report_map, retrieval_manifest, screening_manifest)


def validate_review_protocol(protocol: Dict[str, Any]) -> List[str]:
    """Return all Stage 0 blockers; an empty list means structurally complete."""
    errors: List[str] = []
    if not isinstance(protocol, dict) or protocol.get("schema_version") != 2:
        return ["schema_version must be 2 and the protocol root must be a JSON object"]

    method_sources = protocol.get("methods_sources")
    chapters = method_sources.get("cochrane_chapters_used") if isinstance(method_sources, dict) else None
    if (
        not isinstance(chapters, list)
        or not chapters
        or any(not isinstance(item, str) or not re.fullmatch(r"chapter-\d{2}", item) for item in chapters)
    ):
        errors.append("methods_sources.cochrane_chapters_used must list the Handbook chapter-NN IDs used")
    elif len(set(chapters)) != len(chapters):
        errors.append("methods_sources.cochrane_chapters_used must be unique")
    if not isinstance(method_sources, dict) or not _is_filled(method_sources.get("chapter_scope_rationale")):
        errors.append("methods_sources.chapter_scope_rationale must explain the selected Handbook scope")

    for path in (
        "project.id",
        "project.title",
        "project.lead",
        "project.created_date",
        "question.framework",
        "question.population",
        "question.intervention_or_exposure",
        "question.comparator",
        "question.clinical_context",
        "question.objective",
        "eligibility.report_characteristics.publication_status",
        "eligibility.report_characteristics.language_policy",
        "eligibility.report_characteristics.date_limits",
        "eligibility.report_characteristics.restriction_rationale",
        "eligibility.multiple_reports_linkage_rule",
        "search.planned_date_range",
        "search.planned_search_date",
        "search.restrictions_and_rationale",
        "search.search_peer_review_plan",
        "selection.conflict_resolution",
        "full_text.collection_name",
        "full_text.attachment_policy",
        "full_text.identity_matching_policy",
        "full_text.unavailable_report_policy",
        "full_text.manual_queue_path",
        "full_text.manual_confirmation_rule",
        "full_text.fact_classification_rule",
        "full_text.ocr_policy",
        "data_collection.independent_verification_rule",
        "data_collection.author_contact_policy",
        "data_collection.pilot_and_training_plan",
        "risk_of_bias.disagreement_resolution",
        "synthesis.clinical_methodological_compatibility_rule",
        "synthesis.model_and_estimator",
        "synthesis.confidence_interval_method",
        "synthesis.multi_arm_study_rule",
        "synthesis.multiple_outcome_rule",
        "synthesis.missing_data_rule",
        "synthesis.heterogeneity_rationale",
        "synthesis.subgroups_and_meta_regression_rationale",
        "synthesis.sensitivity_analysis_rationale",
        "synthesis.small_study_effects_plan",
        "synthesis.software_and_version",
        "synthesis.analysis_manifest_path",
        "synthesis.software.primary_engine.name",
        "synthesis.software.primary_engine.version",
        "synthesis.software.primary_engine.role",
        "synthesis.software.random_seed",
        "certainty.framework",
        "certainty.downgrade_upgrade_rules",
        "agent_governance.human_accountable_lead",
        "figure_table_contract.contract_path",
    ):
        _need_text(protocol, path, errors)

    for path in (
        "eligibility.inclusion_criteria",
        "eligibility.exclusion_criteria",
        "eligibility.eligible_study_designs",
        "search.sources",
        "selection.full_text_exclusion_reasons",
        "full_text.manual_acquisition_routes",
        "full_text.retrieval_status_vocabulary",
        "full_text.full_text_review_status_vocabulary",
        "full_text.fact_status_vocabulary",
        "full_text.required_provenance",
        "synthesis.synthesis_groups",
        "synthesis.heterogeneity_assessment",
        "certainty.critical_outcomes",
        "synthesis.software.primary_engine.packages",
        "synthesis.software.runtime_lock_paths",
        "synthesis.software.certainty_tools",
    ):
        _need_list(protocol, path, errors)

    primary_packages = _value(protocol, "synthesis.software.primary_engine.packages")
    if isinstance(primary_packages, list) and not primary_packages:
        errors.append("synthesis.software.primary_engine.packages must contain package names and versions")
    elif isinstance(primary_packages, list) and any(
        not isinstance(package, str) or not re.search(r"\d", package)
        for package in primary_packages
    ):
        errors.append("synthesis.software.primary_engine.packages must include explicit package versions")
    primary_engine_name = _value(protocol, "synthesis.software.primary_engine.name")
    if isinstance(primary_engine_name, str) and primary_engine_name.strip().casefold() in {"python", "python3"}:
        errors.append(
            "synthesis.software.primary_engine cannot be Python; use a locked production "
            "R/Stata/validated synthesis engine and reserve Python for orchestration and QA"
        )
    certainty_tools = _value(protocol, "synthesis.software.certainty_tools")
    if isinstance(certainty_tools, list) and not certainty_tools:
        errors.append("synthesis.software.certainty_tools must declare the tool used for certainty assessment")
    runtime_lock_paths = _value(protocol, "synthesis.software.runtime_lock_paths")
    if isinstance(runtime_lock_paths, list):
        if not runtime_lock_paths:
            errors.append("synthesis.software.runtime_lock_paths must declare at least one lock file")
        for index, lock_path in enumerate(runtime_lock_paths):
            if not _is_safe_project_relative_path(lock_path):
                errors.append(
                    f"synthesis.software.runtime_lock_paths[{index}] must be a safe project-relative path"
                )

    _need_two_distinct(protocol, "selection.title_abstract_reviewers", errors)
    _need_two_distinct(protocol, "selection.full_text_reviewers", errors)
    _need_two_distinct(protocol, "data_collection.extractors", errors)
    _need_two_distinct(protocol, "risk_of_bias.reviewers", errors)
    _need_text(protocol, "selection.adjudicator", errors)

    outcomes = protocol.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        errors.append("outcomes must define at least one primary or secondary outcome")
    else:
        for index, outcome in enumerate(outcomes):
            prefix = f"outcomes[{index}]"
            if not isinstance(outcome, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in (
                "name",
                "definition",
                "measurement",
                "time_window",
                "timepoint_selection_rule",
                "measure_selection_rule",
                "preferred_effect_measure",
                "clinical_importance",
                "related_effect_handling",
            ):
                if not _is_filled(outcome.get(field)):
                    errors.append(f"{prefix}.{field} must be completed")
            if outcome.get("role") not in ("primary", "secondary"):
                errors.append(f"{prefix}.role must be primary or secondary")

    tools = _value(protocol, "risk_of_bias.tool_by_design")
    if (
        not isinstance(tools, dict)
        or not tools
        or any(not _is_filled(key) or not _is_filled(value) for key, value in tools.items())
    ):
        errors.append("risk_of_bias.tool_by_design must map each eligible design to a named assessment approach")
    else:
        eligible_designs = {
            str(design).strip().casefold()
            for design in _value(protocol, "eligibility.eligible_study_designs") or []
            if _is_filled(design)
        }
        mapped_designs = {str(design).strip().casefold() for design in tools}
        if mapped_designs != eligible_designs:
            errors.append("risk_of_bias.tool_by_design keys must exactly match eligible_study_designs")

    effect_measures = _value(protocol, "synthesis.effect_measures")
    if not isinstance(effect_measures, dict) or not effect_measures or any(not _is_filled(v) for v in effect_measures.values()):
        errors.append("synthesis.effect_measures must map each planned outcome/group to an effect measure")

    manifest_path = _value(protocol, "synthesis.analysis_manifest_path")
    if not _is_safe_project_relative_path(manifest_path):
        errors.append("synthesis.analysis_manifest_path must be a safe project-relative path")
    elif PurePosixPath(manifest_path).name != "analysis_manifest.json":
        errors.append("synthesis.analysis_manifest_path must name analysis_manifest.json")

    pairwise_plan = _value(protocol, "synthesis.pairwise_meta_analysis")
    if pairwise_plan is None:
        errors.append("synthesis.pairwise_meta_analysis must be declared")
    elif not isinstance(pairwise_plan, dict) or not isinstance(pairwise_plan.get("enabled"), bool):
        errors.append("synthesis.pairwise_meta_analysis.enabled must be an explicit boolean")
    elif not pairwise_plan["enabled"] and not _is_filled(pairwise_plan.get("not_planned_rationale")):
        errors.append("synthesis.pairwise_meta_analysis.not_planned_rationale is required when pairwise synthesis is disabled")

    registration = protocol.get("registration")
    if not isinstance(registration, dict) or registration.get("status") not in ("registered", "submitted", "not_registered"):
        errors.append("registration.status must be registered, submitted, or not_registered")
    elif registration["status"] == "not_registered":
        if not _is_filled(registration.get("not_registered_rationale")):
            errors.append("registration.not_registered_rationale is required when status is not_registered")
    elif not (_is_filled(registration.get("registration_id")) or _is_filled(registration.get("protocol_url_or_path"))):
        errors.append("a registered/submitted protocol requires a registration ID or protocol URL/path")

    full_text = protocol.get("full_text")
    if not isinstance(full_text, dict) or full_text.get("manual_confirmation_required") is not True:
        errors.append("full_text.manual_confirmation_required must be true")
    elif isinstance(full_text.get("retrieval_status_vocabulary"), list):
        retrieval_states = {str(value) for value in full_text["retrieval_status_vocabulary"]}
        fact_states = {str(value) for value in full_text.get("fact_status_vocabulary", [])}
        required_retrieval_states = {
            "automatic_retrieval_succeeded",
            "automatic_retrieval_failed",
            "awaiting_manual_acquisition",
            "manual_acquired_unconfirmed",
            "manual_confirmed",
            "not_retrieved_after_all_routes",
            "identity_ambiguous",
            "attachment_ambiguous",
        }
        if not required_retrieval_states.issubset(retrieval_states):
            errors.append("full_text retrieval statuses must represent automated, manual, ambiguous, and unresolved retrieval")
        review_states = {str(value) for value in full_text.get("full_text_review_status_vocabulary", [])}
        if not {"not_started", "pending_independent_review", "review_in_progress", "complete_after_adjudication"}.issubset(review_states):
            errors.append("full_text review statuses must represent independent review and adjudication completion")
        if not _FACT_STATES.issubset(fact_states):
            errors.append("full_text fact statuses must distinguish inaccessible, pending review, reported, absent, unclear, and not applicable")
        required_provenance = {
            "zotero_item_key",
            "identity_match_method_and_result",
            "attachment_key_and_path",
            "retrieval_status",
            "retrieval_timestamp",
            "manual_confirmation_actor_and_timestamp_when_applicable",
            "attachment_SHA256",
            "text_extraction_method_and_status",
            "page_locator_when_available",
            "full_text_review_status",
            "fact_status_per_extracted_field",
        }
        if not required_provenance.issubset({str(value) for value in full_text.get("required_provenance", [])}):
            errors.append("full_text.required_provenance is missing required Zotero, confirmation, or fact-state fields")

    nma = _value(protocol, "synthesis.network_meta_analysis")
    if not isinstance(nma, dict) or not isinstance(nma.get("enabled"), bool):
        errors.append("synthesis.network_meta_analysis.enabled must be an explicit boolean")
    elif nma["enabled"]:
        for field in (
            "intervention_node_definitions",
            "transitivity_assessment",
            "network_connectivity_and_geometry",
            "incoherence_assessment",
            "model_specification",
            "model_and_multi_arm_handling",
            "ranking_interpretation",
            "certainty_framework",
            "assumption_failure_plan",
        ):
            if not _is_filled(nma.get(field)):
                errors.append(f"synthesis.network_meta_analysis.{field} must be completed when NMA is enabled")
        _need_list(protocol, "synthesis.network_meta_analysis.transitivity_effect_modifiers", errors)
    elif not _is_filled(nma.get("not_planned_rationale")):
        errors.append("synthesis.network_meta_analysis.not_planned_rationale is required when NMA is disabled")

    governance = protocol.get("agent_governance")
    if not isinstance(governance, dict) or governance.get("independent_reviews_required_per_stage") != 2:
        errors.append("agent_governance must require two independent stage reviews")
    if isinstance(governance, dict) and governance.get("executor_reviews_own_stage") is not False:
        errors.append("agent_governance.executor_reviews_own_stage must be false")
    return errors


def validate_analysis_manifest(manifest: Dict[str, Any]) -> List[str]:
    """Validate the machine-readable synthesis methods and runtime record."""
    errors: List[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["analysis manifest schema_version must be 1"]
    if manifest.get("stage_id") != "synthesis":
        errors.append("analysis manifest stage_id must be synthesis")
    for field in ("project_id", "code_commit"):
        if not _is_filled(manifest.get(field)):
            errors.append(f"analysis manifest {field} must be completed")
    for field in ("protocol_sha256", "input_snapshot_sha256"):
        if not _SHA256.fullmatch(str(manifest.get(field, ""))):
            errors.append(f"analysis manifest {field} must be a SHA-256 hash")
    input_snapshot_path = manifest.get("input_snapshot_path")
    if not _is_safe_project_relative_path(input_snapshot_path):
        errors.append("analysis manifest input_snapshot_path must be project-relative")
    estimands = manifest.get("estimands")
    if not isinstance(estimands, list) or not estimands or any(not _is_filled(item) for item in estimands):
        errors.append("analysis manifest estimands must contain at least one completed estimand")
    effect_map = manifest.get("effect_measure_by_outcome")
    if not isinstance(effect_map, dict) or not effect_map or any(not _is_filled(value) for value in effect_map.values()):
        errors.append("analysis manifest effect_measure_by_outcome must map outcomes to effect measures")

    pairwise = manifest.get("pairwise")
    if not isinstance(pairwise, dict):
        errors.append("analysis manifest pairwise must be an object")
    else:
        pairwise_planned = pairwise.get("planned", True)
        if not isinstance(pairwise_planned, bool):
            errors.append("analysis manifest pairwise.planned must be an explicit boolean")
            pairwise_planned = True
        if pairwise_planned:
            for field in (
                "primary_model",
                "primary_estimator",
                "interval_method",
                "zero_event_rule",
                "multi_arm_and_dependency_rule",
                "missing_data_rule",
                "prediction_interval",
            ):
                if not _is_filled(pairwise.get(field)):
                    errors.append(f"analysis manifest pairwise.{field} must be completed")
            if not isinstance(pairwise.get("heterogeneity_statistics"), list) or not pairwise["heterogeneity_statistics"]:
                errors.append("analysis manifest pairwise.heterogeneity_statistics must be a non-empty list")
            if not isinstance(pairwise.get("sensitivity_analyses"), list):
                errors.append("analysis manifest pairwise.sensitivity_analyses must be a list")
        elif not _is_filled(pairwise.get("not_planned_rationale")):
            errors.append("analysis manifest pairwise.not_planned_rationale is required when pairwise synthesis is not planned")

    nma = manifest.get("network_meta_analysis")
    if not isinstance(nma, dict) or not isinstance(nma.get("planned"), bool):
        errors.append("analysis manifest network_meta_analysis.planned must be an explicit boolean")
    elif nma["planned"]:
        for field in (
            "model",
            "node_definitions",
            "connectivity",
            "transitivity",
            "transitivity_effect_modifiers",
            "inconsistency",
            "multi_arm_covariance",
            "heterogeneity",
            "ranking_uncertainty",
            "certainty_method",
            "assumption_failure_plan",
        ):
            if field == "transitivity_effect_modifiers":
                if not isinstance(nma.get(field), list) or not nma[field] or any(not _is_filled(item) for item in nma[field]):
                    errors.append("analysis manifest network_meta_analysis.transitivity_effect_modifiers must be a non-empty list")
            elif not _is_filled(nma.get(field)):
                errors.append(f"analysis manifest network_meta_analysis.{field} must be completed when NMA is planned")
    elif not _is_filled(nma.get("not_planned_rationale")):
        errors.append("analysis manifest network_meta_analysis.not_planned_rationale is required when NMA is not planned")

    software = manifest.get("software")
    if not isinstance(software, dict):
        errors.append("analysis manifest software must be an object")
    else:
        primary = software.get("primary_engine")
        if not isinstance(primary, dict):
            errors.append("analysis manifest software.primary_engine must be an object")
        else:
            for field in ("name", "version", "role"):
                if not _is_filled(primary.get(field)):
                    errors.append(f"analysis manifest software.primary_engine.{field} must be completed")
            if not isinstance(primary.get("packages"), list) or not primary["packages"]:
                errors.append("analysis manifest software.primary_engine.packages must be a non-empty list")
            elif any(
                not isinstance(package, str) or not re.search(r"\d", package)
                for package in primary["packages"]
            ):
                errors.append(
                    "analysis manifest software.primary_engine.packages must include explicit package versions"
                )
            if str(primary.get("name", "")).strip().casefold() in {"python", "python3"}:
                errors.append(
                    "analysis manifest software.primary_engine cannot be Python; use a locked production "
                    "R/Stata/validated synthesis engine and reserve Python for orchestration and QA"
                )
        if not isinstance(software.get("verification_engines"), list):
            errors.append("analysis manifest software.verification_engines must be a list")
        if not isinstance(software.get("certainty_tools"), list) or not software["certainty_tools"]:
            errors.append("analysis manifest software.certainty_tools must be a non-empty list")
        if not isinstance(software.get("runtime_lock_paths"), list) or not software["runtime_lock_paths"]:
            errors.append("analysis manifest software.runtime_lock_paths must be a non-empty list")
        elif any(not _is_safe_project_relative_path(item) for item in software["runtime_lock_paths"]):
            errors.append("analysis manifest software.runtime_lock_paths must contain safe project-relative paths")
        if not _is_filled(software.get("random_seed")):
            errors.append("analysis manifest software.random_seed must record a seed or deterministic-analysis rationale")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("analysis manifest outputs must contain at least one output record")
    else:
        for index, output in enumerate(outputs):
            if not isinstance(output, dict) or not _is_safe_project_relative_path(output.get("path")):
                errors.append(f"analysis manifest outputs[{index}].path must be project-relative")
            if not isinstance(output, dict) or not _SHA256.fullmatch(str(output.get("sha256", ""))):
                errors.append(f"analysis manifest outputs[{index}].sha256 must be a SHA-256 hash")
    if not isinstance(manifest.get("diagnostics"), list):
        errors.append("analysis manifest diagnostics must be a list")
    if not isinstance(manifest.get("deviations"), list):
        errors.append("analysis manifest deviations must be a list")
    declared_paths = []
    for item in list(manifest.get("outputs", [])) + list(manifest.get("intermediate_outputs", [])):
        if isinstance(item, dict) and _is_safe_project_relative_path(item.get("path")):
            declared_paths.append(item["path"])
    if len(declared_paths) != len(set(declared_paths)):
        errors.append("analysis manifest output and intermediate paths must be unique")
    intermediate_outputs = manifest.get("intermediate_outputs", [])
    if not isinstance(intermediate_outputs, list):
        errors.append("analysis manifest intermediate_outputs must be a list")
    else:
        for index, output in enumerate(intermediate_outputs):
            if not isinstance(output, dict) or not _is_safe_project_relative_path(output.get("path")):
                errors.append(f"analysis manifest intermediate_outputs[{index}].path must be project-relative")
            if not isinstance(output, dict) or not _SHA256.fullmatch(str(output.get("sha256", ""))):
                errors.append(f"analysis manifest intermediate_outputs[{index}].sha256 must be a SHA-256 hash")
    convergence = manifest.get("convergence", {})
    if not isinstance(convergence, dict):
        errors.append("analysis manifest convergence must be an object")
    elif convergence and not _is_filled(convergence.get("status")):
        errors.append("analysis manifest convergence.status must be completed when convergence is recorded")
    return errors


def validate_analysis_manifest_file(
    path: Union[str, Path],
    project_dir: Optional[Union[str, Path]] = None,
    protocol_path: Optional[Union[str, Path]] = None,
) -> List[str]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read analysis manifest JSON: {exc}"]
    errors = validate_analysis_manifest(manifest)
    if project_dir is None or not isinstance(manifest, dict):
        return errors
    project = Path(project_dir).expanduser().resolve()
    records = [("output", output) for output in manifest.get("outputs", [])]
    records.extend(("intermediate output", output) for output in manifest.get("intermediate_outputs", []))
    for index, (label, output) in enumerate(records):
        if not isinstance(output, dict) or not _is_safe_project_relative_path(output.get("path")):
            continue
        output_path = (project / Path(*PurePosixPath(output["path"]).parts)).resolve()
        try:
            output_path.relative_to(project)
        except ValueError:
            errors.append(f"analysis manifest {label}[{index}].path escaped the review project")
            continue
        if not output_path.is_file():
            errors.append(f"analysis manifest {label} file is missing: {output['path']}")
            continue
        actual_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
        if actual_hash != str(output.get("sha256", "")).lower():
            errors.append(f"analysis manifest {label}[{index}].sha256 does not match its file")

    if _is_safe_project_relative_path(manifest.get("input_snapshot_path")):
        input_path = (project / Path(*PurePosixPath(manifest["input_snapshot_path"]).parts)).resolve()
        try:
            input_path.relative_to(project)
        except ValueError:
            errors.append("analysis manifest input_snapshot_path escaped the review project")
        else:
            if not input_path.is_file():
                errors.append(f"analysis manifest input snapshot file is missing: {manifest['input_snapshot_path']}")
            elif hashlib.sha256(input_path.read_bytes()).hexdigest() != str(manifest.get("input_snapshot_sha256", "")).lower():
                errors.append("analysis manifest input_snapshot_sha256 does not match its file")

    # A release manifest must point to lock files that are actually archived in
    # the review project. The standalone schema validator intentionally only
    # checks the declaration; protocol-bound validation checks the bytes.
    if protocol_path is not None and isinstance(manifest.get("software"), dict):
        runtime_paths = manifest["software"].get("runtime_lock_paths", [])
        if isinstance(runtime_paths, list):
            for index, lock_path in enumerate(runtime_paths):
                if not _is_safe_project_relative_path(lock_path):
                    continue
                lock_file = (project / Path(*PurePosixPath(lock_path).parts)).resolve()
                try:
                    lock_file.relative_to(project)
                except ValueError:
                    errors.append(f"analysis manifest runtime lock [{index}] escaped the review project")
                    continue
                if not lock_file.is_file():
                    errors.append(f"analysis manifest runtime lock file is missing: {lock_path}")

    if protocol_path is not None:
        try:
            protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Unable to read approved review protocol for analysis binding: {exc}")
        else:
            errors.extend(validate_analysis_manifest_binding(manifest, protocol, path, project))
    return errors


def validate_analysis_manifest_binding(
    manifest: Dict[str, Any],
    protocol: Dict[str, Any],
    manifest_path: Optional[Union[str, Path]] = None,
    project_dir: Optional[Union[str, Path]] = None,
) -> List[str]:
    """Check synthesis decisions against the approved protocol declaration."""
    errors: List[str] = []
    if not isinstance(protocol, dict):
        return ["approved review protocol must be a JSON object"]

    protocol_project = protocol.get("project") if isinstance(protocol.get("project"), dict) else {}
    protocol_project_id = protocol_project.get("id")
    if _is_filled(protocol_project_id) and manifest.get("project_id") != protocol_project_id:
        errors.append("analysis manifest project_id does not match the approved protocol project.id")

    synthesis = protocol.get("synthesis") if isinstance(protocol.get("synthesis"), dict) else {}
    declared_path = synthesis.get("analysis_manifest_path")
    if manifest_path is not None and _is_safe_project_relative_path(declared_path):
        project = Path(project_dir or Path(manifest_path).parent).expanduser().resolve()
        actual = Path(manifest_path).expanduser().resolve()
        try:
            actual_rel = actual.relative_to(project).as_posix()
        except ValueError:
            actual_rel = ""
        if actual_rel != declared_path:
            errors.append(
                "analysis manifest path does not match synthesis.analysis_manifest_path "
                f"({actual_rel or actual} != {declared_path})"
            )

    nma_protocol = synthesis.get("network_meta_analysis") if isinstance(synthesis.get("network_meta_analysis"), dict) else {}
    nma_manifest = manifest.get("network_meta_analysis") if isinstance(manifest.get("network_meta_analysis"), dict) else {}
    if isinstance(nma_protocol.get("enabled"), bool) and nma_manifest.get("planned") != nma_protocol.get("enabled"):
        errors.append("analysis manifest NMA planned status does not match the approved protocol")

    pairwise_protocol = synthesis.get("pairwise_meta_analysis")
    if isinstance(pairwise_protocol, dict) and isinstance(pairwise_protocol.get("enabled"), bool):
        pairwise_manifest = manifest.get("pairwise") if isinstance(manifest.get("pairwise"), dict) else {}
        if pairwise_manifest.get("planned") != pairwise_protocol["enabled"]:
            errors.append("analysis manifest pairwise planned status does not match the approved protocol")

    protocol_effects = synthesis.get("effect_measures")
    manifest_effects = manifest.get("effect_measure_by_outcome")
    if isinstance(protocol_effects, dict) and isinstance(manifest_effects, dict):
        missing = sorted(set(protocol_effects) - set(manifest_effects))
        extra = sorted(set(manifest_effects) - set(protocol_effects))
        mismatched = sorted(
            key for key in set(protocol_effects).intersection(manifest_effects)
            if str(protocol_effects[key]).strip().casefold() != str(manifest_effects[key]).strip().casefold()
        )
        if missing:
            errors.append(f"analysis manifest effect_measure_by_outcome is missing protocol outcomes: {missing}")
        if extra:
            errors.append(f"analysis manifest effect_measure_by_outcome contains outcomes not declared in protocol: {extra}")
        if mismatched:
            errors.append(f"analysis manifest effect measures disagree with protocol for: {mismatched}")

    primary_protocol = synthesis.get("software", {}).get("primary_engine", {}) if isinstance(synthesis.get("software"), dict) else {}
    primary_manifest = manifest.get("software", {}).get("primary_engine", {}) if isinstance(manifest.get("software"), dict) else {}
    for field in ("name", "version"):
        expected = primary_protocol.get(field)
        actual = primary_manifest.get(field)
        if _is_filled(expected) and str(actual).strip().casefold() != str(expected).strip().casefold():
            errors.append(f"analysis manifest primary software {field} does not match the approved protocol")
    expected_role = primary_protocol.get("role")
    actual_role = primary_manifest.get("role")
    if _is_filled(expected_role) and str(actual_role).strip().casefold() != str(expected_role).strip().casefold():
        errors.append("analysis manifest primary software role does not match the approved protocol")
    expected_packages = primary_protocol.get("packages")
    actual_packages = primary_manifest.get("packages")
    if isinstance(expected_packages, list) and expected_packages:
        expected_package_names = {str(item).strip().casefold() for item in expected_packages if _is_filled(item)}
        actual_package_names = {str(item).strip().casefold() for item in actual_packages or [] if _is_filled(item)}
        if expected_package_names != actual_package_names:
            errors.append("analysis manifest primary software packages do not exactly match the approved protocol")
        if any(not re.search(r"\d", str(item)) for item in expected_packages if _is_filled(item)):
            errors.append("approved protocol primary software packages must include explicit versions")
        if any(not re.search(r"\d", str(item)) for item in actual_packages or [] if _is_filled(item)):
            errors.append("analysis manifest primary software packages must include explicit versions")
    expected_runtime = synthesis.get("software", {}).get("runtime_lock_paths") if isinstance(synthesis.get("software"), dict) else None
    actual_runtime = manifest.get("software", {}).get("runtime_lock_paths") if isinstance(manifest.get("software"), dict) else None
    if isinstance(expected_runtime, list) and expected_runtime:
        if {str(item).strip().casefold() for item in expected_runtime} != {str(item).strip().casefold() for item in actual_runtime or []}:
            errors.append("analysis manifest runtime lock paths do not exactly match the approved protocol")
    expected_certainty_tools = synthesis.get("software", {}).get("certainty_tools") if isinstance(synthesis.get("software"), dict) else None
    actual_certainty_tools = manifest.get("software", {}).get("certainty_tools") if isinstance(manifest.get("software"), dict) else None
    if isinstance(expected_certainty_tools, list) and expected_certainty_tools:
        if {
            str(item).strip().casefold() for item in expected_certainty_tools if _is_filled(item)
        } != {
            str(item).strip().casefold() for item in actual_certainty_tools or [] if _is_filled(item)
        }:
            errors.append("analysis manifest certainty tools do not exactly match the approved protocol")
    expected_seed = synthesis.get("software", {}).get("random_seed") if isinstance(synthesis.get("software"), dict) else None
    actual_seed = manifest.get("software", {}).get("random_seed") if isinstance(manifest.get("software"), dict) else None
    if _is_filled(expected_seed) and str(actual_seed).strip().casefold() != str(expected_seed).strip().casefold():
        errors.append("analysis manifest random seed does not match the approved protocol")

    model_text = str(synthesis.get("model_and_estimator", "")).casefold()
    pairwise = manifest.get("pairwise") if isinstance(manifest.get("pairwise"), dict) else {}
    manifest_model = " ".join(str(pairwise.get(field, "")) for field in ("primary_model", "primary_estimator")).casefold()
    def model_family(text: str) -> Optional[str]:
        if "random" in text:
            return "random"
        if "fixed" in text:
            return "fixed"
        if "bayes" in text:
            return "bayesian"
        return None
    expected_family = model_family(model_text)
    actual_family = model_family(manifest_model)
    if expected_family and actual_family and expected_family != actual_family:
        errors.append("analysis manifest pairwise model family does not match the approved protocol")
    pairwise_is_planned = pairwise.get("planned", True) is True
    if pairwise_is_planned:
        estimator_text = str(pairwise.get("primary_estimator", "")).casefold()
        estimator_aliases = {
            "reml": ("reml",),
            "paule-mandel": ("paule", "mandel"),
            "paule mandel": ("paule", "mandel"),
            "dersimonian-laird": ("der", "simonian", "laird"),
        }
        for label, tokens in estimator_aliases.items():
            if label in model_text and not all(token in estimator_text for token in tokens):
                errors.append(f"analysis manifest estimator does not match the protocol declaration ({label})")
        interval_text = str(synthesis.get("confidence_interval_method", "")).casefold()
        manifest_interval = str(pairwise.get("interval_method", "")).casefold()
        interval_aliases = {
            "hartung-knapp": ("hartung", "knapp"),
            "hartung knapp": ("hartung", "knapp"),
        }
        for label, tokens in interval_aliases.items():
            if label in interval_text and not all(token in manifest_interval for token in tokens):
                errors.append(f"analysis manifest interval method does not match the protocol declaration ({label})")

    if nma_manifest.get("planned") is True:
        nma_model_text = str(nma_protocol.get("model_and_multi_arm_handling", "")).casefold()
        nma_manifest_model = str(nma_manifest.get("model", "")).casefold()
        nma_family_expected = model_family(nma_model_text)
        nma_family_actual = model_family(nma_manifest_model)
        if nma_family_expected and nma_family_actual and nma_family_expected != nma_family_actual:
            errors.append("analysis manifest NMA model family does not match the approved protocol")
        nma_field_bindings = {
            "intervention_node_definitions": "node_definitions",
            "network_connectivity_and_geometry": "connectivity",
            "transitivity_assessment": "transitivity",
            "transitivity_effect_modifiers": "transitivity_effect_modifiers",
            "incoherence_assessment": "inconsistency",
            "model_and_multi_arm_handling": "multi_arm_covariance",
            "ranking_interpretation": "ranking_uncertainty",
            "certainty_framework": "certainty_method",
            "assumption_failure_plan": "assumption_failure_plan",
        }
        for protocol_field, manifest_field in nma_field_bindings.items():
            expected = nma_protocol.get(protocol_field)
            actual = nma_manifest.get(manifest_field)
            if _contract_value_filled(expected) and not _contract_value_filled(actual):
                errors.append(f"analysis manifest network_meta_analysis.{manifest_field} is missing protocol field {protocol_field}")
            elif _contract_value_filled(expected) and _canonical_contract_value(expected) != _canonical_contract_value(actual):
                errors.append(
                    "analysis manifest network_meta_analysis."
                    f"{manifest_field} does not exactly match protocol {protocol_field}"
                )
        expected_nma_model = nma_protocol.get("model_specification")
        actual_nma_model = nma_manifest.get("model")
        if _is_filled(expected_nma_model) and _canonical_contract_value(expected_nma_model) != _canonical_contract_value(actual_nma_model):
            errors.append("analysis manifest network_meta_analysis.model does not exactly match protocol model_specification")
    return errors


def validate_review_protocol_file(path: Union[str, Path]) -> List[str]:
    protocol_path = Path(path)
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read review protocol JSON: {exc}"]
    return validate_review_protocol(protocol)

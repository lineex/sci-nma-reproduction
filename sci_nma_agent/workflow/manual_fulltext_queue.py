"""Durable, report-level handoff and confirmation for manual full-text retrieval."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..databases.zotero_mcp import (
    ToolCallEvidence,
    _attachment_inventory,
    _canonical_sha256,
    _evidence_to_record,
    _extract_text_and_locators,
    _first_string,
    _argument_role,
    _records_from_response,
)


QUEUE_SCHEMA_VERSION = 1
MANUAL_QUEUE_STATES = {
    "automatic_retrieval_failed",
    "awaiting_manual_acquisition",
    "manual_acquired_unconfirmed",
    "not_retrieved_after_all_routes",
    "identity_ambiguous",
    "attachment_ambiguous",
}
QUEUE_RETRIEVAL_STATES = MANUAL_QUEUE_STATES | {"manual_confirmed"}


class ManualFullTextQueueError(RuntimeError):
    """Raised when a queue handoff or confirmation does not reconcile."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_or_name(path: Path, project_dir: Path) -> str:
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return path.name


def _identity_from_record(record: Mapping[str, Any]) -> Dict[str, str]:
    source = record.get("report_identity")
    sources = [record]
    if isinstance(source, Mapping):
        sources.insert(0, source)
    return _identity_from_sources(
        sources,
        (
            ("doi", ("doi", "DOI")),
            ("pmid", ("pmid", "PMID")),
            ("title", ("title", "report_title")),
            ("year", ("year", "publication_year")),
        ),
        "report",
    )


def _identity_from_sources(
    sources: Sequence[Mapping[str, Any]],
    fields: Sequence[Tuple[str, Sequence[str]]],
    source_label: str,
) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for identity_source in sources:
        for target, aliases in fields:
            for alias in aliases:
                value = _first_string(identity_source, alias)
                if not value:
                    continue
                prior = result.get(target)
                if prior and not _identity_values_match(target, prior, value):
                    raise ManualFullTextQueueError(f"Conflicting {source_label} identity values ({target})")
                result[target] = value
    return result


def _year_identity_token(value: Any) -> Optional[str]:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", str(value or ""))
    return match.group(1) if match else None


def _doi_identity_token(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", normalized)
    return re.sub(r"\s+", "", normalized)


def _approved_report_identity_index(
    study_report_map: Mapping[str, Any], screening_manifest: Mapping[str, Any]
) -> Dict[Tuple[str, str], Dict[str, str]]:
    result: Dict[Tuple[str, str], Dict[str, str]] = {}
    studies = study_report_map.get("studies")
    if isinstance(studies, list):
        for study in studies:
            if not isinstance(study, Mapping):
                continue
            study_id = str(study.get("study_id", "")).strip()
            for field in ("reports", "report_metadata", "report_details"):
                details = study.get(field)
                if isinstance(details, Mapping):
                    entries = [dict(value, report_id=key) for key, value in details.items() if isinstance(value, Mapping)]
                elif isinstance(details, list):
                    entries = details
                else:
                    entries = []
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        continue
                    report_id = str(entry.get("report_id", entry.get("id", ""))).strip()
                    identity = _identity_from_record(entry)
                    if study_id and report_id and identity:
                        pair = (study_id, report_id)
                        merged = dict(result.get(pair, {}))
                        for identity_field, value in identity.items():
                            prior = merged.get(identity_field)
                            if prior and not _identity_values_match(identity_field, prior, value):
                                raise ManualFullTextQueueError(
                                    f"Approved study/report identity sources conflict for {study_id}/{report_id} ({identity_field})"
                                )
                            merged[identity_field] = value
                        result[pair] = merged
    records = screening_manifest.get("records")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            pair = (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip())
            if not all(pair):
                continue
            identity = dict(result.get(pair, {}))
            screening_identity = _identity_from_record(record)
            for field, value in screening_identity.items():
                prior = identity.get(field)
                if prior and not _identity_values_match(field, prior, value):
                    raise ManualFullTextQueueError(
                        f"Approved study/report identity sources conflict for {pair[0]}/{pair[1]} ({field})"
                    )
                identity[field] = value
            if identity:
                result[pair] = identity
    return result


def _identity_values_match(field: str, left: str, right: str) -> bool:
    if field == "year":
        left_year = _year_identity_token(left)
        right_year = _year_identity_token(right)
        return bool(left_year and right_year and left_year == right_year)
    if field == "doi":
        left_doi = _doi_identity_token(left)
        right_doi = _doi_identity_token(right)
        return bool(left_doi and right_doi and left_doi == right_doi)
    return _identity_equal(left, right)


def _report_instructions(record: Mapping[str, Any], identity: Optional[Mapping[str, str]] = None) -> List[str]:
    identity = dict(identity or {})
    target = "; ".join(f"{key.upper()}={value}" for key, value in identity.items())
    return [
        "In Zotero, open the project's named full-text collection and locate this report.",
        f"Verify the report identity against {target}." if target else "Verify title, authors, year, and DOI/PMID against the screened report.",
        "Use Zotero or institutional access to acquire the full text and attach it to the exact parent item.",
        "Return to this queue and confirm the exact Zotero item key and attachment key; do not choose among ambiguous matches automatically.",
        "After confirmation, the retrieval stage will resume for unfinished queue rows and require two independent reviews again.",
    ]


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextlib.contextmanager
def _exclusive_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _queue_row(
    record: Mapping[str, Any],
    prior: Optional[Mapping[str, Any]] = None,
    expected_identity: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    study_id = str(record.get("study_id", "")).strip()
    report_id = str(record.get("report_id", "")).strip()
    retrieval_status = str(record.get("retrieval_status", ""))
    if prior:
        row = dict(prior)
        row["retrieval_status"] = retrieval_status
        row["unresolved_reason"] = record.get("unresolved_reason")
        row["source_route_attempts"] = list(record.get("route_attempts") or [])
        row["expected_identity"] = dict(expected_identity or row.get("expected_identity", {}))
        if retrieval_status == "manual_confirmed":
            row["queue_status"] = "confirmed"
        return row
    status = "confirmed" if retrieval_status == "manual_confirmed" else (
        "candidate_attached" if retrieval_status == "manual_acquired_unconfirmed" else "open"
    )
    return {
        "queue_id": f"{study_id}::{report_id}",
        "study_id": study_id,
        "report_id": report_id,
        "queue_status": status,
        "retrieval_status": retrieval_status,
        "unresolved_reason": record.get("unresolved_reason"),
        "expected_identity": dict(expected_identity or {}),
        "source_route_attempts": list(record.get("route_attempts") or []),
        "candidate": {
            "zotero_item_key": record.get("zotero_item_key"),
            "attachment_key": record.get("attachment_key"),
        },
        "instructions": _report_instructions(record, expected_identity),
        "confirmation_history": [record.get("manual_confirmation")] if retrieval_status == "manual_confirmed" and isinstance(record.get("manual_confirmation"), dict) else [],
        "events": [{"event": "queued", "timestamp": _now(), "retrieval_status": retrieval_status}],
    }


def validate_manual_fulltext_queue(
    queue: Mapping[str, Any], retrieval_manifest: Mapping[str, Any]
) -> List[str]:
    errors: List[str] = []
    if not isinstance(queue, Mapping) or queue.get("schema_version") != QUEUE_SCHEMA_VERSION:
        return ["manual full-text queue schema_version must be 1"]
    records = queue.get("records")
    retrieval_records = retrieval_manifest.get("records") if isinstance(retrieval_manifest, Mapping) else None
    if not isinstance(records, list) or not isinstance(retrieval_records, list):
        return ["manual full-text queue and retrieval manifest must contain record lists"]
    expected_hash = queue.get("retrieval_manifest_sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash):
        errors.append("manual full-text queue retrieval_manifest_sha256 must be SHA-256")
    for field in ("study_report_map_sha256", "title_abstract_screening_manifest_sha256"):
        if not isinstance(queue.get(field), str) or not re.fullmatch(r"[a-fA-F0-9]{64}", queue[field]):
            errors.append(f"manual full-text queue {field} must be SHA-256")
    pairs: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        pair = (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip())
        if not all(pair):
            errors.append(f"{prefix} requires study_id and report_id")
        if pair in pairs:
            errors.append(f"{prefix} duplicates a study/report queue row")
        pairs[pair] = record
        if record.get("queue_status") not in {"open", "candidate_attached", "confirmed", "resolved_automatically", "exhausted"}:
            errors.append(f"{prefix}.queue_status is invalid")
        instructions = record.get("instructions")
        if not isinstance(instructions, list) or not instructions or any(not isinstance(item, str) or not item.strip() for item in instructions):
            errors.append(f"{prefix}.instructions must contain report-specific handoff instructions")
        if not isinstance(record.get("events"), list):
            errors.append(f"{prefix}.events must be a list")
        if not isinstance(record.get("confirmation_history"), list):
            errors.append(f"{prefix}.confirmation_history must be a list")
        if record.get("queue_status") == "confirmed":
            identity = record.get("expected_identity")
            if not isinstance(identity, Mapping) or not any(identity.get(field) for field in ("doi", "pmid", "title")):
                errors.append(f"{prefix}.expected_identity must include an approved DOI, PMID, or title before confirmation")
            if not record.get("confirmation_history"):
                errors.append(f"{prefix}.confirmation_history is required for a confirmed row")

    retrieval_by_pair = {
        (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip()): record
        for record in retrieval_records if isinstance(record, Mapping)
    }
    for pair, record in retrieval_by_pair.items():
        retrieval_status = record.get("retrieval_status")
        queue_record = pairs.get(pair)
        if retrieval_status in MANUAL_QUEUE_STATES and queue_record is None:
            errors.append(f"retrieval row {pair[0]}/{pair[1]} is unresolved but missing a manual queue row")
            continue
        if retrieval_status in MANUAL_QUEUE_STATES and queue_record and queue_record.get("queue_status") in {"confirmed", "resolved_automatically"}:
            errors.append(f"retrieval row {pair[0]}/{pair[1]} is unresolved but its queue row is marked resolved")
        if retrieval_status == "manual_confirmed":
            if queue_record is None:
                errors.append(f"manually confirmed retrieval row {pair[0]}/{pair[1]} is missing its queue evidence")
            elif queue_record.get("queue_status") != "confirmed":
                errors.append(f"manually confirmed retrieval row {pair[0]}/{pair[1]} must have a confirmed queue row")
    for pair in pairs:
        if pair not in retrieval_by_pair:
            errors.append(f"manual queue row {pair[0]}/{pair[1]} is outside the retrieval manifest")
    return errors


def build_manual_fulltext_queue(
    project_dir: str,
    retrieval_manifest_path: str,
    study_report_map_path: str,
    screening_manifest_path: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    project = Path(project_dir).expanduser().resolve()
    manifest_path = Path(retrieval_manifest_path).expanduser()
    manifest_path = (project / manifest_path).resolve() if not manifest_path.is_absolute() else manifest_path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualFullTextQueueError(f"Unable to read retrieval manifest: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("records"), list):
        raise ManualFullTextQueueError("Retrieval manifest must contain a records list")
    map_path = Path(study_report_map_path).expanduser()
    map_path = (project / map_path).resolve() if not map_path.is_absolute() else map_path.resolve()
    screening_path = Path(screening_manifest_path).expanduser()
    screening_path = (project / screening_path).resolve() if not screening_path.is_absolute() else screening_path.resolve()
    try:
        study_report_map = json.loads(map_path.read_text(encoding="utf-8"))
        screening_manifest = json.loads(screening_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualFullTextQueueError(f"Unable to read approved identity inputs: {exc}") from exc
    if not isinstance(study_report_map, dict) or not isinstance(screening_manifest, dict):
        raise ManualFullTextQueueError("Approved map and screening artifacts must be JSON objects")
    if output_path:
        target = Path(output_path).expanduser()
        target = (project / target).resolve() if not target.is_absolute() else target.resolve()
    else:
        target = project / "screening" / "manual_fulltext_queue.json"
    try:
        target.relative_to(project)
        manifest_relative = manifest_path.relative_to(project).as_posix()
        map_relative = map_path.relative_to(project).as_posix()
        screening_relative = screening_path.relative_to(project).as_posix()
    except ValueError as exc:
        raise ManualFullTextQueueError("Queue and retrieval-manifest artifacts must remain inside the review project") from exc

    retrieval_hash = _sha256(manifest_path)
    approved_identities = _approved_report_identity_index(study_report_map, screening_manifest)
    with _exclusive_lock(target):
        prior: Dict[Tuple[str, str], Mapping[str, Any]] = {}
        if target.exists():
            try:
                old = json.loads(target.read_text(encoding="utf-8"))
                if not isinstance(old, dict) or old.get("schema_version") != QUEUE_SCHEMA_VERSION:
                    raise ManualFullTextQueueError("Existing manual queue has an unsupported schema")
                prior = {
                    (str(row.get("study_id", "")).strip(), str(row.get("report_id", "")).strip()): row
                    for row in old.get("records", []) if isinstance(row, dict)
                }
            except (OSError, json.JSONDecodeError) as exc:
                raise ManualFullTextQueueError(f"Unable to read existing manual queue: {exc}") from exc
            if (
                old.get("retrieval_manifest_sha256") != retrieval_hash
                or old.get("study_report_map_sha256") != _sha256(map_path)
                or old.get("title_abstract_screening_manifest_sha256") != _sha256(screening_path)
            ):
                raise ManualFullTextQueueError(
                    "Existing queue is bound to a different retrieval manifest; choose a new versioned --output path"
                )
            return {"queue_path": str(target), "record_count": len(prior), "retrieval_manifest_sha256": retrieval_hash, "unchanged": True}

        rows = []
        for record in manifest["records"]:
            if not isinstance(record, dict):
                continue
            pair = (str(record.get("study_id", "")).strip(), str(record.get("report_id", "")).strip())
            if record.get("retrieval_status") in MANUAL_QUEUE_STATES | {"manual_confirmed"}:
                rows.append(_queue_row(record, prior.get(pair), approved_identities.get(pair)))
        queue = {
            "schema_version": QUEUE_SCHEMA_VERSION,
            "created_at": _now(),
            "updated_at": _now(),
            "retrieval_manifest_path": manifest_relative,
            "retrieval_manifest_sha256": retrieval_hash,
            "study_report_map_path": map_relative,
            "study_report_map_sha256": _sha256(map_path),
            "title_abstract_screening_manifest_path": screening_relative,
            "title_abstract_screening_manifest_sha256": _sha256(screening_path),
            "records": rows,
        }
        errors = validate_manual_fulltext_queue(queue, manifest)
        if errors:
            raise ManualFullTextQueueError("Manual queue validation failed: " + "; ".join(errors))
        _atomic_write_json(target, queue)
    return {"queue_path": str(target), "record_count": len(rows), "retrieval_manifest_sha256": retrieval_hash, "unchanged": False}


def _normalize_identity(value: Any) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _identity_equal(left: Any, right: Any) -> bool:
    normalized_left = _normalize_identity(left)
    normalized_right = _normalize_identity(right)
    return bool(normalized_left and normalized_right and normalized_left == normalized_right)


def _metadata_identity(item: Mapping[str, Any]) -> Dict[str, str]:
    layers = [item]
    current = item
    seen = {id(item)}
    while isinstance(current.get("data"), Mapping) and id(current["data"]) not in seen:
        current = current["data"]
        seen.add(id(current))
        layers.append(current)
    return _identity_from_sources(
        list(reversed(layers)),
        (
            ("doi", ("DOI", "doi")),
            ("pmid", ("PMID", "pmid", "pubmedId", "pubmed_id")),
            ("title", ("title", "name")),
            ("year", ("year", "date", "publicationDate", "publication_date")),
        ),
        "Zotero",
    )


def _identity_match(expected: Mapping[str, str], observed: Mapping[str, str]) -> Tuple[bool, List[str]]:
    checks: List[str] = []
    stable_fields = [key for key in ("doi", "pmid", "title") if expected.get(key)]
    if not stable_fields:
        return False, ["Approved report identity must provide DOI, PMID, or title"]
    if not any(key in {"doi", "pmid"} for key in stable_fields) and not expected.get("year"):
        return False, ["Title-only identity requires an approved publication year"]
    for key in ("doi", "pmid", "title", "year"):
        expected_value = expected.get(key)
        if not expected_value:
            continue
        observed_value = observed.get(key)
        if not observed_value:
            continue
        if key == "year":
            expected_year = _year_identity_token(expected_value)
            observed_year = _year_identity_token(observed_value)
            equal = bool(expected_year and observed_year and expected_year == observed_year)
        else:
            equal = _identity_values_match(key, expected_value, observed_value)
        if not equal:
            return False, [f"Zotero item {key} does not match the queue's expected identity"]
        checks.append(key)
    if not any(field in checks for field in stable_fields):
        return False, ["Zotero item details do not expose an approved DOI, PMID, or title for comparison"]
    if "title" in stable_fields and "doi" not in checks and "pmid" not in checks and "year" not in checks:
        return False, ["Title-only identity requires a matching publication year in Zotero details"]
    return True, checks


def _attachment_records(value: Any, wanted_key: str) -> List[Mapping[str, Any]]:
    found: List[Mapping[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for name, child in node.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(name).lower())
                if normalized in {"attachments", "children"} and isinstance(child, list):
                    for attachment in child:
                        if not isinstance(attachment, Mapping):
                            continue
                        key = _first_string(attachment, "key", "attachmentKey", "attachment_key", "id", "attachmentId")
                        if key == wanted_key:
                            found.append(attachment)
                        walk(attachment)
                elif isinstance(child, Mapping):
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def _attachment_parent_keys(record: Mapping[str, Any]) -> List[str]:
    parents: List[str] = []
    current: Any = record
    seen = set()
    while isinstance(current, Mapping) and id(current) not in seen:
        seen.add(id(current))
        for field in ("parentItem", "parent_item", "parentKey", "parent_key"):
            value = _first_string(current, field)
            if value:
                parents.append(value)
        current = current.get("data")
    return parents


def _mcp_argument_roles(arguments: Mapping[str, Any]) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for name, value in arguments.items():
        role = _argument_role(str(name))
        if role not in {"item", "attachment_key", "content_mode"}:
            continue
        normalized = str(value).strip()
        if role in roles and roles[role] != normalized:
            raise ManualFullTextQueueError(f"Zotero MCP call contains conflicting {role} arguments")
        roles[role] = normalized
    return roles


async def confirm_zotero_attachment(
    *,
    project_dir: str,
    retrieval_manifest_path: str,
    queue_path: str,
    study_id: str,
    report_id: str,
    item_key: str,
    attachment_key: str,
    actor: str,
    identity_evidence: str,
    attachment_file: str,
    client: Any,
    study_report_map_path: str,
    screening_manifest_path: str,
    output_manifest_path: str,
    output_queue_path: str,
    expected_run: int,
) -> Dict[str, Any]:
    project = Path(project_dir).expanduser().resolve()
    paths = []
    for raw in (
        retrieval_manifest_path, queue_path, study_report_map_path, screening_manifest_path,
        output_manifest_path, output_queue_path,
    ):
        path = Path(raw).expanduser()
        path = (project / path).resolve() if not path.is_absolute() else path.resolve()
        try:
            path.relative_to(project)
        except ValueError as exc:
            raise ManualFullTextQueueError("Manual retrieval artifacts must remain inside the review project") from exc
        paths.append(path)
    manifest_path, queue_file, map_path, screening_path, output_manifest, output_queue = paths
    if output_manifest == output_queue:
        raise ManualFullTextQueueError("Versioned retrieval manifest and queue output paths must be different")
    local_file_source = Path(attachment_file).expanduser().resolve()
    if not local_file_source.is_file() or local_file_source.stat().st_size <= 0:
        raise ManualFullTextQueueError(f"User-supplied local file does not exist: {local_file_source}")
    actor = str(actor or "").strip()
    identity_evidence = str(identity_evidence or "").strip()
    study_id = str(study_id or "").strip()
    report_id = str(report_id or "").strip()
    item_key = str(item_key or "").strip()
    attachment_key = str(attachment_key or "").strip()
    if not all((actor, identity_evidence, study_id, report_id, item_key, attachment_key)):
        raise ManualFullTextQueueError("study/report, Zotero item/attachment, actor, and identity evidence are required")
    if output_manifest.exists() or output_queue.exists():
        raise ManualFullTextQueueError("Versioned confirmation output already exists; choose a new run number")
    try:
        retrieval = json.loads(manifest_path.read_text(encoding="utf-8"))
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        study_report_map = json.loads(map_path.read_text(encoding="utf-8"))
        screening_manifest = json.loads(screening_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualFullTextQueueError(f"Unable to read retrieval manifest or manual queue: {exc}") from exc
    if not isinstance(retrieval, dict) or not isinstance(queue, dict):
        raise ManualFullTextQueueError("Retrieval manifest and manual queue must be JSON objects")
    if queue.get("retrieval_manifest_sha256") != _sha256(manifest_path):
        raise ManualFullTextQueueError("Manual queue is stale relative to the retrieval manifest")
    if queue.get("study_report_map_sha256") != _sha256(map_path):
        raise ManualFullTextQueueError("Manual queue is stale relative to the approved study/report map")
    if queue.get("title_abstract_screening_manifest_sha256") != _sha256(screening_path):
        raise ManualFullTextQueueError("Manual queue is stale relative to approved title/abstract screening")
    queue_errors = validate_manual_fulltext_queue(queue, retrieval)
    if queue_errors:
        raise ManualFullTextQueueError("Manual queue is invalid: " + "; ".join(queue_errors))
    matches = [
        record for record in retrieval.get("records", [])
        if isinstance(record, dict) and (record.get("study_id"), record.get("report_id")) == (study_id, report_id)
    ]
    queue_rows = [
        record for record in queue.get("records", [])
        if isinstance(record, dict) and (record.get("study_id"), record.get("report_id")) == (study_id, report_id)
    ]
    if len(matches) != 1 or len(queue_rows) != 1:
        raise ManualFullTextQueueError("Exactly one matching retrieval row and queue row are required")
    source_record, queue_row = matches[0], queue_rows[0]
    if queue_row.get("queue_status") == "confirmed" or source_record.get("retrieval_status") == "manual_confirmed":
        raise ManualFullTextQueueError("This report is already manually confirmed")
    if queue_row.get("queue_status") not in {"open", "candidate_attached", "exhausted"}:
        raise ManualFullTextQueueError("This queue row is not awaiting manual confirmation")
    existing_item = str(source_record.get("zotero_item_key") or queue_row.get("candidate", {}).get("zotero_item_key") or "").strip()

    details_evidence: ToolCallEvidence = await client.read_item_details(item_key)
    details_arguments = _mcp_argument_roles(details_evidence.arguments)
    if details_arguments.get("item") != item_key:
        raise ManualFullTextQueueError("Zotero MCP item-details call did not accept the exact selected item key")
    detail_records = _records_from_response(details_evidence.raw_response)
    exact_items = [
        row for row in detail_records
        if _first_string(row, "key", "itemKey", "item_key", "id", "itemId") == item_key
    ]
    if len(exact_items) != 1:
        raise ManualFullTextQueueError("Zotero MCP details did not return exactly the requested item key")
    item = exact_items[0]
    inventory = _attachment_inventory(item)
    if attachment_key not in inventory["keys"]:
        raise ManualFullTextQueueError("Selected attachment key is not currently attached to the exact Zotero item")
    matched_attachments = _attachment_records(item, attachment_key)
    if len(matched_attachments) != 1:
        raise ManualFullTextQueueError("Selected attachment key is duplicated or ambiguous in Zotero item details")
    attachment_metadata = matched_attachments[0]
    parent_keys = _attachment_parent_keys(attachment_metadata)
    if any(parent_key != item_key for parent_key in parent_keys):
        raise ManualFullTextQueueError("Selected Zotero attachment explicitly belongs to a different parent item")
    zotero_filename = _first_string(attachment_metadata, "filename", "fileName", "file_name")
    if zotero_filename and Path(re.split(r"[/\\]", zotero_filename)[-1]).name.casefold() != local_file_source.name.casefold():
        raise ManualFullTextQueueError("Local attachment filename does not match the selected Zotero attachment metadata")
    approved_identities = _approved_report_identity_index(study_report_map, screening_manifest)
    expected_identity = approved_identities.get((study_id, report_id), {})
    if not expected_identity or queue_row.get("expected_identity") != expected_identity:
        raise ManualFullTextQueueError("Queue identity does not match the approved report identity evidence")
    observed_identity = _metadata_identity(item)
    if expected_identity:
        matched, checks = _identity_match(expected_identity, observed_identity)
        if not matched:
            raise ManualFullTextQueueError("Zotero item identity revalidation failed: " + "; ".join(checks))
    else:
        checks = ["user-attested identity evidence"]

    content_evidence: ToolCallEvidence = await client.read_item_content(item_key, attachment_key=attachment_key)
    if not any(_argument_role(str(name)) == "attachment_key" and str(value) == attachment_key for name, value in content_evidence.arguments.items()):
        raise ManualFullTextQueueError("Zotero MCP content tool did not accept the exact selected attachment key")
    text, locators = _extract_text_and_locators(content_evidence.raw_response)
    if not text:
        raise ManualFullTextQueueError("Zotero returned no extractable text for the selected attachment")
    content_arguments = _mcp_argument_roles(content_evidence.arguments)
    if content_arguments.get("item") != item_key:
        raise ManualFullTextQueueError("Zotero MCP content tool did not accept the exact selected item key")
    if content_arguments.get("attachment_key") != attachment_key:
        raise ManualFullTextQueueError("Zotero MCP content tool did not accept the exact selected attachment key")
    if content_arguments.get("content_mode", "").casefold() != "complete":
        raise ManualFullTextQueueError("Zotero MCP content tool did not accept complete mode for the selected attachment")
    content_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    local_file_sha256 = _sha256(local_file_source)
    artifact_key = hashlib.sha256(f"{study_id}\0{report_id}".encode("utf-8")).hexdigest()[:10]
    artifact_stem = (
        f"{_normalize_identity(study_id) or 'study'}__"
        f"{_normalize_identity(report_id) or 'report'}__{artifact_key}"
    )
    material_directory = project / "original_materials" / "manual_fulltext" / f"run-{expected_run:04d}"
    material_path = material_directory / f"{artifact_stem}.txt"
    attachment_extension = local_file_source.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", attachment_extension):
        attachment_extension = ""
    local_file_material_path = material_directory / f"{artifact_stem}__local_copy{attachment_extension}"
    local_file_temporary_path = local_file_material_path.with_name(
        local_file_material_path.name + f".{os.getpid()}.tmp"
    )
    if material_path.exists() or local_file_material_path.exists() or local_file_temporary_path.exists():
        raise ManualFullTextQueueError("Versioned full-text artifacts already exist; choose a new run number")
    material_directory.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(local_file_source, local_file_temporary_path)
        os.replace(local_file_temporary_path, local_file_material_path)
        if _sha256(local_file_material_path) != local_file_sha256:
            raise ManualFullTextQueueError("Archived local file hash does not match the user-supplied file")
        material_path.write_bytes((text + "\n").encode("utf-8"))
        material_sha256 = _sha256(material_path)
        if material_sha256 != hashlib.sha256((text + "\n").encode("utf-8")).hexdigest():
            raise ManualFullTextQueueError("Persisted extracted-text hash verification failed")
    except Exception:
        local_file_temporary_path.unlink(missing_ok=True)
        local_file_material_path.unlink(missing_ok=True)
        material_path.unlink(missing_ok=True)
        raise

    now = _now()
    confirmation = {
        "actor": actor,
        "confirmed_at": now,
        "identity_evidence": identity_evidence,
        "identity_checks": checks,
        "zotero_item_key": item_key,
        "recorded_candidate_item_key": existing_item or None,
        "candidate_corrected": bool(existing_item and existing_item != item_key),
        "attachment_key": attachment_key,
        "local_file_name": local_file_source.name,
        "local_file_path": local_file_material_path.relative_to(project).as_posix(),
        "local_file_sha256": local_file_sha256,
        "local_file_relation_status": "unverified_user_supplied",
        "content_sha256": content_sha256,
        "content_path": material_path.relative_to(project).as_posix(),
        "content_file_sha256": material_sha256,
        "page_locators": locators,
        "item_details_call": _evidence_to_record(details_evidence),
        "content_call": _evidence_to_record(content_evidence),
    }
    updated = json.loads(json.dumps(retrieval, ensure_ascii=False))
    updated["study_report_map_sha256"] = queue["study_report_map_sha256"]
    updated["title_abstract_screening_manifest_sha256"] = queue[
        "title_abstract_screening_manifest_sha256"
    ]
    target_record = next(
        record for record in updated["records"]
        if isinstance(record, dict) and (record.get("study_id"), record.get("report_id")) == (study_id, report_id)
    )
    target_record.update({
        "retrieval_status": "manual_confirmed",
        "full_text_review_status": "not_started",
        "fact_status": "pending_full_text_review",
        "zotero_item_key": item_key,
        "attachment_key": attachment_key,
        "local_file_name": local_file_source.name,
        "local_file_path": local_file_material_path.relative_to(project).as_posix(),
        "local_file_sha256": local_file_sha256,
        "local_file_relation_status": "unverified_user_supplied",
        "content_sha256": content_sha256,
        "content_path": material_path.relative_to(project).as_posix(),
        "content_file_sha256": material_sha256,
        "identity_match_status": "unique_match",
        "retrieval_timestamp": now,
        "manual_confirmation": confirmation,
    })
    target_record.pop("unresolved_reason", None)
    routes = list(target_record.get("route_attempts") or [])
    routes.append({
        "route": "zotero_mcp_manual_confirmation",
        "status": "attachment_revalidated_and_content_extracted",
        "attempted_at": now,
        "actor": actor,
        "item_key": item_key,
        "attachment_key": attachment_key,
    })
    target_record["route_attempts"] = routes
    queue_updated = json.loads(json.dumps(queue, ensure_ascii=False))
    target_queue_row = next(
        row for row in queue_updated["records"]
        if isinstance(row, dict) and (row.get("study_id"), row.get("report_id")) == (study_id, report_id)
    )
    target_queue_row["queue_status"] = "confirmed"
    target_queue_row["retrieval_status"] = "manual_confirmed"
    target_queue_row["expected_identity"] = dict(expected_identity)
    target_queue_row["candidate"] = {"zotero_item_key": item_key, "attachment_key": attachment_key}
    target_queue_row.setdefault("events", []).append({
        "event": "manual_attachment_confirmed",
        "timestamp": now,
        "actor": actor,
        "local_file_sha256": local_file_sha256,
        "content_sha256": content_sha256,
    })
    target_queue_row.setdefault("confirmation_history", []).append(confirmation)
    queue_updated["created_at"] = queue.get("created_at", now)
    queue_updated["updated_at"] = now
    queue_updated["retrieval_manifest_path"] = output_manifest.relative_to(project).as_posix()
    _atomic_write_json(output_manifest, updated)
    queue_updated["retrieval_manifest_sha256"] = _sha256(output_manifest)
    queue_updated["retrieval_manifest_path"] = output_manifest.relative_to(project).as_posix()
    errors = validate_manual_fulltext_queue(queue_updated, updated)
    if errors:
        output_manifest.unlink(missing_ok=True)
        local_file_material_path.unlink(missing_ok=True)
        material_path.unlink(missing_ok=True)
        raise ManualFullTextQueueError("Confirmed queue validation failed: " + "; ".join(errors))
    _atomic_write_json(output_queue, queue_updated)
    return {
        "retrieval_manifest_path": str(output_manifest),
        "retrieval_manifest_sha256": _sha256(output_manifest),
        "queue_path": str(output_queue),
        "local_file_sha256": local_file_sha256,
        "local_file_path": str(local_file_material_path),
        "content_sha256": content_sha256,
        "content_path": str(material_path),
        "study_id": study_id,
        "report_id": report_id,
        "actor": actor,
        "run": expected_run,
    }


def validate_manual_fulltext_queue_file(
    queue_path: str,
    retrieval_manifest_path: str,
    study_report_map_path: Optional[str] = None,
    screening_manifest_path: Optional[str] = None,
) -> List[str]:
    try:
        queue_file = Path(queue_path)
        manifest_file = Path(retrieval_manifest_path)
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        map_file = Path(study_report_map_path) if study_report_map_path is not None else None
        screening_file = Path(screening_manifest_path) if screening_manifest_path is not None else None
        study_report_map = json.loads(map_file.read_text(encoding="utf-8")) if map_file else None
        screening_manifest = json.loads(screening_file.read_text(encoding="utf-8")) if screening_file else None
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read manual queue or retrieval manifest: {exc}"]
    expected_hash = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    if not isinstance(queue, dict):
        return ["manual full-text queue must be a JSON object"]
    if queue.get("retrieval_manifest_sha256") != expected_hash:
        return ["manual full-text queue hash does not match the retrieval manifest"]
    if not isinstance(manifest, dict):
        return ["full-text retrieval manifest must be a JSON object"]
    if study_report_map_path is not None:
        assert map_file is not None
        if queue.get("study_report_map_sha256") != hashlib.sha256(map_file.read_bytes()).hexdigest():
            return ["manual full-text queue hash does not match the approved study/report map"]
    if screening_manifest_path is not None:
        assert screening_file is not None
        if queue.get("title_abstract_screening_manifest_sha256") != hashlib.sha256(screening_file.read_bytes()).hexdigest():
            return ["manual full-text queue hash does not match approved title/abstract screening"]
    errors = validate_manual_fulltext_queue(queue, manifest)
    if study_report_map is not None and screening_manifest is not None:
        try:
            approved_identity = _approved_report_identity_index(study_report_map, screening_manifest)
        except ManualFullTextQueueError as exc:
            errors.append(str(exc))
            return errors
        for index, row in enumerate(queue.get("records", [])):
            if not isinstance(row, Mapping):
                continue
            pair = (str(row.get("study_id", "")).strip(), str(row.get("report_id", "")).strip())
            if row.get("expected_identity", {}) != approved_identity.get(pair, {}):
                errors.append(f"records[{index}].expected_identity conflicts with approved map/screening metadata")
    return errors

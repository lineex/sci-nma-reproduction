"""Auditable, approval-gated workflow for new systematic reviews and meta-analyses."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .protocol_validation import (
    validate_analysis_manifest_file,
    validate_fact_status_manifest_file,
    validate_full_text_screening_manifest_file,
    validate_full_text_retrieval_manifest_file,
    validate_methods_source_log_for_protocol_file,
    validate_review_protocol_file,
    validate_study_report_map_file,
    validate_title_abstract_screening_manifest_file,
)
from .manual_fulltext_queue import (
    MANUAL_QUEUE_STATES,
    build_manual_fulltext_queue,
    validate_manual_fulltext_queue_file,
)


STAGES = [
    ("protocol", "Question, eligibility criteria, and frozen protocol"),
    ("search", "Reproducible multi-source search"),
    ("deduplication", "Import, provenance, and study/report linkage"),
    ("title_abstract_screening", "Independent title and abstract screening"),
    ("fulltext_retrieval", "Full-text retrieval and availability reconciliation"),
    ("fulltext_screening", "Independent full-text eligibility assessment"),
    ("data_extraction", "Study-level and outcome-level data extraction"),
    ("risk_of_bias", "Design- and outcome-specific risk-of-bias assessment"),
    ("synthesis", "Synthesis decision and statistical analysis"),
    ("certainty", "Certainty of evidence and Summary of Findings"),
    ("reporting", "PRISMA reporting, reproducibility, and final audit"),
]
STAGE_IDS = [stage_id for stage_id, _ in STAGES]


class StageLedgerError(RuntimeError):
    """Raised when a workflow transition or review gate is invalid."""


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


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _is_artifact_record(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and bool(record["path"])
        and isinstance(record.get("size_bytes"), int)
        and not isinstance(record.get("size_bytes"), bool)
        and record["size_bytes"] >= 0
        and _is_sha256(record.get("sha256"))
    )


def _is_review_record(review: Any) -> bool:
    return (
        isinstance(review, dict)
        and all(
            isinstance(review.get(field), str) and bool(review[field])
            for field in ("reviewer", "reviewer_session", "findings", "reviewed_at")
        )
        and isinstance(review.get("verdict"), str)
        and review["verdict"] in {"approve", "revise"}
        and _is_artifact_record(review.get("report"))
    )


class AgentStageLedger:
    """File-backed stage state with two independent agent reviews per gate.

    The ledger is the hand-off contract between agent execution and peer review.
    It does not call an LLM provider; Codex or another agent runner supplies the
    executor, review reports, and artifact paths through the CLI.
    """

    FILENAME = "agent_stage_ledger.json"
    REQUIRED_REVIEWS = 2

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.path = self.project_dir / "verification" / self.FILENAME

    @classmethod
    def initialize(cls, project_dir: str, overwrite: bool = False) -> Dict[str, Any]:
        instance = cls(project_dir)
        instance.path.parent.mkdir(parents=True, exist_ok=True)
        with instance._exclusive_lock():
            if instance.path.exists() and not overwrite:
                raise StageLedgerError(f"Stage ledger already exists: {instance.path}")
            ledger = {
                "schema_version": 2,
                "project_dir": str(instance.project_dir),
                "created_at": _now(),
                "updated_at": _now(),
                "required_independent_reviews": cls.REQUIRED_REVIEWS,
                "current_stage": None,
                "stages": {
                    stage_id: {
                        "title": title,
                        "status": "pending",
                        "executor": None,
                        "run_count": 0,
                        "attempts": [],
                        "artifact_manifest": [],
                        "reviews": [],
                    }
                    for stage_id, title in STAGES
                },
                "events": [],
                "event_chain_head": "0" * 64,
            }
            instance._append_event(ledger, "ledger_initialized", {"stage_count": len(STAGES)})
            instance._save(ledger)
            return ledger

    def load(self) -> Dict[str, Any]:
        if not self.path.is_file():
            raise StageLedgerError(f"Stage ledger not found: {self.path}; run review-stage init first")
        try:
            ledger = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StageLedgerError(f"Unable to read stage ledger: {exc}") from exc
        if not isinstance(ledger, dict) or ledger.get("schema_version") != 2:
            raise StageLedgerError("Unsupported or malformed stage ledger schema")
        if (
            not isinstance(ledger.get("project_dir"), str)
            or not isinstance(ledger.get("created_at"), str)
            or not isinstance(ledger.get("updated_at"), str)
            or ledger.get("required_independent_reviews") != self.REQUIRED_REVIEWS
        ):
            raise StageLedgerError("Stage ledger metadata is malformed")
        stages = ledger.get("stages")
        if not isinstance(stages, dict) or set(stages) != set(STAGE_IDS):
            raise StageLedgerError("Stage ledger stages do not match the supported workflow")
        if ledger.get("current_stage") not in (None, *STAGE_IDS):
            raise StageLedgerError("Stage ledger current_stage is invalid")
        if not _is_sha256(ledger.get("event_chain_head")):
            raise StageLedgerError("Stage ledger event_chain_head is malformed")
        if not isinstance(ledger.get("events"), list):
            raise StageLedgerError("Stage ledger events must be a list")
        for event in ledger["events"]:
            if (
                not isinstance(event, dict)
                or not isinstance(event.get("event_type"), str)
                or not isinstance(event.get("timestamp"), str)
                or not isinstance(event.get("payload"), dict)
                or not all(_is_sha256(event.get(field)) for field in ("previous_hash", "state_hash", "event_hash"))
            ):
                raise StageLedgerError("Stage ledger contains a malformed event record")
        stage_states = {"pending", "in_progress", "awaiting_review", "needs_revision", "approved"}
        for stage_id, stage in stages.items():
            if (
                not isinstance(stage, dict)
                or not isinstance(stage.get("status"), str)
                or stage["status"] not in stage_states
            ):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' is malformed")
            if (
                not isinstance(stage.get("title"), str)
                or not isinstance(stage.get("run_count"), int)
                or isinstance(stage.get("run_count"), bool)
                or stage["run_count"] < 0
                or stage.get("executor") is not None and not isinstance(stage.get("executor"), str)
                or stage.get("executor_session") is not None
                and not isinstance(stage.get("executor_session"), str)
            ):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' has malformed metadata")
            if any(not isinstance(stage.get(field), list) for field in ("artifact_manifest", "reviews", "attempts")):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' has malformed artifact/review history")
            if any(
                not isinstance(record, dict)
                for record in stage["artifact_manifest"] + stage["reviews"] + stage["attempts"]
            ):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed history entries")
            if any(not _is_artifact_record(item) for item in stage["artifact_manifest"]):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains a malformed artifact record")
            if any(not _is_review_record(item) for item in stage["reviews"]):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains a malformed review record")
            if not isinstance(stage.get("history", []), list) or any(
                not isinstance(item, dict) for item in stage.get("history", [])
            ):
                raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed stage history")
            for history_record in stage.get("history", []):
                if any(
                    not isinstance(history_record.get(field, []), list)
                    for field in ("artifact_manifest", "reviews")
                ):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed stage history")
                if any(not _is_artifact_record(item) for item in history_record.get("artifact_manifest", [])):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed stage history artifacts")
                if any(not _is_review_record(item) for item in history_record.get("reviews", [])):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed stage history reviews")
            for attempt in stage["attempts"]:
                if not isinstance(attempt.get("artifact_manifest", []), list) or any(
                    not _is_artifact_record(item) for item in attempt.get("artifact_manifest", [])
                ):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed attempt artifacts")
                if not isinstance(attempt.get("reviews", []), list) or any(
                    not _is_review_record(item) for item in attempt.get("reviews", [])
                ):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains malformed attempt reviews")
                if (
                    not isinstance(attempt.get("run"), int)
                    or isinstance(attempt.get("run"), bool)
                    or attempt["run"] < 1
                    or not isinstance(attempt.get("executor"), str)
                    or not isinstance(attempt.get("executor_session"), str)
                    or not isinstance(attempt.get("started_at"), str)
                ):
                    raise StageLedgerError(f"Stage ledger record for '{stage_id}' contains a malformed attempt record")
        return ledger

    def verify_integrity(self) -> bool:
        ledger = self.load()
        previous = "0" * 64
        for event in ledger.get("events", []):
            if event.get("previous_hash") != previous:
                return False
            body = {key: value for key, value in event.items() if key != "event_hash"}
            current = hashlib.sha256(previous.encode("ascii") + _canonical(body)).hexdigest()
            if event.get("event_hash") != current:
                return False
            previous = current
        return (
            previous == ledger.get("event_chain_head")
            and bool(ledger.get("events"))
            and ledger["events"][-1].get("state_hash") == self._state_hash(ledger)
        )

    def start(self, stage_id: str, agent: str, agent_session: str, rerun: bool = False) -> Dict[str, Any]:
        self._validate_stage(stage_id)
        agent = self._required_name(agent, "agent")
        agent_session = self._required_name(agent_session, "agent session")
        with self._exclusive_lock():
            ledger = self.load()
            stage = ledger["stages"][stage_id]
            if not self.verify_integrity():
                raise StageLedgerError("Stage ledger event hash chain is invalid")

            self._assert_all_upstream(ledger, stage_id)

            if stage["status"] in {"approved", "awaiting_review", "needs_revision"} and rerun:
                if stage["artifact_manifest"] or stage["reviews"]:
                    self._archive_active_evidence(ledger, stage_id)
                self._invalidate_from(ledger, stage_id)
                stage = ledger["stages"][stage_id]
            elif stage["status"] == "approved":
                raise StageLedgerError(f"Stage '{stage_id}' is already approved; use --rerun to invalidate downstream work")
            elif stage["status"] == "in_progress":
                if stage.get("executor") != agent or stage.get("executor_session") != agent_session:
                    raise StageLedgerError(
                        f"Stage '{stage_id}' is already running under a different agent or session"
                    )
                return ledger
            elif stage["status"] not in ("pending", "needs_revision"):
                raise StageLedgerError(f"Stage '{stage_id}' cannot start from status '{stage['status']}'")

            if stage["status"] == "needs_revision" and not rerun and (stage.get("artifact_manifest") or stage.get("reviews")):
                self._archive_active_evidence(ledger, stage_id)

            if stage["status"] == "needs_revision" and stage.get("attempts"):
                previous_attempt = stage["attempts"][-1]
                previous_attempt["closed_at"] = _now()
                previous_attempt["final_status"] = "needs_revision"
                stage.setdefault("history", []).append(
                    {
                        "run": previous_attempt.get("run"),
                        "status": "needs_revision",
                        "executor": previous_attempt.get("executor"),
                        "executor_session": previous_attempt.get("executor_session"),
                        "artifact_manifest": copy.deepcopy(stage.get("artifact_manifest", [])),
                        "reviews": copy.deepcopy(stage.get("reviews", [])),
                        "closed_at": previous_attempt["closed_at"],
                    }
                )

            stage["status"] = "in_progress"
            stage["executor"] = agent
            stage["executor_session"] = agent_session
            stage["started_at"] = _now()
            stage["submitted_at"] = None
            stage["reviews"] = []
            stage["artifact_manifest"] = []
            stage["summary"] = None
            stage["run_count"] += 1
            stage["attempts"].append(
                {
                    "run": stage["run_count"],
                    "executor": agent,
                    "executor_session": agent_session,
                    "started_at": stage["started_at"],
                }
            )
            ledger["current_stage"] = stage_id
            self._append_event(
                ledger,
                "stage_started",
                {"stage": stage_id, "agent": agent, "agent_session": agent_session, "run": stage["run_count"]},
            )
            self._save(ledger)
            return ledger

    def validate_resume(self, stage_id: str, agent: str, agent_session: str) -> Dict[str, Any]:
        """Check resume eligibility without changing the ledger state."""
        self._validate_stage(stage_id)
        agent = self._required_name(agent, "agent")
        agent_session = self._required_name(agent_session, "agent session")
        with self._exclusive_lock():
            ledger = self.load()
            action = self._resume_action(ledger, stage_id, agent, agent_session)
            stage = ledger["stages"][stage_id]
            return {
                "stage_id": stage_id,
                "action": action,
                "status": stage["status"],
                "run_count": stage["run_count"],
            }

    def resume(self, stage_id: str, agent: str, agent_session: str) -> Dict[str, Any]:
        """Resume an unfinished stage or reopen its evidence as a new attempt.

        A submitted or approved attempt is archived before reset. An unsubmitted
        in-progress attempt may be handed to a new executor session without
        discarding its report-level queue state.
        """
        self._validate_stage(stage_id)
        agent = self._required_name(agent, "agent")
        agent_session = self._required_name(agent_session, "agent session")
        with self._exclusive_lock():
            ledger = self.load()
            action = self._resume_action(ledger, stage_id, agent, agent_session)
            stage = ledger["stages"][stage_id]
            if action == "unchanged":
                return ledger
            if action == "handoff":
                previous_executor = stage.get("executor")
                previous_session = stage.get("executor_session")
                stage["executor"] = agent
                stage["executor_session"] = agent_session
                stage.setdefault("attempts", [])[-1]["handoffs"] = stage.setdefault("attempts", [])[-1].get("handoffs", []) + [{
                    "from_executor": previous_executor,
                    "from_session": previous_session,
                    "to_executor": agent,
                    "to_session": agent_session,
                    "timestamp": _now(),
                }]
                self._append_event(
                    ledger,
                    "stage_execution_handoff",
                    {"stage": stage_id, "from_executor": previous_executor, "from_session": previous_session,
                     "to_executor": agent, "to_session": agent_session, "run": stage["run_count"]},
                )
                self._save(ledger)
                return ledger
            if stage["status"] in {"approved", "awaiting_review", "needs_revision"}:
                if stage.get("artifact_manifest") or stage.get("reviews"):
                    self._archive_active_evidence(ledger, stage_id)
                self._invalidate_from(ledger, stage_id)
                stage = ledger["stages"][stage_id]

            stage["status"] = "in_progress"
            stage["executor"] = agent
            stage["executor_session"] = agent_session
            stage["started_at"] = _now()
            stage["submitted_at"] = None
            stage["reviews"] = []
            stage["artifact_manifest"] = []
            stage["summary"] = None
            stage["run_count"] += 1
            stage["attempts"].append({
                "run": stage["run_count"],
                "executor": agent,
                "executor_session": agent_session,
                "started_at": stage["started_at"],
                "resumed": True,
            })
            ledger["current_stage"] = stage_id
            self._append_event(
                ledger,
                "stage_resumed",
                {"stage": stage_id, "agent": agent, "agent_session": agent_session, "run": stage["run_count"]},
            )
            self._save(ledger)
            return ledger

    def _resume_action(self, ledger: Dict[str, Any], stage_id: str, agent: str, agent_session: str) -> str:
        if not self.verify_integrity():
            raise StageLedgerError("Stage ledger event hash chain is invalid")
        self._assert_all_upstream(ledger, stage_id)
        stage = ledger["stages"][stage_id]
        if stage["status"] == "in_progress":
            if stage.get("artifact_manifest") or stage.get("reviews"):
                raise StageLedgerError("Cannot hand off a stage after submission; use a new --rerun attempt")
            if not stage.get("attempts"):
                raise StageLedgerError(f"Stage '{stage_id}' cannot resume without an active attempt")
            if stage.get("executor") == agent and stage.get("executor_session") == agent_session:
                return "unchanged"
            return "handoff"
        if stage["status"] == "pending" or stage["status"] in {"approved", "awaiting_review", "needs_revision"}:
            if stage["status"] in {"approved", "awaiting_review", "needs_revision"}:
                self._assert_stage_evidence_current(stage_id, stage)
            return "new_attempt"
        raise StageLedgerError(f"Stage '{stage_id}' cannot resume from status '{stage['status']}'")

    def submit(
        self,
        stage_id: str,
        agent: str,
        agent_session: str,
        artifacts: Iterable[str],
        summary: str,
    ) -> Dict[str, Any]:
        self._validate_stage(stage_id)
        agent = self._required_name(agent, "agent")
        agent_session = self._required_name(agent_session, "agent session")
        summary = self._required_name(summary, "summary")
        with self._exclusive_lock():
            ledger = self.load()
            if not self.verify_integrity():
                raise StageLedgerError("Stage ledger event hash chain is invalid")
            self._assert_all_upstream(ledger, stage_id)
            stage = ledger["stages"][stage_id]
            if (
                stage["status"] != "in_progress"
                or stage.get("executor") != agent
                or stage.get("executor_session") != agent_session
            ):
                raise StageLedgerError(f"Agent '{agent}' does not own active stage '{stage_id}'")

            artifact_paths = list(artifacts)
            artifact_manifest = [self._artifact_record(path) for path in artifact_paths]
            if not artifact_manifest:
                raise StageLedgerError("At least one durable stage artifact is required")
            if stage_id == "protocol":
                protocol_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "review_protocol.json"
                ]
                if len(protocol_paths) != 1:
                    raise StageLedgerError("Protocol stage must submit exactly one review_protocol.json artifact")
                protocol_errors = validate_review_protocol_file(protocol_paths[0])
                if protocol_errors:
                    raise StageLedgerError("Protocol validation failed: " + "; ".join(protocol_errors))
                source_log_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "methods_source_log.json"
                ]
                if len(source_log_paths) != 1:
                    raise StageLedgerError("Protocol stage must submit exactly one methods_source_log.json artifact")
                source_log_errors = validate_methods_source_log_for_protocol_file(
                    source_log_paths[0], protocol_paths[0]
                )
                if source_log_errors:
                    raise StageLedgerError("Methods-source log validation failed: " + "; ".join(source_log_errors))
            elif stage_id == "deduplication":
                map_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "study_report_map.json"
                ]
                if len(map_paths) != 1:
                    raise StageLedgerError("Deduplication stage must submit exactly one study_report_map.json artifact")
                map_errors = validate_study_report_map_file(map_paths[0])
                if map_errors:
                    raise StageLedgerError("Study/report map validation failed: " + "; ".join(map_errors))
            elif stage_id == "title_abstract_screening":
                screening_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "title_abstract_screening_manifest.json"
                ]
                if len(screening_paths) != 1:
                    raise StageLedgerError(
                        "Title/abstract screening must submit exactly one title_abstract_screening_manifest.json"
                    )
                approved_map_records = [
                    record
                    for record in ledger["stages"]["deduplication"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "study_report_map.json"
                ]
                if len(approved_map_records) != 1:
                    raise StageLedgerError("Approved deduplication evidence must contain exactly one study_report_map.json")
                approved_map_path = self.project_dir / approved_map_records[0]["path"]
                screening_errors = validate_title_abstract_screening_manifest_file(
                    screening_paths[0], approved_map_path
                )
                if screening_errors:
                    raise StageLedgerError("Title/abstract screening validation failed: " + "; ".join(screening_errors))
            elif stage_id == "fulltext_retrieval":
                manifest_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "full_text_retrieval_manifest.json"
                ]
                if len(manifest_paths) != 1:
                    raise StageLedgerError(
                        "Full-text retrieval stage must submit exactly one full_text_retrieval_manifest.json artifact"
                    )
                approved_map_records = [
                    record
                    for record in ledger["stages"]["deduplication"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "study_report_map.json"
                ]
                if len(approved_map_records) != 1:
                    raise StageLedgerError("Approved deduplication evidence must contain exactly one study_report_map.json")
                approved_map_path = self.project_dir / approved_map_records[0]["path"]
                approved_scope_records = [
                    record
                    for record in ledger["stages"]["title_abstract_screening"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "title_abstract_screening_manifest.json"
                ]
                if len(approved_scope_records) != 1:
                    raise StageLedgerError(
                        "Approved title/abstract screening evidence must contain exactly one screening manifest"
                    )
                approved_scope_path = self.project_dir / approved_scope_records[0]["path"]
                retrieval_errors = validate_full_text_retrieval_manifest_file(
                    manifest_paths[0], approved_map_path, approved_scope_path, self.project_dir
                )
                if retrieval_errors:
                    raise StageLedgerError("Full-text retrieval validation failed: " + "; ".join(retrieval_errors))
                queue_records = [
                    record for record in artifact_manifest
                    if Path(record["path"]).name == "manual_fulltext_queue.json"
                ]
                if len(queue_records) > 1:
                    raise StageLedgerError("Full-text retrieval may submit at most one manual_fulltext_queue.json")
                retrieval_data = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
                has_manual_rows = any(
                    isinstance(record, dict)
                    and record.get("retrieval_status") in MANUAL_QUEUE_STATES | {"manual_confirmed"}
                    for record in retrieval_data.get("records", [])
                )
                if has_manual_rows and not queue_records:
                    queue_path = (
                        self.project_dir / "screening" / "retrieval_attempts"
                        / f"run-{stage['run_count']:04d}" / "manual_fulltext_queue.json"
                    )
                    queue_result = build_manual_fulltext_queue(
                        str(self.project_dir),
                        str(manifest_paths[0]),
                        str(approved_map_path),
                        str(approved_scope_path),
                        str(queue_path),
                    )
                    queue_path = Path(queue_result["queue_path"])
                    queue_records = [self._artifact_record(str(queue_path))]
                    artifact_manifest.extend(queue_records)
                if queue_records:
                    queue_path = self.project_dir / queue_records[0]["path"]
                    queue_errors = validate_manual_fulltext_queue_file(
                        str(queue_path),
                        str(manifest_paths[0]),
                        str(approved_map_path),
                        str(approved_scope_path),
                    )
                    if queue_errors:
                        raise StageLedgerError("Manual full-text queue validation failed: " + "; ".join(queue_errors))
                submitted_paths = {record["path"] for record in artifact_manifest}
                for retrieval_record in retrieval_data.get("records", []):
                    if not isinstance(retrieval_record, dict) or retrieval_record.get("retrieval_status") != "manual_confirmed":
                        continue
                    for field in ("local_file_path", "content_path"):
                        material_path = (self.project_dir / retrieval_record[field]).resolve()
                        relative_path = material_path.relative_to(self.project_dir).as_posix()
                        if relative_path not in submitted_paths:
                            artifact_manifest.append(self._artifact_record(str(material_path)))
                            submitted_paths.add(relative_path)
            elif stage_id == "fulltext_screening":
                screening_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "full_text_screening_manifest.json"
                ]
                if len(screening_paths) != 1:
                    raise StageLedgerError(
                        "Full-text screening must submit exactly one full_text_screening_manifest.json"
                    )
                upstream_map = [
                    record for record in ledger["stages"]["deduplication"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "study_report_map.json"
                ]
                upstream_retrieval = [
                    record for record in ledger["stages"]["fulltext_retrieval"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "full_text_retrieval_manifest.json"
                ]
                if len(upstream_map) != 1 or len(upstream_retrieval) != 1:
                    raise StageLedgerError("Approved map and retrieval manifest are required for full-text screening")
                screening_errors = validate_full_text_screening_manifest_file(
                    screening_paths[0],
                    self.project_dir / upstream_map[0]["path"],
                    self.project_dir / upstream_retrieval[0]["path"],
                )
                if screening_errors:
                    raise StageLedgerError("Full-text screening validation failed: " + "; ".join(screening_errors))
            elif stage_id == "data_extraction":
                fact_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if Path(record["path"]).name == "fact_status_manifest.json"
                ]
                if len(fact_paths) != 1:
                    raise StageLedgerError("Data-extraction stage must submit exactly one fact_status_manifest.json artifact")
                approved_map_records = [
                    record
                    for record in ledger["stages"]["deduplication"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "study_report_map.json"
                ]
                if len(approved_map_records) != 1:
                    raise StageLedgerError("Approved deduplication evidence must contain exactly one study_report_map.json")
                approved_map_path = self.project_dir / approved_map_records[0]["path"]
                approved_retrieval_records = [
                    record for record in ledger["stages"]["fulltext_retrieval"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "full_text_retrieval_manifest.json"
                ]
                approved_screening_records = [
                    record for record in ledger["stages"]["fulltext_screening"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "full_text_screening_manifest.json"
                ]
                if len(approved_retrieval_records) != 1 or len(approved_screening_records) != 1:
                    raise StageLedgerError("Approved retrieval and full-text screening manifests are required for extraction")
                fact_errors = validate_fact_status_manifest_file(
                    fact_paths[0],
                    approved_map_path,
                    self.project_dir / approved_retrieval_records[0]["path"],
                    self.project_dir / approved_screening_records[0]["path"],
                )
                if fact_errors:
                    raise StageLedgerError("Fact-status validation failed: " + "; ".join(fact_errors))
            elif stage_id == "synthesis":
                approved_protocol_records = [
                    record
                    for record in ledger["stages"]["protocol"].get("artifact_manifest", [])
                    if Path(record["path"]).name == "review_protocol.json"
                ]
                if len(approved_protocol_records) != 1:
                    raise StageLedgerError("Approved protocol evidence must contain exactly one review_protocol.json")
                protocol_path = self.project_dir / approved_protocol_records[0]["path"]
                try:
                    approved_protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise StageLedgerError(f"Unable to read approved review protocol: {exc}") from exc
                declared_path = approved_protocol.get("synthesis", {}).get("analysis_manifest_path")
                analysis_paths = [
                    self.project_dir / record["path"]
                    for record in artifact_manifest
                    if record["path"] == declared_path
                ]
                if len(analysis_paths) != 1:
                    raise StageLedgerError(
                        "Synthesis stage must submit exactly one analysis_manifest.json at the protocol-declared path"
                    )
                try:
                    analysis_data = json.loads(analysis_paths[0].read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise StageLedgerError(f"Unable to read analysis manifest: {exc}") from exc
                required_paths = {
                    analysis_paths[0].relative_to(self.project_dir).as_posix(),
                    str(analysis_data.get("input_snapshot_path", "")),
                    *(
                        str(path)
                        for path in analysis_data.get("software", {}).get("runtime_lock_paths", [])
                        if isinstance(path, str)
                    ),
                    *(
                        str(item.get("path", ""))
                        for item in analysis_data.get("outputs", [])
                        if isinstance(item, dict)
                    ),
                    *(
                        str(item.get("path", ""))
                        for item in analysis_data.get("intermediate_outputs", [])
                        if isinstance(item, dict)
                    ),
                }
                submitted_paths = {record["path"] for record in artifact_manifest}
                missing_paths = sorted(path for path in required_paths if path and path not in submitted_paths)
                if missing_paths:
                    raise StageLedgerError(
                        "Synthesis stage must submit the analysis manifest, input snapshot, and every declared "
                        f"result artifact: missing {missing_paths}"
                    )
                analysis_errors = validate_analysis_manifest_file(
                    analysis_paths[0], self.project_dir, protocol_path=protocol_path
                )
                if analysis_errors:
                    raise StageLedgerError("Analysis manifest validation failed: " + "; ".join(analysis_errors))
                if analysis_data.get("protocol_sha256") != approved_protocol_records[0].get("sha256"):
                    raise StageLedgerError("Analysis manifest protocol_sha256 does not match the approved protocol artifact")
            stage["artifact_manifest"] = artifact_manifest
            stage["summary"] = summary
            stage["submitted_at"] = _now()
            stage["status"] = "awaiting_review"
            stage["attempts"][-1].update(
                {
                    "submitted_at": stage["submitted_at"],
                    "summary": summary,
                    "artifact_manifest": copy.deepcopy(artifact_manifest),
                    "submitted_by": agent,
                    "submitted_by_session": agent_session,
                }
            )
            self._append_event(
                ledger,
                "stage_submitted",
                {"stage": stage_id, "agent": agent, "agent_session": agent_session, "artifacts": artifact_manifest},
            )
            self._save(ledger)
            return ledger

    def review(
        self,
        stage_id: str,
        reviewer: str,
        reviewer_session: str,
        verdict: str,
        report_path: str,
        findings: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._validate_stage(stage_id)
        reviewer = self._required_name(reviewer, "reviewer")
        reviewer_session = self._required_name(reviewer_session, "reviewer session")
        verdict = verdict.strip().lower()
        if verdict not in ("approve", "revise"):
            raise StageLedgerError("Review verdict must be 'approve' or 'revise'")
        with self._exclusive_lock():
            ledger = self.load()
            if not self.verify_integrity():
                raise StageLedgerError("Stage ledger event hash chain is invalid")
            self._assert_all_upstream(ledger, stage_id)
            stage = ledger["stages"][stage_id]
            if stage["status"] != "awaiting_review":
                raise StageLedgerError(f"Stage '{stage_id}' is not ready for review")
            self._assert_manifest_current(stage.get("artifact_manifest", []), stage_id, "submitted artifact")
            for prior_review in stage.get("reviews", []):
                self._assert_manifest_current([prior_review["report"]], stage_id, "review report")
            if reviewer == stage.get("executor") or reviewer_session == stage.get("executor_session"):
                raise StageLedgerError("The executing agent cannot review its own stage")
            if any(
                review["reviewer"] == reviewer or review["reviewer_session"] == reviewer_session
                for review in stage["reviews"]
            ):
                raise StageLedgerError("Reviewer ID or session already reviewed this stage")

            report = self._artifact_record(report_path)
            report_file = self.project_dir / report["path"]
            try:
                report_text = report_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise StageLedgerError("Review report must be non-empty UTF-8 text") from exc
            if not report_text.strip():
                raise StageLedgerError("Review report must be non-empty UTF-8 text")
            findings = str(findings or "").strip()
            if not findings:
                raise StageLedgerError("Reviewer findings are required for approve and revise votes")
            if any(record["path"] == report["path"] for record in stage.get("artifact_manifest", [])):
                raise StageLedgerError("Review report must be a separate artifact from the submitted stage output")
            if any(
                review["report"]["path"] == report["path"]
                or review["report"]["sha256"] == report["sha256"]
                for review in stage["reviews"]
            ):
                raise StageLedgerError("Each reviewer must provide a distinct report artifact with different content")
            review = {
                "reviewer": reviewer,
                "reviewer_session": reviewer_session,
                "verdict": verdict,
                "report": report,
                "findings": findings or "",
                "reviewed_at": _now(),
            }
            stage["reviews"].append(review)
            stage["attempts"][-1]["reviews"] = copy.deepcopy(stage["reviews"])
            approvals = sum(1 for item in stage["reviews"] if item["verdict"] == "approve")
            revisions = sum(1 for item in stage["reviews"] if item["verdict"] == "revise")
            if revisions:
                stage["status"] = "needs_revision"
            elif approvals >= self.REQUIRED_REVIEWS:
                stage["status"] = "approved"
                stage["approved_at"] = _now()
                stage["attempts"][-1]["approved_at"] = stage["approved_at"]
            else:
                stage["status"] = "awaiting_review"

            self._append_event(
                ledger,
                "stage_reviewed",
                {
                    "stage": stage_id,
                    "reviewer": reviewer,
                    "reviewer_session": reviewer_session,
                    "verdict": verdict,
                    "report": report,
                    "findings": findings or "",
                    "status": stage["status"],
                },
            )
            if stage["status"] == "approved":
                self._append_event(ledger, "stage_approved", {"stage": stage_id, "review_count": len(stage["reviews"])})
            self._save(ledger)
            return ledger

    def status(self) -> Dict[str, Any]:
        ledger = self.load()
        ledger["integrity_valid"] = self.verify_integrity()
        ledger["evidence_integrity_valid"] = self.verify_evidence_integrity()
        return ledger

    def verify_evidence_integrity(self) -> bool:
        ledger = self.load()
        try:
            self._assert_all_recorded_evidence_current(ledger)
        except (StageLedgerError, KeyError, TypeError):
            return False
        return True

    def _assert_all_recorded_evidence_current(self, ledger: Dict[str, Any]) -> None:
        for stage_id, stage in ledger["stages"].items():
            self._assert_manifest_current(stage.get("artifact_manifest", []), stage_id, "stage artifact")
            if stage_id == "synthesis" and stage.get("artifact_manifest"):
                self._assert_synthesis_manifest_current(stage)
            for review in stage.get("reviews", []):
                self._assert_manifest_current([review["report"]], stage_id, "review report")
            for attempt in stage.get("attempts", []):
                self._assert_manifest_current(attempt.get("artifact_manifest", []), stage_id, "attempt artifact")
                for review in attempt.get("reviews", []):
                    self._assert_manifest_current([review["report"]], stage_id, "attempt review report")
            for history in stage.get("history", []):
                self._assert_manifest_current(history.get("artifact_manifest", []), stage_id, "historical artifact")
                for review in history.get("reviews", []):
                    self._assert_manifest_current([review["report"]], stage_id, "historical review report")

    def _assert_all_upstream(self, ledger: Dict[str, Any], stage_id: str) -> None:
        self._assert_all_recorded_evidence_current(ledger)
        stage_index = STAGE_IDS.index(stage_id)
        for upstream_id in STAGE_IDS[:stage_index]:
            upstream = ledger["stages"][upstream_id]
            if upstream["status"] != "approved":
                raise StageLedgerError(
                    f"Stage '{stage_id}' is blocked: upstream stage '{upstream_id}' is '{upstream['status']}', not approved"
                )
            self._assert_stage_evidence_current(upstream_id, upstream)

    def _artifact_record(self, artifact: str) -> Dict[str, Any]:
        raw_path = Path(artifact).expanduser()
        path = (self.project_dir / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
        try:
            relative = path.relative_to(self.project_dir)
        except ValueError as exc:
            raise StageLedgerError(f"Artifact must be inside the review project: {path}") from exc
        if not path.is_file():
            raise StageLedgerError(f"Stage artifact does not exist: {path}")
        return {"path": relative.as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

    def _assert_stage_evidence_current(self, stage_id: str, stage: Dict[str, Any]) -> None:
        self._assert_manifest_current(stage.get("artifact_manifest", []), stage_id, "approved artifact")
        for review in stage.get("reviews", []):
            self._assert_manifest_current([review["report"]], stage_id, "review report")
        if stage_id == "synthesis" and stage.get("artifact_manifest"):
            self._assert_synthesis_manifest_current(stage)

    def _assert_manifest_current(self, manifest: List[Dict[str, Any]], stage_id: str, kind: str) -> None:
        for record in manifest:
            path = (self.project_dir / record["path"]).resolve()
            try:
                path.relative_to(self.project_dir)
            except ValueError as exc:
                raise StageLedgerError(f"{kind.title()} path escaped project for stage '{stage_id}'") from exc
            if (
                not path.is_file()
                or path.stat().st_size != record.get("size_bytes")
                or _sha256(path) != record.get("sha256")
            ):
                raise StageLedgerError(f"{kind.title()} changed after submission for stage '{stage_id}': {record['path']}")

    def _assert_synthesis_manifest_current(self, stage: Dict[str, Any]) -> None:
        """Re-validate nested input/output hashes whenever active synthesis evidence is read."""
        records = [
            record for record in stage.get("artifact_manifest", [])
            if Path(record.get("path", "")).name == "analysis_manifest.json"
        ]
        if len(records) != 1:
            raise StageLedgerError("Synthesis evidence must contain exactly one analysis_manifest.json")
        protocol_records = [
            record for record in self.load()["stages"]["protocol"].get("artifact_manifest", [])
            if Path(record.get("path", "")).name == "review_protocol.json"
        ]
        if len(protocol_records) != 1:
            raise StageLedgerError("Approved protocol evidence must contain exactly one review_protocol.json")
        manifest_path = self.project_dir / records[0]["path"]
        protocol_path = self.project_dir / protocol_records[0]["path"]
        errors = validate_analysis_manifest_file(manifest_path, self.project_dir, protocol_path=protocol_path)
        if errors:
            raise StageLedgerError("Analysis manifest evidence is stale or inconsistent: " + "; ".join(errors))
        try:
            analysis_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StageLedgerError(f"Unable to read analysis manifest evidence: {exc}") from exc
        required_paths = {
            records[0]["path"],
            str(analysis_data.get("input_snapshot_path", "")),
            *(
                str(path)
                for path in analysis_data.get("software", {}).get("runtime_lock_paths", [])
                if isinstance(path, str)
            ),
            *(str(item.get("path", "")) for item in analysis_data.get("outputs", []) if isinstance(item, dict)),
            *(
                str(item.get("path", ""))
                for item in analysis_data.get("intermediate_outputs", [])
                if isinstance(item, dict)
            ),
        }
        submitted_paths = {record.get("path") for record in stage.get("artifact_manifest", [])}
        missing_paths = sorted(path for path in required_paths if path and path not in submitted_paths)
        if missing_paths:
            raise StageLedgerError(f"Synthesis evidence is missing declared artifacts: {missing_paths}")

    def _archive_active_evidence(self, ledger: Dict[str, Any], stage_id: str) -> None:
        stage = ledger["stages"][stage_id]
        artifacts = stage.get("artifact_manifest", [])
        reviews = stage.get("reviews", [])
        if not artifacts and not reviews:
            return
        self._assert_manifest_current(artifacts, stage_id, "submitted artifact")
        for review in reviews:
            self._assert_manifest_current([review["report"]], stage_id, "review report")
        run = max(1, int(stage.get("run_count", 1)))
        archive_root = self.project_dir / "verification" / "history" / stage_id / f"run-{run:04d}"

        def archive_record(record: Dict[str, Any], bucket: str) -> Dict[str, Any]:
            source = (self.project_dir / record["path"]).resolve()
            try:
                source.relative_to(self.project_dir)
            except ValueError as exc:
                raise StageLedgerError(f"Evidence path escaped project during archive for stage '{stage_id}'") from exc
            if Path(record["path"]).as_posix().startswith("verification/history/"):
                return copy.deepcopy(record)
            destination = archive_root / bucket / Path(record["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.stat().st_size != record["size_bytes"] or _sha256(destination) != record["sha256"]:
                    raise StageLedgerError(f"Archive destination contains different evidence: {destination}")
            else:
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                shutil.copyfile(source, temporary)
                os.replace(temporary, destination)
            return {
                "path": destination.relative_to(self.project_dir).as_posix(),
                "size_bytes": record["size_bytes"],
                "sha256": record["sha256"],
            }

        archived_artifacts = [archive_record(record, "artifacts") for record in artifacts]
        archived_reviews = copy.deepcopy(reviews)
        for review in archived_reviews:
            review["report"] = archive_record(review["report"], "reviews")
        stage["artifact_manifest"] = archived_artifacts
        stage["reviews"] = archived_reviews
        if stage.get("attempts"):
            attempt = stage["attempts"][-1]
            if attempt.get("run") == stage.get("run_count"):
                attempt["artifact_manifest"] = copy.deepcopy(archived_artifacts)
                attempt["reviews"] = copy.deepcopy(archived_reviews)
                attempt["final_status"] = stage.get("status")
                attempt["archived_at"] = _now()

    def _invalidate_from(self, ledger: Dict[str, Any], stage_id: str) -> None:
        start_index = STAGE_IDS.index(stage_id)
        for current_id in STAGE_IDS[start_index:]:
            stage = ledger["stages"][current_id]
            if stage.get("artifact_manifest") or stage.get("reviews"):
                self._archive_active_evidence(ledger, current_id)
            if stage.get("status") != "pending":
                stage.setdefault("history", []).append(
                    {
                        "status": stage.get("status"),
                        "executor": stage.get("executor"),
                        "artifact_manifest": stage.get("artifact_manifest", []),
                        "reviews": stage.get("reviews", []),
                        "invalidated_at": _now(),
                    }
                )
            if stage.get("attempts") and stage["attempts"][-1].get("run") == stage.get("run_count"):
                stage["attempts"][-1].setdefault("final_status", stage.get("status"))
                stage["attempts"][-1].setdefault("closed_at", _now())
            stage["status"] = "pending"
            stage["executor"] = None
            stage["executor_session"] = None
            stage["artifact_manifest"] = []
            stage["reviews"] = []
            stage["summary"] = None
            stage["submitted_at"] = None
            stage.pop("approved_at", None)
        ledger["current_stage"] = None
        self._append_event(ledger, "downstream_stages_invalidated", {"from_stage": stage_id})

    @staticmethod
    def _validate_stage(stage_id: str) -> None:
        if stage_id not in STAGE_IDS:
            raise StageLedgerError(f"Unknown stage '{stage_id}'. Choose from: {', '.join(STAGE_IDS)}")

    @staticmethod
    def _required_name(value: str, field: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise StageLedgerError(f"{field} must be a non-empty agent identifier")
        return value

    @staticmethod
    def _append_event(ledger: Dict[str, Any], event_type: str, payload: Dict[str, Any]) -> None:
        previous = ledger.get("event_chain_head", "0" * 64)
        state_hash = AgentStageLedger._state_hash(ledger)
        body = {
            "timestamp": _now(),
            "event_type": event_type,
            "payload": payload,
            "previous_hash": previous,
            "state_hash": state_hash,
        }
        event_hash = hashlib.sha256(previous.encode("ascii") + _canonical(body)).hexdigest()
        ledger.setdefault("events", []).append({**body, "event_hash": event_hash})
        ledger["event_chain_head"] = event_hash
        ledger["updated_at"] = body["timestamp"]

    @staticmethod
    def _state_hash(ledger: Dict[str, Any]) -> str:
        state = {
            "schema_version": ledger.get("schema_version"),
            "project_dir": ledger.get("project_dir"),
            "created_at": ledger.get("created_at"),
            "required_independent_reviews": ledger.get("required_independent_reviews"),
            "current_stage": ledger.get("current_stage"),
            "stages": ledger.get("stages"),
        }
        return hashlib.sha256(_canonical(state)).hexdigest()

    def _save(self, ledger: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    @contextlib.contextmanager
    def _exclusive_lock(self):
        """Serialize read-modify-write operations across concurrent reviewer agents."""
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
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

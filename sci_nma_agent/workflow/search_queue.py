"""Serial browser-search queue with auditable, resumable state transitions.

The queue is deliberately independent of a particular browser connector.  A
browser executor claims exactly one database task, runs it in the configured
authenticated browser session, records counts for each component line,
exports full records only for the final combination, writes a hash-bound
evidence JSON, and then completes or pauses that task.  A second task cannot
be started while one task is active.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, Optional, Union


QUEUE_SCHEMA_VERSION = 2
TASK_STATES = {"pending", "running", "paused", "completed", "failed"}
ACTIVE_STATES = {"running"}
TERMINAL_STATES = {"completed"}
SUPPORTED_BROWSER_ROUTES = {"cdp_builtin_browser", "chrome_devtools"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
class SearchQueueError(ValueError):
    """Raised when a serial search queue cannot be safely advanced."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = PurePosixPath(value.replace("\\", "/"))
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and str(path) not in {"", "."}
    )


def _project_file(project_dir: Path, relative_path: str) -> Path:
    if not _is_safe_relative_path(relative_path):
        raise SearchQueueError(f"project-relative path is required: {relative_path!r}")
    candidate = (project_dir / Path(*PurePosixPath(relative_path).parts)).resolve()
    try:
        candidate.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise SearchQueueError("evidence path escaped the review project") from exc
    return candidate


def _lock_path(queue_path: Path) -> Path:
    return queue_path.with_name(queue_path.name + ".lock")


class _QueueFileLock:
    """Small cross-platform exclusive lock for queue read-modify-write calls."""

    def __init__(self, queue_path: Path, timeout_sec: float = 15.0):
        self.queue_path = queue_path
        self.lock_path = _lock_path(queue_path)
        self.timeout_sec = timeout_sec
        self._fd: Optional[int] = None

    def __enter__(self) -> "_QueueFileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_sec
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(
                    self._fd,
                    json.dumps(
                        {"pid": os.getpid(), "created_at": now_iso()},
                        ensure_ascii=False,
                    ).encode("utf-8"),
                )
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise SearchQueueError(
                        f"search queue is locked by another executor: {self.queue_path}"
                    )
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchQueueError(f"cannot read search queue JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SearchQueueError("search queue JSON must contain an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validate_queue(queue: Mapping[str, Any]) -> None:
    if queue.get("schema_version") != QUEUE_SCHEMA_VERSION:
        raise SearchQueueError(
            f"search queue schema_version must be {QUEUE_SCHEMA_VERSION}"
        )
    tasks = queue.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SearchQueueError("search queue must contain a non-empty tasks list")
    execution_policy = queue.get("execution_policy")
    if not isinstance(execution_policy, Mapping):
        raise SearchQueueError("search queue execution_policy must be an object")
    active = [
        task for task in tasks
        if isinstance(task, Mapping) and task.get("status") in ACTIVE_STATES
    ]
    if len(active) > 1:
        raise SearchQueueError("search queue contains more than one active browser task")
    ordinals = []
    ids = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise SearchQueueError(f"tasks[{index}] must be an object")
        if task.get("status") not in TASK_STATES:
            raise SearchQueueError(f"tasks[{index}].status is invalid")
        task_id = str(task.get("task_id", "")).strip()
        if not task_id or task_id in ids:
            raise SearchQueueError(f"tasks[{index}].task_id must be unique and non-empty")
        ids.add(task_id)
        ordinal = task.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 1:
            raise SearchQueueError(f"tasks[{index}].ordinal must be a positive integer")
        ordinals.append(ordinal)
        database = str(task.get("database", "")).strip()
        if not database:
            raise SearchQueueError(f"tasks[{index}].database is required")
        expected_contract = {
            "component_lines": "count_only",
            "final_combination": "export_full_records",
            "final_export_scope": "final_combination_only",
        }
        if task.get("execution_contract") != expected_contract:
            raise SearchQueueError(
                f"tasks[{index}].execution_contract must require component counts "
                "and final-combination full-record export"
            )
        line_plan = task.get("line_plan")
        if not isinstance(line_plan, list) or not line_plan:
            raise SearchQueueError(f"tasks[{index}].line_plan is required")
        line_numbers = []
        combination_numbers = []
        for line in line_plan:
            if not isinstance(line, Mapping):
                raise SearchQueueError(f"tasks[{index}].line_plan entries must be objects")
            number = line.get("line_number")
            line_type = line.get("line_type")
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                raise SearchQueueError(
                    f"tasks[{index}].line_plan.line_number must be a positive integer"
                )
            if line_type not in {"concept", "filter", "limit", "combination"}:
                raise SearchQueueError(
                    f"tasks[{index}].line_plan.line_type is invalid"
                )
            expected_role = (
                "final_combination"
                if line_type == "combination"
                else "component_count_only"
            )
            if line.get("result_role") != expected_role:
                raise SearchQueueError(
                    f"tasks[{index}].line_plan result_role is inconsistent"
                )
            line_numbers.append(number)
            if line_type == "combination":
                combination_numbers.append(number)
        if sorted(line_numbers) != list(range(1, len(line_plan) + 1)):
            raise SearchQueueError(
                f"tasks[{index}].line_plan numbers must be contiguous and ordered"
            )
        expected_component_numbers = [
            number for number in line_numbers if number not in combination_numbers
        ]
        if task.get("component_line_numbers") != expected_component_numbers:
            raise SearchQueueError(
                f"tasks[{index}].component_line_numbers do not match line_plan"
            )
        if (
            len(combination_numbers) != 1
            or task.get("final_combination_line_number") != combination_numbers[0]
        ):
            raise SearchQueueError(
                f"tasks[{index}].final_combination_line_number is invalid"
            )
        if (
            isinstance(execution_policy, Mapping)
            and execution_policy.get("line_checkpoints_required") is True
        ):
            checkpoints = task.get("line_checkpoints")
            if not isinstance(checkpoints, list) or len(checkpoints) != len(line_plan):
                raise SearchQueueError(
                    f"tasks[{index}].line_checkpoints must cover every strategy line"
                )
            pending_seen = False
            for checkpoint_index, (line, checkpoint) in enumerate(
                zip(line_plan, checkpoints)
            ):
                if not isinstance(checkpoint, Mapping):
                    raise SearchQueueError(
                        f"tasks[{index}].line_checkpoints[{checkpoint_index}] must be an object"
                    )
                if checkpoint.get("line_number") != line["line_number"]:
                    raise SearchQueueError(
                        f"tasks[{index}].line_checkpoints must follow strategy line order"
                    )
                checkpoint_status = checkpoint.get("status")
                if checkpoint_status not in {"pending", "completed"}:
                    raise SearchQueueError(
                        f"tasks[{index}].line_checkpoints[{checkpoint_index}].status is invalid"
                    )
                if checkpoint_status == "pending":
                    pending_seen = True
                    if (
                        checkpoint.get("result_count") is not None
                        or checkpoint.get("history_or_query_locator") is not None
                        or checkpoint.get("completed_at") is not None
                    ):
                        raise SearchQueueError(
                            f"tasks[{index}].pending line checkpoint contains completion data"
                        )
                else:
                    if pending_seen:
                        raise SearchQueueError(
                            f"tasks[{index}].line checkpoints must be completed in order"
                        )
                    count = checkpoint.get("result_count")
                    if (
                        not isinstance(count, int)
                        or isinstance(count, bool)
                        or count < 0
                        or not str(checkpoint.get("history_or_query_locator", "")).strip()
                        or not str(checkpoint.get("completed_at", "")).strip()
                    ):
                        raise SearchQueueError(
                            f"tasks[{index}].completed line checkpoint lacks count or locator"
                        )
        if task.get("status") == "running":
            if not str(task.get("executor_session", "")).strip():
                raise SearchQueueError(
                    f"tasks[{index}].executor_session is required while running"
                )
    if sorted(ordinals) != list(range(1, len(tasks) + 1)):
        raise SearchQueueError("task ordinals must be contiguous and ordered")

    # A later task may not be completed while an earlier task is unresolved.
    unresolved_before = False
    for task in tasks:
        if task["status"] in {"pending", "running", "paused", "failed"}:
            unresolved_before = True
        elif task["status"] == "completed" and unresolved_before:
            raise SearchQueueError(
                "search queue cannot complete a later database before earlier tasks"
            )


def _append_event(
    queue: Dict[str, Any],
    *,
    action: str,
    task: Optional[Mapping[str, Any]],
    actor: str,
    session: str,
    details: Optional[Mapping[str, Any]] = None,
) -> None:
    event = {
        "event_id": str(uuid.uuid4()),
        "action": action,
        "task_id": task.get("task_id") if task else None,
        "database": task.get("database") if task else None,
        "actor": actor,
        "session": session,
        "created_at": now_iso(),
        "details": dict(details or {}),
    }
    queue.setdefault("events", []).append(event)


def _load_and_validate(queue_path: Path) -> Dict[str, Any]:
    queue = _read_json(queue_path)
    _validate_queue(queue)
    return queue


def _mutate(
    queue_path: Path,
    mutator,
) -> Dict[str, Any]:
    queue_path = queue_path.expanduser().resolve()
    with _QueueFileLock(queue_path):
        queue = _load_and_validate(queue_path)
        result = mutator(queue)
        _validate_queue(queue)
        _write_json(queue_path, queue)
        return result


def _find_task(queue: Mapping[str, Any], task_id: str) -> Dict[str, Any]:
    for task in queue.get("tasks", []):
        if isinstance(task, dict) and task.get("task_id") == task_id:
            return task
    raise SearchQueueError(f"unknown search task: {task_id}")


def _active_task(queue: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    for task in queue.get("tasks", []):
        if isinstance(task, dict) and task.get("status") == "running":
            return task
    return None


def _next_task(queue: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    for task in queue.get("tasks", []):
        if not isinstance(task, dict):
            continue
        if task["status"] in {"pending", "paused", "failed"}:
            return task
        if task["status"] == "running":
            return None
    return None


def _validate_task_source_hashes(project_dir: Path, task: Mapping[str, Any]) -> None:
    for artifact_field, hash_field in (
        ("strategy_artifact", "strategy_sha256"),
        ("execution_artifact", "execution_query_sha256"),
    ):
        relative = task.get(artifact_field)
        if not _is_safe_relative_path(relative):
            raise SearchQueueError(f"{artifact_field} must be a project-relative path")
        artifact = _project_file(project_dir, relative)
        if not artifact.is_file():
            raise SearchQueueError(f"queued search artifact is missing: {relative}")
        expected = str(task.get(hash_field, "")).casefold()
        if not SHA256_RE.fullmatch(expected) or file_sha256(artifact) != expected:
            raise SearchQueueError(f"{artifact_field} hash is stale: {relative}")


def create_search_queue(
    *,
    pico: Mapping[str, Any],
    project_dir: Union[str, Path],
    queue_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Generate native strategy artifacts and a deterministic serial queue."""
    from ..databases.query_harmonizer import QueryHarmonizer

    project = Path(project_dir).expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    queue_file = (
        Path(queue_path).expanduser().resolve()
        if queue_path is not None
        else project / "search" / "browser_search_queue.json"
    )
    if queue_file.exists() and not overwrite:
        raise SearchQueueError(
            f"search queue already exists; use overwrite explicitly: {queue_file}"
        )
    plan = QueryHarmonizer.harmonize_with_strategy(dict(pico))
    artifacts = QueryHarmonizer.write_strategy_artifacts(dict(pico), str(project))
    tasks: List[Dict[str, Any]] = []
    for ordinal, (database, item) in enumerate(plan["databases"].items(), start=1):
        native_path = Path(artifacts[database]).resolve()
        execution_path = project / item["appendix_policy"]["execution_artifact"]
        tasks.append(
            {
                "task_id": f"SEARCH-{ordinal:03d}-{database}",
                "ordinal": ordinal,
                "database": database,
                "platform": database,
                "interface": "browser",
                "execution_contract": {
                    "component_lines": "count_only",
                    "final_combination": "export_full_records",
                    "final_export_scope": "final_combination_only",
                },
                "line_plan": [
                    {
                        "line_number": line["line_number"],
                        "line_type": line["line_type"],
                        "concept_block": line.get("concept_block"),
                        "native_syntax": line["native_syntax"],
                        "result_role": (
                            "final_combination"
                            if line["line_type"] == "combination"
                            else "component_count_only"
                        ),
                    }
                    for line in item["native_lines"]
                ],
                "line_checkpoints": [
                    {
                        "line_number": line["line_number"],
                        "status": "pending",
                        "result_count": None,
                        "history_or_query_locator": None,
                        "completed_at": None,
                    }
                    for line in item["native_lines"]
                ],
                "component_line_numbers": [
                    line["line_number"]
                    for line in item["native_lines"]
                    if line["line_type"] != "combination"
                ],
                "final_combination_line_number": next(
                    line["line_number"]
                    for line in item["native_lines"]
                    if line["line_type"] == "combination"
                ),
                "status": "pending",
                "strategy_artifact": native_path.relative_to(project).as_posix(),
                "execution_artifact": execution_path.relative_to(project).as_posix(),
                "strategy_sha256": file_sha256(native_path),
                "execution_query_sha256": file_sha256(execution_path),
                "browser_route": None,
                "executor_session": None,
                "executor": None,
                "attempt_count": 0,
                "started_at": None,
                "completed_at": None,
                "paused_at": None,
                "failed_at": None,
                "evidence": None,
                "last_error": None,
            }
        )
    queue = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": f"SEARCH-QUEUE-{uuid.uuid4().hex[:12]}",
        "created_at": now_iso(),
        "project_dir": str(project),
        "pico_source": None,
        "strategy_policy": deepcopy(plan["search_policy"]),
        "concept_blocks": deepcopy(plan["concept_blocks"]),
        "execution_policy": {
            "mode": "strict_serial",
            "max_active_tasks": 1,
            "browser_route_order": ["cdp_builtin_browser", "chrome_devtools"],
            "verification_checkpoint": "pause_and_resume_same_session",
            "parallel_browser_calls": False,
            "advance_requires_user_confirmation": True,
            "line_checkpoints_required": True,
        },
        "tasks": tasks,
        "events": [],
    }
    _append_event(
        queue,
        action="queue_created",
        task=None,
        actor="search-queue",
        session="queue-creation",
        details={
            "task_count": len(tasks),
            "strategy_plan_sha256": canonical_sha256(plan),
        },
    )
    _validate_queue(queue)
    _write_json(queue_file, queue)
    queue["queue_path"] = str(queue_file)
    return queue


def load_search_queue(queue_path: Union[str, Path]) -> Dict[str, Any]:
    queue_file = Path(queue_path).expanduser().resolve()
    queue = _load_and_validate(queue_file)
    queue["queue_path"] = str(queue_file)
    return queue


def validate_search_queue_file(
    queue_path: Union[str, Path],
    *,
    project_dir: Optional[Union[str, Path]] = None,
    require_completed: bool = False,
) -> List[str]:
    """Validate a persisted queue and, optionally, release readiness.

    The queue transition functions validate evidence at completion time.  The
    stage ledger calls this function again at submission/review time so a
    changed strategy, execution query, history, or export cannot silently
    invalidate the search stage after the browser run.
    """
    errors: List[str] = []
    try:
        queue = load_search_queue(queue_path)
    except (OSError, SearchQueueError) as exc:
        return [str(exc)]

    queue_file = Path(queue["queue_path"]).resolve()
    expected_project = (
        Path(project_dir).expanduser().resolve()
        if project_dir is not None
        else Path(str(queue.get("project_dir", ""))).expanduser().resolve()
    )
    if Path(str(queue.get("project_dir", ""))).expanduser().resolve() != expected_project:
        errors.append("search queue project_dir does not match the submitted project")

    policy = queue.get("execution_policy", {})
    if (
        not isinstance(policy, Mapping)
        or policy.get("mode") != "strict_serial"
        or policy.get("max_active_tasks") != 1
        or policy.get("parallel_browser_calls") is not False
        or policy.get("advance_requires_user_confirmation") is not True
        or policy.get("line_checkpoints_required") is not True
    ):
        errors.append(
            "search queue execution_policy must be strict_serial with "
            "max_active_tasks=1, parallel_browser_calls=false, "
            "line_checkpoints_required=true, and advance_requires_user_confirmation=true"
        )

    for task in queue.get("tasks", []):
        if not isinstance(task, Mapping):
            continue
        task_label = str(task.get("task_id", task.get("database", "unknown")))
        for field in ("strategy_artifact", "execution_artifact"):
            relative = task.get(field)
            if not _is_safe_relative_path(relative):
                errors.append(f"{task_label}: {field} must be project-relative")
                continue
            path = _project_file(expected_project, relative)
            if not path.is_file():
                errors.append(f"{task_label}: missing {field}: {relative}")
                continue
            expected_hash = (
                task.get("strategy_sha256")
                if field == "strategy_artifact"
                else task.get("execution_query_sha256")
            )
            if str(expected_hash).casefold() != file_sha256(path):
                errors.append(f"{task_label}: {field} hash is stale")

        if task.get("status") == "completed":
            evidence = task.get("evidence")
            if not isinstance(evidence, Mapping):
                errors.append(f"{task_label}: completed task has no evidence object")
                continue
            try:
                _validate_evidence(evidence, project_dir=expected_project, task=task)
            except SearchQueueError as exc:
                errors.append(f"{task_label}: {exc}")
        elif require_completed:
            errors.append(
                f"{task_label}: task status is {task.get('status')}; "
                "all browser tasks must be completed before search-stage release"
            )

    if require_completed and any(
        isinstance(task, Mapping) and task.get("status") != "completed"
        for task in queue.get("tasks", [])
    ):
        errors.append("search queue is not release-ready: unresolved browser tasks remain")

    if not queue_file.is_file():
        errors.append(f"search queue file is missing: {queue_file}")
    return errors


def start_search_task(
    queue_path: Union[str, Path],
    *,
    session: str,
    actor: str,
    browser_route: str = "cdp_builtin_browser",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Claim the next task; a running task always blocks another claim."""
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        active = _active_task(queue)
        if active is not None:
            raise SearchQueueError(
                f"search task {active['task_id']} is already running; "
                "complete, pause, or fail it before starting another"
            )
        policy = queue.get("execution_policy", {})
        if (
            not isinstance(policy, Mapping)
            or policy.get("line_checkpoints_required") is not True
        ):
            raise SearchQueueError(
                "this queue predates durable per-line checkpoints; preserve it and "
                "reconcile or initialize a checkpoint-enabled queue before searching"
            )
        if browser_route not in SUPPORTED_BROWSER_ROUTES:
            raise SearchQueueError(
                "browser_route must be cdp_builtin_browser or chrome_devtools"
            )
        task = _next_task(queue)
        if task is None:
            raise SearchQueueError("search queue has no runnable task")
        if task_id and task["task_id"] != task_id:
            raise SearchQueueError(
                f"task {task_id} is not next; the queue requires {task['task_id']} first"
            )
        if task["status"] != "pending":
            raise SearchQueueError(
                f"task {task['task_id']} is {task['status']}; resume it explicitly before retrying"
            )
        project = Path(str(queue.get("project_dir", ""))).expanduser().resolve()
        _validate_task_source_hashes(project, task)
        if (
            queue.get("execution_policy", {}).get("advance_requires_user_confirmation") is True
            and task.get("ordinal", 1) > 1
        ):
            previous = next(
                (
                    item for item in queue.get("tasks", [])
                    if item.get("ordinal") == task.get("ordinal", 0) - 1
                ),
                None,
            )
            confirmation = task.get("user_confirmation")
            if (
                previous is None
                or previous.get("status") != "completed"
                or not isinstance(confirmation, Mapping)
                or confirmation.get("previous_task_id") != previous.get("task_id")
                or str(confirmation.get("actor", "")).casefold() != "user"
            ):
                raise SearchQueueError(
                    "user confirmation is required before starting the next database"
                )
            _validate_task_source_hashes(project, previous)
            previous_evidence = previous.get("evidence")
            if not isinstance(previous_evidence, Mapping):
                raise SearchQueueError(
                    "the preceding database has no saved search evidence"
                )
            _validate_evidence(
                previous_evidence,
                project_dir=project,
                task=previous,
            )
        task["status"] = "running"
        task["executor_session"] = session
        task["executor"] = actor
        task["browser_route"] = browser_route
        task["attempt_count"] = int(task.get("attempt_count", 0)) + 1
        task["started_at"] = now_iso()
        task["paused_at"] = None
        task["last_error"] = None
        _append_event(
            queue,
            action="task_started",
            task=task,
            actor=actor,
            session=session,
            details={"attempt_count": task["attempt_count"]},
        )
        return deepcopy(task)

    return _mutate(Path(queue_path), mutate)


def resume_search_task(
    queue_path: Union[str, Path],
    *,
    task_id: str,
    actor: str,
    session: str,
) -> Dict[str, Any]:
    """Move a paused/failed task back to pending without starting it."""
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        if _active_task(queue) is not None:
            raise SearchQueueError("finish the active browser task before resuming another")
        task = _find_task(queue, task_id)
        if task["status"] not in {"paused", "failed"}:
            raise SearchQueueError(
                f"only paused or failed tasks can be resumed: {task_id}"
            )
        task["status"] = "pending"
        task["executor_session"] = None
        task["executor"] = None
        task["last_error"] = None
        _append_event(
            queue,
            action="task_resumed",
            task=task,
            actor=actor,
            session=session,
        )
        return deepcopy(task)

    return _mutate(Path(queue_path), mutate)


def record_search_line_count(
    queue_path: Union[str, Path],
    *,
    task_id: str,
    session: str,
    actor: str,
    line_number: int,
    result_count: int,
    history_or_query_locator: str,
) -> Dict[str, Any]:
    """Persist one line's result count before allowing the next line to run."""
    if not isinstance(line_number, int) or isinstance(line_number, bool) or line_number < 1:
        raise SearchQueueError("line_number must be a positive integer")
    if (
        not isinstance(result_count, int)
        or isinstance(result_count, bool)
        or result_count < 0
    ):
        raise SearchQueueError("result_count must be a non-negative integer")
    locator = str(history_or_query_locator).strip()
    if not locator:
        raise SearchQueueError("history_or_query_locator is required")
    if not str(actor).strip():
        raise SearchQueueError("actor is required")

    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        task = _require_running_task(queue, task_id=task_id, session=session)
        checkpoints = task.get("line_checkpoints")
        if not isinstance(checkpoints, list):
            raise SearchQueueError(
                "this legacy queue does not persist per-line checkpoints"
            )
        next_checkpoint = next(
            (entry for entry in checkpoints if entry.get("status") == "pending"),
            None,
        )
        if next_checkpoint is None:
            raise SearchQueueError("all strategy lines already have saved counts")
        if next_checkpoint["line_number"] != line_number:
            raise SearchQueueError(
                f"record line {next_checkpoint['line_number']} next; "
                f"line {line_number} is out of order"
            )
        next_checkpoint["status"] = "completed"
        next_checkpoint["result_count"] = result_count
        next_checkpoint["history_or_query_locator"] = locator
        next_checkpoint["completed_at"] = now_iso()
        line = task["line_plan"][line_number - 1]
        _append_event(
            queue,
            action="search_line_count_recorded",
            task=task,
            actor=actor,
            session=session,
            details={
                "line_number": line_number,
                "line_type": line["line_type"],
                "result_role": line["result_role"],
                "result_count": result_count,
                "history_or_query_locator": locator,
            },
        )
        return deepcopy(next_checkpoint)

    return _mutate(Path(queue_path), mutate)


def confirm_next_search_task(
    queue_path: Union[str, Path],
    *,
    actor: str,
    session: str,
) -> Dict[str, Any]:
    """Record the user's explicit decision to advance to the next database."""
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        if _active_task(queue) is not None:
            raise SearchQueueError("finish the active database before confirming the next")
        if queue.get("execution_policy", {}).get("advance_requires_user_confirmation") is not True:
            raise SearchQueueError("this legacy queue does not require explicit database confirmation")
        next_task = _next_task(queue)
        if next_task is None or next_task.get("status") != "pending":
            raise SearchQueueError("there is no pending next database to confirm")
        previous = next(
            (
                item for item in queue.get("tasks", [])
                if item.get("ordinal") == next_task.get("ordinal", 0) - 1
            ),
            None,
        )
        if previous is None or previous.get("status") != "completed":
            raise SearchQueueError("the preceding database must be completed before confirmation")
        project = Path(str(queue.get("project_dir", ""))).expanduser().resolve()
        _validate_task_source_hashes(project, previous)
        previous_evidence = previous.get("evidence")
        if not isinstance(previous_evidence, Mapping):
            raise SearchQueueError("the preceding database has no saved search evidence")
        _validate_evidence(
            previous_evidence,
            project_dir=project,
            task=previous,
        )
        confirmation_actor = str(actor).strip()
        confirmation_session = str(session).strip()
        if not confirmation_actor or not confirmation_session:
            raise SearchQueueError("confirmation actor and session are required")
        if confirmation_actor.casefold() != "user":
            raise SearchQueueError(
                "the continuation confirmation must be recorded with actor 'user'"
            )
        confirmation = {
            "actor": confirmation_actor,
            "session": confirmation_session,
            "confirmed_at": now_iso(),
            "previous_task_id": previous["task_id"],
        }
        next_task["user_confirmation"] = confirmation
        _append_event(
            queue,
            action="user_confirmed_next_database",
            task=next_task,
            actor=confirmation_actor,
            session=confirmation_session,
            details={
                "previous_task_id": previous["task_id"],
                "next_task_id": next_task["task_id"],
            },
        )
        return deepcopy(next_task)

    return _mutate(Path(queue_path), mutate)


def _require_running_task(
    queue: Dict[str, Any],
    *,
    task_id: str,
    session: str,
) -> Dict[str, Any]:
    task = _find_task(queue, task_id)
    if task["status"] != "running":
        raise SearchQueueError(f"task {task_id} is not running")
    if task.get("executor_session") != session:
        raise SearchQueueError(
            f"task {task_id} is owned by another executor session"
        )
    return task


def pause_search_task(
    queue_path: Union[str, Path],
    *,
    task_id: str,
    session: str,
    actor: str,
    reason: str,
    checkpoint: Optional[str] = None,
) -> Dict[str, Any]:
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        task = _require_running_task(queue, task_id=task_id, session=session)
        if not str(reason).strip():
            raise SearchQueueError("pause reason is required")
        task["status"] = "paused"
        task["paused_at"] = now_iso()
        task["last_error"] = str(reason).strip()
        details = {"reason": str(reason).strip()}
        if checkpoint:
            details["checkpoint"] = checkpoint
        _append_event(
            queue,
            action="task_paused",
            task=task,
            actor=actor,
            session=session,
            details=details,
        )
        return deepcopy(task)

    return _mutate(Path(queue_path), mutate)


def fail_search_task(
    queue_path: Union[str, Path],
    *,
    task_id: str,
    session: str,
    actor: str,
    reason: str,
) -> Dict[str, Any]:
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        task = _require_running_task(queue, task_id=task_id, session=session)
        if not str(reason).strip():
            raise SearchQueueError("failure reason is required")
        task["status"] = "failed"
        task["failed_at"] = now_iso()
        task["last_error"] = str(reason).strip()
        _append_event(
            queue,
            action="task_failed",
            task=task,
            actor=actor,
            session=session,
            details={"reason": str(reason).strip()},
        )
        return deepcopy(task)

    return _mutate(Path(queue_path), mutate)


def _validate_evidence(
    evidence: Mapping[str, Any],
    *,
    project_dir: Path,
    task: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise SearchQueueError("search evidence must be a JSON object")
    route = str(evidence.get("browser_route", "")).strip()
    if route not in SUPPORTED_BROWSER_ROUTES:
        raise SearchQueueError(
            "browser_route must be cdp_builtin_browser or chrome_devtools"
        )
    if evidence.get("database") != task.get("database"):
        raise SearchQueueError("search evidence database does not match the task")
    if task.get("browser_route") and route != task.get("browser_route"):
        raise SearchQueueError("search evidence browser_route does not match the claimed route")
    _validate_task_source_hashes(project_dir, task)
    for field in ("strategy_sha256", "execution_query_sha256"):
        expected = str(task.get(field, "")).casefold()
        observed = str(evidence.get(field, "")).casefold()
        if not expected or not SHA256_RE.fullmatch(observed) or observed != expected:
            raise SearchQueueError(
                f"search evidence {field} must match the queued strategy artifact"
            )
    if evidence.get("final_export_scope") != "final_combination_only":
        raise SearchQueueError(
            "final_export_scope must be final_combination_only; component lines "
            "must not export detailed records"
        )
    if evidence.get("final_record_detail_level") != "full":
        raise SearchQueueError(
            "final_record_detail_level must be full for the final combination export"
        )
    if evidence.get("final_export_complete") is not True:
        raise SearchQueueError(
            "final_export_complete must be true before the search task can complete"
        )

    line_counts = evidence.get("component_line_counts")
    if not isinstance(line_counts, list):
        raise SearchQueueError("component_line_counts must be a list")
    expected_line_numbers = list(task.get("component_line_numbers", []))
    observed_line_numbers = []
    for index, line in enumerate(line_counts):
        if not isinstance(line, Mapping):
            raise SearchQueueError(
                f"component_line_counts[{index}] must be an object"
            )
        number = line.get("line_number")
        if number in observed_line_numbers:
            raise SearchQueueError(
                f"component_line_counts contains duplicate line {number}"
            )
        if number not in expected_line_numbers:
            raise SearchQueueError(
                f"component_line_counts contains non-component line {number}"
            )
        count = line.get("result_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise SearchQueueError(
                f"component_line_counts[{index}].result_count must be non-negative"
            )
        if not str(line.get("history_or_query_locator", "")).strip():
            raise SearchQueueError(
                f"component_line_counts[{index}].history_or_query_locator is required"
            )
        forbidden = {
            "export_path",
            "export_sha256",
            "records",
            "record_ids",
            "records_exported",
            "detail_path",
            "detail_sha256",
        }
        leaked = sorted(forbidden.intersection(line))
        if leaked:
            raise SearchQueueError(
                f"component line {number} contains detailed-record fields: {leaked}"
            )
        observed_line_numbers.append(number)
    if observed_line_numbers != expected_line_numbers:
        raise SearchQueueError(
            "component_line_counts must contain every component line exactly once "
            "in strategy order"
        )

    final_total = evidence.get("final_search_total")
    if not isinstance(final_total, int) or isinstance(final_total, bool) or final_total < 0:
        raise SearchQueueError("final_search_total must be a non-negative integer")
    final_exported = evidence.get("final_records_exported")
    if (
        not isinstance(final_exported, int)
        or isinstance(final_exported, bool)
        or final_exported < 0
    ):
        raise SearchQueueError(
            "final_records_exported must be a non-negative integer"
        )
    if final_exported != final_total:
        raise SearchQueueError(
            "final_records_exported must equal final_search_total for a complete "
            "final-combination export"
        )
    for path_field, hash_field in (
        ("final_export_path", "final_export_sha256"),
        ("final_history_path", "final_history_sha256"),
    ):
        if not _is_safe_relative_path(evidence.get(path_field)):
            raise SearchQueueError(
                f"search evidence {path_field} must be a project-relative path"
            )
        path = _project_file(project_dir, evidence[path_field])
        if not path.is_file():
            raise SearchQueueError(
                f"search evidence file is missing: {evidence[path_field]}"
            )
        digest = file_sha256(path)
        if str(evidence.get(hash_field, "")).casefold() != digest:
            raise SearchQueueError(f"{hash_field} does not match {path_field}")
    if (
        not str(evidence.get("final_combination_locator", "")).strip()
        or evidence.get("final_combination_line_number")
        != task.get("final_combination_line_number")
    ):
        raise SearchQueueError(
            "final_combination_locator and final_combination_line_number are required"
        )
    checkpoints = task.get("line_checkpoints")
    if isinstance(checkpoints, list):
        completed_checkpoints = {
            checkpoint["line_number"]: checkpoint
            for checkpoint in checkpoints
            if isinstance(checkpoint, Mapping)
            and checkpoint.get("status") == "completed"
        }
        if len(completed_checkpoints) != len(task.get("line_plan", [])):
            raise SearchQueueError(
                "every strategy line must have a saved count checkpoint before completion"
            )
        for line in line_counts:
            checkpoint = completed_checkpoints.get(line["line_number"])
            if checkpoint is None or (
                checkpoint["result_count"] != line["result_count"]
                or checkpoint["history_or_query_locator"]
                != line["history_or_query_locator"]
            ):
                raise SearchQueueError(
                    f"component line {line['line_number']} evidence differs from its saved checkpoint"
                )
        final_checkpoint = completed_checkpoints.get(
            task["final_combination_line_number"]
        )
        if final_checkpoint is None or (
            final_checkpoint["result_count"] != final_total
            or final_checkpoint["history_or_query_locator"]
            != evidence["final_combination_locator"]
        ):
            raise SearchQueueError(
                "final combination evidence differs from its saved line checkpoint"
            )
    for field in ("search_date", "timezone"):
        if not str(evidence.get(field, "")).strip():
            raise SearchQueueError(f"search evidence {field} is required")
    checked = dict(evidence)
    # Retain the old names as read-only aliases for downstream consumers while
    # making the final-combination semantics explicit and unambiguous.
    checked["reported_hit_count"] = final_total
    checked["export_path"] = checked["final_export_path"]
    checked["export_sha256"] = checked["final_export_sha256"]
    checked["history_path"] = checked["final_history_path"]
    checked["history_sha256"] = checked["final_history_sha256"]
    checked["history_or_query_locator"] = checked["final_combination_locator"]
    return checked


def complete_search_task(
    queue_path: Union[str, Path],
    *,
    task_id: str,
    session: str,
    actor: str,
    evidence: Mapping[str, Any],
    project_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    def mutate(queue: Dict[str, Any]) -> Dict[str, Any]:
        task = _require_running_task(queue, task_id=task_id, session=session)
        project = (
            Path(project_dir).expanduser().resolve()
            if project_dir is not None
            else Path(str(queue["project_dir"])).expanduser().resolve()
        )
        checked = _validate_evidence(evidence, project_dir=project, task=task)
        task["status"] = "completed"
        task["completed_at"] = now_iso()
        task["evidence"] = checked
        _append_event(
            queue,
            action="task_completed",
            task=task,
            actor=actor,
            session=session,
            details={
                "final_search_total": checked["final_search_total"],
                "final_records_exported": checked["final_records_exported"],
                "final_export_path": checked["final_export_path"],
                "final_history_path": checked["final_history_path"],
            },
        )
        return deepcopy(task)

    return _mutate(Path(queue_path), mutate)


def queue_status(queue_path: Union[str, Path]) -> Dict[str, Any]:
    queue = load_search_queue(queue_path)
    counts = {state: 0 for state in TASK_STATES}
    for task in queue["tasks"]:
        counts[task["status"]] += 1
    active = _active_task(queue)
    next_task = _next_task(queue)
    return {
        "queue_path": queue["queue_path"],
        "queue_id": queue["queue_id"],
        "execution_policy": queue["execution_policy"],
        "counts": counts,
        "active_task": deepcopy(active) if active else None,
        "next_task": deepcopy(next_task) if next_task else None,
        "tasks": deepcopy(queue["tasks"]),
    }


def render_search_checklist(queue_path: Union[str, Path]) -> str:
    """Render the durable queue state as a human-readable, resumable to-do list."""
    queue = load_search_queue(queue_path)
    lines = [
        f"# Search checklist — {queue['queue_id']}",
        "",
        "- Browser execution: serial; at most one database task at a time.",
        "- Continuation: the next database requires an explicit user confirmation.",
        "",
    ]
    policy = queue.get("execution_policy", {})
    if (
        not isinstance(policy, Mapping)
        or policy.get("line_checkpoints_required") is not True
    ):
        lines.extend(
            [
                "> **Queue migration required:** this saved queue predates durable "
                "per-line checkpoints. Preserve its current state and reconcile "
                "the completed line counts before continuing.",
                "",
            ]
        )
    tasks = queue["tasks"]
    for index, task in enumerate(tasks):
        status = task["status"]
        task_mark = "x" if status == "completed" else " "
        lines.append(
            f"## [{task_mark}] {task['ordinal']}. {task['database']} — {status}"
        )
        lines.append(
            f"- Strategy: `{task['strategy_artifact']}` "
            f"(sha256 `{task['strategy_sha256']}`)"
        )
        checkpoints = task.get("line_checkpoints", [])
        lines.append("- Query-line checklist:")
        for plan_line, checkpoint in zip(task["line_plan"], checkpoints):
            mark = "x" if checkpoint.get("status") == "completed" else " "
            label = (
                "final combination"
                if plan_line["result_role"] == "final_combination"
                else (
                    f"{plan_line['line_type']}: "
                    f"{plan_line.get('concept_block') or 'database line'}"
                )
            )
            detail = ""
            if checkpoint.get("status") == "completed":
                detail = (
                    f" — {checkpoint['result_count']} hits; "
                    f"{checkpoint['history_or_query_locator']}"
                )
            lines.append(
                f"  - [{mark}] Line {plan_line['line_number']}: {label}{detail}"
            )
        if status == "completed":
            evidence = task.get("evidence") or {}
            lines.append(
                "- [x] Final export/history verified: "
                f"{evidence.get('final_records_exported')} records; "
                f"`{evidence.get('final_export_path')}`; "
                f"`{evidence.get('final_history_path')}`"
            )
            if index + 1 < len(tasks):
                next_task = tasks[index + 1]
                confirmation = next_task.get("user_confirmation")
                if (
                    isinstance(confirmation, Mapping)
                    and confirmation.get("previous_task_id") == task["task_id"]
                ):
                    lines.append(
                        "- [x] User confirmed continuation "
                        f"({confirmation.get('confirmed_at')}; "
                        f"session `{confirmation.get('session')}`)"
                    )
                else:
                    lines.append(
                        "- [ ] Present this database report and wait for the user's "
                        "explicit confirmation before starting the next database."
                    )
        elif task.get("last_error"):
            lines.append(f"- Blocker/checkpoint: {task['last_error']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


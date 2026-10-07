"""Serial browser-search queue with auditable, resumable state transitions.

The queue is deliberately independent of a particular browser connector.  A
browser executor claims exactly one database task, runs it in the configured
authenticated browser session, writes a hash-bound evidence JSON, and then
completes or pauses that task.  A second task cannot be started while one task
is active.
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


QUEUE_SCHEMA_VERSION = 1
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
    ):
        errors.append(
            "search queue execution_policy must be strict_serial with "
            "max_active_tasks=1 and parallel_browser_calls=false"
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
    for field in ("strategy_sha256", "execution_query_sha256"):
        expected = str(task.get(field, "")).casefold()
        observed = str(evidence.get(field, "")).casefold()
        if not expected or not SHA256_RE.fullmatch(observed) or observed != expected:
            raise SearchQueueError(
                f"search evidence {field} must match the queued strategy artifact"
            )
    reported = evidence.get("reported_hit_count")
    if not isinstance(reported, int) or isinstance(reported, bool) or reported < 0:
        raise SearchQueueError("reported_hit_count must be a non-negative integer")
    for field in ("export_path", "history_path"):
        if not _is_safe_relative_path(evidence.get(field)):
            raise SearchQueueError(
                f"search evidence {field} must be a project-relative path"
            )
        path = _project_file(project_dir, evidence[field])
        if not path.is_file():
            raise SearchQueueError(f"search evidence file is missing: {evidence[field]}")
        digest = file_sha256(path)
        hash_field = "export_sha256" if field == "export_path" else "history_sha256"
        if str(evidence.get(hash_field, "")).casefold() != digest:
            raise SearchQueueError(
                f"{hash_field} does not match {field}"
            )
    for field in ("search_date", "timezone", "history_or_query_locator"):
        if not str(evidence.get(field, "")).strip():
            raise SearchQueueError(f"search evidence {field} is required")
    return dict(evidence)


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
                "reported_hit_count": checked["reported_hit_count"],
                "export_path": checked["export_path"],
                "history_path": checked["history_path"],
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


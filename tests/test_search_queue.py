import hashlib
import json
import sys
from pathlib import Path

import pytest

from sci_nma_agent import cli
from sci_nma_agent.workflow.search_queue import (
    SearchQueueError,
    complete_search_task,
    create_search_queue,
    file_sha256,
    pause_search_task,
    queue_status,
    resume_search_task,
    start_search_task,
    validate_search_queue_file,
)


def _pico():
    return {
        "population": ["sepsis"],
        "intervention": ["hydrocortisone"],
        "mesh_mapping": {
            "sepsis": "Sepsis",
            "hydrocortisone": "Hydrocortisone",
        },
        "emtree_mapping": {
            "sepsis": "sepsis",
            "hydrocortisone": "hydrocortisone",
        },
    }


def _evidence(project: Path, task: dict, route: str = "cdp_builtin_browser"):
    export = project / "raw_exports" / task["database"] / "run-001.ris"
    history = project / "search" / f"{task['database']}_history.json"
    export.parent.mkdir(parents=True, exist_ok=True)
    history.parent.mkdir(parents=True, exist_ok=True)
    export.write_text("TY  - RCT\nER  -\n", encoding="utf-8")
    history.write_text(
        json.dumps({"database": task["database"], "sets": ["#1", "#2"]}),
        encoding="utf-8",
    )
    return {
        "database": task["database"],
        "browser_route": route,
        "strategy_sha256": task["strategy_sha256"],
        "execution_query_sha256": task["execution_query_sha256"],
        "reported_hit_count": 1,
        "export_path": export.relative_to(project).as_posix(),
        "export_sha256": file_sha256(export),
        "history_path": history.relative_to(project).as_posix(),
        "history_sha256": file_sha256(history),
        "search_date": "2026-10-07",
        "timezone": "Asia/Shanghai",
        "history_or_query_locator": "history:#2",
    }


def test_search_queue_is_strictly_serial_and_hash_bound(tmp_path):
    queue_path = tmp_path / "search" / "browser_search_queue.json"
    queue = create_search_queue(
        pico=_pico(),
        project_dir=tmp_path,
        queue_path=queue_path,
    )
    assert queue["execution_policy"]["max_active_tasks"] == 1
    assert queue["execution_policy"]["parallel_browser_calls"] is False
    assert len(queue["tasks"]) == 5

    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    with pytest.raises(SearchQueueError, match="already running"):
        start_search_task(
            queue_path,
            actor="search-agent-2",
            session="session-2",
        )

    complete_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        evidence=_evidence(tmp_path, first),
    )
    status = queue_status(queue_path)
    assert status["counts"]["completed"] == 1
    assert status["next_task"]["ordinal"] == 2


def test_pause_requires_explicit_resume_before_next_browser_task(tmp_path):
    queue_path = tmp_path / "queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
        browser_route="chrome_devtools",
    )
    paused = pause_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        reason="site verification requires user action",
        checkpoint="same_authenticated_browser",
    )
    assert paused["status"] == "paused"
    with pytest.raises(SearchQueueError, match="is paused"):
        start_search_task(
            queue_path,
            actor="search-agent",
            session="session-2",
        )
    resumed = resume_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="user",
        session="user-session",
    )
    assert resumed["status"] == "pending"
    restarted = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-3",
        browser_route="chrome_devtools",
    )
    assert restarted["task_id"] == first["task_id"]


def test_evidence_must_match_claimed_route_and_strategy(tmp_path):
    queue_path = tmp_path / "queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    evidence = _evidence(tmp_path, first)
    evidence["browser_route"] = "chrome_devtools"
    with pytest.raises(SearchQueueError, match="does not match the claimed route"):
        complete_search_task(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )


def test_cli_creates_and_reports_serial_search_queue(tmp_path, monkeypatch, capsys):
    pico = tmp_path / "pico.json"
    pico.write_text(json.dumps(_pico()), encoding="utf-8")
    queue = tmp_path / "search" / "browser_search_queue.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent",
            "search-queue",
            "create",
            "--pico",
            str(pico),
            "--project",
            str(tmp_path),
            "--output",
            str(queue),
        ],
    )
    cli.main()
    created = json.loads(capsys.readouterr().out)
    assert created["execution_policy"]["mode"] == "strict_serial"

    monkeypatch.setattr(
        sys,
        "argv",
        ["sci-nma-agent", "search-queue", "status", "--queue", str(queue)],
    )
    cli.main()
    status = json.loads(capsys.readouterr().out)
    assert status["counts"]["pending"] == 5


def test_queue_release_validation_rejects_unfinished_or_stale_evidence(tmp_path):
    queue_path = tmp_path / "search" / "browser_search_queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    errors = validate_search_queue_file(
        queue_path,
        project_dir=tmp_path,
        require_completed=True,
    )
    assert any("all browser tasks must be completed" in error for error in errors)

    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    complete_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        evidence=_evidence(tmp_path, first),
    )
    task = queue_status(queue_path)["tasks"][0]
    Path(tmp_path / task["strategy_artifact"]).write_text(
        "changed after browser execution\n",
        encoding="utf-8",
    )
    errors = validate_search_queue_file(
        queue_path,
        project_dir=tmp_path,
        require_completed=False,
    )
    assert any("strategy_artifact hash is stale" in error for error in errors)

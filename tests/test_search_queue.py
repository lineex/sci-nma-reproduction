import hashlib
import json
import sys
from pathlib import Path

import pytest

from sci_nma_agent import cli
from sci_nma_agent.workflow.search_queue import (
    SearchQueueError,
    complete_search_task,
    confirm_next_search_task,
    create_search_queue,
    file_sha256,
    pause_search_task,
    queue_status,
    record_search_line_count,
    render_search_checklist,
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
        "component_line_counts": [
            {
                "line_number": line_number,
                "result_count": 1,
                "history_or_query_locator": f"history:#{line_number}",
            }
            for line_number in task["component_line_numbers"]
        ],
        "final_search_total": 1,
        "final_combination_line_number": task["final_combination_line_number"],
        "final_combination_locator": "history:#7",
        "final_export_scope": "final_combination_only",
        "final_record_detail_level": "full",
        "final_export_complete": True,
        "final_records_exported": 1,
        "final_export_path": export.relative_to(project).as_posix(),
        "final_export_sha256": file_sha256(export),
        "final_history_path": history.relative_to(project).as_posix(),
        "final_history_sha256": file_sha256(history),
        "search_date": "2026-10-07",
        "timezone": "Asia/Shanghai",
    }


def _record_all_line_counts(queue_path: Path, task: dict, evidence: dict, session: str):
    saved_task = next(
        item
        for item in queue_status(queue_path)["tasks"]
        if item["task_id"] == task["task_id"]
    )
    component_counts = {
        item["line_number"]: item
        for item in evidence["component_line_counts"]
    }
    for line in task["line_plan"]:
        saved_checkpoint = saved_task["line_checkpoints"][line["line_number"] - 1]
        if saved_checkpoint["status"] == "completed":
            continue
        if line["result_role"] == "final_combination":
            count = evidence["final_search_total"]
            locator = evidence["final_combination_locator"]
        else:
            saved = component_counts[line["line_number"]]
            count = saved["result_count"]
            locator = saved["history_or_query_locator"]
        record_search_line_count(
            queue_path,
            task_id=task["task_id"],
            actor="search-agent",
            session=session,
            line_number=line["line_number"],
            result_count=count,
            history_or_query_locator=locator,
        )


def test_search_queue_is_strictly_serial_and_hash_bound(tmp_path):
    queue_path = tmp_path / "search" / "browser_search_queue.json"
    queue = create_search_queue(
        pico=_pico(),
        project_dir=tmp_path,
        queue_path=queue_path,
    )
    assert queue["execution_policy"]["max_active_tasks"] == 1
    assert queue["execution_policy"]["parallel_browser_calls"] is False
    assert queue["execution_policy"]["line_checkpoints_required"] is True
    assert len(queue["tasks"]) == 5
    assert queue["schema_version"] == 2
    assert queue["tasks"][0]["execution_contract"] == {
        "component_lines": "count_only",
        "final_combination": "export_full_records",
        "final_export_scope": "final_combination_only",
    }
    assert all(
        line["result_role"] == (
            "final_combination"
            if line["line_type"] == "combination"
            else "component_count_only"
        )
        for line in queue["tasks"][0]["line_plan"]
    )

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

    evidence = _evidence(tmp_path, first)
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    complete_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        evidence=evidence,
    )
    status = queue_status(queue_path)
    assert status["counts"]["completed"] == 1
    assert status["next_task"]["ordinal"] == 2
    with pytest.raises(SearchQueueError, match="user confirmation is required"):
        start_search_task(
            queue_path,
            actor="search-agent",
            session="session-2",
        )

    history_path = tmp_path / status["tasks"][0]["evidence"]["final_history_path"]
    retained_history = history_path.read_bytes()
    history_path.write_bytes(retained_history + b"\n")
    with pytest.raises(SearchQueueError, match="final_history_sha256 does not match"):
        confirm_next_search_task(
            queue_path,
            actor="user",
            session="user-session-1",
        )
    history_path.write_bytes(retained_history)

    with pytest.raises(SearchQueueError, match="actor 'user'"):
        confirm_next_search_task(
            queue_path,
            actor="search-agent",
            session="search-session-2",
        )
    confirmed = confirm_next_search_task(
        queue_path,
        actor="user",
        session="user-session-1",
    )
    assert confirmed["ordinal"] == 2
    assert confirmed["user_confirmation"]["previous_task_id"] == first["task_id"]
    second = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-2",
    )
    assert second["ordinal"] == 2


def test_search_queue_cannot_confirm_next_database_before_current_is_complete(tmp_path):
    queue_path = tmp_path / "search" / "browser_search_queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    with pytest.raises(SearchQueueError, match="preceding database must be completed"):
        confirm_next_search_task(
            queue_path,
            actor="user",
            session="user-session",
        )


def test_legacy_queue_is_preserved_but_cannot_start_without_line_checkpoints(tmp_path):
    queue_path = tmp_path / "legacy-queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    saved = json.loads(queue_path.read_text(encoding="utf-8"))
    saved["execution_policy"].pop("line_checkpoints_required")
    saved["execution_policy"].pop("advance_requires_user_confirmation")
    for task in saved["tasks"]:
        task.pop("line_checkpoints")
    queue_path.write_text(json.dumps(saved), encoding="utf-8")

    checklist = render_search_checklist(queue_path)
    assert "Queue migration required" in checklist
    with pytest.raises(SearchQueueError, match="predates durable per-line checkpoints"):
        start_search_task(
            queue_path,
            actor="search-agent",
            session="session-1",
        )


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


def test_search_line_checkpoints_are_ordered_and_survive_resume(tmp_path):
    queue_path = tmp_path / "queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    with pytest.raises(SearchQueueError, match="record line 1 next"):
        record_search_line_count(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-1",
            line_number=2,
            result_count=3,
            history_or_query_locator="history:#2",
        )

    checkpoint = record_search_line_count(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        line_number=1,
        result_count=12,
        history_or_query_locator="history:#1",
    )
    assert checkpoint["status"] == "completed"
    pause_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        reason="session interrupted after line 1",
        checkpoint="line-1-count-saved",
    )
    resume_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="user",
        session="user-session",
    )
    restarted = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-2",
    )
    assert restarted["line_checkpoints"][0]["result_count"] == 12
    assert restarted["line_checkpoints"][1]["status"] == "pending"
    with pytest.raises(SearchQueueError, match="record line 2 next"):
        record_search_line_count(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-2",
            line_number=1,
            result_count=12,
            history_or_query_locator="history:#1",
        )


def test_search_task_cannot_complete_without_matching_persisted_line_checkpoints(tmp_path):
    queue_path = tmp_path / "queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    task = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    evidence = _evidence(tmp_path, task)
    with pytest.raises(SearchQueueError, match="every strategy line must have a saved count checkpoint"):
        complete_search_task(
            queue_path,
            task_id=task["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )

    _record_all_line_counts(queue_path, task, evidence, "session-1")
    evidence["final_search_total"] = 7
    evidence["final_records_exported"] = 7
    with pytest.raises(SearchQueueError, match="differs from its saved line checkpoint"):
        complete_search_task(
            queue_path,
            task_id=task["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )


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
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    with pytest.raises(SearchQueueError, match="does not match the claimed route"):
        complete_search_task(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )


def test_component_lines_are_count_only_and_final_export_is_full_detail(tmp_path):
    queue_path = tmp_path / "queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    first = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    evidence = _evidence(tmp_path, first)
    evidence["component_line_counts"][0]["export_path"] = "raw_exports/PubMed/line-1.ris"
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    with pytest.raises(SearchQueueError, match="detailed-record fields"):
        complete_search_task(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )

    evidence = _evidence(tmp_path, first)
    evidence["final_export_scope"] = "component_line"
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    with pytest.raises(SearchQueueError, match="final_export_scope"):
        complete_search_task(
            queue_path,
            task_id=first["task_id"],
            actor="search-agent",
            session="session-1",
            evidence=evidence,
        )

    evidence = _evidence(tmp_path, first)
    evidence["final_records_exported"] = 0
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    with pytest.raises(SearchQueueError, match="must equal final_search_total"):
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
    assert created["execution_policy"]["advance_requires_user_confirmation"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        ["sci-nma-agent", "search-queue", "status", "--queue", str(queue)],
    )
    cli.main()
    status = json.loads(capsys.readouterr().out)
    assert status["counts"]["pending"] == 5

    monkeypatch.setattr(
        sys,
        "argv",
        ["sci-nma-agent", "search-queue", "checklist", "--queue", str(queue)],
    )
    cli.main()
    checklist = capsys.readouterr().out
    assert "Search checklist —" in checklist
    assert "Line 1" in checklist
    assert "[ ] 1. PubMed — pending" in checklist


def test_cli_records_search_line_checkpoint(tmp_path, monkeypatch, capsys):
    queue_path = tmp_path / "search" / "browser_search_queue.json"
    create_search_queue(pico=_pico(), project_dir=tmp_path, queue_path=queue_path)
    task = start_search_task(
        queue_path,
        actor="search-agent",
        session="session-1",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent",
            "search-queue",
            "record-line",
            "--queue",
            str(queue_path),
            "--task-id",
            task["task_id"],
            "--actor",
            "search-agent",
            "--session",
            "session-1",
            "--line-number",
            "1",
            "--result-count",
            "8123",
            "--locator",
            "history:#1",
        ],
    )
    cli.main()
    saved = json.loads(capsys.readouterr().out)
    assert saved["line_number"] == 1
    assert saved["status"] == "completed"

    checklist = render_search_checklist(queue_path)
    assert "[x] Line 1" in checklist
    assert "8123 hits; history:#1" in checklist


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
    evidence = _evidence(tmp_path, first)
    _record_all_line_counts(queue_path, first, evidence, "session-1")
    complete_search_task(
        queue_path,
        task_id=first["task_id"],
        actor="search-agent",
        session="session-1",
        evidence=evidence,
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

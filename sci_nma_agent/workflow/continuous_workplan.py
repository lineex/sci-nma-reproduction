"""Initialize durable project-level work-plan artifacts without overwriting them."""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def initialize_continuous_workplan(project_dir: Path) -> Dict[str, str]:
    """Create the work-plan scaffold and append-only event log if absent.

    The protocol is still a template at ``sci-nma-agent init`` time, so its
    hash remains null until the approved protocol is frozen.
    """
    project = project_dir.expanduser().resolve()
    verification = project / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    checkpoints = verification / "workplan_checkpoints"
    sessions = verification / "workplan_sessions"
    checkpoints.mkdir(exist_ok=True)
    sessions.mkdir(exist_ok=True)

    workplan_path = verification / "research_workplan.json"
    events_path = verification / "workplan_events.jsonl"
    if workplan_path.exists() != events_path.exists():
        raise RuntimeError(
            "incomplete work-plan state: research_workplan.json and "
            "workplan_events.jsonl must be reconciled before initialization"
        )
    created_at = _now_iso()
    if not workplan_path.exists():
        template_path = (
            Path(__file__).parents[1]
            / "templates"
            / "continuous_workplan_template.json"
        )
        template = json.loads(template_path.read_text(encoding="utf-8"))
        template["workplan_id"] = project.name
        template["project_path"] = str(project)
        template["protocol_sha256"] = None
        template["status"] = "active"
        template["created_at"] = created_at
        template["updated_at"] = created_at
        for task in template.get("tasks", []):
            task["created_at"] = created_at
            task["updated_at"] = created_at
        workplan_path.write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if not events_path.exists():
        event = {
            "event_id": f"evt-{uuid.uuid4().hex}",
            "timestamp": created_at,
            "session_id": None,
            "task_id": None,
            "action": "workplan_initialized",
            "status_before": None,
            "status_after": "active",
            "summary": (
                "Initialized the resumable stage work-plan scaffold; bind it "
                "to the approved protocol before search."
            ),
            "inputs": [],
            "outputs": [
                {
                    "path": "verification/research_workplan.json",
                    "sha256": hashlib.sha256(workplan_path.read_bytes()).hexdigest(),
                }
            ],
            "acceptance_checks": [
                "Stage task tree scaffold exists",
                "Protocol hash is pending protocol approval",
            ],
            "next_action": (
                "Complete and approve review_protocol.json, then record its "
                "SHA-256 and seed child tasks from the approved workflow."
            ),
            "human_action_required": False,
        }
        with events_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    return {
        "workplan_path": workplan_path.relative_to(project).as_posix(),
        "events_path": events_path.relative_to(project).as_posix(),
    }

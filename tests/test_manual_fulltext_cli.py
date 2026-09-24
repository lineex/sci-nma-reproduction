import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from sci_nma_agent import cli


def test_manual_queue_command_displays_report_rows(tmp_path, monkeypatch, capsys):
    queue_path = tmp_path / "screening" / "queue.json"
    queue_path.parent.mkdir()
    queue_path.write_text(
        json.dumps({
            "records": [{
                "queue_id": "S1::R1",
                "study_id": "S1",
                "report_id": "R1",
                "queue_status": "open",
                "retrieval_status": "awaiting_manual_acquisition",
                "unresolved_reason": "No attachment in Zotero",
                "expected_identity": {"doi": "10.1000/example"},
                "source_route_attempts": [{"route": "zotero_mcp", "status": "no_attachment"}],
                "instructions": ["Attach the report to its Zotero item"],
            }]
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli.AgentStageLedger,
        "status",
        lambda self: {"stages": {"fulltext_retrieval": {"status": "in_progress", "run_count": 1}}},
    )
    monkeypatch.setattr(
        cli,
        "build_manual_fulltext_queue",
        lambda *args, **kwargs: {
            "queue_path": str(queue_path),
            "record_count": 1,
            "retrieval_manifest_sha256": "a" * 64,
            "unchanged": False,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "manual-fulltext", "queue", "--project", str(tmp_path),
            "--manifest", "screening/retrieval.json", "--study-report-map", "corpus/map.json",
            "--screening-manifest", "screening/ta.json",
        ],
    )

    cli.main()

    output = json.loads(capsys.readouterr().out)
    assert output["record_count"] == 1
    assert output["records"][0]["report_id"] == "R1"
    assert output["records"][0]["unresolved_reason"] == "No attachment in Zotero"


def test_manual_queue_check_surfaces_validation_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "validate_manual_fulltext_queue_file", lambda *args: ["queue hash mismatch"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "manual-fulltext", "check", "--project", str(tmp_path),
            "--manifest", "retrieval.json", "--queue", "queue.json",
            "--study-report-map", "map.json", "--screening-manifest", "screening.json",
        ],
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("invalid queue must return a failing exit code")

    output = json.loads(capsys.readouterr().out)
    assert output == {"valid": False, "errors": ["queue hash mismatch"]}


def test_manual_confirm_resumes_and_reports_new_stage_attempt(tmp_path, monkeypatch, capsys):
    class FakeLedger:
        def __init__(self, project):
            self.project = project

        def status(self):
            return {"stages": {"fulltext_retrieval": {"status": "approved", "run_count": 3}}}

        def validate_resume(self, stage, agent, session):
            assert (stage, agent, session) == ("fulltext_retrieval", "retrieval-agent", "session-4")

        def resume(self, stage, agent, session):
            assert (stage, agent, session) == ("fulltext_retrieval", "retrieval-agent", "session-4")
            return {"stages": {stage: {"status": "in_progress", "run_count": 4}}}

    @asynccontextmanager
    async def fake_connect(url):
        assert url == "http://localhost:23120/mcp"
        yield object()

    async def fake_confirm(**kwargs):
        assert kwargs["expected_run"] == 4
        assert "run-0004" in kwargs["output_manifest_path"]
        assert "resume-" in kwargs["output_manifest_path"]
        return {"report_id": kwargs["report_id"], "retrieval_manifest_sha256": "b" * 64}

    monkeypatch.setattr(cli, "AgentStageLedger", FakeLedger)
    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", staticmethod(fake_connect))
    monkeypatch.setattr(cli, "confirm_zotero_attachment", fake_confirm)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "manual-fulltext", "confirm", "--project", str(tmp_path),
            "--manifest", "old/retrieval.json", "--queue", "old/queue.json",
            "--study-report-map", "approved/map.json", "--screening-manifest", "approved/ta.json",
            "--study-id", "S1", "--report-id", "R1", "--item-key", "ITEM1",
            "--attachment-key", "ATTACH1", "--attachment-file", str(tmp_path / "report.pdf"),
            "--actor", "review-user", "--identity-evidence", "Matched DOI and title",
            "--agent", "retrieval-agent", "--agent-session", "session-4",
            "--url", "http://localhost:23120/mcp",
        ],
    )

    cli.main()

    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "R1"
    assert output["stage_status"] == "in_progress"
    assert output["stage_run"] == 4
    assert "two independent reviews" in output["next_action"]


def test_manual_confirm_preflights_ledger_before_connecting_to_zotero(tmp_path, monkeypatch, capsys):
    class FakeLedger:
        def __init__(self, project):
            self.project = project

        def status(self):
            return {
                "integrity_valid": False,
                "evidence_integrity_valid": True,
                "stages": {"fulltext_retrieval": {"status": "in_progress", "run_count": 1}},
            }

        def validate_resume(self, stage, agent, session):
            raise cli.StageLedgerError("Stage ledger event hash chain is invalid")

    async def unexpected_connect(url):
        raise AssertionError("ledger preflight must run before contacting Zotero")

    monkeypatch.setattr(cli, "AgentStageLedger", FakeLedger)
    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", staticmethod(unexpected_connect))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "manual-fulltext", "confirm", "--project", str(tmp_path),
            "--manifest", "old/retrieval.json", "--queue", "old/queue.json",
            "--study-report-map", "approved/map.json", "--screening-manifest", "approved/ta.json",
            "--study-id", "S1", "--report-id", "R1", "--item-key", "ITEM1",
            "--attachment-key", "ATTACH1", "--attachment-file", str(tmp_path / "report.pdf"),
            "--actor", "review-user", "--identity-evidence", "Matched DOI and title",
            "--agent", "retrieval-agent", "--agent-session", "session-2",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    assert "Stage ledger event hash chain is invalid" in capsys.readouterr().out


def test_manual_confirm_rolls_back_outputs_if_resume_races_after_preflight(tmp_path, monkeypatch, capsys):
    created = []

    class FakeLedger:
        def __init__(self, project):
            self.project = project

        def status(self):
            return {"stages": {"fulltext_retrieval": {"status": "in_progress", "run_count": 1}}}

        def validate_resume(self, stage, agent, session):
            assert (stage, agent, session) == ("fulltext_retrieval", "retrieval-agent", "session-2")

        def resume(self, stage, agent, session):
            raise cli.StageLedgerError("Stage changed after preflight")

    @asynccontextmanager
    async def fake_connect(url):
        yield object()

    async def fake_confirm(**kwargs):
        outputs = [
            tmp_path / kwargs["output_manifest_path"],
            tmp_path / kwargs["output_queue_path"],
            tmp_path / "original_materials" / "manual_fulltext" / "run-0001" / "source.pdf",
            tmp_path / "original_materials" / "manual_fulltext" / "run-0001" / "source.txt",
        ]
        for path in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"generated")
            created.append(path)
        return {key: str(path) for key, path in zip(
            ("retrieval_manifest_path", "queue_path", "local_file_path", "content_path"), outputs
        )}

    monkeypatch.setattr(cli, "AgentStageLedger", FakeLedger)
    monkeypatch.setattr(cli.ZoteroMCPReadClient, "connect", staticmethod(fake_connect))
    monkeypatch.setattr(cli, "confirm_zotero_attachment", fake_confirm)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "manual-fulltext", "confirm", "--project", str(tmp_path),
            "--manifest", "old/retrieval.json", "--queue", "old/queue.json",
            "--study-report-map", "approved/map.json", "--screening-manifest", "approved/ta.json",
            "--study-id", "S1", "--report-id", "R1", "--item-key", "ITEM1",
            "--attachment-key", "ATTACH1", "--attachment-file", str(tmp_path / "report.pdf"),
            "--actor", "review-user", "--identity-evidence", "Matched DOI and title",
            "--agent", "retrieval-agent", "--agent-session", "session-2",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    assert all(not path.exists() for path in created)
    assert "Stage changed after preflight" in capsys.readouterr().out


def test_review_stage_resume_calls_ledger_handoff(tmp_path, monkeypatch, capsys):
    captured = {}

    class FakeLedger:
        FILENAME = "agent_stage_ledger.json"

        def __init__(self, project):
            captured["project"] = project

        def resume(self, stage, agent, session):
            captured["resume"] = (stage, agent, session)
            return {"stages": {stage: {"status": "in_progress"}}}

    monkeypatch.setattr(cli, "AgentStageLedger", FakeLedger)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "review-stage", "resume", "--project", str(tmp_path),
            "--stage", "fulltext_retrieval", "--agent", "retrieval-agent", "--agent-session", "session-b",
        ],
    )

    cli.main()

    output = json.loads(capsys.readouterr().out)
    assert captured["resume"] == ("fulltext_retrieval", "retrieval-agent", "session-b")
    assert output["status"] == "in_progress"

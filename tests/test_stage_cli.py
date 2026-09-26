import json
import sys

import pytest

from sci_nma_agent import cli


def test_status_cli_fails_when_any_evidence_hash_is_stale(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["sci-nma-agent", "review-stage", "status", "--project", "unused"],
    )
    monkeypatch.setattr(cli.AgentStageLedger, "__init__", lambda self, project: None)
    monkeypatch.setattr(
        cli.AgentStageLedger,
        "status",
        lambda self: {
            "integrity_valid": True,
            "evidence_integrity_valid": False,
            "current_stage": None,
            "stages": {"protocol": {"status": "approved"}},
        },
    )

    with pytest.raises(SystemExit) as raised:
        cli.main()

    output = json.loads(capsys.readouterr().out)
    assert output["integrity_valid"] is True
    assert output["evidence_integrity_valid"] is False
    assert raised.value.code == 1


def test_review_cli_requires_nonempty_findings(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sci-nma-agent", "review-stage", "review", "--project", "unused",
            "--stage", "protocol", "--reviewer", "reviewer-a",
            "--reviewer-session", "session-a", "--verdict", "approve",
            "--report", "verification/reviews/a.md",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        cli.main()

    assert raised.value.code == 2


def test_init_copies_gated_manifest_and_methods_source_templates(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sci-nma-agent", "init", str(tmp_path)])

    cli.main()
    assert "Statistical default: R" in capsys.readouterr().out

    expected = [
        "verification/analysis_manifest.json",
        "verification/methods_source_log.json",
        "screening/title_abstract_screening_manifest.json",
        "screening/full_text_retrieval_manifest.json",
        "screening/full_text_screening_manifest.json",
        "data/fact_status_manifest.json",
    ]
    assert all((tmp_path / relative).is_file() for relative in expected)

    protocol = json.loads((tmp_path / "review_protocol.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (tmp_path / "verification" / "analysis_manifest.json").read_text(encoding="utf-8")
    )
    assert protocol["synthesis"]["software"]["primary_engine"]["name"] == "R"
    assert manifest["software"]["primary_engine"]["name"] == "R"


def test_synthesize_cli_keeps_production_release_gate_explicit(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "data.json"
    dataset.write_text(
        json.dumps(
            [{
                "study_id": "S1",
                "events_treatment": 2,
                "total_treatment": 10,
                "events_control": 3,
                "total_control": 10,
            }]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["sci-nma-agent", "synthesize", "--data", str(dataset)])

    cli.main()

    output = capsys.readouterr().out
    assert "Exploratory QA Result (not a production synthesis)" in output
    assert "protocol-declared locked engine and analysis_manifest.json" in output

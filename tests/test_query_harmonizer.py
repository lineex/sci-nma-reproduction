from __future__ import annotations

import json
import sys

import pytest

from sci_nma_agent import cli
from sci_nma_agent.databases.query_harmonizer import QueryHarmonizer


def _pico(**overrides):
    base = {
        "population": ["septic shock"],
        "intervention": ["hydrocortisone"],
        "comparison": ["placebo"],
        "primary_outcome": "28-day mortality",
        "secondary_outcomes": ["shock reversal"],
        "year_range": [2000, 2026],
        "mesh_mapping": {
            "septic shock": "Shock, Septic",
            "hydrocortisone": "Hydrocortisone",
        },
        "emtree_mapping": {
            "septic shock": "septic shock",
            "hydrocortisone": "hydrocortisone",
        },
    }
    base.update(overrides)
    return base


def test_default_search_is_sensitivity_first_and_omits_comparator_and_outcome():
    plan = QueryHarmonizer.harmonize_with_strategy(_pico())

    assert plan["search_policy"]["include_comparator"] is False
    assert plan["search_policy"]["include_outcome"] is False
    assert plan["search_policy"]["include_study_design_filter"] is False
    assert plan["search_policy"]["include_language_limit"] is False
    assert plan["search_policy"]["include_humans_limit"] is False
    assert plan["search_policy"]["include_date_limit"] is False
    assert plan["concept_blocks"]["included"] == ["P", "I"]
    assert plan["concept_blocks"]["omitted_by_default"] == ["C", "O"]
    for item in plan["databases"].values():
        concept_lines = [
            line["native_syntax"].lower()
            for line in item["native_lines"]
            if line["line_type"] == "concept"
        ]
        assert all("placebo" not in line for line in concept_lines)
        assert all("mortality" not in line for line in concept_lines)
    assert "2000" not in plan["databases"]["PubMed"]["execution_query"]


def test_comparator_and_outcome_can_be_enabled_explicitly():
    plan = QueryHarmonizer.harmonize_with_strategy(
        _pico(
            search={
                "include_comparator": True,
                "include_outcome": True,
                "comparator_search_rationale": "Comparator terminology is stable in this topic.",
                "outcome_search_rationale": "Outcome terminology is required for this focused question.",
            }
        )
    )

    assert plan["concept_blocks"]["included"] == ["P", "I", "C", "O"]
    assert "placebo" in plan["databases"]["PubMed"]["execution_query"]
    assert "28-day mortality" in plan["databases"]["PubMed"]["execution_query"]


def test_optional_blocks_require_documented_rationale():
    with pytest.raises(ValueError, match="outcome_search_rationale"):
        QueryHarmonizer.harmonize_with_strategy(
            _pico(search={"include_outcome": True})
        )


def test_string_false_is_not_treated_as_true():
    plan = QueryHarmonizer.harmonize_with_strategy(
        _pico(search={"include_outcome": "false", "include_date_limit": "false"})
    )
    assert plan["search_policy"]["include_outcome"] is False
    assert plan["search_policy"]["include_date_limit"] is False


def test_restrictions_are_explicit_and_database_specific():
    plan = QueryHarmonizer.harmonize_with_strategy(
        _pico(
            search={
                "include_study_design_filter": True,
                "include_document_type_limit": True,
                "include_language_limit": True,
                "include_humans_limit": True,
                "include_date_limit": True,
                "restrictions_and_rationale": "The protocol prespecifies these database-specific restrictions.",
            }
        )
    )
    assert "1999:2026[dp]" not in plan["databases"]["PubMed"]["execution_query"]
    assert "2000:2026[dp]" in plan["databases"]["PubMed"]["execution_query"]
    assert "validated_RCT_design_filter" in plan["databases"]["PubMed"]["restriction_status"]["applied"]
    assert "validated_RCT_design_filter" in plan["databases"]["Web_of_Science"]["restriction_status"]["not_applied"]
    assert "document_type_limit" in plan["databases"]["Web_of_Science"]["restriction_status"]["applied"]
    assert "humans_limit" in plan["databases"]["PubMed"]["restriction_status"]["not_applied"]
    assert "date_limit" in plan["databases"]["Cochrane_CENTRAL"]["restriction_status"]["not_applied"]


def test_nested_search_policy_wins_over_legacy_top_level_aliases():
    plan = QueryHarmonizer.harmonize_with_strategy(
        _pico(
            search={
                "include_outcome": True,
                "include_humans_limit": False,
                "outcome_search_rationale": "Outcome terminology is required for this focused question.",
            },
            search_outcome=False,
            humans_only=True,
        )
    )

    assert plan["search_policy"]["include_outcome"] is True
    assert plan["search_policy"]["include_humans_limit"] is False
    assert "28-day mortality" in plan["databases"]["PubMed"]["execution_query"]
    assert "[humans]/lim" not in plan["databases"]["Embase"]["execution_query"]


def test_native_strategy_contains_database_specific_syntax_and_separate_execution_artifact():
    plan = QueryHarmonizer.harmonize_with_strategy(_pico())

    assert "MeSH Terms" in plan["databases"]["PubMed"]["native_lines"][0]["native_syntax"]
    assert "/exp" in plan["databases"]["Embase"]["native_lines"][0]["native_syntax"]
    assert ":ti,ab,kw" in plan["databases"]["Cochrane_CENTRAL"]["native_lines"][0]["native_syntax"]
    assert plan["databases"]["Web_of_Science"]["native_lines"][0]["native_syntax"].startswith("TS=")
    assert "TITLE-ABS-KEY" in plan["databases"]["Scopus"]["native_lines"][0]["native_syntax"]
    for item in plan["databases"].values():
        assert item["appendix_policy"]["display_final_execution_query"] is False
        assert item["appendix_policy"]["component_execution"] == "count_only"
        assert item["appendix_policy"]["final_combination_execution"] == "export_full_records"
        assert item["appendix_policy"]["final_export_scope"] == "final_combination_only"
        assert item["appendix_policy"]["strategy_status"] == "planned_generated"
        assert item["appendix_policy"]["exact_run_record_required"] is True
        assert item["appendix_policy"]["execution_artifact"].endswith("_search.txt")
        assert item["native_lines"][-1]["line_type"] == "combination"
    assert plan["databases"]["Embase"]["native_lines"][-1]["native_syntax"] == "#1 AND #2"


def test_appendix_safe_strategy_never_exposes_collapsed_execution_query():
    plan = QueryHarmonizer.appendix_safe_strategy(_pico())

    for item in plan["databases"].values():
        assert "execution_query" not in item
        assert item["appendix_policy"]["display_final_execution_query"] is False


def test_write_strategy_artifacts_keeps_collapsed_query_out_of_appendix_json(tmp_path):
    paths = QueryHarmonizer.write_strategy_artifacts(_pico(), str(tmp_path))

    assert set(paths) == {"PubMed", "Embase", "Cochrane_CENTRAL", "Web_of_Science", "Scopus"}
    for database, strategy_path in paths.items():
        payload = json.loads((tmp_path / "search_strategies" / f"{database}_native_strategy.json").read_text(encoding="utf-8"))
        assert payload["display_final_execution_query"] is False
        assert payload["component_execution"] == "count_only"
        assert payload["final_combination_execution"] == "export_full_records"
        assert payload["final_export_scope"] == "final_combination_only"
        assert "execution_query" not in payload
        assert payload["strategy_status"] == "planned_generated"
        assert payload["exact_run_record_required"] is True
        assert (tmp_path / "search_strategies" / f"{database}_search.txt").is_file()
        assert strategy_path.endswith(f"{database}_native_strategy.json")


def test_missing_population_or_intervention_is_rejected():
    with pytest.raises(ValueError, match="population and intervention"):
        QueryHarmonizer.harmonize_with_strategy({"population": [], "intervention": []})


def test_protocol_template_question_fields_are_accepted():
    plan = QueryHarmonizer.harmonize_with_strategy(
        {
            "question": {
                "population": "septic shock",
                "intervention_or_exposure": "hydrocortisone",
            }
        }
    )

    assert '"septic shock"[tiab]' in plan["databases"]["PubMed"]["execution_query"]
    assert '"hydrocortisone"[tiab]' in plan["databases"]["PubMed"]["execution_query"]


def test_search_cli_shows_native_lines_but_hides_execution_query_by_default(tmp_path, monkeypatch, capsys):
    pico_path = tmp_path / "pico.json"
    pico_path.write_text(json.dumps(_pico()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["sci-nma-agent", "search", "--pico", str(pico_path)])

    cli.main()

    output = capsys.readouterr().out
    assert "Native Database Search Strategy" in output
    assert "TS=(\"septic shock\")" in output
    assert "execution_query (private artifact)" not in output

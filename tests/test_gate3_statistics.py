"""
Unit tests for Gate 3: Numerical & Statistical Consistency.
"""

import pytest
import math
from sci_nma_agent.core.gate3_statistics import Gate3Statistics
from sci_nma_agent.meta_engine.logit_transform import LogitTransformEngine
from sci_nma_agent.meta_engine.pairwise import PairwiseMetaAnalysis
from sci_nma_agent.meta_engine.network_meta import NetworkMetaEngine
from sci_nma_agent.meta_engine.publication_bias import PublicationBiasEngine


def test_logit_transformation_roundtrip():
    probs = [0.05, 0.25, 0.50, 0.75, 0.95]
    for p in probs:
        z = LogitTransformEngine.forward(p)
        p_rec = LogitTransformEngine.backward(z)
        assert math.isclose(p, p_rec, abs_tol=1e-5)


def test_odds_ratio_calculation():
    # 2x2 table: a=20, b=80 (n1=100); c=40, d=60 (n2=100)
    # OR = (20*60)/(80*40) = 1200/3200 = 0.375
    or_val, log_or, se_log_or, ci = Gate3Statistics.calculate_odds_ratio(20, 80, 40, 60)
    assert math.isclose(or_val, 0.375, abs_tol=1e-3)
    assert ci[0] < or_val < ci[1]


def test_pairwise_meta_analysis():
    studies = [
        {"study_id": "S1", "events_treatment": 15, "total_treatment": 100, "events_control": 30, "total_control": 100},
        {"study_id": "S2", "events_treatment": 25, "total_treatment": 150, "events_control": 45, "total_control": 150},
        {"study_id": "S3", "events_treatment": 10, "total_treatment": 80, "events_control": 20, "total_control": 80}
    ]
    res = PairwiseMetaAnalysis.analyze_binary(studies, measure="OR", model="random")
    assert res["k"] == 3
    assert res["pooled_estimate"] < 1.0  # Favors treatment
    assert res["ci_lower"] < res["pooled_estimate"] < res["ci_upper"]
    assert 0.0 <= res["i2_percent"] <= 100.0
    assert res["engine_role"] == "exploratory_qa"
    assert res["production_use"] == "not_for_release"


def test_gate3_random_effects_is_explicitly_qa_only():
    result = Gate3Statistics.meta_analysis_random_effects([0.1, 0.2], [0.04, 0.05])
    assert result["engine_role"] == "exploratory_qa"
    assert result["production_use"] == "not_for_release"


def test_exploratory_nma_rejects_disconnected_treatment_components():
    trials = [{"study_id": "S1", "t1": "A", "t2": "B", "log_or": -0.2, "se": 0.2}]
    with pytest.raises(ValueError, match="network is disconnected"):
        NetworkMetaEngine.calculate_nma(trials, ["A", "B", "C"], reference_treatment="A")


def test_small_study_effect_test_is_not_assessed_below_prespecified_threshold():
    result = PublicationBiasEngine.egger_test([0.1, 0.2, 0.3], [0.04, 0.05, 0.06])
    assert result["k"] == 3
    assert "Not assessed" in result["interpretation"]

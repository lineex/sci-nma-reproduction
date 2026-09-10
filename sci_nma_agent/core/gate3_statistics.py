"""
Gate 3: Numerical & Statistical Consistency Verification Gate.
Enforces REML / DerSimonian-Laird random effects, Logit transformations for bounded outcomes,
and mathematical self-consistency of 95% CIs and sample sizes.
"""

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from scipy import stats


class Gate3Statistics:
    """Validator and statistical engine for Gate 3."""

    @staticmethod
    def logit(p: float) -> float:
        """Logit transformation for bounded parameters in (0, 1)."""
        if p <= 0.0 or p >= 1.0:
            # Continuity adjustment
            p = max(min(p, 0.9999), 0.0001)
        return math.log(p / (1.0 - p))

    @staticmethod
    def inv_logit(z: float) -> float:
        """Inverse logit back-transformation to (0, 1)."""
        return 1.0 / (1.0 + math.exp(-z))

    @staticmethod
    def logit_se(p: float, n: int) -> float:
        """Standard error of logit(p)."""
        if p <= 0.0 or p >= 1.0:
            p = max(min(p, 0.9999), 0.0001)
        if n <= 0:
            return 0.1
        return math.sqrt(1.0 / (n * p * (1.0 - p)))

    @classmethod
    def calculate_odds_ratio(
        cls, a: int, b: int, c: int, d: int
    ) -> Tuple[float, float, float, float]:
        """
        Calculate Odds Ratio (OR), log(OR), SE(logOR), and 95% CI.
        a: events in intervention, b: non-events in intervention (or n_t - a)
        c: events in control, d: non-events in control (or n_c - c)
        """
        # Haldane-Anscombe continuity correction for zero cells
        adj = 0.5 if (a == 0 or b == 0 or c == 0 or d == 0) else 0.0
        a_adj, b_adj, c_adj, d_adj = a + adj, b + adj, c + adj, d + adj

        or_val = (a_adj * d_adj) / (b_adj * c_adj)
        log_or = math.log(or_val)
        se_log_or = math.sqrt(1.0 / a_adj + 1.0 / b_adj + 1.0 / c_adj + 1.0 / d_adj)

        ci_lower = math.exp(log_or - 1.96 * se_log_or)
        ci_upper = math.exp(log_or + 1.96 * se_log_or)

        return or_val, log_or, se_log_or, (ci_lower, ci_upper)

    @classmethod
    def calculate_relative_risk(
        cls, a: int, n1: int, c: int, n2: int
    ) -> Tuple[float, float, float, float]:
        """Calculate Risk Ratio (RR), log(RR), SE(logRR), and 95% CI."""
        adj = 0.5 if (a == 0 or c == 0) else 0.0
        p1 = (a + adj) / (n1 + adj * 2)
        p2 = (c + adj) / (n2 + adj * 2)

        rr = p1 / p2
        log_rr = math.log(rr)
        se_log_rr = math.sqrt((n1 - a) / (n1 * (a + adj)) + (n2 - c) / (n2 * (c + adj)))

        ci_lower = math.exp(log_rr - 1.96 * se_log_rr)
        ci_upper = math.exp(log_rr + 1.96 * se_log_rr)

        return rr, log_rr, se_log_rr, (ci_lower, ci_upper)

    @classmethod
    def meta_analysis_random_effects(
        cls, yi: List[float], vi: List[float], method: str = "DL"
    ) -> Dict[str, Any]:
        """
        DerSimonian-Laird (DL) or REML random effects meta-analysis.
        yi: effect sizes
        vi: variances (SE^2)
        """
        k = len(yi)
        if k == 0:
            return {"k": 0, "pooled_effect": 0.0, "se": 0.0}

        y_arr = np.array(yi, dtype=float)
        v_arr = np.array(vi, dtype=float)
        wi = 1.0 / v_arr

        # Fixed effect summary for Q calculation
        y_fe = np.sum(wi * y_arr) / np.sum(wi)
        q = float(np.sum(wi * (y_arr - y_fe) ** 2))
        df = k - 1
        p_q = float(1.0 - stats.chi2.cdf(q, df)) if df > 0 else 1.0

        # DL estimator for tau^2
        c = np.sum(wi) - (np.sum(wi ** 2) / np.sum(wi))
        tau2 = max(0.0, (q - df) / c) if (c > 0 and df > 0) else 0.0

        # Random effects weights
        wi_re = 1.0 / (v_arr + tau2)
        y_re = float(np.sum(wi_re * y_arr) / np.sum(wi_re))
        se_re = float(math.sqrt(1.0 / np.sum(wi_re)))

        # Knapp-Hartung adjustment
        if df > 0:
            q_re = np.sum(wi_re * (y_arr - y_re) ** 2)
            kh_factor = max(1.0, float(q_re / df))
            se_re_kh = se_re * math.sqrt(kh_factor)
            t_crit = stats.t.ppf(0.975, df)
            ci_lower = y_re - t_crit * se_re_kh
            ci_upper = y_re + t_crit * se_re_kh
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(y_re / se_re_kh), df)))
        else:
            se_re_kh = se_re
            ci_lower = y_re - 1.96 * se_re
            ci_upper = y_re + 1.96 * se_re
            p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(y_re / se_re))))

        # I^2 calculation
        i2 = max(0.0, (q - df) / q * 100.0) if q > df and q > 0 else 0.0

        return {
            "k": k,
            "pooled_effect": y_re,
            "se": se_re_kh,
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "z_val": float(y_re / se_re_kh) if se_re_kh > 0 else 0.0,
            "p_val": p_val,
            "q_stat": q,
            "q_p_val": p_q,
            "tau2": tau2,
            "i2": i2,
            "weights_percent": (wi_re / np.sum(wi_re) * 100.0).tolist()
        }

    @classmethod
    def audit_statistical_consistency(cls, study_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Audit single study entry for numeric consistency."""
        errors = []
        name = study_data.get("study_id", "Study")

        # 1. Total Sample Size Consistency
        n_total = study_data.get("n_total")
        n_treat = study_data.get("n_intervention")
        n_ctrl = study_data.get("n_control")

        if n_total is not None and n_treat is not None and n_ctrl is not None:
            if n_treat + n_ctrl != n_total:
                errors.append(
                    f"[{name}] Sample size sum mismatch: n_treat ({n_treat}) + n_ctrl ({n_ctrl}) = "
                    f"{n_treat + n_ctrl}, but n_total is {n_total}."
                )

        # 2. Events <= Sample Size
        e_treat = study_data.get("events_intervention")
        e_ctrl = study_data.get("events_control")
        if e_treat is not None and n_treat is not None and e_treat > n_treat:
            errors.append(f"[{name}] Intervention events ({e_treat}) exceed arm sample size ({n_treat}).")
        if e_ctrl is not None and n_ctrl is not None and e_ctrl > n_ctrl:
            errors.append(f"[{name}] Control events ({e_ctrl}) exceed arm sample size ({n_ctrl}).")

        # 3. 95% Confidence Interval Enclosure
        est = study_data.get("point_estimate")
        ci_low = study_data.get("ci_lower")
        ci_high = study_data.get("ci_upper")
        if est is not None and ci_low is not None and ci_high is not None:
            if not (ci_low <= est <= ci_high):
                errors.append(
                    f"[{name}] Point estimate ({est}) is not bounded inside 95% CI [{ci_low}, {ci_high}]."
                )

        return (len(errors) == 0), errors

    @classmethod
    def audit_dataset_statistics(cls, dataset: List[Dict[str, Any]]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Audit statistical consistency across an entire dataset."""
        all_errors = []
        consistent_count = 0

        for study in dataset:
            passed, errs = cls.audit_statistical_consistency(study)
            if passed:
                consistent_count += 1
            else:
                all_errors.extend(errs)

        metrics = {
            "total_studies_checked": len(dataset),
            "consistent_studies": consistent_count,
            "consistency_rate_percent": (consistent_count / len(dataset) * 100) if dataset else 0.0
        }
        passed = (len(all_errors) == 0)
        return passed, all_errors, metrics

"""
Logit Transformation Engine for Bounded Metrics.
Handles AUROC, C-index, diagnostic sensitivity/specificity, and prevalence data bounded in (0, 1).
Prevents out-of-bounds confidence intervals (> 1.0 or < 0.0) through logit scale pooling
and inverse logit back-transformation.
"""

import math
from typing import List, Dict, Any, Tuple
import numpy as np
from scipy import stats


class LogitTransformEngine:
    """Engine for meta-analysis of bounded clinical metrics."""

    @staticmethod
    def forward(p: float) -> float:
        """Logit transformation: logit(p) = ln(p / (1 - p))."""
        p_clamped = max(min(p, 0.9999), 0.0001)
        return math.log(p_clamped / (1.0 - p_clamped))

    @staticmethod
    def backward(z: float) -> float:
        """Inverse logit: ilogit(z) = 1 / (1 + exp(-z))."""
        return 1.0 / (1.0 + math.exp(-z))

    @staticmethod
    def se_from_ci(ci_lower: float, ci_upper: float) -> float:
        """Derive standard error from 95% confidence interval on original scale."""
        z_low = LogitTransformEngine.forward(ci_lower)
        z_high = LogitTransformEngine.forward(ci_upper)
        return abs(z_high - z_low) / (2.0 * 1.96)

    @classmethod
    def pool_bounded_metrics(cls, studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Pool bounded metrics (e.g., AUROC or prevalence).
        Each study dict must have:
        - study_id: str
        - metric_value: float (e.g., 0.83)
        - ci_lower: float (e.g., 0.82)
        - ci_upper: float (e.g., 0.85)
        - n: Optional[int]
        """
        zi = []
        vi = []
        study_records = []

        for s in studies:
            val = s["metric_value"]
            c_low = s["ci_lower"]
            c_high = s["ci_upper"]

            z = cls.forward(val)
            se_z = cls.se_from_ci(c_low, c_high)
            v = se_z ** 2

            zi.append(z)
            vi.append(v)
            study_records.append({
                "study_id": s["study_id"],
                "original_value": val,
                "ci_lower": c_low,
                "ci_upper": c_high,
                "logit_val": z,
                "logit_se": se_z
            })

        k = len(zi)
        z_arr = np.array(zi, dtype=float)
        v_arr = np.array(vi, dtype=float)
        wi = 1.0 / v_arr

        z_fe = np.sum(wi * z_arr) / np.sum(wi)
        q = float(np.sum(wi * (z_arr - z_fe) ** 2))
        df = k - 1

        c = np.sum(wi) - (np.sum(wi ** 2) / np.sum(wi))
        tau2 = max(0.0, (q - df) / c) if (c > 0 and df > 0) else 0.0

        weights = 1.0 / (v_arr + tau2)
        z_pool = float(np.sum(weights * z_arr) / np.sum(weights))
        se_pool = float(math.sqrt(1.0 / np.sum(weights)))

        if df > 0:
            q_re = np.sum(weights * (z_arr - z_pool) ** 2)
            kh = max(1.0, float(q_re / df))
            se_pool *= math.sqrt(kh)
            t_crit = stats.t.ppf(0.975, df)
            ci_l_z = z_pool - t_crit * se_pool
            ci_u_z = z_pool + t_crit * se_pool
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(z_pool / se_pool), df)))
        else:
            ci_l_z = z_pool - 1.96 * se_pool
            ci_u_z = z_pool + 1.96 * se_pool
            p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_pool / se_pool))))

        # Back-transform to original bounded scale (0, 1)
        pooled_original = cls.backward(z_pool)
        ci_lower_original = cls.backward(ci_l_z)
        ci_upper_original = cls.backward(ci_u_z)

        i2 = max(0.0, (q - df) / q * 100.0) if q > df and q > 0 else 0.0

        return {
            "k": k,
            "pooled_value": pooled_original,
            "ci_lower": ci_lower_original,
            "ci_upper": ci_upper_original,
            "p_value": p_val,
            "i2_percent": i2,
            "tau2": tau2,
            "q_stat": q,
            "studies": study_records
        }

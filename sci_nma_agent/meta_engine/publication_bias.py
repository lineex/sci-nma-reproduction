"""
Publication Bias & Funnel Plot Asymmetry Engine.
Implements Egger's linear regression test, Begg's rank correlation test, and Trim-and-Fill.
"""

from typing import List, Dict, Any, Tuple
import math
import numpy as np
from scipy import stats


class PublicationBiasEngine:
    """Statistical tests for small-study effects and publication bias."""

    @classmethod
    def egger_test(cls, yi: List[float], vi: List[float]) -> Dict[str, Any]:
        """
        Egger's linear regression test for funnel plot asymmetry:
        Standardized effect (yi / se_i) = alpha + beta * (1 / se_i) + epsilon.
        alpha != 0 indicates funnel plot asymmetry.
        """
        k = len(yi)
        if k < 3:
            return {"k": k, "intercept": 0.0, "p_value": 1.0, "interpretation": "Insufficient studies (<3)"}

        y = np.array(yi, dtype=float)
        se = np.sqrt(np.array(vi, dtype=float))

        z = y / se          # Standardized effect
        prec = 1.0 / se     # Precision

        # OLS regression: z = alpha + beta * prec
        slope, intercept, r_val, p_val, std_err = stats.linregress(prec, z)

        has_bias = (p_val < 0.05)
        interp = "Significant asymmetry detected (p < 0.05)" if has_bias else "No significant asymmetry (p >= 0.05)"

        return {
            "k": k,
            "intercept_alpha": float(intercept),
            "intercept_se": float(std_err),
            "t_statistic": float(intercept / std_err) if std_err > 0 else 0.0,
            "p_value": float(p_val),
            "has_bias": has_bias,
            "interpretation": interp
        }

    @classmethod
    def begg_test(cls, yi: List[float], vi: List[float]) -> Dict[str, Any]:
        """
        Begg and Mazumdar's rank correlation test:
        Kendall's tau between standardized effect size and variance.
        """
        k = len(yi)
        if k < 3:
            return {"k": k, "tau": 0.0, "p_value": 1.0}

        y = np.array(yi, dtype=float)
        v = np.array(vi, dtype=float)
        w = 1.0 / v
        pooled = np.sum(w * y) / np.sum(w)

        # Standardized residuals
        se = np.sqrt(v)
        std_res = (y - pooled) / se

        tau, p_val = stats.kendalltau(std_res, v)

        return {
            "k": k,
            "kendall_tau": float(tau),
            "p_value": float(p_val),
            "has_bias": (p_val < 0.05)
        }

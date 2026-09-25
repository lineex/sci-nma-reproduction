"""
Publication Bias & Funnel Plot Asymmetry Engine.
Implements exploratory Egger and Begg diagnostics. Trim-and-fill is not
implemented; small-study diagnostics remain protocol- and study-count
dependent.
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
        if k < 10:
            return {"k": k, "intercept": 0.0, "p_value": 1.0, "interpretation": "Not assessed: fewer than 10 studies"}

        y = np.array(yi, dtype=float)
        se = np.sqrt(np.array(vi, dtype=float))

        z = y / se          # Standardized effect
        prec = 1.0 / se     # Precision

        # OLS regression: z = alpha + beta * prec. Test the intercept, not
        # the slope, using the residual degrees of freedom.
        X = np.column_stack([np.ones(k), prec])
        try:
            xtx_inv = np.linalg.inv(X.T @ X)
        except np.linalg.LinAlgError:
            return {"k": k, "intercept": 0.0, "p_value": 1.0, "interpretation": "Not assessed: singular precision values"}
        beta = xtx_inv @ X.T @ z
        residuals = z - X @ beta
        df = k - 2
        residual_variance = float(np.sum(residuals ** 2) / df) if df > 0 else 0.0
        intercept = float(beta[0])
        intercept_se = math.sqrt(max(0.0, residual_variance * xtx_inv[0, 0]))
        t_statistic = intercept / intercept_se if intercept_se > 0 else 0.0
        p_val = float(2.0 * stats.t.sf(abs(t_statistic), df)) if df > 0 else 1.0

        has_bias = (p_val < 0.05)
        interp = "Significant asymmetry detected (p < 0.05)" if has_bias else "No significant asymmetry (p >= 0.05)"

        return {
            "k": k,
            "intercept_alpha": float(intercept),
            "intercept_se": float(intercept_se),
            "t_statistic": float(t_statistic),
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
        if k < 10:
            return {"k": k, "tau": 0.0, "p_value": 1.0, "interpretation": "Not assessed: fewer than 10 studies"}

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

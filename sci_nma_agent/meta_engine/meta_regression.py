"""
Meta-Regression Engine.
Fits weighted meta-regression models with variance weights (1/SE²) and calculates R² analog.
"""

from typing import List, Dict, Any, Tuple
import math
import numpy as np
from scipy import stats


class MetaRegressionEngine:
    """Calculates weighted linear meta-regression."""

    @classmethod
    def fit_univariate(
        cls,
        yi: List[float],
        vi: List[float],
        covariates: List[float],
        covariate_name: str = "Covariate"
    ) -> Dict[str, Any]:
        """
        Fit weighted regression: yi = beta0 + beta1 * xi + e.
        Weights: wi = 1 / vi (inverse variance).
        """
        k = len(yi)
        y = np.array(yi, dtype=float)
        v = np.array(vi, dtype=float)
        x = np.array(covariates, dtype=float)

        w = 1.0 / v
        W = np.diag(w)
        X = np.column_stack([np.ones(k), x])

        # Weighted least squares: beta = (X^T W X)^(-1) X^T W y
        XtW = X.T @ W
        XtWX = XtW @ X
        XtWy = XtW @ y

        beta = np.linalg.inv(XtWX) @ XtWy
        cov_beta = np.linalg.inv(XtWX)

        se_beta0 = math.sqrt(cov_beta[0, 0])
        se_beta1 = math.sqrt(cov_beta[1, 1])

        # Residuals
        y_pred = X @ beta
        residuals = y - y_pred
        q_res = float(np.sum(w * (residuals ** 2)))
        df_res = k - 2

        # P-value for slope
        z_slope = beta[1] / se_beta1 if se_beta1 > 0 else 0.0
        p_slope = float(2.0 * (1.0 - stats.norm.cdf(abs(z_slope))))

        # Total Q (without covariate)
        y_mean = np.sum(w * y) / np.sum(w)
        q_total = float(np.sum(w * (y - y_mean) ** 2))

        # R^2 analog (explained variance)
        r2_analog = max(0.0, (q_total - q_res) / q_total * 100.0) if q_total > 0 else 0.0

        return {
            "k": k,
            "covariate": covariate_name,
            "intercept": float(beta[0]),
            "intercept_se": se_beta0,
            "slope": float(beta[1]),
            "slope_se": se_beta1,
            "slope_p_value": p_slope,
            "q_residual": q_res,
            "df_residual": df_res,
            "r2_analog_percent": r2_analog,
            "fitted_values": y_pred.tolist(),
            "weights": w.tolist()
        }

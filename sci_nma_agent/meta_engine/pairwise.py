"""
Pairwise Meta-Analysis Engine.
Calculates pooled effect sizes (OR, RR, MD, SMD) using DerSimonian-Laird and REML
with Knapp-Hartung adjustments and heterogeneity metrics (I², τ², Q).
"""

from typing import List, Dict, Any, Tuple
import math
import numpy as np
from scipy import stats


class PairwiseMetaAnalysis:
    """Statistical calculator for pairwise meta-analysis."""

    @classmethod
    def analyze_binary(
        cls, studies: List[Dict[str, Any]], measure: str = "OR", model: str = "random"
    ) -> Dict[str, Any]:
        """
        Analyze binary event data across studies.
        Each study dict must contain:
        - study_id: str
        - events_treatment: int
        - total_treatment: int
        - events_control: int
        - total_control: int
        """
        yi = []
        vi = []
        study_records = []

        for s in studies:
            a = s["events_treatment"]
            n1 = s["total_treatment"]
            c = s["events_control"]
            n2 = s["total_control"]
            b = n1 - a
            d = n2 - c

            # Continuity correction for 0 cells
            adj = 0.5 if (a == 0 or b == 0 or c == 0 or d == 0) else 0.0
            a_adj, b_adj, c_adj, d_adj = a + adj, b + adj, c + adj, d + adj

            if measure.upper() == "OR":
                est = (a_adj * d_adj) / (b_adj * c_adj)
                y = math.log(est)
                v = 1.0 / a_adj + 1.0 / b_adj + 1.0 / c_adj + 1.0 / d_adj
            elif measure.upper() == "RR":
                p1 = a_adj / (n1 + adj * 2)
                p2 = c_adj / (n2 + adj * 2)
                est = p1 / p2
                y = math.log(est)
                v = (n1 - a) / (n1 * a_adj) + (n2 - c) / (n2 * c_adj)
            else:
                # Risk difference
                p1 = a / n1
                p2 = c / n2
                y = p1 - p2
                v = (p1 * (1 - p1)) / n1 + (p2 * (1 - p2)) / n2
                est = y

            se = math.sqrt(v)
            ci_low = math.exp(y - 1.96 * se) if measure.upper() in ["OR", "RR"] else (y - 1.96 * se)
            ci_high = math.exp(y + 1.96 * se) if measure.upper() in ["OR", "RR"] else (y + 1.96 * se)

            yi.append(y)
            vi.append(v)

            study_records.append({
                "study_id": s.get("study_id", "Study"),
                "events_treatment": a,
                "total_treatment": n1,
                "events_control": c,
                "total_control": n2,
                "effect_size": est,
                "log_effect": y,
                "se": se,
                "ci_lower": ci_low,
                "ci_upper": ci_high
            })

        k = len(yi)
        if k == 0:
            return {"k": 0, "pooled_effect": 1.0}

        y_arr = np.array(yi, dtype=float)
        v_arr = np.array(vi, dtype=float)
        wi = 1.0 / v_arr

        # Fixed effect baseline
        y_fe = np.sum(wi * y_arr) / np.sum(wi)
        q = float(np.sum(wi * (y_arr - y_fe) ** 2))
        df = k - 1
        p_q = float(1.0 - stats.chi2.cdf(q, df)) if df > 0 else 1.0

        # DL tau^2
        c_denom = np.sum(wi) - (np.sum(wi ** 2) / np.sum(wi))
        tau2 = max(0.0, (q - df) / c_denom) if (c_denom > 0 and df > 0) else 0.0

        if model == "fixed":
            weights = wi
            y_pool = y_fe
            se_pool = float(math.sqrt(1.0 / np.sum(wi)))
        else:
            weights = 1.0 / (v_arr + tau2)
            y_pool = float(np.sum(weights * y_arr) / np.sum(weights))
            se_pool = float(math.sqrt(1.0 / np.sum(weights)))

            # Knapp-Hartung adjustment
            if df > 0:
                q_re = np.sum(weights * (y_arr - y_pool) ** 2)
                kh_factor = max(1.0, float(q_re / df))
                se_pool = se_pool * math.sqrt(kh_factor)

        # Percent weights
        weights_pct = (weights / np.sum(weights) * 100.0).tolist()
        for idx, rec in enumerate(study_records):
            rec["weight_percent"] = weights_pct[idx]

        # Pooled CI & p-value
        if df > 0 and model == "random":
            t_crit = stats.t.ppf(0.975, df)
            ci_l_log = y_pool - t_crit * se_pool
            ci_u_log = y_pool + t_crit * se_pool
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(y_pool / se_pool), df)))
        else:
            ci_l_log = y_pool - 1.96 * se_pool
            ci_u_log = y_pool + 1.96 * se_pool
            p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(y_pool / se_pool))))

        pooled_est = math.exp(y_pool) if measure.upper() in ["OR", "RR"] else y_pool
        ci_l = math.exp(ci_l_log) if measure.upper() in ["OR", "RR"] else ci_l_log
        ci_u = math.exp(ci_u_log) if measure.upper() in ["OR", "RR"] else ci_u_log

        i2 = max(0.0, (q - df) / q * 100.0) if q > df and q > 0 else 0.0

        return {
            "k": k,
            "measure": measure.upper(),
            "model": model,
            "pooled_estimate": pooled_est,
            "pooled_log": y_pool,
            "se": se_pool,
            "ci_lower": ci_l,
            "ci_upper": ci_u,
            "p_value": p_val,
            "q_statistic": q,
            "q_p_value": p_q,
            "tau2": tau2,
            "i2_percent": i2,
            "studies": study_records
        }

"""
Network Meta-Analysis (NMA) Engine.
Provides an exploratory direct-comparison/bridge calculation for QA fixtures.
It is not a full contrast-based NMA implementation and its point-estimate
ranking must not be reported as uncertainty-aware SUCRA without validation in
the locked production NMA software.
"""

from typing import List, Dict, Any, Tuple, Optional
import math
import numpy as np


class NetworkMetaEngine:
    """Exploratory network QA calculator; production NMA uses a validated engine."""

    @classmethod
    def calculate_nma(
        cls,
        trials: List[Dict[str, Any]],
        treatments: List[str],
        reference_treatment: str = "Placebo"
    ) -> Dict[str, Any]:
        """
        Synthesize network of randomized trials.
        trials: list of dicts with:
        - study_id: str
        - t1: str (treatment 1)
        - t2: str (treatment 2)
        - log_or: float
        - se: float
        """
        if len(set(treatments)) != len(treatments):
            raise ValueError("treatments must be unique")
        if reference_treatment not in treatments:
            raise ValueError("reference_treatment must be included in treatments")
        adjacency = {treatment: set() for treatment in treatments}
        for trial in trials:
            t1, t2 = trial["t1"], trial["t2"]
            if t1 not in adjacency or t2 not in adjacency or t1 == t2:
                raise ValueError("each trial must connect two distinct declared treatments")
            if not math.isfinite(float(trial["se"])) or float(trial["se"]) <= 0:
                raise ValueError("each trial standard error must be finite and positive")
            adjacency[t1].add(t2)
            adjacency[t2].add(t1)
        reachable = {reference_treatment}
        frontier = [reference_treatment]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency[current]:
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    frontier.append(neighbor)
        disconnected = [treatment for treatment in treatments if treatment not in reachable]
        if disconnected:
            raise ValueError(
                "network is disconnected from the reference treatment; "
                f"report separate components instead of ranking together: {disconnected}"
            )

        # 1. Direct comparisons matrix
        direct_pairs = {}
        for tr in trials:
            t1, t2 = tr["t1"], tr["t2"]
            pair = tuple(sorted([t1, t2]))
            # Determine direction: effect of t1 vs t2
            y = tr["log_or"] if pair == (t1, t2) else -tr["log_or"]
            v = tr["se"] ** 2

            if pair not in direct_pairs:
                direct_pairs[pair] = {"y": [], "v": []}
            direct_pairs[pair]["y"].append(y)
            direct_pairs[pair]["v"].append(v)

        # Pool direct comparisons (inverse variance)
        direct_estimates = {}
        for pair, dat in direct_pairs.items():
            w = [1.0 / vi for vi in dat["v"]]
            pooled_y = sum(wi * yi for wi, yi in zip(w, dat["y"])) / sum(w)
            pooled_se = math.sqrt(1.0 / sum(w))
            direct_estimates[pair] = {"log_effect": pooled_y, "se": pooled_se}

        # 2. Derive relative effects vs reference treatment (Bucher indirect synthesis)
        rel_effects = {}
        for t in treatments:
            if t == reference_treatment:
                rel_effects[t] = {"log_or": 0.0, "se": 0.0, "or": 1.0, "ci_lower": 1.0, "ci_upper": 1.0}
                continue

            pair = tuple(sorted([t, reference_treatment]))
            if pair in direct_estimates:
                est = direct_estimates[pair]
                # Direction relative to reference (t vs ref)
                y = est["log_effect"] if pair == (t, reference_treatment) else -est["log_effect"]
                se = est["se"]
            else:
                # Find an intermediary bridge treatment
                bridge_found = False
                for bridge in treatments:
                    p1 = tuple(sorted([t, bridge]))
                    p2 = tuple(sorted([bridge, reference_treatment]))
                    if p1 in direct_estimates and p2 in direct_estimates:
                        y1 = direct_estimates[p1]["log_effect"] if p1 == (t, bridge) else -direct_estimates[p1]["log_effect"]
                        y2 = direct_estimates[p2]["log_effect"] if p2 == (bridge, reference_treatment) else -direct_estimates[p2]["log_effect"]
                        y = y1 + y2
                        se = math.sqrt(direct_estimates[p1]["se"] ** 2 + direct_estimates[p2]["se"] ** 2)
                        bridge_found = True
                        break
                if not bridge_found:
                    raise ValueError(
                        "QA NMA calculator supports only direct or single-bridge contrasts; "
                        "use the locked production NMA engine for multi-hop networks"
                    )

            ci_low = math.exp(y - 1.96 * se)
            ci_high = math.exp(y + 1.96 * se)
            rel_effects[t] = {
                "log_or": y,
                "se": se,
                "or": math.exp(y),
                "ci_lower": ci_low,
                "ci_upper": ci_high
            }

        # 3. Construct League Table Matrix
        n_treatments = len(treatments)
        league_table = {}
        for tA in treatments:
            league_table[tA] = {}
            for tB in treatments:
                if tA == tB:
                    league_table[tA][tB] = tA
                else:
                    # Effect of tA vs tB = (tA vs ref) - (tB vs ref)
                    log_ab = rel_effects[tA]["log_or"] - rel_effects[tB]["log_or"]
                    se_ab = math.sqrt(rel_effects[tA]["se"] ** 2 + rel_effects[tB]["se"] ** 2)
                    or_ab = math.exp(log_ab)
                    ci_l = math.exp(log_ab - 1.96 * se_ab)
                    ci_u = math.exp(log_ab + 1.96 * se_ab)
                    league_table[tA][tB] = f"{or_ab:.2f} ({ci_l:.2f}, {ci_u:.2f})"

        # 4. SUCRA (Surface Under Cumulative Ranking Curve) Calculation
        # For survival or reduction in mortality, lower OR is superior
        # Rank by point estimates vs reference
        sorted_treats = sorted(treatments, key=lambda x: rel_effects[x]["log_or"])
        a = len(treatments)
        sucra_scores = {}
        rankings = []

        for rank_idx, t in enumerate(sorted_treats):
            # Simulated posterior ranking score
            sucra = (a - 1 - rank_idx) / (a - 1) if (a > 1) else 1.0
            sucra_pct = sucra * 100.0
            sucra_scores[t] = sucra_pct
            rankings.append({
                "treatment": t,
                "rank": rank_idx + 1,
                "sucra_percent": sucra_pct,
                "relative_or_vs_ref": rel_effects[t]["or"],
                "ci_lower": rel_effects[t]["ci_lower"],
                "ci_upper": rel_effects[t]["ci_upper"]
            })

        return {
            "engine_role": "exploratory_qa",
            "production_use": "not_for_release",
            "model_scope": "direct_comparison_and_single_bridge_Bucher_QA",
            "reference_treatment": reference_treatment,
            "relative_effects_vs_reference": rel_effects,
            "league_table": league_table,
            "sucra_scores": sucra_scores,
            "rankings": rankings
        }

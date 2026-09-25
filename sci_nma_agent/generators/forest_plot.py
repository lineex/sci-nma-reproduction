"""
High-Density Subgroup Forest Plot Generator.
Generates publication-grade forest plots in 600 DPI PNG, pure live-text SVG (<text>), and Type 42 PDF.
Adheres to Critical Care / Lancet / NEJM forest plot visualization specifications.
"""

import os
from typing import List, Dict, Any, Optional
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches


class ForestPlotGenerator:
    """Generates publication-grade Forest Plots across PNG, SVG, and PDF formats."""

    @classmethod
    def generate_not_estimable(
        cls,
        output_prefix: str,
        title: str = "All-Cause Mortality at 28-30 Days",
        message: str = "Pairwise meta-analysis not planned; no pooled pairwise estimate is estimable.",
        xlabel: str = "Odds Ratio (95% CI)",
        dpi: int = 600,
    ) -> Dict[str, str]:
        """Render the fixed forest-figure contract when pairwise synthesis is not estimable.

        This intentionally contains no synthetic study row, effect estimate, CI, or
        summary diamond. It is used for NMA-only production protocols so the fixed
        Figure 2 file contract remains present without fabricating pairwise data.
        """
        plt.rcParams['svg.fonttype'] = 'none'
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(figsize=(11, 8.0), dpi=dpi)
        ax.set_xscale("log")
        ax.set_xlim(0.1, 10.0)
        ax.set_xticks([0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.axvline(x=1.0, color="#64748B", linestyle="--", lw=1.2, zorder=1)
        ax.text(
            0.5, 0.56, "Not estimable", transform=ax.transAxes,
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A"
        )
        ax.text(
            0.5, 0.46, message, transform=ax.transAxes,
            ha="center", va="center", fontsize=11, color="#334155", wrap=True
        )
        ax.set_ylim(0.0, 1.0)
        ax.set_yticks([])
        ax.set_xlabel(xlabel, fontsize=10.5, fontweight="bold", labelpad=10)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=16)
        for spine in ("left", "right", "top"):
            ax.spines[spine].set_visible(False)
        plt.tight_layout()

        os.makedirs(os.path.dirname(output_prefix) if os.path.dirname(output_prefix) else ".", exist_ok=True)
        png_path = f"{output_prefix}.png"
        svg_path = f"{output_prefix}.svg"
        pdf_path = f"{output_prefix}.pdf"
        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        plt.savefig(pdf_path, format="pdf", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return {"png": png_path, "svg": svg_path, "pdf": pdf_path}

    @classmethod
    def generate(
        cls,
        analysis_result: Dict[str, Any],
        output_prefix: str,
        title: str = "All-Cause Mortality at 28-30 Days",
        xlabel: str = "Odds Ratio (95% CI)",
        xscale: str = "log",
        dpi: int = 600
    ) -> Dict[str, str]:
        """
        Generate high-density subgroup forest plot.
        """
        plt.rcParams['svg.fonttype'] = 'none'
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        studies = analysis_result.get("studies", [])
        k = len(studies)
        if k == 0:
            raise ValueError("No studies provided to render forest plot.")

        # Calculate canvas height based on study count
        fig_height = max(8.0, 3.0 + k * 0.45)
        fig, ax = plt.subplots(figsize=(11, fig_height), dpi=dpi)

        # Layout parameters
        y_positions = list(range(k, 0, -1))

        # Overall summary parameters
        pooled_est = analysis_result.get("pooled_estimate", 1.0)
        ci_l = analysis_result.get("ci_lower", 0.8)
        ci_u = analysis_result.get("ci_upper", 1.2)
        i2 = analysis_result.get("i2_percent", 0.0)
        p_val = analysis_result.get("p_value", 0.05)
        tau2 = analysis_result.get("tau2", 0.0)

        # Plot points and CI lines
        for idx, s in enumerate(studies):
            y = y_positions[idx]
            est = s.get("effect_size", 1.0)
            low = s.get("ci_lower", 0.5)
            high = s.get("ci_upper", 2.0)
            weight = s.get("weight_percent", 5.0)

            # Cap whiskers at sensible extremes for display
            low_plot = max(low, 0.05)
            high_plot = min(high, 20.0)

            # Draw CI line with end ticks
            ax.plot([low_plot, high_plot], [y, y], color="#1E293B", lw=1.2, zorder=2)
            ax.plot([low_plot, low_plot], [y - 0.12, y + 0.12], color="#1E293B", lw=1.2, zorder=2)
            ax.plot([high_plot, high_plot], [y - 0.12, y + 0.12], color="#1E293B", lw=1.2, zorder=2)

            # Draw square whose area is proportional to weight
            side = 0.15 + (weight / 100.0) * 0.45
            rect = patches.Rectangle(
                (est * math.exp(-side/2) if xscale == "log" else est - side/2, y - side/2),
                (est * (math.exp(side) - math.exp(-side)) if xscale == "log" else side),
                side,
                facecolor="#2563EB", edgecolor="#1E40AF", lw=1.0, zorder=3
            )
            ax.add_patch(rect)

        # Draw Overall Summary Diamond at y = -0.5
        y_diamond = -0.5
        diamond_pts = np.array([
            [ci_l, y_diamond],
            [pooled_est, y_diamond + 0.28],
            [ci_u, y_diamond],
            [pooled_est, y_diamond - 0.28]
        ])
        diamond = patches.Polygon(
            diamond_pts, closed=True,
            facecolor="#DC2626", edgecolor="#991B1B", lw=1.2, zorder=4
        )
        ax.add_patch(diamond)

        # Reference Vertical Lines
        # 1. Null line at x = 1.0
        ax.axvline(x=1.0, color="#64748B", linestyle="--", lw=1.2, zorder=1)
        # 2. Pooled effect vertical line
        ax.axvline(x=pooled_est, color="#DC2626", linestyle=":", lw=1.2, zorder=1)

        # Horizontal separator lines
        ax.axhline(y=0.4, color="#CBD5E1", lw=1.0)

        # Configure Axes & Limits
        if xscale == "log":
            ax.set_xscale("log")
            ax.set_xlim(0.1, 10.0)
            ax.set_xticks([0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0])
            ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

        ax.set_ylim(-1.5, k + 1.8)
        ax.set_yticks([])  # Custom annotations instead

        # Text Columns: Left (Study Name & Events) and Right (Weight & OR [95% CI])
        # Double top rule
        ax.axhline(y=k + 1.4, color="#0F172A", lw=1.5)
        ax.axhline(y=k + 0.7, color="#0F172A", lw=1.0)

        # Column Headers
        ax.text(0.11, k + 1.0, "Study (Author & Year)", fontsize=10, fontweight="bold", va="center")
        ax.text(0.35, k + 1.0, "Intervention (n/N)", fontsize=9.5, fontweight="bold", va="center")
        ax.text(0.60, k + 1.0, "Control (n/N)", fontsize=9.5, fontweight="bold", va="center")
        ax.text(2.6, k + 1.0, "Weight (%)", fontsize=9.5, fontweight="bold", va="center")
        ax.text(5.0, k + 1.0, "OR [95% CI]", fontsize=10, fontweight="bold", va="center")

        for idx, s in enumerate(studies):
            y = y_positions[idx]
            name = s.get("study_id", f"Study {idx+1}")
            e_t = s.get("events_treatment", "-")
            n_t = s.get("total_treatment", "-")
            e_c = s.get("events_control", "-")
            n_c = s.get("total_control", "-")
            wt = s.get("weight_percent", 0.0)
            est = s.get("effect_size", 1.0)
            ci_l_s = s.get("ci_lower", 0.0)
            ci_u_s = s.get("ci_upper", 0.0)

            ax.text(0.11, y, name, fontsize=9, va="center")
            ax.text(0.35, y, f"{e_t}/{n_t}", fontsize=8.5, va="center")
            ax.text(0.60, y, f"{e_c}/{n_c}", fontsize=8.5, va="center")
            ax.text(2.6, y, f"{wt:.1f}%", fontsize=8.5, va="center")
            ax.text(5.0, y, f"{est:.2f} [{ci_l_s:.2f}, {ci_u_s:.2f}]", fontsize=9, va="center")

        # Summary Row Text
        summary_label = f"RE Model (I² = {i2:.1f}%, τ² = {tau2:.3f}, p = {p_val:.3f})"
        ax.text(0.11, y_diamond, summary_label, fontsize=9.5, fontweight="bold", va="center", color="#0F172A")
        ax.text(2.6, y_diamond, "100.0%", fontsize=9, fontweight="bold", va="center")
        ax.text(5.0, y_diamond, f"{pooled_est:.2f} [{ci_l:.2f}, {ci_u:.2f}]", fontsize=10, fontweight="bold", va="center", color="#DC2626")

        # Bottom Subtitle labels: Favors Intervention vs Favors Control
        ax.text(0.3, -1.3, "◄ Favors Corticosteroids", fontsize=9, fontweight="bold", ha="center", color="#1E3A8A")
        ax.text(3.0, -1.3, "Favors Control ►", fontsize=9, fontweight="bold", ha="center", color="#7F1D1D")

        ax.set_xlabel(xlabel, fontsize=10.5, fontweight="bold", labelpad=10)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=16)

        plt.tight_layout()

        # Output paths
        os.makedirs(os.path.dirname(output_prefix) if os.path.dirname(output_prefix) else ".", exist_ok=True)
        png_path = f"{output_prefix}.png"
        svg_path = f"{output_prefix}.svg"
        pdf_path = f"{output_prefix}.pdf"

        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        plt.savefig(pdf_path, format="pdf", bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return {"png": png_path, "svg": svg_path, "pdf": pdf_path}

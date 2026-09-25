"""
Network Geometry Map Generator.
Renders publication-grade NMA network geometry plots in 600 DPI PNG, live-text SVG, and Type 42 PDF.
Node diameter maps to total randomized sample size, edge width maps to direct trial count.
"""

import os
from typing import Dict, Any, List, Tuple
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches


class NetworkGeometryGenerator:
    """Generates NMA Network Geometry Plots."""

    @classmethod
    def generate_not_estimable(
        cls,
        output_prefix: str,
        title: str = "Network Meta-analysis",
        message: str = "Network meta-analysis not planned; no network geometry is estimable.",
        dpi: int = 600,
    ) -> Dict[str, str]:
        """Render the fixed Figure 3 contract without inventing network data."""
        plt.rcParams['svg.fonttype'] = 'none'
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(figsize=(10, 10), dpi=dpi)
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.axis('off')
        ax.text(0, 0.12, "Not estimable", ha="center", va="center", fontsize=18,
                fontweight="bold", color="#0F172A")
        ax.text(0, -0.08, message, ha="center", va="center", fontsize=11,
                color="#334155", wrap=True)
        ax.text(0, 1.25, title, ha="center", va="center", fontsize=13,
                fontweight="bold", color="#0F172A")
        ax.text(0, -1.25,
                "Treatment nodes and direct comparisons are not applicable because NMA was not planned.",
                ha="center", va="center", fontsize=9, fontstyle="italic", color="#475569")
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
        treatments: List[Dict[str, Any]],
        comparisons: List[Dict[str, Any]],
        output_prefix: str,
        title: str = "Network Geometry of Evaluated Pharmacological Interventions",
        dpi: int = 600
    ) -> Dict[str, str]:
        """
        treatments: list of dicts with:
          - id: str (e.g. 'Hydrocortisone')
          - sample_size: int (e.g. 3850)
          - color: str (e.g. '#2563EB')
        comparisons: list of dicts with:
          - t1: str
          - t2: str
          - trial_count: int (e.g. 14)
        """
        plt.rcParams['svg.fonttype'] = 'none'
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(figsize=(10, 10), dpi=dpi)
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.axis('off')

        n = len(treatments)
        if n == 0:
            raise ValueError("No treatments provided for network geometry.")

        # Compute coordinates on a circle
        coords = {}
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        radius = 1.0

        for i, tr in enumerate(treatments):
            # Rotate so reference is typically bottom or top
            theta = angles[i] + np.pi / 2
            x = radius * np.cos(theta)
            y = radius * np.sin(theta)
            coords[tr["id"]] = (x, y)

        # Draw Edges first
        max_trials = max([c.get("trial_count", 1) for c in comparisons]) if comparisons else 1
        for comp in comparisons:
            t1, t2 = comp["t1"], comp["t2"]
            if t1 in coords and t2 in coords:
                x1, y1 = coords[t1]
                x2, y2 = coords[t2]
                n_trials = comp.get("trial_count", 1)
                lw = max(1.5, (n_trials / max_trials) * 9.0)

                # Line with subtle shadow
                ax.plot([x1, x2], [y1, y2], color="#94A3B8", lw=lw, zorder=1, alpha=0.85)

                # Label midpoint with trial count
                mx = (x1 + x2) / 2
                my = (y1 + y2) / 2
                ax.text(
                    mx, my, f"n={n_trials}",
                    fontsize=8.5, fontweight="bold", color="#1E293B",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#CBD5E1", lw=0.8, alpha=0.9),
                    zorder=3
                )

        # Draw Nodes
        max_n = max([t.get("sample_size", 100) for t in treatments])
        for tr in treatments:
            t_id = tr["id"]
            x, y = coords[t_id]
            size_n = tr.get("sample_size", 500)
            col = tr.get("color", "#3B82F6")

            # Radius proportional to sqrt(sample_size)
            node_r = 0.12 + math.sqrt(size_n / max_n) * 0.16

            circle = patches.Circle(
                (x, y), node_r,
                facecolor=col, edgecolor="#0F172A", lw=2.0, zorder=4
            )
            ax.add_patch(circle)

            # Node Text inside or beside
            # Text inside node: Sample size
            ax.text(
                x, y, f"N={size_n:,}",
                ha="center", va="center", color="white", fontsize=8.5, fontweight="bold", zorder=5
            )

            # Label outside node
            label_dist = node_r + 0.14
            lx = x + (label_dist * (x / radius if radius > 0 else 1))
            ly = y + (label_dist * (y / radius if radius > 0 else 1))
            ha = "center" if abs(x) < 0.2 else ("left" if x > 0 else "right")
            va = "center" if abs(y) < 0.2 else ("bottom" if y > 0 else "top")

            ax.text(
                lx, ly, t_id,
                ha=ha, va=va, fontsize=10.5, fontweight="bold", color="#0F172A", zorder=5
            )

        # Title and Caption
        ax.text(
            0, 1.4, title,
            ha="center", va="center", fontsize=13, fontweight="bold", color="#0F172A"
        )
        ax.text(
            0, -1.4,
            "Node size represents total randomized patients. Edge width represents number of direct trials.",
            ha="center", va="center", fontsize=9, fontstyle="italic", color="#475569"
        )

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

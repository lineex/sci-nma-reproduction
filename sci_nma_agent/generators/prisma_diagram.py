"""
PRISMA 2020 Flow Diagram Generator.
Renders publication-grade flow diagrams in 600 DPI PNG, pure live-text SVG (<text>), and Type 42 PDF.
Adheres to Critical Care / Lancet / BMJ PRISMA 2020 visualization specifications.
"""

import os
from typing import Dict, Any, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch


class PRISMADiagramGenerator:
    """Generates PRISMA 2020 Flow Diagram across PNG, SVG, and PDF formats."""

    @classmethod
    def generate(
        cls,
        flow_data: Dict[str, Any],
        output_prefix: str,
        dpi: int = 600
    ) -> Dict[str, str]:
        """
        Generate PRISMA 2020 Flow Diagram.
        flow_data must include database tallies, duplicates, screening exclusions,
        reports sought/assessed, full-text exclusions breakdown, and included count.
        """
        # Configure Matplotlib for live-text vector export
        plt.rcParams['svg.fonttype'] = 'none'
        plt.rcParams['pdf.fonttype'] = 42
        plt.rcParams['font.sans-serif'] = ['Arial', 'Calibri', 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(figsize=(12, 14), dpi=dpi)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis('off')

        # Color Palette (Lancet / Critical Care Style)
        C_BANNER = "#D97706"       # Amber / Gold banner
        C_PHASE = "#1E3A8A"        # Deep Blue
        C_BOX_BG = "#F8FAFC"       # Light Gray-Blue
        C_BOX_BORDER = "#475569"   # Slate Gray
        C_EXCLUDE_BG = "#FFF7ED"   # Warm Off-White
        C_EXCLUDE_BORDER = "#EA580C"# Amber-Orange
        C_ARROW = "#334155"

        # 1. Top Header Banner
        banner = FancyBboxPatch(
            (10, 94), 85, 4.5,
            boxstyle="round,pad=0.2,rounding_size=0.8",
            facecolor=C_BANNER, edgecolor="#B45309", linewidth=1.5
        )
        ax.add_patch(banner)
        ax.text(
            52.5, 96.2, "Identification of studies via databases and registers (PRISMA 2020)",
            ha="center", va="center", color="white", fontsize=13, fontweight="bold"
        )

        # 2. Left Vertical Phase Navigation Bars
        phases = [
            ("Identification", 73, 19),
            ("Screening", 47, 23),
            ("Included", 18, 26)
        ]
        for name, y_center, h in phases:
            bar = FancyBboxPatch(
                (2, y_center - h/2), 5, h,
                boxstyle="round,pad=0.2,rounding_size=0.6",
                facecolor=C_PHASE, edgecolor="#172554", linewidth=1.2
            )
            ax.add_patch(bar)
            ax.text(
                4.5, y_center, name,
                ha="center", va="center", color="white", fontsize=11, fontweight="bold", rotation=90
            )

        # Extract values
        dbs = flow_data.get("databases", {})
        total_ident = flow_data.get("total_identified", sum(dbs.values()))
        dups = flow_data.get("duplicates_removed", 0)
        screened = flow_data.get("records_screened", total_ident - dups)
        screen_ex = flow_data.get("screening_excluded", 0)
        sought = flow_data.get("reports_sought", screened - screen_ex)
        not_retr = flow_data.get("reports_not_retrieved", 0)
        assessed = flow_data.get("reports_assessed", sought - not_retr)
        ft_ex = flow_data.get("fulltext_excluded", 0)
        ft_reasons = flow_data.get("fulltext_exclusion_reasons", {})
        included = flow_data.get("studies_included", assessed - ft_ex)

        # 3. Top Identification Box (Left)
        db_lines = [f"• {db} (n = {cnt})" for db, cnt in dbs.items()]
        db_text = f"Records identified from databases (n = {sum(dbs.values())}):\n" + "\n".join(db_lines)
        if flow_data.get("registries_or_citations", 0) > 0:
            db_text += f"\n• Citation searching (n = {flow_data['registries_or_citations']})"

        box_ident = FancyBboxPatch(
            (12, 69), 38, 20,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_BOX_BG, edgecolor=C_BOX_BORDER, linewidth=1.2
        )
        ax.add_patch(box_ident)
        ax.text(14, 86, db_text, va="top", fontsize=9.5, linespacing=1.3)

        # 4. Duplicates Removed Box (Right)
        dup_text = (
            f"Records removed before screening:\n"
            f"• Duplicate records removed (n = {dups})\n"
            f"• Records marked ineligible by automation (n = 0)\n"
            f"• Records removed for other reasons (n = 0)"
        )
        box_dup = FancyBboxPatch(
            (56, 73), 39, 12,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_EXCLUDE_BG, edgecolor=C_EXCLUDE_BORDER, linewidth=1.2
        )
        ax.add_patch(box_dup)
        ax.text(58, 83, dup_text, va="top", fontsize=9.5, linespacing=1.3)

        # Arrow Ident -> Dup
        ax.annotate(
            "", xy=(56, 79), xytext=(50, 79),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 5. Screening Box
        box_screen = FancyBboxPatch(
            (12, 53), 38, 8,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_BOX_BG, edgecolor=C_BOX_BORDER, linewidth=1.2
        )
        ax.add_patch(box_screen)
        ax.text(31, 57, f"Records screened\n(n = {screened})", ha="center", va="center", fontsize=10, fontweight="bold")

        # Arrow Ident -> Screen
        ax.annotate(
            "", xy=(31, 61), xytext=(31, 69),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 6. Screening Excluded Box
        box_sc_ex = FancyBboxPatch(
            (56, 52), 39, 10,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_EXCLUDE_BG, edgecolor=C_EXCLUDE_BORDER, linewidth=1.2
        )
        ax.add_patch(box_sc_ex)
        ax.text(58, 59.5, f"Records excluded by title/abstract\n(n = {screen_ex})", va="top", fontsize=9.5, fontweight="bold")

        # Arrow Screen -> Sc Ex
        ax.annotate(
            "", xy=(56, 57), xytext=(50, 57),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 7. Reports Sought Box
        box_sought = FancyBboxPatch(
            (12, 38), 38, 7,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_BOX_BG, edgecolor=C_BOX_BORDER, linewidth=1.2
        )
        ax.add_patch(box_sought)
        ax.text(31, 41.5, f"Reports sought for retrieval\n(n = {sought})", ha="center", va="center", fontsize=10, fontweight="bold")

        # Arrow Screen -> Sought
        ax.annotate(
            "", xy=(31, 45), xytext=(31, 53),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 8. Reports Not Retrieved (Right)
        box_not_retr = FancyBboxPatch(
            (56, 38), 39, 7,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_EXCLUDE_BG, edgecolor=C_EXCLUDE_BORDER, linewidth=1.2
        )
        ax.add_patch(box_not_retr)
        ax.text(58, 41.5, f"Reports not retrieved\n(n = {not_retr})", va="center", fontsize=9.5)

        ax.annotate(
            "", xy=(56, 41.5), xytext=(50, 41.5),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 9. Reports Assessed Box
        box_assess = FancyBboxPatch(
            (12, 23), 38, 8,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_BOX_BG, edgecolor=C_BOX_BORDER, linewidth=1.2
        )
        ax.add_patch(box_assess)
        ax.text(31, 27, f"Reports assessed for eligibility\n(n = {assessed})", ha="center", va="center", fontsize=10, fontweight="bold")

        ax.annotate(
            "", xy=(31, 31), xytext=(31, 38),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 10. Fulltext Excluded Reasons Box (Right)
        ft_lines = [f"• {reason} (n = {cnt})" for reason, cnt in ft_reasons.items()]
        ft_text = f"Reports excluded (n = {ft_ex}):\n" + "\n".join(ft_lines)

        box_ft_ex = FancyBboxPatch(
            (56, 17), 39, 14,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor=C_EXCLUDE_BG, edgecolor=C_EXCLUDE_BORDER, linewidth=1.2
        )
        ax.add_patch(box_ft_ex)
        ax.text(58, 29, ft_text, va="top", fontsize=9, linespacing=1.3)

        ax.annotate(
            "", xy=(56, 27), xytext=(50, 27),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        # 11. Final Included Box (Bottom Left)
        box_inc = FancyBboxPatch(
            (12, 6), 38, 10,
            boxstyle="round,pad=0.3,rounding_size=0.8",
            facecolor="#ECFDF5", edgecolor="#059669", linewidth=1.5
        )
        ax.add_patch(box_inc)
        inc_title = f"Studies included in review\n(n = {included})"
        if flow_data.get("reports_included"):
            inc_title += f"\nReports of included studies (n = {flow_data['reports_included']})"
        ax.text(31, 11, inc_title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#065F46")

        ax.annotate(
            "", xy=(31, 16), xytext=(31, 23),
            arrowprops=dict(arrowstyle="->", lw=1.5, color=C_ARROW)
        )

        plt.tight_layout()

        # Output paths
        os.makedirs(os.path.dirname(output_prefix) if os.path.dirname(output_prefix) else ".", exist_ok=True)
        png_path = f"{output_prefix}.png"
        svg_path = f"{output_prefix}.svg"
        pdf_path = f"{output_prefix}.pdf"

        # Export all 3 formats
        plt.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        plt.savefig(pdf_path, format="pdf", bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return {
            "png": png_path,
            "svg": svg_path,
            "pdf": pdf_path
        }
